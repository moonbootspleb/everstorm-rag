"""Everstorm RAG — shared ingest, FAISS index, and rag_step for notebook, demos, and Streamlit."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 300
CHUNK_OVERLAP = 30
EMBEDDING_MODEL = "thenlper/gte-small"
DEFAULT_TOP_K = 4
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_TEMPLATE = """
You are a **Customer Support Chatbot**. Use only the information in CONTEXT to answer.
If the answer is not in CONTEXT, respond with "I'm not sure from the docs."

Rules:
1) Use ONLY the provided <context> to answer.
2) If the answer is not in the context, say: "I don't know based on the retrieved documents."
3) Be concise and accurate. Prefer quoting key phrases from the context.
4) When possible, cite sources as [source: source] using the metadata.

CONTEXT:
{context}

USER:
{question}
"""

RETRIEVAL_ONLY_MESSAGE = (
    "Retrieval-only mode: no LLM is configured. Set **OLLAMA_BASE_URL** (remote Ollama via "
    "Tailscale Funnel) or **OPENAI_API_KEY** in this Space's secrets (Settings → Repository "
    "secrets). Locally: `ollama serve` + `ollama pull gemma3:1b`. Top matching policy "
    "excerpts are shown below."
)

_llm = None
_vectorstore: FAISS | None = None
_retriever = None
_prompt: ChatPromptTemplate | None = None


def project_root() -> Path:
    """Resolve data/ and vectorstore/ root (project_2 or demos-2 on HF)."""
    env_root = os.environ.get("EVERSTORM_RAG_ROOT", "").strip()
    if env_root:
        root = Path(env_root).resolve()
        if (root / "data").is_dir():
            return root
    here = Path(__file__).resolve().parent
    if (here / "data").is_dir():
        return here
    parent = here.parent
    if (parent / "data").is_dir():
        return parent
    return here


def data_dir() -> Path:
    return project_root() / "data"


def vectorstore_dir() -> Path:
    return project_root() / "vectorstore"


def pdf_paths() -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(data_dir() / "Everstorm_*.pdf")))


def load_pdfs(paths: list[Path] | None = None) -> list[Document]:
    """Load all Everstorm policy PDFs via PyPDFLoader."""
    paths = paths or pdf_paths()
    docs: list[Document] = []
    for path in paths:
        docs.extend(PyPDFLoader(str(path)).load())
    return docs


def chunk_documents(raw_docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(raw_docs)


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_vectorstore(chunks: list[Document], save_dir: Path | None = None) -> FAISS:
    save_dir = save_dir or vectorstore_dir()
    save_dir.mkdir(parents=True, exist_ok=True)
    vs = FAISS.from_documents(chunks, get_embeddings())
    vs.save_local(str(save_dir))
    global _vectorstore, _retriever
    _vectorstore = vs
    _retriever = None
    return vs


def load_vectorstore(save_dir: Path | None = None) -> FAISS:
    global _vectorstore, _retriever
    save_dir = save_dir or vectorstore_dir()
    index_file = save_dir / "index.faiss"
    if not index_file.exists():
        raise FileNotFoundError(
            f"No FAISS index at {save_dir}. Run: python scripts/build_index.py"
        )
    _vectorstore = FAISS.load_local(
        str(save_dir),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )
    _retriever = None
    return _vectorstore


def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        load_vectorstore()
    return _vectorstore


def get_retriever(top_k: int = DEFAULT_TOP_K):
    global _retriever
    if _retriever is None:
        _retriever = get_vectorstore().as_retriever(search_kwargs={"k": top_k})
    return _retriever


def get_prompt() -> ChatPromptTemplate:
    global _prompt
    if _prompt is None:
        _prompt = ChatPromptTemplate.from_template(SYSTEM_TEMPLATE)
    return _prompt


def format_docs(docs: list[Document]) -> str:
    parts = []
    for doc in docs:
        source = Path(doc.metadata.get("source", "unknown")).name
        parts.append(f"[source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _source_label(doc: Document) -> str:
    return Path(doc.metadata.get("source", "unknown")).name


def ollama_base_url() -> str | None:
    """Remote Ollama URL (e.g. Tailscale Funnel). No trailing slash."""
    url = os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
    return url or None


def _make_chat_ollama(base_url: str):
    """Connect to Ollama at base_url. OLLAMA_API_KEY is optional (proxy auth only)."""
    from langchain_ollama import ChatOllama

    kwargs: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "temperature": 0.1,
        "base_url": base_url,
    }
    api_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if api_key:
        kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}
    return ChatOllama(**kwargs)


def get_llm():
    """Remote Ollama (OLLAMA_BASE_URL) → OpenAI → local Ollama for dev."""
    global _llm
    if _llm is not None:
        return _llm

    remote = ollama_base_url()
    if remote:
        try:
            _llm = _make_chat_ollama(remote)
            return _llm
        except Exception:
            _llm = None
            return None

    if os.environ.get("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI

            _llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.1)
            return _llm
        except ImportError:
            from langchain_community.chat_models import ChatOpenAI

            _llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.1)
            return _llm

    try:
        _llm = _make_chat_ollama("http://127.0.0.1:11434")
        return _llm
    except Exception:
        _llm = None
        return None


def llm_backend_name() -> str:
    remote = ollama_base_url()
    if remote:
        from urllib.parse import urlparse

        host = urlparse(remote).netloc or remote
        return f"ollama:{OLLAMA_MODEL}@{host}"
    if os.environ.get("OPENAI_API_KEY"):
        return f"openai:{OPENAI_MODEL}"
    if os.environ.get("SPACE_ID"):
        return "retrieval-only"
    return f"ollama:{OLLAMA_MODEL}@127.0.0.1:11434"


def retrieve_with_scores(question: str, top_k: int = DEFAULT_TOP_K) -> list[tuple[Document, float]]:
    return get_vectorstore().similarity_search_with_score(question, k=top_k)


def policy_catalog() -> list[dict[str, Any]]:
    """Per-PDF summary for the Policies tab."""
    paths = pdf_paths()
    if not paths:
        return []
    try:
        chunks = chunk_documents(load_pdfs())
    except Exception:
        chunks = []
    by_source: dict[str, list[Document]] = {}
    for ch in chunks:
        key = _source_label(ch)
        by_source.setdefault(key, []).append(ch)
    catalog = []
    for path in paths:
        name = path.name
        doc_chunks = by_source.get(name, [])
        preview = ""
        if doc_chunks:
            preview = doc_chunks[0].page_content[:1200]
        elif path.exists():
            try:
                preview = load_pdfs([path])[0].page_content[:1200]
            except Exception:
                preview = ""
        catalog.append(
            {
                "filename": name,
                "path": str(path),
                "chunk_count": len(doc_chunks),
                "preview": preview,
            }
        )
    return catalog


def rag_step(question: str, top_k: int = DEFAULT_TOP_K) -> dict[str, Any]:
    """Retrieve → prompt → LLM; returns answer, sources, and optional retrieval_only flag."""
    retriever = get_retriever(top_k=top_k)
    docs = retriever.invoke(question)
    context = format_docs(docs)
    sources = [
        {
            "source": _source_label(d),
            "excerpt": d.page_content[:500],
        }
        for d in docs
    ]

    llm = get_llm()
    if llm is None:
        excerpt_block = "\n\n".join(
            f"**{_source_label(d)}**\n{d.page_content[:400]}..." for d in docs
        )
        return {
            "answer": f"{RETRIEVAL_ONLY_MESSAGE}\n\n{excerpt_block}",
            "sources": sources,
            "retrieval_only": True,
            "backend": "retrieval-only",
        }

    prompt = get_prompt()
    messages = prompt.format_messages(context=context, question=question)
    try:
        if hasattr(llm, "invoke"):
            response = llm.invoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)
        else:
            text = prompt.format(context=context, question=question)
            answer = llm.invoke(text)
    except Exception as exc:
        excerpt_block = "\n\n".join(
            f"**{_source_label(d)}**\n{d.page_content[:400]}..." for d in docs
        )
        return {
            "answer": (
                f"LLM call failed ({exc}). Showing retrieved excerpts instead.\n\n"
                f"{excerpt_block}"
            ),
            "sources": sources,
            "retrieval_only": True,
            "backend": llm_backend_name(),
        }

    return {
        "answer": answer,
        "sources": sources,
        "retrieval_only": False,
        "backend": llm_backend_name(),
    }
