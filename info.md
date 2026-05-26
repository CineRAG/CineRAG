# CineRAG Nuvolos Runbook — GPU Backend App + Separate Frontend App

This runbook assumes the project runs across two Nuvolos apps:

Backend GPU app:

```text
4 vCPU
28 GB Memory
Tesla T4 GPU
16 GB GPU Memory
```

Frontend app:

```text
Node/npm available
Used only for React/Vite frontend
```

Backend GPU app runs:

- Ollama
- FastAPI backend
- backend smoke test

Frontend app runs:

- React frontend

## 0. Sync Code And Dependencies Before Any Restart

**Run this section every time before restarting Ollama or the backend, even when "nothing changed".** The most common deploy failure in this project has been Nuvolos serving stale code from a previous checkout, or a Chroma index built with an embedding model that no longer matches the running code. Skipping this section is what produced the recurring "same `Why this movie?` text on every card" bug. This step closes that gap.

Open a terminal in the Backend GPU app.

### 0.1 Pull latest code from `main`

```bash
cd /files/CineRAG
git fetch origin
git pull origin main
```

If `git pull` reports merge conflicts, stop. Resolve them on a developer machine, push to `main`, then re-run `git pull` here. Do not attempt conflict resolution on Nuvolos.

### 0.2 Refresh Python dependencies (idempotent)

```bash
cd /files/CineRAG/backend
conda activate cinerag_backend
pip install -r requirements.txt
```

`pip install -r` is a no-op when nothing has changed, so running it on every restart is safe and cheap.

### 0.3 Verify Chroma embedding dimension matches the current code

The retriever embedding model has changed in the past (e.g. `all-MiniLM-L6-v2` 384-dim → `BAAI/bge-base-en-v1.5` 768-dim). If the on-disk Chroma index was built with a different model than the code expects, queries fail with a dimension mismatch — or, worse, return silently meaningless results.

```bash
python -c 'import chromadb; col=chromadb.PersistentClient(path="/files/CineRAG/data/chroma_db").get_collection("movies"); print("Chroma dim:", len(col.peek(1)["embeddings"][0]), " docs:", col.count())'
```

(Avoid `<<EOF` heredocs in this runbook — the Nuvolos web terminal can mis-handle them on multi-line paste and leave the shell stuck at the `>` continuation prompt. Always use `python -c '...'` single-line form here.)

Expected, with the current code (`BAAI/bge-base-en-v1.5`): `Chroma dim: 768`.

If you see `384` (old MiniLM index) — or any dimension that does not match `EMBEDDING_MODEL` in `backend/rag/retriever.py` — re-index before restarting:

```bash
python /files/CineRAG/scripts/index_movies.py
```

Re-indexing the 42k-movie corpus on the Tesla T4 takes roughly 5–15 minutes.

### 0.4 Pre-cache the cross-encoder reranker (first deploy only on this app)

`backend/chat/service.py` instantiates `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` inside `ChatService.__init__`. On a freshly provisioned Nuvolos app the first instantiation downloads ~80 MB from HuggingFace, which can stall uvicorn startup if the network is slow. Pre-warm the cache:

```bash
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); print('cross-encoder cached')"
```

The retriever's BGE model (`BAAI/bge-base-en-v1.5`, ~440 MB) is downloaded on first use the same way; pre-warm it too if the app is freshly provisioned:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5'); print('bge cached')"
```

These two pre-caches are only needed once per Nuvolos app — subsequent restarts reuse the cached weights under `~/.cache/huggingface`.

---

## 1. Start Ollama In Backend GPU App

Open Terminal 1 in the Backend GPU app.

```bash
cd /files

export PATH="/space_mounts/pars/ollama/app/bin:$PATH"
export OLLAMA_MODELS="/space_mounts/pars/ollama/models"
export OLLAMA_HOST=0.0.0.0:11434

ln -sfn /space_mounts/pars/ollama/state ~/.ollama

ollama serve
```

Keep this terminal open.

In another Backend GPU app terminal, verify Ollama:

```bash
curl http://127.0.0.1:11434/api/tags
nvidia-smi
```

Expected:

- `curl` returns a JSON model list. The production backend calls `gpt-oss:120b-cloud` (an Ollama Cloud model). Cloud models may not appear in `/api/tags` — that is fine, as long as Ollama is authenticated against the shared state at `/space_mounts/pars/ollama/state` (Step 1 sets up the symlink that points `~/.ollama` there)
- `nvidia-smi` shows Tesla T4
- during chat generation, `nvidia-smi` shows Ollama GPU memory/process activity

If `ollama: command not found`, run:

```bash
export PATH="/space_mounts/pars/ollama/app/bin:$PATH"
which ollama
```

## 2. Start Backend API In Backend GPU App

Open Terminal 2 in the Backend GPU app.

```bash
cd /files/CineRAG/backend
conda activate cinerag_backend

export OLLAMA_BASE_URL=http://127.0.0.1:11434
CHROMA_DB_PATH=/files/CineRAG/data/chroma_db uvicorn main:app --host 0.0.0.0 --port 8000
```

Wait for:

```text
Application startup complete.
```

Health check from another Backend GPU app terminal:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected:

```text
"status":"ok"
```

Expected paths:

```text
"chroma_db_path":"/files/CineRAG/data/chroma_db"
"bm25_index_path":"/space_mounts/pars/data/bm25_index.pkl"
```

## 3. Run Backend Smoke Test In Backend GPU App

Open Terminal 3 in the Backend GPU app.

```bash
cd /files/CineRAG/backend
conda activate cinerag_backend

BASE_URL=http://127.0.0.1:8000 PROJECT_ROOT=/files/CineRAG bash backend_smoke_test.sh
```

Expected:

- health/docs pass
- Ollama API reachable on `localhost:11434`
- auth pass
- movie search/detail pass
- watched CRUD pass
- first `/api/chat` returns HTTP 200
- second `/api/chat` with same `session_id` returns HTTP 200
- DB conversation history persists at least 4 messages

Known possible issue:

- If `/api/chat` returns HTTP 200 but `recommendations` is empty, backend/Ollama wiring works. That is a generation-grounding issue in the LLM layer, not a deployment issue.

## 4. Watch Ollama/GPU Activity In Backend GPU App

While smoke test or frontend chat is running:

```bash
nvidia-smi
```

Also check Ollama reachability:

```bash
curl http://127.0.0.1:11434/api/tags
```

If using foreground `ollama serve`, logs are printed in Terminal 1.

If you prefer background Ollama instead:

```bash
cd /files

export PATH="/space_mounts/pars/ollama/app/bin:$PATH"
export OLLAMA_MODELS="/space_mounts/pars/ollama/models"
export OLLAMA_HOST=0.0.0.0:11434
ln -sfn /space_mounts/pars/ollama/state ~/.ollama

nohup ollama serve > /space_mounts/pars/ollama/logs/serve.log 2>&1 &
sleep 5

curl http://127.0.0.1:11434/api/tags
tail -n 80 /space_mounts/pars/ollama/logs/serve.log
```

## 5. Get Backend GPU App IP

In the Backend GPU app:

```bash
hostname -i
```

Copy the IP. Example:

```text
10.103.12.121
```

From the Frontend app, verify that the backend is reachable:

```bash
curl http://<BACKEND_GPU_APP_IP>:8000/api/health
```

Example:

```bash
curl http://10.103.12.121:8000/api/health
```

Expected:

```text
"status":"ok"
```

If this fails, the Frontend app cannot reach the Backend app over the Nuvolos network. Re-check the Backend app IP and confirm uvicorn was started with:

```bash
--host 0.0.0.0 --port 8000
```

## 6. Start Frontend In Frontend App

Open a terminal in the Frontend app.

Check Node/npm:

```bash
which node
which npm
node -v
npm -v
```

Then run:

```bash
cd /files/CineRAG/frontend
npm install

VITE_API_BASE_URL=http://<BACKEND_GPU_APP_IP>:8000 npm run dev -- --host 0.0.0.0
```

Example:

```bash
VITE_API_BASE_URL=http://10.103.12.121:8000 npm run dev -- --host 0.0.0.0
```

Use the Nuvolos-exposed frontend URL to open the app in the browser.

## 7. Final Manual Demo Flow

After all services are running:

1. Open frontend.
2. Sign up or log in.
3. Search for a movie.
4. Add watched movie with rating.
5. Open chat.
6. Ask a recommendation query.
7. Confirm the response completes.
8. Confirm recommendation cards appear.
9. Mark one recommendation as watched.
10. Ask a second query in the same chat session.
11. Confirm the second response completes.
12. Confirm watched/profile state updates correctly.

## 8. Common Problems

If Ollama is not found in Backend GPU app:

```bash
export PATH="/space_mounts/pars/ollama/app/bin:$PATH"
which ollama
```

If Ollama is not reachable in Backend GPU app:

```bash
curl http://127.0.0.1:11434/api/tags
```

If backend chat returns `503`, confirm backend was started with:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Then restart backend.

If Chroma startup hangs or retrieval fails, confirm backend was started with:

```bash
CHROMA_DB_PATH=/files/CineRAG/data/chroma_db
```

If GPU is not being used:

```bash
nvidia-smi
tail -n 80 /space_mounts/pars/ollama/logs/serve.log
```

If `nvidia-smi` does not show Tesla T4, the Backend app probably does not have GPU resources attached.

If `npm: command not found` in Backend GPU app, do not install frontend tooling there during demo setup. Use the separate Frontend app for React/Vite.

If Frontend app cannot reach Backend app:

```bash
curl http://<BACKEND_GPU_APP_IP>:8000/api/health
```

If this fails:

- re-run `hostname -i` in Backend GPU app
- update `VITE_API_BASE_URL`
- confirm backend uses `--host 0.0.0.0`
- confirm both apps are on the same Nuvolos instance network

If frontend opens but API calls fail, restart frontend with:

```bash
VITE_API_BASE_URL=http://<BACKEND_GPU_APP_IP>:8000 npm run dev -- --host 0.0.0.0
```

If backend `/api/chat` returns an error mentioning `gpt-oss:120b-cloud` (model not found, unauthorized, etc.):

- Confirm `~/.ollama` symlink points to `/space_mounts/pars/ollama/state` (Ollama Cloud auth tokens live there). If the symlink was lost, re-create it per Step 1.
- Sanity-check the model with a direct call:

  ```bash
  curl http://127.0.0.1:11434/api/chat -d '{"model":"gpt-oss:120b-cloud","messages":[{"role":"user","content":"ping"}],"stream":false}'
  ```

  If this succeeds, the issue is in the backend wiring, not in Ollama auth. If it fails, fix Ollama auth first.

If uvicorn startup stalls for more than a minute on a freshly provisioned app, it is most likely downloading the BGE retriever model (`BAAI/bge-base-en-v1.5`, ~440 MB) or the cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80 MB) from HuggingFace. Run Step 0.4 to pre-cache both before the next restart.

If `/api/chat` returns 200 but `recommendations` are empty or look unrelated to the query, the most common cause is the Chroma index having been built with a different embedding model than the running code expects. Re-run the check in Step 0.3.