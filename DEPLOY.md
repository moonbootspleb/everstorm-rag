# Deploy Everstorm RAG to Hugging Face Spaces + moonboots.tech

Production demo: **Gradio on HF CPU basic** embedded on the React blog. No Fly.io required.

| Piece | Where |
|-------|--------|
| Space source | [`BYTEBTYEGO/demos-2/`](.) |
| Blog embed | `COMPANYSITE` → `/blog/building-a-support-rag-chatbot` |
| Netlify env | `VITE_EVERSTORM_RAG_SPACE_URL` |

---

## 1. Build the vector index locally

```bash
cd BYTEBTYEGO/demos-2
source ../project_2/.venv/bin/activate   # or your project_2 venv
python scripts/build_index.py
```

Creates `demos-2/vectorstore/` from `data/` or `project_2/data/`.

```bash
du -sh vectorstore/
ls vectorstore/index.faiss
```

---

## 2. Create the Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. **Space name:** `everstorm-rag` (URL: `https://huggingface.co/spaces/moonbootspleb/everstorm-rag`).
3. **SDK:** Gradio.
4. **Hardware:** **CPU basic** (free tier).
5. **Visibility:** Public (required for iframe embed).
6. Create the Space.

---

## 3. Push files to the Space repo

Clone the Space git repo, then copy from `BYTEBTYEGO/demos-2/`:

| File / folder | Notes |
|---------------|--------|
| `app.py` | Gradio entry (HF `app_file`) |
| `theme.py` | MoonBoots styling |
| `rag_core.py` | RAG logic |
| `requirements.txt` | Space dependencies |
| `README.md` | HF YAML frontmatter |
| `data/` | All `Everstorm_*.pdf` |
| `vectorstore/` | Prebuilt FAISS index |

Example:

```bash
git clone https://huggingface.co/spaces/moonbootspleb/everstorm-rag
cd everstorm-rag

SRC=~/MOONBOOTS/BYTEBTYEGO/demos-2
cp "$SRC/app.py" "$SRC/theme.py" "$SRC/rag_core.py" "$SRC/requirements.txt" "$SRC/README.md" .
cp -R "$SRC/data" "$SRC/vectorstore" .

git add app.py theme.py rag_core.py requirements.txt README.md data vectorstore
git commit -m "Everstorm RAG: Gradio + FAISS index"
git push
```

Wait for **Building** → **Running** (first build may take 5–15 minutes).

---

## 4. Space secrets (Support chat)

Choose **one** generation backend in Space → **Settings** → **Repository secrets**.

### Option A — Remote Ollama via Tailscale Funnel (recommended for self-hosted LLM)

HF Spaces run in Hugging Face’s cloud; they cannot join your tailnet directly. Expose Ollama on your Linux box with **Tailscale Funnel**, then point the Space at the public HTTPS URL.

**On your Linux machine (one-time):**

```bash
# Install Ollama + Tailscale if needed, then:
ollama serve                    # or systemd
ollama pull gemma3:1b

cd BYTEBTYEGO/demos-2
chmod +x scripts/setup_tailscale_funnel.sh scripts/verify_ollama_remote.sh
./scripts/setup_tailscale_funnel.sh
```

Note the Funnel HTTPS URL (e.g. `https://your-host.tail12345.ts.net`).

**Verify from outside your LAN** (phone hotspot or another network):

```bash
./scripts/verify_ollama_remote.sh https://your-host.tail12345.ts.net
```

No Ollama auth is required — the Space calls your Funnel URL over HTTPS with no bearer token.

**HF Space secrets** (no auth):

| Secret | Example | Required |
|--------|---------|----------|
| `OLLAMA_BASE_URL` | `https://your-host.tail12345.ts.net` | Yes |
| `OLLAMA_MODEL` | `gemma3:1b` | No (defaults in code) |

Do **not** set `OLLAMA_API_KEY` unless you add auth yourself. Do **not** set `OPENAI_API_KEY` if you want home Ollama only.

**Optional hardening** (Funnel exposes Ollama to the public internet):

- Restrict Tailscale Funnel identity in the Tailscale admin console
- Put nginx/caddy with bearer auth in front of `:11434`, then set matching `OLLAMA_API_KEY` in HF secrets

After saving secrets, the Space rebuilds. Status banner should show `ollama:gemma3:1b@your-host...`.

**Operational notes:** Your Linux box and Funnel must stay up. Expect several seconds latency (HF cloud → your home → back). Use a small model on CPU.

### Option B — OpenAI cloud

1. Add **`OPENAI_API_KEY`** for `gpt-4o-mini` chat.
2. Rebuild triggers automatically.

Without either Option A or B, **Support chat** is retrieval-only; **Retrieve** and **Policies** still work.

---

## 5. Test the Space

| Check | Command / URL |
|-------|----------------|
| Space page | `https://huggingface.co/spaces/moonbootspleb/everstorm-rag` |
| Embed host (iframe) | `https://moonbootspleb-everstorm-rag.hf.space` |
| Policies tab | All 4 PDFs, chunk counts |
| Retrieve | Query “refund policy” → scored chunks |
| Support chat | Example question + sources (with OpenAI key) |

---

## 6. Embed on Netlify (moonboots.tech)

1. **Site configuration → Environment variables:**

   ```bash
   VITE_EVERSTORM_RAG_SPACE_URL=https://huggingface.co/spaces/moonbootspleb/everstorm-rag
   # optional direct embed host:
   # VITE_EVERSTORM_RAG_EMBED_URL=https://moonbootspleb-everstorm-rag.hf.space
   ```

2. Ensure `COMPANYSITE/public/everstorm/*.pdf` is committed (policy viewer on the blog).

3. **Deploys → Clear cache and deploy site**.

4. Open `https://moonboots.tech/blog/building-a-support-rag-chatbot`.

---

## 7. Smoke test checklist (production)

- [ ] HF Space status **Running**, no errors in Logs
- [ ] Embed URL loads: `https://moonbootspleb-everstorm-rag.hf.space`
- [ ] Blog: **Load interactive demo** mounts iframe (no API-not-configured banner)
- [ ] **Policies**, **Retrieve**, **Support chat** tabs work in embed
- [ ] **Open on Hugging Face** opens the Space in a new tab
- [ ] `/everstorm/Everstorm_Return_and_exchange_policy.pdf` loads on the blog
- [ ] With `OLLAMA_BASE_URL` or `OPENAI_API_KEY`: full chat answers; without: retrieval-only excerpts

---

## 8. Updating the index

1. Edit PDFs under `demos-2/data/` or `project_2/data/`.
2. `python scripts/build_index.py` in `demos-2/`.
3. Copy new `vectorstore/` into the Space repo and `git push`.

---

## Optional: local FastAPI (not used by the blog)

For development without HF:

```bash
cd BYTEBTYEGO/demos-2
pip install -r requirements-api.txt
./scripts/run_api.sh
```

Set `VITE_EVERSTORM_RAG_API_URL=http://127.0.0.1:8080` in `COMPANYSITE/.env` only for local API testing. The production blog uses the HF embed.

Fly.io deploy (`fly.toml`, `Dockerfile`) is optional and not required for moonboots.tech.

---

## Quick reference

| Item | Value |
|------|--------|
| Space name | `everstorm-rag` |
| HF page | `https://huggingface.co/spaces/moonbootspleb/everstorm-rag` |
| Embed URL | `https://moonbootspleb-everstorm-rag.hf.space` |
| Netlify env | `VITE_EVERSTORM_RAG_SPACE_URL` |
| Blog post | `/blog/building-a-support-rag-chatbot` |
