from pathlib import Path
import pdfplumber
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

PDF_PATH = "../data/mockMedicalPolicy.pdf"    # <— set to your file
INDEX_DIR = "../data"

def load_pdf_text(path: str) -> str:
    chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    # One giant string (single chunk)
    return "\n".join(chunks)

def main():
    text = load_pdf_text(PDF_PATH)
    if not text.strip():
        raise RuntimeError("PDF text is empty—check the file or extractor.")

    # One single Document only
    doc = Document(page_content=text, metadata={"source": PDF_PATH, "chunk_id": "single-0"})

    embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vs = FAISS.from_documents([doc], embed)
    Path(INDEX_DIR).mkdir(parents=True, exist_ok=True)
    vs.save_local(INDEX_DIR)
    print(f"Indexed 1 single chunk into {INDEX_DIR}")

if __name__ == "__main__":
    main()
