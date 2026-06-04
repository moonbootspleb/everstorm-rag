"""Local Streamlit chat UI for Everstorm RAG (Ollama). Not used on moonboots.tech production."""

from __future__ import annotations

import streamlit as st

from api import bootstrap  # noqa: F401 — EVERSTORM_RAG_ROOT

import rag_core
from rag_core import llm_backend_name, rag_step

st.set_page_config(page_title="Everstorm Support (local)", page_icon="🌩️")
st.title("Everstorm Outfitters — Support")
st.caption(
    f"Backend: `{llm_backend_name()}` · Local lab only. "
    "Production demo: moonboots.tech blog + FastAPI (`demos-2/api/`)."
)
st.markdown(
    "Run `ollama serve` and `ollama pull gemma3:1b` for local generation, "
    "or set `OPENAI_API_KEY` for cloud."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for s in msg["sources"]:
                    st.markdown(f"**{s['source']}**")
                    st.caption(s["excerpt"])

if prompt := st.chat_input("Ask about returns, shipping, sizing, or payments…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving policy docs…"):
            result = rag_step(prompt)
        st.markdown(result["answer"])
        sources = result.get("sources") or []
        if sources:
            with st.expander("Sources"):
                for s in sources:
                    st.markdown(f"**{s['source']}**")
                    st.caption(s["excerpt"])
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": sources,
        }
    )
