# File: app/core/mcp_server.py
# Author: Dipanjanghosal
# Date: 2025-08-18

"""
MCP (Model Context Protocol) server for SOP database access and policy extraction.
This server exposes the consolidated SOP database and medical policy extraction using FastMCP.
"""
import sqlite3
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_openai import AzureChatOpenAI

from app.config.logging_config import logger

# --- Configuration ---
DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "claims.db"
INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "faiss_medpol_single")

# Initialize FastMCP server
mcp = FastMCP("sop-database-and-policy-extractor")

# --- Azure OpenAI LLM Setup ---
try:
    llm = AzureChatOpenAI(
        temperature=0,
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        model_name=os.getenv("MODEL_NAME"),
        openai_api_version=os.getenv("OPENAI_API_VERSION"),
    )
    logger.info("Azure OpenAI LLM initialized for policy extraction")
except Exception as e:
    logger.error(f"Failed to initialize Azure OpenAI: {e}")
    llm = None

# --- FAISS Vector Store Setup ---
_embeddings = None
_vectorstore = None

try:
    if os.path.exists(INDEX_DIR):
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        _vectorstore = FAISS.load_local(
            INDEX_DIR,
            _embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info(f"FAISS vectorstore loaded from {INDEX_DIR}")
    else:
        logger.warning(f"FAISS index directory not found: {INDEX_DIR}")
except Exception as e:
    logger.error(f"Failed to load FAISS vectorstore: {e}")

# --- Policy Extraction Parser Setup ---
response_schemas = [
    ResponseSchema(name="found", description="true if the code was found", type="boolean"),
    ResponseSchema(name="code", description="5-digit procedure code", type="string"),
    ResponseSchema(name="code_status", description="Active/Inactive", type="string"),
    ResponseSchema(name="effective_date", description="Effective date", type="string"),
    ResponseSchema(name="long_description", description="Long description", type="string"),
    ResponseSchema(name="short_description", description="Short description", type="string"),
    ResponseSchema(name="possible_provider_specialty", description="Provider specialty name", type="string"),
    ResponseSchema(name="possible_provider_specialty_code", description="Provider specialty code", type="string"),
    ResponseSchema(name="possible_provider_type", description="Provider type name", type="string"),
    ResponseSchema(name="possible_provider_type_code", description="Provider type code", type="string"),
    ResponseSchema(name="possible_type_of_service", description="Type of service", type="string"),
    ResponseSchema(
        name="possible_place_of_service",
        description="List of objects {name, code}",
        type="array"
    ),
    ResponseSchema(name="raw_span", description="Exact text span used", type="string"),
    ResponseSchema(name="notes", description="Disambiguation notes", type="string"),
]

if llm:
    parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = parser.get_format_instructions()

    PROMPT = PromptTemplate(
        template=(
            "You are an expert medical policy extractor. "
            "Given the entire medical policy document text, find the entry for procedure code = {code}.\n\n"
            "Return ONLY JSON following this exact schema:\n"
            "{format_instructions}\n\n"
            "Rules:\n"
            "- If code not found, set found=false and leave other fields empty/null\n"
            "- Extract exact raw_span text you used for this code\n"
            "- Be precise and only return the JSON structure\n\n"
            "# DOCUMENT TEXT START\n{doc_text}\n# DOCUMENT TEXT END"
        ),
        input_variables=["code", "doc_text"],
        partial_variables={"format_instructions": format_instructions},
    )

# --- Database Connection Functions ---
def get_db_connection():
    """Create and return a database connection."""
    try:
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(f"Database not found at {DATABASE_PATH}")
        
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise e

# --- Policy Extraction Helper Functions ---
def _get_single_doc_text() -> str:
    """Retrieve the single document from FAISS vectorstore."""
    if not _vectorstore:
        raise RuntimeError("FAISS vectorstore not initialized")
    
    hits = _vectorstore.similarity_search("return the single doc", k=1)
    if not hits:
        raise RuntimeError("No document found in FAISS index")
    return hits[0].page_content

def _extract_policy_json(code: str) -> Dict[str, Any]:
    """Extract policy information for a given code using LLM."""
    if not llm or not _vectorstore:
        return {
            "found": False,
            "code": code,
            "notes": "LLM or vectorstore not available",
        }
    
    try:
        text = _get_single_doc_text()
        prompt = PROMPT.format(code=code, doc_text=text)
        raw = llm.invoke(prompt).content
        
        try:
            return parser.parse(raw)
        except Exception:
            try:
                return json.loads(raw)
            except Exception:
                return {
                    "found": False,
                    "code": code,
                    "notes": "Failed to parse LLM output",
                    "raw_output": raw[:500]  # Truncate for logging
                }
    except Exception as e:
        logger.error(f"Policy extraction failed for code {code}: {e}")
        return {
            "found": False,
            "code": code,
            "notes": f"Extraction error: {str(e)}"
        }

# --- MCP Tools ---

@mcp.tool()
def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a SQL query against the claims database.
    
    Args:
        query: The SQL query to execute
        params: Optional parameters for the query (default: None)
    
    Returns:
        JSON string with query results and execution metadata
    """
    if params is None:
        params = {}
    
    start_time = time.perf_counter()
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        logger.info(f"Executing query: {query[:200]}")
        
        # Convert dict params to tuple if needed for sqlite3
        if isinstance(params, dict) and params:
            cursor.execute(query, params)
        elif isinstance(params, (list, tuple)):
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # Handle SELECT vs DML operations
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            row_count = len(data)
        else:
            conn.commit()
            data = None
            row_count = cursor.rowcount

        execution_time_ms = (time.perf_counter() - start_time) * 1000
        
        result = {
            "success": True,
            "data": data,
            "execution_time_ms": round(execution_time_ms, 2),
            "row_count": row_count
        }
        
        return json.dumps(result, indent=2)
        
    except sqlite3.Error as e:
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Database query failed: {e}")
        
        result = {
            "success": False,
            "error": str(e),
            "execution_time_ms": round(execution_time_ms, 2)
        }
        
        return json.dumps(result, indent=2)
    finally:
        if conn:
            conn.close()

@mcp.tool()
def get_all_sops() -> str:
    """
    Retrieve all SOP steps from the database.
    
    Returns:
        JSON string with all SOP steps ordered by code and step number
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sop_code, step_number, description, query 
            FROM SOP 
            ORDER BY sop_code, step_number
        """)
        rows = cursor.fetchall()
        
        sops = []
        for row in rows:
            sop_step = {
                "id": row["id"],
                "sop_code": row["sop_code"],
                "step_number": row["step_number"],
                "description": row["description"],
                "query": row["query"]
            }
            sops.append(sop_step)
        
        result = {
            "success": True,
            "data": sops,
            "count": len(sops)
        }
        
        return json.dumps(result, indent=2)
        
    except sqlite3.Error as e:
        logger.error(f"Error retrieving all SOPs: {e}")
        result = {
            "success": False,
            "error": str(e)
        }
        return json.dumps(result, indent=2)
    finally:
        if conn:
            conn.close()

@mcp.tool()
def get_sop_by_code(sop_code: str) -> str:
    """
    Retrieve all steps for a specific SOP code.
    
    Args:
        sop_code: The SOP code to search for
    
    Returns:
        JSON string with SOP steps for the specified code
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sop_code, step_number, description, query 
            FROM SOP 
            WHERE sop_code = ? 
            ORDER BY step_number
        """, (sop_code.upper(),))
        
        rows = cursor.fetchall()
        
        if not rows:
            result = {
                "success": False,
                "error": f"SOP code '{sop_code}' not found"
            }
            return json.dumps(result, indent=2)
        
        sops = []
        for row in rows:
            sop_step = {
                "id": row["id"],
                "sop_code": row["sop_code"],
                "step_number": row["step_number"],
                "description": row["description"],
                "query": row["query"]
            }
            sops.append(sop_step)
        
        result = {
            "success": True,
            "data": sops,
            "count": len(sops),
            "sop_code": sop_code.upper()
        }
        
        return json.dumps(result, indent=2)
        
    except sqlite3.Error as e:
        logger.error(f"Error retrieving SOP {sop_code}: {e}")
        result = {
            "success": False,
            "error": str(e)
        }
        return json.dumps(result, indent=2)
    finally:
        if conn:
            conn.close()

@mcp.tool()
def get_database_schema() -> str:
    """
    Get the database schema information.
    
    Returns:
        JSON string with table schema information
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema_info = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            schema_info[table] = [
                {
                    "name": col[1],
                    "type": col[2],
                    "not_null": bool(col[4]),
                    "default_value": col[5],
                    "primary_key": bool(col[6])
                }
                for col in columns
            ]
        
        result = {
            "success": True,
            "schema": schema_info,
            "tables": tables
        }
        
        return json.dumps(result, indent=2)
        
    except sqlite3.Error as e:
        logger.error(f"Error retrieving schema: {e}")
        result = {
            "success": False,
            "error": str(e)
        }
        return json.dumps(result, indent=2)
    finally:
        if conn:
            conn.close()

@mcp.tool()
def extract_policy_json_by_code(code: str, fields: Optional[List[str]] = None) -> str:
    """
    Extract medical policy information for a specific procedure code.
    
    Args:
        code: 5-digit procedure code (e.g., '27447')
        fields: Optional list of specific fields to return
    
    Returns:
        JSON string with extracted policy information
    """
    result = _extract_policy_json(code)
    
    # Normalize place_of_service if returned as string
    pos = result.get("possible_place_of_service")
    if isinstance(pos, str) and pos:
        items = []
        for token in pos.split(","):
            token = token.strip()
            if "(" in token and token.endswith(")"):
                name = token[:token.rfind("(")].strip()
                code_val = token[token.rfind("(")+1:-1].strip()
                items.append({"name": name, "code": code_val})
            else:
                items.append({"name": token, "code": ""})
        result["possible_place_of_service"] = items
    
    # Filter fields if requested
    if fields:
        filtered = {k: result.get(k) for k in fields}
        # Always include essential fields
        filtered["found"] = result.get("found", False)
        filtered["code"] = result.get("code", code)
        return json.dumps(filtered, indent=2)
    
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    # Initialize and run the server
    logger.info("Starting MCP server with SOP database and policy extraction tools")
    mcp.run(transport='sse')
