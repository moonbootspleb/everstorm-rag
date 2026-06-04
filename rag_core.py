"""Everstorm RAG — shared ingest, FAISS index, and rag_step for notebook, demos, and Streamlit."""

from __future__ import annotations

import glob
import os
import re
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
CHAT_TOP_K = 8
PER_PDF_K = 2
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_TEMPLATE = """
You are an Everstorm Outfitters customer support assistant. Use ONLY the CONTEXT below.

Rules:
1) Answer only from the context — do not invent policies or contact details.
2) If the context does not contain the answer, say: "I don't know based on the retrieved documents."
3) Be concise. Quote key phrases and cite sources as [source: filename].
4) For contact or support questions: list every @everstorm.example email in the context and
   what each is for (returns, shipping, billing, sizing, claims, etc.). If contact emails
   appear in the context, use them — do not say you are unsure.

CONTEXT:
{context}

USER:
{question}
"""

CONTACT_QUERY_RE = re.compile(
    r"\b(contact|support|help|reach|email us|get in touch|phone|call us)\b",
    re.I,
)
CONTACT_SEARCH_QUERY = (
    "Contact email everstorm.example returns logistics billing claims sizecare parts"
)

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
_corpus_cache: dict[str, Any] | None = None
_contact_snippets: list[Document] | None = None


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


def load_policy_corpus() -> dict[str, Any]:
    """Eager-load all Everstorm PDFs; return counts and filenames for startup checks."""
    global _corpus_cache
    if _corpus_cache is not None:
        return _corpus_cache

    paths = pdf_paths()
    pages: list[Document] = []
    errors: list[str] = []
    for path in paths:
        try:
            pages.extend(PyPDFLoader(str(path)).load())
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    all_text = re.sub(r"\s+", " ", "\n".join(d.page_content for d in pages))
    emails = sorted(set(m.group().lower() for m in re.finditer(r"[\w.+-]+@everstorm\.example", all_text, re.I)))

    _corpus_cache = {
        "pdf_count": len(paths),
        "page_count": len(pages),
        "files": [p.name for p in paths],
        "paths": [str(p) for p in paths],
        "errors": errors,
        "contact_emails": emails,
    }
    contact_snippets()
    return _corpus_cache


def _is_contact_question(question: str) -> bool:
    return bool(CONTACT_QUERY_RE.search(question))


def _build_contact_snippets() -> list[Document]:
    """Extract department email lines from policy PDFs for contact-style questions."""
    email_re = re.compile(r"[\w.+-]+@everstorm\.example", re.I)
    snippets: list[Document] = []
    seen_emails: set[str] = set()

    for path in pdf_paths():
        try:
            pages = PyPDFLoader(str(path)).load()
        except Exception:
            continue
        for page in pages:
            norm = re.sub(r"\s+", " ", page.page_content)
            for match in email_re.finditer(norm):
                email = match.group().lower()
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                start = max(0, match.start() - 100)
                end = min(len(norm), match.end() + 80)
                context = norm[start:end].strip()
                snippets.append(
                    Document(
                        page_content=f"[source: {path.name}] {context}",
                        metadata={"source": str(path), "kind": "contact"},
                    )
                )

    if snippets:
        lines = "\n".join(f"- {s.page_content}" for s in snippets)
        snippets.insert(
            0,
            Document(
                page_content=(
                    "Everstorm department contacts from policy documents:\n" + lines
                ),
                metadata={"source": "contact_directory", "kind": "contact"},
            ),
        )
    return snippets


def contact_snippets() -> list[Document]:
    global _contact_snippets
    if _contact_snippets is None:
        _contact_snippets = _build_contact_snippets()
    return _contact_snippets


def _append_unique(docs: list[Document], seen: set[str], incoming: list[Document]) -> None:
    for doc in incoming:
        key = _doc_key(doc)
        if key not in seen:
            seen.add(key)
            docs.append(doc)


def _doc_key(doc: Document) -> str:
    return f"{_source_label(doc)}:{doc.page_content[:120]}"


def _search_by_source(vs: FAISS, question: str, path: Path, k: int) -> list[Document]:
    """Similarity search scoped to one PDF (full path or basename metadata)."""
    src = str(path)
    for filt in ({"source": src}, {"source": path.name}):
        try:
            hits = vs.similarity_search(question, k=k, filter=filt)
            if hits:
                return hits
        except Exception:
            continue

    hits = vs.similarity_search(question, k=max(k * 4, 8))
    name = path.name
    matched = [d for d in hits if name in _source_label(d)]
    return matched[:k]


def retrieve_documents(question: str, top_k: int = CHAT_TOP_K) -> list[Document]:
    """Retrieve chunks for RAG, pulling from every indexed policy PDF when possible."""
    paths = pdf_paths()
    if not paths:
        return get_retriever(top_k=top_k).invoke(question)

    vs = get_vectorstore()
    seen: set[str] = set()
    docs: list[Document] = []

    if _is_contact_question(question):
        _append_unique(docs, seen, contact_snippets())
        _append_unique(
            docs,
            seen,
            [doc for doc, _ in retrieve_with_scores(CONTACT_SEARCH_QUERY, top_k=top_k)],
        )

    for path in paths:
        _append_unique(docs, seen, _search_by_source(vs, question, path, k=PER_PDF_K))

    if len(docs) < top_k:
        _append_unique(
            docs,
            seen,
            [doc for doc, _ in retrieve_with_scores(question, top_k=top_k * 2)],
        )

    return docs[:top_k]


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


def rag_step(question: str, top_k: int = CHAT_TOP_K) -> dict[str, Any]:
    """Retrieve → prompt → LLM; returns answer, sources, and optional retrieval_only flag."""
    docs = retrieve_documents(question, top_k=top_k)
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
