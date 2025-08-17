#File: app/core/mcp_server.py

"""
MCP (Model Context Protocol) server for SOP database access.
This server exposes the consolidated SOP database using FastMCP.
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config.logging_config import logger
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "claims.db"

# # --- Logging ---
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
# )
# logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("sop-database")

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
            # For named parameters, pass as dict
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
                    "not_null": bool(col[1]),
                    "default_value": col[2],
                    "primary_key": bool(col[3])
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

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')