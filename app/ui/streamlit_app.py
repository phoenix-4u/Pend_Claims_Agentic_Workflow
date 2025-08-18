import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd

# Make top-level project importable
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.crud import crud
from app.db.base import get_db
from app.sops.loader import sop_loader
from app.workflows.claim_processor import ClaimProcessor
from app.config.logging_config import logger


# --------------------------
# Streamlit page config + CSS
# --------------------------
st.set_page_config(
    page_title="Pend Claim Analysis",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------
# Session state initialization
# --------------------------
if "processing" not in st.session_state:
    st.session_state.processing = False
if "claim_data" not in st.session_state:
    st.session_state.claim_data = None
if "sop_results" not in st.session_state:
    st.session_state.sop_results = None
if "icn" not in st.session_state:
    st.session_state.icn = ""


# --------------------------
# UI helpers
# --------------------------
def display_claim_summary(claim_data: Dict[str, Any]):
    with st.expander("Claim Summary", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("ICN", claim_data.get("icn", "N/A"))
            st.metric("Member", claim_data.get("member_name", "N/A"))
            st.metric("DOB", claim_data.get("member_dob", "N/A"))

        with col2:
            st.metric("Provider", claim_data.get("provider_name", "N/A"))
            st.metric("Specialty", claim_data.get("provider_specialty", "N/A"))
            st.metric("Claim Type", claim_data.get("claim_type", "N/A"))

        with col3:
            st.metric("Total Charge", f"${claim_data.get('total_charge', 0):,.2f}")
            st.metric("Primary DX", claim_data.get("primary_dx_code", "N/A"))
            st.metric("Lines", len(claim_data.get("claim_lines", [])))


def display_claim_lines(claim_lines: List[Dict[str, Any]]):
    if not claim_lines:
        st.warning("No claim lines found for this claim.")
        return

    display_data = [
        {
            "Line #": line.get("line_no", "N/A"),
            "Procedure": line.get("procedure_code", "N/A"),
            "Diagnosis": line.get("diagnosis_code", "N/A"),
            "DOS": f"{line.get('first_dos', 'N/A')} to {line.get('last_dos', 'N/A')}",
            "POS": line.get("pos_code", "N/A"),
            "Charge": f"${line.get('charge', 0):,.2f}",
            "Condition Code": line.get("condition_code", "N/A"),
        }
        for line in claim_lines
    ]

    st.dataframe(
        pd.DataFrame(display_data),
        use_container_width=True,
        hide_index=True,
    )


def display_processing_steps(steps: List[Dict[str, Any]]):
    st.subheader("Processing Steps")

    for i, step in enumerate(steps):
        status = step.get("status", "pending").lower()
        icon = "✅" if status == "completed" else "❌" if status == "failed" else "🔄"

        with st.expander(f"{icon} {step.get('name', f'Step {i+1}')}", expanded=True):
            st.json(step)


def display_decision(decision: Dict[str, Any]):
    if not decision:
        return

    decision_type = decision.get("type", "").upper()
    reason = decision.get("reason", "No reason provided.")

    if decision_type == "APPROVE":
        st.success(f"## ✅ Claim Approved\n**Reason:** {reason}")
    elif decision_type == "DENY":
        st.error(f"## ❌ Claim Denied\n**Reason:** {reason}")
    else:
        st.warning(f"## ⏳ Claim Pended\n**Reason:** {reason}")


# --------------------------
# Core async processing
# --------------------------
async def process_claim(icn: str, progress_placeholder) -> (Optional[Dict[str, Any]], Optional[Dict[str, Any]]):
    try:
        with get_db() as db:
            claim_data = crud.get_claim_with_lines(db, icn)
            logger.info(f"Claim data: {claim_data}")
            if not claim_data:
                st.error(f"No claim found with ICN: {icn}")
                return None, None

            condition_codes = crud.get_condition_codes(db, icn)
            logger.info(f"Condition codes: {condition_codes}")
            if not condition_codes:
                st.error(f"No condition codes found for claim {icn}")
                return None, None

            # Use the async SOP loader method to avoid event loop conflicts
            sop = await sop_loader.get_sop_for_condition_code_async(condition_codes[0])
            logger.info(f"SOP: {sop}")
            if not sop or not getattr(sop, "entry_point", None):
                st.error(f"No SOP found or SOP entry point missing for condition code: {condition_codes}")
                return None, None

            processor = ClaimProcessor(sop)

            # Stream workflow states to the UI
            state = None
            try:
                async for state in processor.workflow.astream(
                    {
                        "icn": icn,
                        "sop_code": sop.sop_code,
                        "current_step": sop.entry_point,
                        "step_history": [],
                        "step_results": {},
                        "decision": None,
                        "decision_reason": None,
                        "start_time": datetime.utcnow(),
                        "end_time": None,
                        "error": None,
                    }
                ):
                    progress_placeholder.json(state)
                    # small yield to UI
                    await asyncio.sleep(0.05)
            except Exception as stream_err:
                logger.error(f"Workflow stream error for {icn}: {stream_err}", exc_info=True)
                st.error("An error occurred while executing the workflow.")
                return None, None

            if not state:
                st.error("No workflow state was produced.")
                return None, None

            # Ensure final state is JSON-serializable for session state storage
            if hasattr(state, "model_dump"):
                state = state.model_dump()
            elif hasattr(state, "dict"):
                state = state.dict()

            return claim_data, state

    except Exception as e:
        logger.error(f"Error processing claim {icn}: {e}", exc_info=True)
        st.error(f"An error occurred while processing the claim: {str(e)}")
        return None, None


# --------------------------
# Main async UI flow
# --------------------------
async def main():
    st.title("📋 Pend Claim Analysis")

    with st.sidebar:
        st.header("Claim Lookup")
        icn = st.text_input("Enter ICN", st.session_state.icn or "")

        process_clicked = st.button(
            "Process Claim",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.processing,
        )

        if process_clicked:
            if not icn:
                st.error("Please enter an ICN")
            else:
                st.session_state.processing = True
                st.session_state.icn = icn.strip()
                st.session_state.claim_data = None
                st.session_state.sop_results = None

                progress_placeholder = st.empty()
                with st.spinner("Processing claim..."):
                    claim_data, result = await process_claim(st.session_state.icn, progress_placeholder)

                if claim_data and result:
                    st.session_state.claim_data = claim_data
                    st.session_state.sop_results = result
                    st.success("Claim processed successfully!")
                st.session_state.processing = False

    # Render results if available
    if st.session_state.get("claim_data") and st.session_state.get("sop_results"):
        display_claim_summary(st.session_state.claim_data)
        display_claim_lines(st.session_state.claim_data.get("claim_lines", []))
        step_history = st.session_state.sop_results.get("step_history", [])
        display_processing_steps(step_history if isinstance(step_history, list) else [])
        display_decision(
            {
                "type": st.session_state.sop_results.get("decision"),
                "reason": st.session_state.sop_results.get("decision_reason"),
            }
        )
    elif not st.session_state.processing:
        st.info("Enter an ICN in the sidebar to begin.")


# --------------------------
# Entry point: loop-aware
# --------------------------
if __name__ == "__main__":
    # try:
    #     loop = asyncio.get_event_loop()
    #     if loop.is_running():
    #         # If a loop is already running (some hosting setups), schedule without blocking
    #         loop.create_task(main())
    #     else:
    #         loop.run_until_complete(main())
    # except RuntimeError:
    #     # No current loop; create one and run
    #     loop = asyncio.new_event_loop()
    #     try:
    #         asyncio.set_event_loop(loop)
    #         loop.run_until_complete(main())
    #     finally:
    #         try:
    #             loop.close()
    #         except Exception:
    #             pass
    
    asyncio.run(main())
