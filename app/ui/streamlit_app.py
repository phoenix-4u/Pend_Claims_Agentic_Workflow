import sys
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd

# Make top-level project importable
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.crud import crud, sop_crud
from app.db.base import get_db
from app.sops.loader import sop_loader
from app.sops.models import SOPStep
from app.workflows.claim_processor import ClaimProcessor
from app.config.logging_config import logger
from app.ui.batch_processing_page import display_batch_processing_page

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
def display_claim_summary(claim_data: Optional[Dict[str, Any]]):
    """Displays a detailed summary of the claim."""
    if not claim_data or not isinstance(claim_data, dict):
        st.warning("No claim data to display.")
        return

    with st.expander("Claim Summary", expanded=True):
        details = {
            "ICN": claim_data.get("icn"),
            "Member": f"{claim_data.get('member_name')} (DOB: {claim_data.get('member_dob')})",
            "Provider": f"{claim_data.get('provider_name')} ({claim_data.get('provider_speciality')})",
            "Total Charge": f"${claim_data.get('total_charge', 0):,.2f}",
            "Primary DX": claim_data.get("primary_dx_code"),
            "Lines": len(claim_data.get("claim_lines", [])),
        }
        
        # Create a two-column layout
        col1, col2 = st.columns(2)
        
        # Display half of the details in each column
        items_per_column = (len(details) + 1) // 2
        
        with col1:
            for i, (label, value) in enumerate(details.items()):
                if i < items_per_column:
                    st.metric(label, value or "N/A")
        
        with col2:
            for i, (label, value) in enumerate(details.items()):
                if i >= items_per_column:
                    st.metric(label, value or "N/A")

def display_claim_lines(claim_lines: Optional[List[Dict[str, Any]]]):
    """Displays claim line items in a clear, formatted table."""
    if not claim_lines:
        st.warning("No claim lines found for this claim.")
        return

    line_items = []
    for line in claim_lines:
        line_items.append({
            "Line #": line.get("line_no"),
            "Procedure": line.get("procedure_code"),
            "Diagnosis": line.get("diagnosis_code"),
            "DOS": f"{line.get('first_dos')} to {line.get('last_dos')}",
            "POS": line.get("pos_code"),
            "Charge": f"${line.get('charge', 0):,.2f}",
            "Condition": line.get("condition_code") or "N/A",
        })

    df = pd.DataFrame(line_items)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Charge": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

def display_processing_steps(steps: Optional[List[Dict[str, Any]]]):
    """Displays the processing steps with intuitive icons and clear formatting."""
    st.subheader("Processing Steps")

    if not steps:
        st.info("No processing steps to display.")
        return

    for i, step in enumerate(steps):
        status = str(step.get("status", "pending")).lower()
        
        icon_map = {"completed": "✅", "failed": "❌", "pending": "🔄"}
        icon = icon_map.get(status, "❓")
        
        step_name = step.get("step", f"Step {i + 1}")
        
        with st.expander(f"{icon} {step_name}", expanded=True):
            details = step.get("details", {})
            if details:
                st.json(details)
            else:
                st.info("No details available for this step.")

def display_decision_and_details(decision: Optional[Dict[str, Any]]):
    """Displays the final decision and its details in a formatted box."""
    if not decision or not isinstance(decision, dict):
        st.warning("No decision details available.")
        return

    decision_type = str(decision.get("type") or "PEND").upper()
    reason = str(decision.get("reason") or "No reason provided.")

    # Color coding for decisions
    if decision_type == "APPROVE":
        st.success(f"## ✅ AI Recommendation: Approve the claim\n**Reason:** {reason}")
    elif decision_type == "DENY":
        st.error(f"## ❌ AI Recommendation: Deny the claim\n**Reason:** {reason}")
    else:
        st.warning(f"## ⏳ Claim Pended\n**Reason:** {reason}")

def display_sop_upload_page():
    """Displays the page for uploading new SOPs."""
    st.header("Upload a New SOP")

    with st.form("sop_upload_form"):
        sop_code = st.text_input("SOP Code (e.g., B008)")
        
        uploaded_file = st.file_uploader(
            "Upload SOP file (.xlsx or .csv)",
            type=["xlsx", "csv"]
        )
        
        submitted = st.form_submit_button("Upload SOP")

        if submitted:
            if not all([sop_code, uploaded_file]):
                st.error("Please fill in all fields and upload a file.")
                return

            try:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file, delimiter="|")
                else:
                    df = pd.read_excel(uploaded_file)

                required_columns = {"sop_code", "step_number", "description", "query"}
                
                if not required_columns.issubset(df.columns):
                    st.error(f"File must contain the following columns: {', '.join(required_columns)} found {', '.join(df.columns)}")
                    return

                with get_db() as db:
                    for index, row in df.iterrows():
                        try:
                            # Convert row to dict and handle NaN values
                            row_data = row.to_dict()
                            # Replace NaN/None values with empty strings
                            for key, value in row_data.items():
                                if pd.isna(value) or value is None:
                                    row_data[key] = ""
                            
                            # Create SOP step with cleaned data
                            sop_step = SOPStep(**row_data)
                            sop_crud.create_sop(
                                db=db,
                                sop_code=sop_code,
                                step_number=sop_step.step_number,
                                description=sop_step.description,
                                query=sop_step.query or ""  # Ensure query is never None
                            )
                        except Exception as e:
                            st.error(f"Error processing row {index + 1}: {e}")
                            db.rollback()
                            return
                
                st.success(f"SOP '{sop_code}' uploaded successfully with {len(df)} steps.")
                
                # Reload SOPs from the database to reflect changes
                try:
                    sop_loader.reload()
                    # st.info("SOP definitions have been reloaded.")
                except Exception as reload_e:
                    st.error(f"SOPs uploaded but failed to reload: {reload_e}")

            except Exception as e:
                st.error(f"An error occurred while processing the file: {e}")

# --------------------------
# Core async processing
# --------------------------
async def process_claim(icn: str, progress_placeholder) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Processes a claim and returns the final workflow result."""
    try:
        with get_db() as db:
            claim_data = crud.get_claim_with_lines(db, icn)
            if not claim_data:
                st.error(f"No claim found with ICN: {icn}")
                return None, None

            condition_codes = crud.get_condition_codes(db, icn)
            if not condition_codes:
                st.error(f"No condition codes found for claim {icn}")
                return claim_data, None

            # Try to find an SOP for any of the condition codes
            sop = None
            found_code = None
            for code in condition_codes:
                sop = await sop_loader.get_sop_async(code)
                if sop and getattr(sop, "entry_point", None):
                    found_code = code
                    break

            if not sop or not getattr(sop, "entry_point", None):
                st.error(f"No SOP found for condition codes: {condition_codes}")
                return claim_data, None

            logger.info(f"Found SOP {found_code} for claim {icn}")

            processor = ClaimProcessor(sop)
            
            # Option 1: Use the process_claim method directly (recommended)
            # This ensures the decision is properly set
            logger.info(f"Processing claim {icn} using ClaimProcessor.process_claim()")
            final_state = await processor.process_claim(icn)
            
            # Display final result
            progress_placeholder.json(final_state)
            
            return claim_data, final_state
            
            # Option 2: If you want to keep streaming, uncomment below and comment above
            """
            initial_state = {
                "icn": icn,
                "sop_code": sop.sop_code,
                "last_ran_step": None,
                "step_history": [],
                "step_results": {},
                "decision": None,
                "decision_reason": None,
                "start_time": datetime.now(UTC),
                "end_time": None,
                "error": None,
            }

            final_state = None
            async for state in processor.workflow.astream(initial_state):
                progress_placeholder.json(state)
                final_state = state
                await asyncio.sleep(0.1)
            
            # Ensure decision is set if missing
            if final_state and not final_state.get("decision"):
                logger.warning("Decision not set in final state, deriving from step results")
                decision = "APPROVE"
                decision_reason = "All SOP steps completed successfully."
                
                for _, result in final_state.get("step_results", {}).items():
                    if result.get("status") == "failed":
                        decision = "PEND"
                        decision_reason = f"Step {result.get('step_number')} failed: {result.get('error', 'Unknown error')}"
                        break
                
                final_state["decision"] = decision
                final_state["decision_reason"] = decision_reason
            
            return claim_data, final_state
            """

    except Exception as e:
        logger.error(f"Error processing claim {icn}: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
        return None, None

# --------------------------
# Main async UI flow
# --------------------------
async def main():
    """Main function to run the Streamlit application."""
    st.title("📋 Pend Claim Processor")

    # Sidebar for navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Choose a page", ["Process Single Claim", "Batch Processing", "Upload SOP"])

    if page == "Process Single Claim":
        # Sidebar for claim lookup
        with st.sidebar:
            st.header("Claim Lookup")
            icn_input = st.text_input("Enter ICN", value=st.session_state.get("icn", ""))
            
            if st.button("Process Claim", type="primary", use_container_width=True):
                if icn_input:
                    st.session_state.icn = icn_input.strip()
                    st.session_state.processing = True
                    st.session_state.claim_data = None
                    st.session_state.sop_results = None
                    
                    progress_placeholder = st.empty()
                    with st.spinner("Processing claim..."):
                        claim_data, results = await process_claim(st.session_state.icn, progress_placeholder)
                    
                    st.session_state.claim_data = claim_data
                    st.session_state.sop_results = results
                    st.session_state.processing = False
                    
                    if results:
                        st.success("Claim processed successfully!")
                        logger.info(f"Final results: decision={results.get('decision')}, reason={results.get('decision_reason')}")
                    else:
                        st.error("Failed to get SOP results.")
                else:
                    st.error("Please enter an ICN.")

        # Main content area
        if st.session_state.get("processing"):
            st.info("Processing claim, please wait...")
        elif st.session_state.get("claim_data") and st.session_state.get("sop_results"):
            # Display claim summary first
            display_claim_summary(st.session_state.claim_data)
            
            # Display decision prominently
            decision_details = {
                "type": st.session_state.sop_results.get("decision"),
                "reason": st.session_state.sop_results.get("decision_reason"),
            }
            
            # Debug: Log what we're trying to display
            logger.info(f"Displaying decision: {decision_details}")
            

            # Add Approve/Deny buttons
            col1, col2 = st.columns([6, 1])
            with col1:
                display_decision_and_details(decision_details)
            with col2:
                if st.button("Approve", type="primary", use_container_width=True):
                    st.success(f"ICN: {st.session_state.icn} has been updated as approved.")
                if st.button("Deny", type="secondary", use_container_width=True):
                    st.error(f"ICN: {st.session_state.icn} has been updated as denied.")
            
            # Display claim lines
            display_claim_lines(st.session_state.claim_data.get("claim_lines"))
            
            # Display processing steps
            step_history = st.session_state.sop_results.get("step_history", [])
            display_processing_steps(step_history)
            
        elif st.session_state.get("claim_data"):
            display_claim_summary(st.session_state.claim_data)
            st.warning("Claim data loaded but no SOP results available.")
        else:
            st.info("Enter an ICN in the sidebar to begin analysis.")

    elif page == "Batch Processing":
        display_batch_processing_page(
            display_claim_summary,
            display_decision_and_details,
            display_claim_lines,
            display_processing_steps,
        )
    
    elif page == "Upload SOP":
        display_sop_upload_page()

# --------------------------
# Entry point: loop-aware
# --------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An error occurred in the main execution: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
