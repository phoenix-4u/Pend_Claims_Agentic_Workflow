"""MCP (Model Context Protocol) client for executing SQL queries using LangChain."""
import json
import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool as langchain_tool_decorator
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from app.config.logging_config import logger

load_dotenv()

# # --- Logging ---
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
# )
# logger = logging.getLogger(__name__)

required_env_vars = [
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_TYPE", "OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT_NAME", "MODEL_NAME"
]
# Check if any required variables are missing
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    # Log critical error and stop the app if configuration is incomplete
    error_msg = f"Missing required environment variables: {', '.join(missing_vars)}. Please check your .env file or environment settings."
    logger.critical(error_msg)

# Set environment variables for the LangChain Azure client library
# (Setting them here ensures they are available even if not set globally before running)
os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AZURE_OPENAI_ENDPOINT")
os.environ["AZURE_OPENAI_API_TYPE"] = os.getenv("AZURE_OPENAI_API_TYPE")

try:
    # Initialize the AzureChatOpenAI client
    llm = AzureChatOpenAI(
        temperature=0, # Use low temperature for deterministic, factual responses
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"), # Name of your Azure deployment
        model_name=os.getenv("MODEL_NAME"), # Specific model used in the deployment (e.g., gpt-4o)
        openai_api_version=os.getenv("OPENAI_API_VERSION") # API version (e.g., 2024-05-01-preview)
    )
    logger.info("AzureChatOpenAI LLM client initialized successfully.")
except Exception as e:
    # Handle errors during LLM client initialization
    error_msg = f"Failed to initialize Azure OpenAI connection: {e}"
    logger.critical(error_msg, exc_info=True) # Log exception details


# Initialize MCP Client
client = MultiServerMCPClient(
    {
        "sop_database": {
            "url": "http://127.0.0.1:8000/sse",  # Your MCP SSE server URL
            "transport": "sse",
        }
    }
)



# Global tools variable
tools: Optional[List[Any]] = None

class MCPQueryResult(BaseModel):
    """Result of an MCP query execution."""
    success: bool = Field(..., description="Whether the query executed successfully")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Query results as a list of rows")
    error: Optional[str] = Field(default=None, description="Error message if the query failed")
    execution_time_ms: Optional[float] = Field(default=None, description="Query execution time in milliseconds")
    row_count: Optional[int] = Field(default=None, description="Number of rows returned")

class MCPWorkflowState(TypedDict):
    """State for MCP workflow operations."""
    query: str
    params: Optional[Dict[str, Any]]
    database: str
    query_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: Optional[float]

async def initialize_mcp_tools():
    """Initialize MCP tools from the server."""
    global tools
    
    if tools is None:
        logger.debug("MCP tools not initialized. Calling client.get_tools().")
        fetched_tools_from_client = []
        try:
            fetched_tools_from_client = await client.get_tools()
            
            if not isinstance(fetched_tools_from_client, list):
                logger.error(f"client.get_tools() did not return a list, but: {type(fetched_tools_from_client)}. Setting tools to empty list.")
                valid_tools = []
            else:
                valid_tools = []
                for t in fetched_tools_from_client:
                    if hasattr(t, 'name') and isinstance(t.name, str) and \
                       hasattr(t, 'description') and isinstance(t.description, str) and \
                       (hasattr(t, 'ainvoke') and callable(getattr(t, 'ainvoke'))):
                        valid_tools.append(t)
                    else:
                        logger.warning(f"Item from client.get_tools() is not a valid Langchain tool object: {t}. Type: {type(t)}. Skipping.")
            
            tools = valid_tools
            if tools:
                tool_names = [t.name for t in tools if hasattr(t, 'name')]
                logger.info(f"Successfully initialized MCP tools: {tool_names}")
            elif not fetched_tools_from_client:
                logger.warning("client.get_tools() returned no tools or an invalid format. Global tools list is empty.")
            else:
                logger.warning("client.get_tools() returned items, but none were valid Langchain tools. Global tools list is empty.")
        except Exception as e:
            logger.error(f"Failed to fetch or process MCP tools: {e}", exc_info=True)
            tools = []
    else:
        if tools:
            logger.debug(f"MCP tools already initialized: {[tool.name for tool in tools if hasattr(tool, 'name')]}")
        else:
            logger.debug("Global tools variable was not None, but is empty. Consider re-initialization if this is unexpected.")
    
    return tools

async def mcp_initialize_state(initial_input: Dict[str, Any]) -> MCPWorkflowState:
    """Initialize the MCP workflow state."""
    logger.info("MCP Workflow: Initializing state.")
    await initialize_mcp_tools()
    return {
        "query": initial_input.get("query", ""),
        "params": initial_input.get("params", {}),
        "database": initial_input.get("database", "default"),
        "query_result": None,
        "error_message": None,
        "execution_time_ms": None,
    }

async def mcp_execute_query_node(state: MCPWorkflowState) -> MCPWorkflowState:
    """Execute SQL query using MCP tools."""
    logger.info("MCP Workflow: Entering execute_query_node.")
    current_error = state.get('error_message') or ""
    
    global tools
    if not tools:
        logger.error("MCP tools are not initialized. Cannot execute query.")
        state['error_message'] = (current_error + " Internal error: MCP tools not available.").strip()
        return state
    
    # Find the execute_query tool
    execute_tool = next((t for t in tools if hasattr(t, 'name') and t.name == "execute_query"), None)
    if not execute_tool:
        logger.error("'execute_query' tool not found in initialized MCP tools.")
        state['error_message'] = (current_error + " Internal error: execute_query tool is missing.").strip()
        return state
    
    query = state.get("query", "").strip()
    if not query:
        state['error_message'] = (current_error + " Query is empty.").strip()
        logger.warning(f"MCP Workflow: {state['error_message']}")
        return state
    
    params = state.get("params", {})
    logger.info(f"MCP Workflow: Executing query via tool: '{query[:100]}...'")
    
    try:
        # Prepare tool input
        tool_input = {
            "query": query,
            "params": params if params else None
        }
        
        # Execute the tool
        tool_response_raw = await execute_tool.ainvoke(tool_input)
        processed_tool_response = None
        
        if isinstance(tool_response_raw, dict):
            processed_tool_response = tool_response_raw
        elif isinstance(tool_response_raw, str):
            logger.debug(f"MCP tool returned a string. Attempting to parse as JSON.")
            try:
                processed_tool_response = json.loads(tool_response_raw)
                if not isinstance(processed_tool_response, dict):
                    logger.error(f"Parsed JSON from tool string is not a dict. Type: {type(processed_tool_response)}")
                    processed_tool_response = {"success": False, "error": "Tool returned string that parsed to non-dict.", "details": tool_response_raw}
            except json.JSONDecodeError as json_e:
                logger.error(f"Failed to parse string from MCP tool as JSON: {json_e}")
                processed_tool_response = {"success": False, "error": "Tool returned unparsable string.", "details": tool_response_raw}
        else:
            logger.warning(f"MCP tool returned unexpected type. Type: {type(tool_response_raw)}, Response: {str(tool_response_raw)[:200]}")
            processed_tool_response = {"success": False, "error": "Unexpected tool output type.", "details": str(tool_response_raw)}
        
        state["query_result"] = processed_tool_response
        
        if processed_tool_response and processed_tool_response.get("success"):
            logger.info(f"MCP query executed successfully.")
            state["execution_time_ms"] = processed_tool_response.get("execution_time_ms")
        elif processed_tool_response and not processed_tool_response.get("success"):
            error_msg = processed_tool_response.get("error", "Unknown error")
            logger.warning(f"MCP query execution failed: {error_msg}")
            state['error_message'] = (current_error + f" Query execution failed: {error_msg}").strip()
        else:
            logger.error("MCP tool returned invalid response format.")
            state['error_message'] = (current_error + " Invalid response format from MCP tool.").strip()
            
    except Exception as e:
        logger.error(f"Exception invoking MCP execute_query tool: {e}", exc_info=True)
        state["query_result"] = {"success": False, "error": f"Exception during tool call: {str(e)}"}
        state['error_message'] = (current_error + f" Error executing query: {str(e)}").strip()
    
    logger.debug(f"MCP State after query execution: {state}")
    return state

async def mcp_process_results_node(state: MCPWorkflowState) -> MCPWorkflowState:
    """Process and format query results using LLM agent."""
    logger.info("MCP Workflow: Entering process_results_node.")
    
    query_result = state.get("query_result")
    query = state.get("query", "")
    error_message = state.get("error_message")
    
    if error_message:
        logger.warning(f"Processing results with existing error: {error_message}")
        return state
    
    if not query_result:
        state['error_message'] = "No query result to process."
        return state
    
    # Create agent for result processing
    system_prompt = """
    You are a SQL Query Result Processor. Your role is to analyze and format SQL query results in a user-friendly manner.
    
    Instructions:
    1. If the query was successful, provide a clear summary of the results
    2. If there was an error, explain what went wrong
    3. Format the data in a readable way
    4. Provide insights about the data if relevant
    5. Keep responses concise and informative
    """
    
    human_input = f"""
    SQL Query: {query}
    
    Query Result:
    {json.dumps(query_result, indent=2)}
    
    Please process and format this result for the user.
    """
    
    try:
        response_agent = create_react_agent(model=llm, tools=tools or [])
        
        agent_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_input)
        ]
        
        agent_output = await response_agent.ainvoke({"messages": agent_messages})
        processed_response = ""
        
        if isinstance(agent_output, dict):
            if "output" in agent_output:
                processed_response = agent_output["output"]
            elif "messages" in agent_output and agent_output["messages"]:
                for msg in reversed(agent_output["messages"]):
                    if msg.type == "ai":
                        processed_response = msg.content
                        break
        
        if processed_response:
            # Add the processed response to the result
            if isinstance(state["query_result"], dict):
                state["query_result"]["processed_summary"] = processed_response
            logger.info("Query results processed successfully by agent.")
        else:
            logger.warning("Agent did not return a processed response.")
            
    except Exception as e:
        logger.error(f"Error processing results with agent: {e}", exc_info=True)
        # Don't fail the workflow, just log the error
    
    return state

def build_mcp_workflow():
    """Build the MCP workflow graph."""
    workflow = StateGraph(MCPWorkflowState)
    
    workflow.add_node("initialize_state", mcp_initialize_state)
    workflow.add_node("execute_query", mcp_execute_query_node)
    workflow.add_node("process_results", mcp_process_results_node)
    
    workflow.set_entry_point("initialize_state")
    workflow.add_edge("initialize_state", "execute_query")
    workflow.add_edge("execute_query", "process_results")
    workflow.add_edge("process_results", END)
    
    compiled_workflow = workflow.compile()
    logger.info("MCP workflow compiled successfully.")
    return compiled_workflow

# Create the workflow app
mcp_workflow_app = build_mcp_workflow()

class MCPLangChainClient:
    """LangChain-based MCP client with React Agent capabilities."""
    
    def __init__(self):
        """Initialize the MCP LangChain client."""
        self.workflow = mcp_workflow_app
        
    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        database: str = "default"
    ) -> MCPQueryResult:
        """Execute a SQL query via the MCP workflow.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters
            database: Target database name
            
        Returns:
            MCPQueryResult containing the query results or error
        """
        try:
            input_data = {
                "query": query,
                "params": params or {},
                "database": database
            }
            
            logger.debug(f"Executing MCP query via workflow: {query[:200]}...")
            
            final_state = None
            config = {"configurable": {"thread_id": f"mcp-query-{hash(query)}"}}
            
            async for event_chunk in self.workflow.astream(input_data, config=config, stream_mode="values"):
                final_state = event_chunk
            
            if final_state:
                query_result = final_state.get("query_result", {})
                error_message = final_state.get("error_message")
                
                if error_message:
                    return MCPQueryResult(
                        success=False,
                        error=error_message,
                        execution_time_ms=final_state.get("execution_time_ms", 0)
                    )
                
                if query_result and query_result.get("success"):
                    return MCPQueryResult(
                        success=True,
                        data=query_result.get("data"),
                        execution_time_ms=query_result.get("execution_time_ms"),
                        row_count=query_result.get("row_count")
                    )
                else:
                    return MCPQueryResult(
                        success=False,
                        error=query_result.get("error", "Unknown error"),
                        execution_time_ms=query_result.get("execution_time_ms", 0)
                    )
            else:
                return MCPQueryResult(
                    success=False,
                    error="No response from workflow",
                    execution_time_ms=0
                )
                
        except Exception as e:
            error_msg = f"Error executing MCP query via workflow: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return MCPQueryResult(
                success=False,
                error=error_msg,
                execution_time_ms=0
            )
    
    async def get_all_sops(self) -> MCPQueryResult:
        """Retrieve all SOP steps from the database."""
        return await self.execute_query("SELECT id, sop_code, step_number, description, query FROM SOP ORDER BY sop_code, step_number")
    
    async def get_sop_by_code(self, sop_code: str) -> MCPQueryResult:
        """Retrieve all steps for a specific SOP code."""
        return await self.execute_query(
            "SELECT id, sop_code, step_number, description, query FROM SOP WHERE sop_code = :sop_code ORDER BY step_number",
            {"sop_code": sop_code.upper()}
        )
    
    async def close(self):
        try:
            if hasattr(client, "aclose") and callable(getattr(client, "aclose")):
                await client.aclose()
            elif hasattr(client, "close") and callable(getattr(client, "close")):
                res = client.close()
                if asyncio.iscoroutine(res):
                    await res
            elif hasattr(client, "shutdown") and callable(getattr(client, "shutdown")):
                res = client.shutdown()
                if asyncio.iscoroutine(res):
                    await res
            else:
                logger.warning("Client has no close/aclose/shutdown; skipping explicit close.")
        except Exception as e:
            logger.error(f"Error closing MCP client: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

# Create a global instance for convenience
mcp_langchain_client = MCPLangChainClient()

if __name__ == "__main__":
    async def test_mcp_client():
        """Test the MCP LangChain client."""
        logger.info("--- Running MCP LangChain Client Self-Test ---")
        
        test_cases = [
            {
                "name": "Get All SOPs",
                "method": "get_all_sops",
                "args": []
            },
            {
                "name": "Get SOP by Code",
                "method": "get_sop_by_code",
                "args": ["TEST"]
            },
            {
                "name": "Custom Query",
                "method": "execute_query",
                "args": ["SELECT COUNT(*) as total_sops FROM SOP"]
            }
        ]
        
        async with mcp_langchain_client as client:
            for i, test_case in enumerate(test_cases):
                logger.info(f"\n--- Test Case {i+1}: {test_case['name']} ---")
                try:
                    method = getattr(client, test_case['method'])
                    result = await method(*test_case['args'])
                    
                    logger.info(f"Success: {result.success}")
                    if result.success:
                        logger.info(f"Row Count: {result.row_count}")
                        logger.info(f"Execution Time: {result.execution_time_ms}ms")
                        if result.data:
                            logger.info(f"Sample Data: {result.data[:2]}")  # First 2 rows
                    else:
                        logger.error(f"Error: {result.error}")
                        
                except Exception as e:
                    logger.error(f"Test case failed: {e}", exc_info=True)
        
        logger.info("\n--- MCP LangChain Client Self-Test Complete ---")
    
    asyncio.run(test_mcp_client())
