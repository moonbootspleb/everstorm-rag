---
title: Everstorm RAG
emoji: 🌩️
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: "6.0.0"
python_version: "3.11"
app_file: app.py
pinned: false
short_description: Everstorm support chat from all policy PDFs.
models:
  - thenlper/gte-small
---

# Everstorm RAG — Hugging Face Space

Gradio demo for **Project 2**: Everstorm Outfitters customer-support RAG (FAISS + `gte-small`, optional OpenAI on Space).

| | |
|---|---|
| **Space (HF)** | `moonbootspleb/everstorm-rag` |
| **GitHub** | [moonbootspleb/everstorm-rag](https://github.com/moonbootspleb/everstorm-rag) |
| **Source (monorepo)** | `BYTEBTYEGO/demos-2/` |
| **Deploy guide** | [DEPLOY.md](DEPLOY.md) |
| **Embedded on** | [moonboots.tech](https://moonboots.tech/blog/building-a-support-rag-chatbot) |

## Tabs

1. **Policies** — pick a PDF, preview text, chunk count  
2. **Retrieve** — semantic search with scores  
3. **Support chat** — `rag_step()` with expandable sources  

## Space secrets

| Secret | Purpose |
|--------|---------|
| `OLLAMA_BASE_URL` | Remote Ollama via Tailscale Funnel (see [DEPLOY.md](DEPLOY.md)) |
| `OLLAMA_MODEL` | Model name override (default `gemma3:1b`) |
| `OPENAI_API_KEY` | Alternative: `gpt-4o-mini` on OpenAI cloud |

`OLLAMA_API_KEY` is only needed if you put a bearer-auth proxy in front of Ollama; leave it unset for a plain Funnel URL.

Without `OLLAMA_BASE_URL` or `OPENAI_API_KEY`, the Space runs in **retrieval-only** mode. **Retrieve** and **Policies** work without LLM secrets.

## Local run

```bash
cd BYTEBTYEGO/demos-2
pip install -r requirements.txt
python scripts/build_index.py   # if vectorstore/ missing
python app.py
```

See [DEPLOY.md](DEPLOY.md) for Hugging Face push and Netlify embed setup.
