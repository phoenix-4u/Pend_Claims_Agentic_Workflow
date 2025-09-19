import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import math
import json
import asyncio

from ..db.base import get_db
from ..db.crud import crud
from ..models.claims import ClaimProcessedLine
from ..workflows.claim_processor import ClaimProcessor
from ..sops.loader import sop_loader
from ..config.logging_config import logger

async def get_batch_processable_claims():
    """Get all claims that have condition codes matching available SOPs."""
    try:
        # Load all available SOPs
        await sop_loader.load_all_async()
        available_sop_codes = set(sop_loader._sop_definitions.keys())

        with get_db() as db:
            # Get all claims with their condition codes
            all_claims = crud.get_all_claims_with_details(db)

            processable_claims = []
            for claim in all_claims:
                # Get condition codes for this claim
                condition_codes = crud.get_condition_codes(db, claim['icn'])

                # Check if any condition code matches an available SOP
                matching_sops = [code for code in condition_codes if code in available_sop_codes]

                if matching_sops:
                    claim['matching_sops'] = matching_sops
                    processable_claims.append(claim)

            return processable_claims

    except Exception as e:
        logger.error(f"Error getting batch processable claims: {e}")
        return []

async def process_claims_batch(claims_to_process, progress_bar, status_text):
    """Process multiple claims in batch."""
    total_claims = len(claims_to_process)
    processed_count = 0
    successful_count = 0
    failed_count = 0

    results = []

    for i, claim in enumerate(claims_to_process):
        icn = claim['icn']
        status_text.text(f"Processing claim {i+1}/{total_claims}: {icn}")
        progress_bar.progress((i) / total_claims)

        try:
            # Get condition codes for this claim
            with get_db() as db:
                condition_codes = crud.get_condition_codes(db, icn)

            # Find matching SOP
            sop = None
            found_code = None
            for code in condition_codes:
                sop = await sop_loader.get_sop_async(code)
                if sop and getattr(sop, 'entry_point', None):
                    found_code = code
                    break

            if not sop:
                logger.warning(f"No SOP found for claim {icn} with condition codes: {condition_codes}")
                failed_count += 1
                results.append({
                    'icn': icn,
                    'status': 'failed',
                    'error': f'No SOP found for condition codes: {condition_codes}'
                })
                continue

            # Process the claim
            processor = ClaimProcessor(sop)
            result = await processor.process_claim(icn)

            successful_count += 1
            results.append({
                'icn': icn,
                'status': 'success',
                'decision': result.get('decision'),
                'sop_code': found_code
            })

        except Exception as e:
            logger.error(f"Error processing claim {icn}: {e}")
            failed_count += 1
            results.append({
                'icn': icn,
                'status': 'failed',
                'error': str(e)
            })

        processed_count += 1

    progress_bar.progress(1.0)
    status_text.text(f"Batch processing completed: {successful_count} successful, {failed_count} failed out of {total_claims} claims")

    return results

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
        # Batch processing section
        st.subheader("Batch Processing")

        # Check for batch processing trigger
        if "batch_processing" not in st.session_state:
            st.session_state.batch_processing = False
        if "batch_results" not in st.session_state:
            st.session_state.batch_results = None

        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🔄 Process Claims in Batch", type="primary", use_container_width=True):
                st.session_state.batch_processing = True
                st.session_state.batch_results = None
                st.rerun()

        with col2:
            if st.button("📊 Refresh Processed Claims", use_container_width=True):
                st.rerun()

        # Show batch processing status/results
        if st.session_state.batch_processing:
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Initialize batch processing state if needed
            if "batch_step" not in st.session_state:
                st.session_state.batch_step = "loading_claims"
            if "batch_claims" not in st.session_state:
                st.session_state.batch_claims = None
            if "batch_results" not in st.session_state:
                st.session_state.batch_results = None

            try:
                # Step 1: Load claims
                if st.session_state.batch_step == "loading_claims":
                    status_text.text("Loading claims that can be processed...")

                    # Use a simple synchronous approach to avoid asyncio conflicts
                    # Load SOPs synchronously first
                    try:
                        sop_loader.load_all()
                        available_sop_codes = set(sop_loader._sop_definitions.keys())

                        with get_db() as db:
                            all_claims = crud.get_all_claims_with_details(db)
                            processable_claims = []

                            for claim in all_claims:
                                condition_codes = crud.get_condition_codes(db, claim['icn'])
                                matching_sops = [code for code in condition_codes if code in available_sop_codes]

                                if matching_sops:
                                    claim['matching_sops'] = matching_sops
                                    processable_claims.append(claim)

                        st.session_state.batch_claims = processable_claims
                        st.session_state.batch_step = "processing_claims"

                        if not processable_claims:
                            st.warning("No claims found that can be processed with available SOPs.")
                            st.session_state.batch_processing = False
                            st.session_state.batch_step = "loading_claims"
                        else:
                            st.info(f"Found {len(processable_claims)} claims that can be processed.")
                            st.rerun()

                    except Exception as e:
                        logger.error(f"Error loading claims: {e}")
                        st.error(f"Error loading claims: {e}")
                        st.session_state.batch_processing = False
                        st.session_state.batch_step = "loading_claims"

                # Step 2: Process claims one by one
                elif st.session_state.batch_step == "processing_claims":
                    claims_to_process = st.session_state.batch_claims
                    total_claims = len(claims_to_process)

                    # Process claims synchronously to avoid asyncio issues
                    results = []
                    successful_count = 0
                    failed_count = 0

                    for i, claim in enumerate(claims_to_process):
                        icn = claim['icn']
                        status_text.text(f"Processing claim {i+1}/{total_claims}: {icn}")
                        progress_bar.progress((i) / total_claims)

                        try:
                            # Get condition codes for this claim
                            with get_db() as db:
                                condition_codes = crud.get_condition_codes(db, icn)

                            # Find matching SOP (synchronous)
                            sop = None
                            found_code = None
                            for code in condition_codes:
                                sop = sop_loader.get_sop(code)
                                if sop and getattr(sop, 'entry_point', None):
                                    found_code = code
                                    break

                            if not sop:
                                logger.warning(f"No SOP found for claim {icn} with condition codes: {condition_codes}")
                                failed_count += 1
                                results.append({
                                    'icn': icn,
                                    'status': 'failed',
                                    'error': f'No SOP found for condition codes: {condition_codes}'
                                })
                                continue

                            # Process the claim synchronously
                            # Note: This will still use async internally but we'll handle it
                            import nest_asyncio
                            nest_asyncio.apply()  # Allow nested event loops

                            async def process_single_claim():
                                processor = ClaimProcessor(sop)
                                return await processor.process_claim(icn)

                            # Run in current event loop
                            loop = asyncio.get_event_loop()
                            result = loop.run_until_complete(process_single_claim())

                            successful_count += 1
                            results.append({
                                'icn': icn,
                                'status': 'success',
                                'decision': result.get('decision'),
                                'sop_code': found_code
                            })

                        except Exception as e:
                            logger.error(f"Error processing claim {icn}: {e}")
                            failed_count += 1
                            results.append({
                                'icn': icn,
                                'status': 'failed',
                                'error': str(e)
                            })

                    # Complete processing
                    progress_bar.progress(1.0)
                    status_text.text(f"Batch processing completed: {successful_count} successful, {failed_count} failed out of {total_claims} claims")

                    st.session_state.batch_results = results
                    st.session_state.batch_step = "completed"

                    # Display results
                    successful = [r for r in results if r['status'] == 'success']
                    failed = [r for r in results if r['status'] == 'failed']

                    st.success(f"✅ Successfully processed {len(successful)} claims")
                    if failed:
                        st.error(f"❌ Failed to process {len(failed)} claims")

                    # Show detailed results
                    with st.expander("View Batch Processing Results", expanded=True):
                        results_df = pd.DataFrame(results)
                        st.dataframe(results_df, use_container_width=True)

                    st.session_state.batch_processing = False
                    st.session_state.batch_step = "loading_claims"

            except Exception as e:
                st.error(f"Error during batch processing: {e}")
                st.session_state.batch_processing = False
                st.session_state.batch_step = "loading_claims"

        st.divider()

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
