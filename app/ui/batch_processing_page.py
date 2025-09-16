import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import math
import json

from ..db.base import get_db
from ..db.crud import crud
from ..models.claims import ClaimProcessedLine

def get_grid_data_from_db():
    """Fetches data for the main grid from the processed claims table."""
    with get_db() as db:
        processed_claims = crud.get_all_processed_claims(db)
    
        grid_data = []
        for processed_claim in processed_claims:
            # The original claim details are now in the JSON blob
            # We need to get the original claim header to display member and provider names
            claim_header = crud.get_claim_header(db, processed_claim.icn)
            grid_data.append({
                "icn": processed_claim.icn,
                "member_name": claim_header.member_name if claim_header else "N/A",
                "provider_name": claim_header.provider_name if claim_header else "N/A",
                "pend_code": processed_claim.sop_code,
                "recommendation": processed_claim.decision,
            })
        return grid_data

def get_detailed_data_from_db(icn: str):
    """Fetches detailed data for a specific claim from the database."""
    with get_db() as db:
    # Find the processed claim record for the final decision
        processed_claim = db.query(ClaimProcessedLine).filter_by(icn=icn).first()
        
        # Fetch the step-by-step processing details
        processing_steps = crud.get_claim_processing_steps(db, icn)
        
        # We still need the original claim data for the summary and line items
        claim_data = crud.get_claim_with_lines(db, icn)

        if not claim_data:
            return None

        step_history = []
        for step in processing_steps:
            step_history.append({
                "step": f"Step {step.step_number}: {step.description}",
                "status": step.status,
                "details": {
                    "timestamp": step.timestamp,
                    "query": step.query,
                    "data": json.loads(step.data) if step.data else None,
                    "row_count": step.row_count,
                    "execution_time_ms": step.execution_time_ms,
                    "error": step.error,
                },
            })

        detailed_data = {
            "claim_data": claim_data,
            "sop_results": {
                "decision": processed_claim.decision if processed_claim else "Not Processed",
                "decision_reason": processed_claim.decision_reason if processed_claim else "This claim has not been processed yet.",
                "step_history": step_history,
            },
        }
        return detailed_data

def display_batch_processing_page(
    display_claim_summary, 
    display_decision_and_details, 
    display_claim_lines, 
    display_processing_steps
):
    """Displays the batch processing page with a grid of claims."""
    st.header("Batch Claim Processing")

    if "selected_icn" not in st.session_state:
        st.session_state.selected_icn = None
    
    if "page_number" not in st.session_state:
        st.session_state.page_number = 0

    if st.session_state.selected_icn:
        # Detailed view
        icn = st.session_state.selected_icn
        claim_details = get_detailed_data_from_db(icn)

        if claim_details:
            if st.button("← Back to Batch View"):
                st.session_state.selected_icn = None
                st.rerun()

            display_claim_summary(claim_details["claim_data"])
            
            decision_details = {
                "type": claim_details["sop_results"].get("decision"),
                "reason": claim_details["sop_results"].get("decision_reason"),
            }
            # Display decision and buttons
            col1, col2 = st.columns([6, 1])
            with col1:
                display_decision_and_details(decision_details)
            with col2:
                if st.button("Approve", type="primary", use_container_width=True):
                    st.success(f"ICN: {icn} has been updated as approved.")
                if st.button("Deny", type="secondary", use_container_width=True):
                    st.error(f"ICN: {icn} has been updated as denied.")

            display_claim_lines(claim_details["claim_data"].get("claim_lines"))
            display_processing_steps(claim_details["sop_results"].get("step_history"))
        else:
            st.error("Could not find details for the selected claim.")
            st.session_state.selected_icn = None

    else:
        # Grid view with pagination
        grid_data = get_grid_data_from_db()
        st.info(f"Showing {len(grid_data)} processed claims from the database.")
        
        page_size = 10
        page_number = st.session_state.page_number
        total_pages = math.ceil(len(grid_data) / page_size) if grid_data else 1
        
        start_index = page_number * page_size
        end_index = start_index + page_size
        
        paginated_data = grid_data[start_index:end_index]
        df = pd.DataFrame(paginated_data)

        # Display header
        col1, col2, col3, col4, col5, col6 = st.columns([2, 3, 3, 2, 2, 2])
        with col1:
            st.subheader("ICN")
        with col2:
            st.subheader("Member Name")
        with col3:
            st.subheader("Provider Name")
        with col4:
            st.subheader("Pend Code")
        with col5:
            st.subheader("AI Recommendation")
        with col6:
            st.subheader("Action")
        
        st.divider()

        # Display grid data
        if not df.empty:
            for index, row in df.iterrows():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 3, 3, 2, 2, 2])
                with col1:
                    st.write(row["icn"])
                with col2:
                    st.write(row["member_name"])
                with col3:
                    st.write(row["provider_name"])
                with col4:
                    st.write(row["pend_code"])
                with col5:
                    st.write(row["recommendation"])
                with col6:
                    if st.button("View Details", key=f"view_{row['icn']}", use_container_width=True):
                        st.session_state.selected_icn = row["icn"]
                        st.rerun()
        else:
            st.info("No processed claims to display.")

        st.divider()

        # Pagination controls
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("⬅️ Previous", use_container_width=True, disabled=page_number == 0):
                st.session_state.page_number -= 1
                st.rerun()
        
        with col2:
            st.write(f"Page {page_number + 1} of {total_pages}")
        
        with col3:
            if st.button("Next ➡️", use_container_width=True, disabled=page_number >= total_pages - 1):
                st.session_state.page_number += 1
                st.rerun()
