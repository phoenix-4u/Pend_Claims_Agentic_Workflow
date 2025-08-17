import json
from typing import List, Optional, Dict

# Vector store
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# LLM (Gemini via LangChain)
# pip install langchain-google-genai google-generativeai
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

# FastMCP
# pip install fastmcp
from fastmcp import FastMCP

INDEX_DIR = "faiss_medpol_single"

# ---- Configure your LLM here ----
GOOGLE_API_KEY = "GOOGLE_API_KEY"  # <-- replace with your key
MODEL_NAME = "gemini-1.5-flash"         # fast & cheap; switch to pro if you like

app = FastMCP("medical-policy-single-doc")

# Load FAISS (single doc) once
_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
_vectorstore = FAISS.load_local(INDEX_DIR, _embeddings, allow_dangerous_deserialization=True)

# Build a StructuredOutputParser you prefer
response_schemas = [
    ResponseSchema(name="found", description="true if the code was found, false otherwise", type="boolean"),
    ResponseSchema(name="code", description="The 5-digit code looked up (string)", type="string"),
    ResponseSchema(name="code_status", description="Active/Inactive", type="string"),
    ResponseSchema(name="effective_date", description="Effective date string as shown", type="string"),
    ResponseSchema(name="long_description", description="Long description text", type="string"),
    ResponseSchema(name="short_description", description="Short description text", type="string"),
    ResponseSchema(name="possible_provider_specialty", description="Provider specialty name", type="string"),
    ResponseSchema(name="possible_provider_specialty_code", description="Provider specialty 2-digit code", type="string"),
    ResponseSchema(name="possible_provider_type", description="Provider type name", type="string"),
    ResponseSchema(name="possible_provider_type_code", description="Provider type 2-digit code", type="string"),
    ResponseSchema(name="possible_type_of_service", description="Type of service", type="string"),
    ResponseSchema(
        name="possible_place_of_service",
        description="List of objects with keys 'name' and 'code'",
        type="array"
    ),
    ResponseSchema(name="raw_span", description="The exact text span used for this code", type="string"),
    ResponseSchema(name="notes", description="Any disambiguation notes or uncertainty", type="string"),
]
parser = StructuredOutputParser.from_response_schemas(response_schemas)
format_instructions = parser.get_format_instructions()

PROMPT = PromptTemplate(
    template=(
        "You are an expert information extractor.\n"
        "You are given the entire medical policy PDF as text (single block). "
        "Find the entry for the 5-digit procedure code = {code}.\n\n"
        "Return ONLY JSON with the following schema:\n"
        "{format_instructions}\n\n"
        "Rules:\n"
        "- If the code does not exist, set found=false and leave other fields empty (or sensible defaults).\n"
        "- If a field is clearly absent in the text for that code, leave it blank.\n"
        "- Extract the exact 'raw_span' text you relied upon for this code.\n\n"
        "# PDF TEXT START\n"
        "{doc_text}\n"
        "# PDF TEXT END\n"
    ),
    input_variables=["code", "doc_text"],
    partial_variables={"format_instructions": format_instructions},
)

_llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=GOOGLE_API_KEY, temperature=0)

def _get_single_doc_text() -> str:
    # We indexed exactly one document; retrieve it
    # A dummy similarity_search will return it since it's the only chunk
    hits = _vectorstore.similarity_search("return the single doc", k=1)
    if not hits:
        raise RuntimeError("Single document not found in the vectorstore.")
    return hits[0].page_content

def _extract_code_json(code: str) -> Dict:
    text = _get_single_doc_text()
    prompt = PROMPT.format(code=code, doc_text=text)
    raw = _llm.invoke(prompt).content
    try:
        return parser.parse(raw)
    except Exception:
        # Fallback: try to load as vanilla JSON if the model already returned perfect JSON
        try:
            return json.loads(raw)
        except Exception:
            return {
                "found": False,
                "code": code,
                "notes": "Failed to parse model output",
                "raw_output": raw
            }

@app.tool(
    name="extract_policy_json_by_code",
    description="Given a 5-digit code, extract that policy block as structured JSON from the single-chunk PDF."
)
def extract_policy_json_by_code(code: str, fields: Optional[List[str]] = None) -> str:
    """
    Args:
        code: 5-digit procedure code like '27447'
        fields: optional list of field names to return. If omitted, returns full schema.
    """
    result = _extract_code_json(code)
    # Normalize POS to a list of objects if the model returned a string
    pos = result.get("possible_place_of_service")
    if isinstance(pos, str):
        # extremely defensive: try to coerce naive "Name (xx), Name2 (yy)" into objects
        items = []
        for token in pos.split(","):
            token = token.strip()
            if not token:
                continue
            # naive split
            if "(" in token and token.endswith(")"):
                name = token[:token.rfind("(")].strip()
                code2 = token[token.rfind("(")+1:-1].strip()
                items.append({"name": name, "code": code2})
            else:
                items.append({"name": token, "code": ""})
        result["possible_place_of_service"] = items

    if fields:
        filtered = {k: result.get(k) for k in fields}
        # always include 'found' and 'code'
        filtered["found"] = result.get("found", False)
        filtered["code"] = result.get("code", code)
        return json.dumps(filtered)
    return json.dumps(result)

if __name__ == "__main__":

    app.run()
