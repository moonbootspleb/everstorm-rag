"""Resolve EVERSTORM_RAG_ROOT and import rag_core (shared by API and Streamlit)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEMO_ROOT = Path(__file__).resolve().parents[1]
_BYTEBTYEGO = _DEMO_ROOT.parent
_LAB = _BYTEBTYEGO / "project_2"


def _set_rag_root() -> None:
    if (_DEMO_ROOT / "data").is_dir() or (_DEMO_ROOT / "vectorstore").is_dir():
        os.environ.setdefault("EVERSTORM_RAG_ROOT", str(_DEMO_ROOT))
    elif (_LAB / "data").is_dir() or (_LAB / "vectorstore").is_dir():
        os.environ.setdefault("EVERSTORM_RAG_ROOT", str(_LAB))
    elif (_BYTEBTYEGO / "data").is_dir() or (_BYTEBTYEGO / "vectorstore").is_dir():
        os.environ.setdefault("EVERSTORM_RAG_ROOT", str(_BYTEBTYEGO))


_set_rag_root()

if (_DEMO_ROOT / "rag_core.py").exists():
    sys.path.insert(0, str(_DEMO_ROOT))
elif (_LAB / "rag_core.py").exists():
    sys.path.insert(0, str(_LAB))
