"""Loader for Standard Operating Procedure (SOP) definitions (via MCP)."""
import asyncio
from collections import defaultdict
from typing import Dict, TypeVar, Any, Optional, List

from .models import SOPDefinition, SOPStep
from app.config.logging_config import logger

# Import the MCP LangChain client you already implemented
from app.core.mcp_client import mcp_langchain_client 

T = TypeVar('T', bound='SOPStep')


def _ensure_event_loop():
    """Get or create an event loop for sync contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _run_async(coro):
    """Run an async coroutine from sync code safely."""
    try:
        # Try to use nest_asyncio if available (for Jupyter/Streamlit environments)
        import nest_asyncio
        nest_asyncio.apply()
        loop = _ensure_event_loop()
        return loop.run_until_complete(coro)
    except ImportError:
        # Fallback to regular asyncio handling
        loop = _ensure_event_loop()
        if loop.is_running():
            # If already in an async context, the caller must be async; re-raise for clarity
            raise RuntimeError("SOPLoader called from an active event loop; use async methods instead.")
        return loop.run_until_complete(coro)


class SOPLoader:
    """Loads and validates SOP definitions from the MCP-backed database."""

    def __init__(self):
        """Initialize the SOP loader."""
        self._sop_definitions: Dict[str, SOPDefinition] = {}

    async def _fetch_all_sops(self) -> Dict[str, SOPDefinition]:
        """Fetch all SOPs from MCP and build SOPDefinition dictionary."""
        logger.info("SOPLoader: Fetching SOPs from MCP database.")
        result = await mcp_langchain_client.get_all_sops()
        if not result.success:
            msg = f"Failed to fetch SOPs from MCP: {result.error}"
            logger.error(msg)
            raise RuntimeError(msg)

        rows = result.data or []
        # Expecting columns: id, sop_code, step_number, description, query
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            code = (r.get("sop_code") or "").upper()
            if not code:
                logger.warning(f"SOP row missing sop_code: {r}")
                continue
            grouped[code].append(r)

        sop_defs: Dict[str, SOPDefinition] = {}

        for code, steps_rows in grouped.items():
            # Sort by step_number
            steps_rows.sort(key=lambda x: x.get("step_number", 0))

            # Map DB rows to SOPStep model
            steps: List[SOPStep] = []
            for sr in steps_rows:
                try:
                    query_val = sr.get("query")
                    # Replace NaN with None, as NaN is not a valid Pydantic string
                    if isinstance(query_val, float) and query_val != query_val:
                        query_val = None

                    step = SOPStep(
                        step_number=sr.get("step_number"),
                        description=sr.get("description"),
                        query=query_val,
                    )
                    steps.append(step)
                except Exception as e:
                    logger.error(f"Error creating SOPStep for {code}: {e}", exc_info=True)

            # Build SOPDefinition.
            try:
                sop_def = SOPDefinition(
                    sop_code=code,
                    steps=steps,
                )
                sop_defs[code] = sop_def
            except Exception as e:
                logger.error(f"Error creating SOPDefinition for {code}: {e}", exc_info=True)

        logger.info(f"SOPLoader: Loaded {len(sop_defs)} SOP definitions from MCP.")
        return sop_defs

    def load_all(self) -> Dict[str, SOPDefinition]:
        """Load all SOP definitions from MCP and cache them."""
        try:
            self._sop_definitions = _run_async(self._fetch_all_sops())
        except Exception as e:
            logger.error(f"SOPLoader.load_all failed: {e}", exc_info=True)
            self._sop_definitions = {}
        return self._sop_definitions

    async def load_all_async(self) -> Dict[str, SOPDefinition]:
        """Async variant to load all SOP definitions from MCP."""
        try:
            self._sop_definitions = await self._fetch_all_sops()
        except Exception as e:
            logger.error(f"SOPLoader.load_all_async failed: {e}", exc_info=True)
            self._sop_definitions = {}
        return self._sop_definitions

    def get_sop(self, sop_code: str) -> Optional[SOPDefinition]:
        """Get an SOP definition by its code."""
        if not self._sop_definitions:
            self.load_all()
        return self._sop_definitions.get(sop_code.upper())

    async def get_sop_async(self, sop_code: str) -> Optional[SOPDefinition]:
        """Async variant to get an SOP definition by its code."""
        if not self._sop_definitions:
            await self.load_all_async()
        return self._sop_definitions.get(sop_code.upper())

    


    def reload(self) -> Dict[str, SOPDefinition]:
        """Reload all SOP definitions from MCP."""
        self._sop_definitions.clear()
        return self.load_all()

    async def reload_async(self) -> Dict[str, SOPDefinition]:
        """Async reload of all SOP definitions from MCP."""
        self._sop_definitions.clear()
        return await self.load_all_async()


# Create a global instance for convenience
sop_loader = SOPLoader()
