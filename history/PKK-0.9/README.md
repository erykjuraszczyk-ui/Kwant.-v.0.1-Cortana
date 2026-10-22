# PKK 0.9 — Cortana Dialog Layer

PKK 0.9 adds a Polish-language conversation endpoint and a lightweight web chat UI on top of the PKK 0.8 decision, fusion and memory layers.

## Contents
- `GET /cortana` — browser chat panel.
- `POST /cortana/chat` — sends a message, retrieves a bounded PKK context snapshot, and returns a response.
- `GET /cortana/status` — configured provider and privacy warning (never returns the API key).
- `GET /cortana/conversations` — lists local conversation metadata.
- `GET /cortana/conversations/{id}` — reads a conversation transcript.
- `DELETE /cortana/conversations/{id}` — deletes one transcript.
- Local SQLite stores chat history. The browser does not store API keys or transcripts in localStorage.
- Provider modes: `rules` (default, local only), `ollama`, `openai_compatible`.
- If a configured provider fails, PKK falls back to local rules and reports the fallback.

**Important:** PKK 0.9 is still classical software; it does not execute quantum computations. The default rules mode requires no API key and makes no outbound model requests. When Ollama or an OpenAI-compatible provider is configured, user messages and a minimized PKK context snapshot may be sent to that endpoint.

## Requirements
- Python 3.11+
- Packages from `requirements.txt` (includes `httpx`)

## Start on Windows 10/11
```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
or run `scripts\\run-windows.ps1`.

## Start on Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
or run `bash scripts/run-linux.sh`.

Open the UI at http://127.0.0.1:8000/cortana and API docs at http://127.0.0.1:8000/docs.

## Configure a local Ollama model
1. Install/start Ollama separately and download a model appropriate for your machine.
2. Set these environment variables before starting PKK:
```powershell
$env:PKK_CHAT_PROVIDER="ollama"
$env:PKK_CHAT_BASE_URL="http://127.0.0.1:11434"
$env:PKK_CHAT_MODEL="qwen2.5:3b"
.\scriptsun-windows.ps1
```
Use the actual model name available in your local Ollama installation. PKK does not install or download the LLM model automatically.

## Configure an OpenAI-compatible provider
Set `PKK_CHAT_PROVIDER=openai_compatible`, `PKK_CHAT_BASE_URL` to the provider's API root (for example an endpoint ending in `/v1`), `PKK_CHAT_MODEL` to the supported model identifier, and `PKK_CHAT_API_KEY` to the key. Store secrets as environment variables or in a private `.env` file that is not committed to Git. Never put API keys in frontend code or public repositories.

For Docker Compose, copy `.env.example` to `.env`, change the provider settings locally, and run `docker compose up --build`. Do not upload `.env` to GitHub. For a local OpenAI-compatible server, choose its documented base URL. If running Ollama inside a container, `127.0.0.1` refers to the PKK container itself; configure a reachable service hostname instead.

## First chat
Send a POST to `/cortana/chat`:
```json
{
  "message": "Jaki jest aktualny stan modelu świata?",
  "conversation_id": null
}
```
Use the returned `conversation_id` to continue the conversation. The chat layer passes only a limited, summarized slice of PKK metadata; it never sends raw frames or audio.

## Privacy and decision limits
- In `rules` mode, chat is local and deterministic; responses are intentionally limited.
- Other providers may receive the user message and selected context metadata.
- Conversation text is saved in local SQLite until explicitly deleted or the database is removed.
- The context summary may include event text. Avoid storing personal or confidential data unnecessarily.
- PKK 0.9 only returns responses/recommendations. It does not run shell commands, control devices, activate sensors, or perform other external actions.
- Treat any model response as fallible. The chat layer distinguishes recorded evidence from interpretation and uncertainty, but a language model can still make mistakes.
