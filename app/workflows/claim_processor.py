#File: app/workflows/claim_processor.py
#Author: Dipanjanghosal
#Date: 2025-08-17
#Description: LangGraph workflow for processing claims using SOPs.

from typing import Dict, Any, List, Optional, TypedDict, Literal
from datetime import datetime, UTC
import asyncio

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from ..core.mcp_client import mcp_langchain_client as mcp_client
from ..sops.models import SOPDefinition, SOPStep
from ..config.logging_config import logger


class ClaimState(TypedDict):
    """State for the claim processing workflow."""
    icn: str
    sop_code: str
    # For back-compat with UI expecting last_ran_step to be a string name,
    # we will store "Step {n}" where n is the step_number
    last_ran_step: Optional[str]
    step_history: List[Dict[str, Any]]
    step_results: Dict[str, Any]
    decision: Optional[Literal["APPROVE", "DENY", "PEND"]]
    decision_reason: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    error: Optional[str]


def _find_step_by_number(sop: SOPDefinition, step_no: int) -> Optional[SOPStep]:
    for s in sop.steps:
        if s.step_number == step_no:
            return s
    return None


def _sorted_step_numbers(sop: SOPDefinition) -> List[int]:
    return sorted(s.step_number for s in sop.steps)


class ClaimProcessor:
    """Process claims using LangGraph workflows based on SOPs."""

    def __init__(self, sop_definition: SOPDefinition):
        self.sop = sop_definition
        self.workflow = self._create_workflow()

    def _create_workflow(self):
        """
        Build a LangGraph workflow with one node per numeric step_number.
        Node names will be "step_<number>" to keep them unique and addressable.
        """
        workflow = StateGraph(ClaimState)

        # Create nodes for each step
        for s in self.sop.steps:
            node_name = f"step_{s.step_number}"
            workflow.add_node(node_name, self._make_step_handler(s.step_number))

        # Entry point
        entry_node = f"step_{self.sop.entry_point}"
        workflow.set_entry_point(entry_node)

        # Linear edges (by ascending step_number)
        ordered = _sorted_step_numbers(self.sop)
        for i, step_no in enumerate(ordered):
            current_node = f"step_{step_no}"
            if i + 1 < len(ordered):
                next_node = f"step_{ordered[i + 1]}"
                workflow.add_edge(current_node, next_node)
            else:
                workflow.add_edge(current_node, END)

        return workflow.compile()

    def _make_step_handler(self, step_number: int):
        """
        Create an async handler function for a specific numeric step.
        This captures step_number and runs the SQL if present.
        """

        async def handler(state: ClaimState, config: RunnableConfig) -> ClaimState:
            step = _find_step_by_number(self.sop, step_number)
            if not step:
                msg = f"Step {step_number} not found in SOP {self.sop.sop_code}"
                logger.error(msg)
                state["error"] = msg
                state["last_ran_step"] = f"Step {step_number}"
                # When a node returns with an error, the graph will still progress.
                # The final decision will be handled after the graph completes.
                return state

            logger.info(f"Executing SOP {self.sop.sop_code} - Step {step.step_number}: {step.description}")

            exec_result: Dict[str, Any] = {
                "step_number": step.step_number,
                "description": step.description,
                "status": "completed",
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Execute SQL if present
            sql = (step.query or "").strip() if step.query is not None else ""
            if sql:
                # Templating ICN
                sql_to_run = sql.replace("{icn}", state["icn"])
                try:
                    qres = await mcp_client.execute_query(sql_to_run)
                except Exception as e:
                    logger.error(f"Error executing SQL for step {step.step_number}: {e}", exc_info=True)
                    exec_result["status"] = "failed"
                    exec_result["error"] = str(e)
                else:
                    exec_result["query"] = sql_to_run
                    if not qres.success:
                        exec_result["status"] = "failed"
                        exec_result["error"] = qres.error
                    else:
                        exec_result["data"] = qres.data
                        exec_result["row_count"] = qres.row_count
                        exec_result["execution_time_ms"] = qres.execution_time_ms

            # Update state
            state["step_results"][str(step.step_number)] = exec_result
            state["step_history"].append({
                "step": f"Step {step.step_number}",
                "status": exec_result.get("status", "completed"),
                "timestamp": exec_result["timestamp"],
                "details": exec_result,
            })
            state["last_ran_step"] = f"Step {step.step_number}"
            return state

        # Keep function metadata nice for debug
        handler.__name__ = f"handle_step_{step_number}"
        return handler

    async def process_claim(self, icn: str) -> Dict[str, Any]:
        """
        Run the compiled workflow starting from the entry step.
        After the graph completes, derive a decision:
        - APPROVE if all steps completed
        - PEND on the first failure or error
        """
        initial_state = ClaimState(
            icn=icn,
            sop_code=self.sop.sop_code,
            last_ran_step=None,
            step_history=[],
            step_results={},
            decision=None,
            decision_reason=None,
            start_time=datetime.now(UTC),
            end_time=None,
            error=None,
        )

        try:
            final_state = await self.workflow.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"Error processing claim {icn}: {e}", exc_info=True)
            # Return an error result in a consistent shape
            return {
                "icn": icn,
                "sop_code": self.sop.sop_code,
                "last_ran_step": None,
                "step_history": [],
                "step_results": {},
                "decision": "PEND",
                "decision_reason": f"Workflow error: {str(e)}",
                "start_time": initial_state["start_time"],
                "end_time": datetime.now(UTC),
                "error": str(e),
            }

        # Derive decision based on step results
        decision = "APPROVE"
        decision_reason = "All SOP steps completed successfully."
        for _, result in final_state["step_results"].items():
            if result.get("status") == "failed":
                decision = "PEND"
                decision_reason = f"Step {result.get('step_number')} failed: {result.get('error','Unknown error')}."
                break

        final_state["decision"] = final_state.get("decision") or decision
        final_state["decision_reason"] = final_state.get("decision_reason") or decision_reason
        final_state["end_time"] = final_state.get("end_time") or datetime.now(UTC)

        return final_state


# Optional: simple self-test entry-point (kept minimal and non-blocking)
if __name__ == "__main__":
    from app.sops.loader import sop_loader

    async def main():
        # Load SOPs via loader (async)
        await sop_loader.load_all_async()
        sop_b007 = await sop_loader.get_sop_async("B007")

        if sop_b007:
            processor = ClaimProcessor(sop_b007)
            result = await processor.process_claim("20211220004300")
            # Pretty print without importing json globally here
            import json as _json
            print(_json.dumps(result, indent=2, default=str))
        else:
            print("SOP B007 not found")

    asyncio.run(main())
