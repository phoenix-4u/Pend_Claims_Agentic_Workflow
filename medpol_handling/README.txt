For this to properly work, you must first run "ingest_single_chunk.py" file once to generate the Vectorstore

Also, on line 22 of "mcp_depol_single_json.py", you must update the code with your own Google API key for the LLM model to work

sample FastMCP arguments call is:

{"code": "27447", "fields": ["possible_provider_type", "possible_provider_type_code"]}

"code" is the medical code and "fields" is the list of fields you want returned.
See lines 32-51 in mcp_depol_single_json.py for all possible fields