#!/usr/bin/env python3
"""Build vectorstore/ for demos-2 (uses project_2/data when demos-2/data is absent)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
_BYTEBTYEGO = DEMO_ROOT.parent
_LAB = _BYTEBTYEGO / "project_2"

if (DEMO_ROOT / "data").is_dir():
    os.environ["EVERSTORM_RAG_ROOT"] = str(DEMO_ROOT)
elif (_LAB / "data").is_dir():
    os.environ["EVERSTORM_RAG_ROOT"] = str(_LAB)
else:
    os.environ["EVERSTORM_RAG_ROOT"] = str(DEMO_ROOT)

if (DEMO_ROOT / "rag_core.py").exists():
    sys.path.insert(0, str(DEMO_ROOT))
elif (_LAB / "rag_core.py").exists():
    sys.path.insert(0, str(_LAB))

from rag_core import build_vectorstore, chunk_documents, load_pdfs, pdf_paths  # noqa: E402


def main() -> None:
    paths = pdf_paths()
    if not paths:
        raise SystemExit("No Everstorm_*.pdf files under data/")
    raw = load_pdfs(paths)
    chunks = chunk_documents(raw)
    out = DEMO_ROOT / "vectorstore"
    build_vectorstore(chunks, out)
    print(f"Built {len(chunks)} chunks → {out}")


if __name__ == "__main__":
    main()
