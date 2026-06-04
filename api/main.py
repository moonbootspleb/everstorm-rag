"""Everstorm RAG — FastAPI for moonboots.tech (no iframe)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import bootstrap  # noqa: F401 — sets EVERSTORM_RAG_ROOT

import rag_core  # noqa: E402

TOP_K_DEFAULT = 4
_INDEX_ERROR: str | None = None


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "https://moonboots.tech",
        "https://www.moonboots.tech",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _INDEX_ERROR
    try:
        rag_core.load_vectorstore()
        _INDEX_ERROR = None
    except Exception as exc:
        _INDEX_ERROR = str(exc)
    yield


app = FastAPI(
    title="Everstorm RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _require_index() -> None:
    if _INDEX_ERROR:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Vector index not loaded",
                "error": _INDEX_ERROR,
                "hint": "Run scripts/build_index.py and deploy vectorstore/",
            },
        )


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=TOP_K_DEFAULT, ge=1, le=8)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, str]]
    retrieval_only: bool
    backend: str


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=TOP_K_DEFAULT, ge=1, le=8)


class RetrieveChunk(BaseModel):
    rank: int
    score: float
    source: str
    text: str


class RetrieveResponse(BaseModel):
    chunks: list[RetrieveChunk]


class PolicyItem(BaseModel):
    filename: str
    path: str
    chunk_count: int
    preview: str


class HealthResponse(BaseModel):
    ok: bool
    backend: str
    root: str
    index_loaded: bool
    index_error: str | None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=_INDEX_ERROR is None,
        backend=rag_core.llm_backend_name(),
        root=str(rag_core.project_root()),
        index_loaded=_INDEX_ERROR is None,
        index_error=_INDEX_ERROR,
    )


@app.get("/policies", response_model=list[PolicyItem])
def policies() -> list[PolicyItem]:
    _require_index()
    return [PolicyItem(**item) for item in rag_core.policy_catalog()]


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    _require_index()
    result: dict[str, Any] = rag_core.rag_step(body.question.strip(), top_k=body.top_k)
    return ChatResponse(
        answer=result["answer"],
        sources=result.get("sources") or [],
        retrieval_only=bool(result.get("retrieval_only")),
        backend=str(result.get("backend") or rag_core.llm_backend_name()),
    )


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(body: RetrieveRequest) -> RetrieveResponse:
    _require_index()
    rows = rag_core.retrieve_with_scores(body.query.strip(), top_k=body.top_k)
    chunks = []
    for i, (doc, score) in enumerate(rows, 1):
        chunks.append(
            RetrieveChunk(
                rank=i,
                score=float(score),
                source=Path(doc.metadata.get("source", "unknown")).name,
                text=doc.page_content[:600],
            )
        )
    return RetrieveResponse(chunks=chunks)
