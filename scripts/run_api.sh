#!/usr/bin/env bash
# Run Everstorm RAG API from BYTEBTYEGO/demos-2 (falls back to project_2 vectorstore).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export EVERSTORM_RAG_ROOT="${EVERSTORM_RAG_ROOT:-$ROOT}"
if [[ ! -d "$EVERSTORM_RAG_ROOT/vectorstore" && -d "$ROOT/../project_2/vectorstore" ]]; then
  export EVERSTORM_RAG_ROOT="$(cd "$ROOT/../project_2" && pwd)"
fi
exec uvicorn api.main:app --host 127.0.0.1 --port "${PORT:-8080}" "$@"
