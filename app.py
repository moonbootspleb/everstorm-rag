"""Everstorm RAG — Hugging Face Space (Gradio)."""

from __future__ import annotations

import html
import os
import sys
from pathlib import Path


def _patch_asyncio_event_loop_del() -> None:
    """Suppress Gradio 6 asyncio GC noise on Hugging Face Spaces (see gradio#12699)."""
    import asyncio.base_events as base_events

    original_del = getattr(base_events.BaseEventLoop, "__del__", None)
    if original_del is None:
        return

    def _patched_del(self) -> None:
        try:
            original_del(self)
        except ValueError as exc:
            if str(exc) != "Invalid file descriptor: -1":
                raise

    base_events.BaseEventLoop.__del__ = _patched_del  # type: ignore[method-assign]


_patch_asyncio_event_loop_del()

import gradio as gr

_DEMO_ROOT = Path(__file__).resolve().parent
_BYTEBTYEGO = _DEMO_ROOT.parent
_LAB = _BYTEBTYEGO / "project_2"

if (_DEMO_ROOT / "data").is_dir() or (_DEMO_ROOT / "vectorstore").is_dir():
    os.environ.setdefault("EVERSTORM_RAG_ROOT", str(_DEMO_ROOT))
elif (_LAB / "data").is_dir() or (_LAB / "vectorstore").is_dir():
    os.environ.setdefault("EVERSTORM_RAG_ROOT", str(_LAB))

if (_DEMO_ROOT / "rag_core.py").exists():
    sys.path.insert(0, str(_DEMO_ROOT))
elif (_LAB / "rag_core.py").exists():
    sys.path.insert(0, str(_LAB))

import rag_core  # noqa: E402
from theme import (  # noqa: E402
    EVERSTORM_CHAT_JS,
    EVERSTORM_HERO_HTML,
    HAIRLINE,
    INK,
    MOONBOOTS_CSS,
    ORBITAL,
    build_moonboots_theme,
)

_INDEX_ERROR: str | None = None
_CORPUS: dict = {}

try:
    rag_core.load_vectorstore()
    _CORPUS = rag_core.load_policy_corpus()
except Exception as exc:
    _INDEX_ERROR = str(exc)


def _policy_list_html() -> str:
    if _INDEX_ERROR:
        return ""
    files = _CORPUS.get("files") or []
    if not files:
        return "<p style='color:rgba(255,255,255,0.45);'>No policy PDFs found.</p>"
    chips = []
    for name in files:
        label = html.escape(name.replace("Everstorm_", "").replace("_", " ").replace(".pdf", ""))
        chips.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;padding:4px 10px;'
            f"border:1px solid {HAIRLINE};border-radius:999px;background:{ORBITAL};"
            f"font-family:'JetBrains Mono',ui-monospace,monospace;font-size:0.65rem;"
            f'letter-spacing:0.06em;color:{INK};">{label}</span>'
        )
    count = _CORPUS.get("pdf_count", len(files))
    pages = _CORPUS.get("page_count", 0)
    return (
        f'<p style="margin:0 0 8px;color:rgba(255,255,255,0.45);font-size:0.85rem;">'
        f"{count} policies loaded ({pages} pages) — answers draw from all documents.</p>"
        + "".join(chips)
    )


def _status_banner() -> str | None:
    if _INDEX_ERROR:
        return (
            f"**Index not loaded:** `{_INDEX_ERROR}` — "
            "run `python scripts/build_index.py` and commit `vectorstore/`."
        )
    if _CORPUS.get("errors"):
        err = "; ".join(_CORPUS["errors"])
        return f"**Warning:** some PDFs failed to load: {err}"
    return None


def _format_sources_html(sources: list[dict]) -> str:
    if not sources:
        return "<p style='color:rgba(255,255,255,0.5);'>No sources.</p>"
    blocks = []
    for i, s in enumerate(sources, 1):
        src = html.escape(s.get("source", "unknown"))
        excerpt = html.escape(s.get("excerpt", ""))
        blocks.append(
            f'<details style="margin:8px 0;border:1px solid {HAIRLINE};'
            f'border-radius:0.75rem;padding:8px 12px;background:{ORBITAL};">'
            f'<summary style="cursor:pointer;color:{INK};font-family:monospace;">'
            f"[{i}] {src}</summary>"
            f'<p style="margin:8px 0 0;color:rgba(255,255,255,0.55);font-size:0.9em;">{excerpt}</p>'
            f"</details>"
        )
    return "".join(blocks)


def policy_choices() -> list[str]:
    return [p["filename"] for p in rag_core.policy_catalog()] or ["(no PDFs)"]


def show_policy(filename: str) -> tuple[str, str, str]:
    for item in rag_core.policy_catalog():
        if item["filename"] == filename:
            meta = (
                f"**Source file:** `{item['filename']}`  \n"
                f"**Chunks in index:** {item['chunk_count']}  \n"
                f"**Path:** `{item['path']}`"
            )
            preview = item["preview"] or "_No preview available._"
            return meta, preview, item["filename"]
    return "Policy not found.", "", filename


def run_retrieve(query: str, k: int) -> str:
    if not query.strip():
        return "Enter a question."
    if _INDEX_ERROR:
        return _INDEX_ERROR
    rows = rag_core.retrieve_with_scores(query, top_k=int(k))
    parts = []
    for i, (doc, score) in enumerate(rows, 1):
        src = html.escape(Path(doc.metadata.get("source", "unknown")).name)
        text = html.escape(doc.page_content[:600])
        parts.append(
            f'<div style="margin:12px 0;padding:12px;border:1px solid {HAIRLINE};'
            f'border-radius:0.75rem;background:{ORBITAL};">'
            f'<p style="margin:0 0 6px;color:#fff;font-family:monospace;">'
            f"#{i} · score {score:.4f} · {src}</p>"
            f'<p style="margin:0;color:rgba(255,255,255,0.55);font-size:0.9em;">{text}</p></div>'
        )
    return "".join(parts) or "<p>No matches.</p>"


def chat_fn(message: str, history: list[dict]) -> tuple[list[dict], str, str]:
    if not message.strip():
        return history, "", gr.update()
    user_msg = {"role": "user", "content": message}
    if _INDEX_ERROR:
        return history + [user_msg, {"role": "assistant", "content": _INDEX_ERROR}], "", gr.update(value="")
    result = rag_core.rag_step(message)
    answer = result["answer"]
    if result.get("retrieval_only"):
        answer = f"_{rag_core.RETRIEVAL_ONLY_MESSAGE.split('.')[0]}._\n\n{answer}"
    return (
        history + [user_msg, {"role": "assistant", "content": answer}],
        _format_sources_html(result.get("sources") or []),
        gr.update(value=""),
    )


WELCOME_MESSAGE = [
    {
        "role": "assistant",
        "content": (
            "Hi — I'm the Everstorm support assistant. Ask about **shipping**, "
            "**returns & refunds**, **product sizing & care**, or **payment & security**. "
            "For contact questions I'll list the relevant department emails from our policies."
        ),
    }
]

EXAMPLE_QUESTIONS = [
    "What is your refund policy and how do I start a return?",
    "How long does standard shipping take?",
    "How do I contact Everstorm about a return or shipping issue?",
    "What size should I order if I'm between sizes?",
]

_moonboots_theme = build_moonboots_theme()

with gr.Blocks(title="Everstorm Support", fill_width=True) as demo:
    gr.HTML(EVERSTORM_HERO_HTML)
    gr.HTML(_policy_list_html())
    _banner = _status_banner()
    if _banner:
        gr.Markdown(_banner)

    with gr.Column(elem_classes="everstorm-chat-shell"):
        chatbot = gr.Chatbot(
            value=WELCOME_MESSAGE,
            height=480,
            show_label=False,
            layout="bubble",
            autoscroll=True,
            elem_classes="everstorm-chat-messages",
        )
        with gr.Column(elem_classes="everstorm-chat-composer"):
            with gr.Row(elem_classes="everstorm-chat-composer-row"):
                chat_in = gr.Textbox(
                    show_label=False,
                    lines=1,
                    max_lines=8,
                    placeholder="Ask about shipping, returns, sizing, or payments…",
                    autofocus=True,
                    elem_id="everstorm-chat-input",
                    scale=9,
                )
                chat_btn = gr.Button(
                    "Send",
                    variant="primary",
                    scale=1,
                    elem_id="everstorm-chat-send",
                )
            with gr.Row(elem_classes="everstorm-chat-toolbar"):
                clear_btn = gr.Button("Clear chat", scale=0)
                gr.HTML(
                    '<p class="everstorm-chat-hint">Enter to send · Shift+Enter for new line</p>',
                )
    chat_sources = gr.HTML(label="Sources")
    gr.Examples(examples=[[q] for q in EXAMPLE_QUESTIONS], inputs=chat_in)

    chat_btn.click(chat_fn, inputs=[chat_in, chatbot], outputs=[chatbot, chat_sources, chat_in])
    chat_in.submit(chat_fn, inputs=[chat_in, chatbot], outputs=[chatbot, chat_sources, chat_in])
    clear_btn.click(lambda: (WELCOME_MESSAGE, "", ""), outputs=[chatbot, chat_sources, chat_in])

    with gr.Accordion("Browse policies & debug retrieval", open=False):
        with gr.Tabs():
            with gr.Tab("Policies"):
                pol_dd = gr.Dropdown(
                    label="Policy document",
                    choices=policy_choices(),
                    value=policy_choices()[0] if policy_choices() else None,
                )
                pol_meta = gr.Markdown()
                pol_preview = gr.Textbox(label="Excerpt preview", lines=14, max_lines=20)
                pol_file = gr.Textbox(label="Source filename", interactive=False)
                pol_dd.change(show_policy, inputs=pol_dd, outputs=[pol_meta, pol_preview, pol_file])
                demo.load(show_policy, inputs=pol_dd, outputs=[pol_meta, pol_preview, pol_file])

            with gr.Tab("Retrieve"):
                ret_q = gr.Textbox(label="Query", lines=2, placeholder="e.g. refund within 30 days")
                ret_k = gr.Slider(1, 12, value=rag_core.CHAT_TOP_K, step=1, label="Top-k")
                ret_out = gr.HTML(label="Chunks")
                ret_btn = gr.Button("Search", variant="primary")
                ret_btn.click(run_retrieve, inputs=[ret_q, ret_k], outputs=ret_out)
                gr.Examples(examples=[[q] for q in EXAMPLE_QUESTIONS], inputs=ret_q)

demo.launch(
    ssr_mode=False,
    theme=_moonboots_theme,
    css=MOONBOOTS_CSS,
    js=EVERSTORM_CHAT_JS,
)
