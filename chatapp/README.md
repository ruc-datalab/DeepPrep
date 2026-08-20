# ChatApp: ChatGPT-like UI for DeepPrep Action Sandbox

This folder provides an **interactive web UI + backend server** (FastAPI) that looks and feels like a ChatGPT chat window, tailored for **tabular data preparation** with DeepPrep.

It supports:

1) Upload multiple input tables (CSV / PKL / Parquet)
2) Provide a **target table schema description** (guided input: high-level task + column schema)
3) Run **tree-based agentic reasoning** and visualize generated operator chains as an **operator tree**
4) Extract the final solution chain, execute it to produce the target table, show a preview, and allow download

## Architecture (high-level)

- UI is served from [chatapp/static/index.html](static/index.html) by FastAPI.
- Backend server is [chatapp/server.py](server.py).
- Agent runner is [chatapp/agent_runner.py](agent_runner.py):
    - Starts a background thread
    - Calls `TreeBasedAgenticReasoningAgent` turn-by-turn
    - Maintains an **operator tree** (trie-like) via [chatapp/operator_tree.py](operator_tree.py)
    - Pushes events to the UI over WebSocket `/ws/{trial_id}`
- In-memory state is managed by [chatapp/state.py](state.py).

Important: the ChatApp server also exposes a **minimal set of ApiClient-compatible endpoints** (`/trials`, `/simulate`, `/evaluate`, etc.).
This allows `TreeBasedAgenticReasoningAgent` (which internally uses `ApiClient`) to talk to **this same process**.

## Feature details

### 1) Upload tables

- Endpoint: `POST /ui/upload` (multipart form)
- Supported file types:
    - `.csv`
    - `.pkl` / `.pickle` (must contain a DataFrame, or a dict containing a DataFrame)
    - `.parquet`
- Uploaded files are stored under [chatapp/uploads/](uploads/).
- Tables are loaded into pandas and normalized to names: `table_1`, `table_2`, ...

### 2) Target schema description (guided)

- Endpoint: `POST /ui/target_description`
- UI collects two fields:
    - **High-level task description** (free text)
    - **Schema JSON** (structured, see below)

Recommended `schemaJson` format:

```json
{
    "Task Description": "...",
    "Column Schema": {
        "colA": {"description": "...", "requirements": ["distinct", "non-null"]},
        "colB": {"description": "...", "requirements": []}
    }
}
```

You may also provide a simpler mapping:

```json
{
    "colA": {"description": "...", "requirements": ["distinct"]},
    "colB": "some text description"
}
```

The server will normalize it into a `DataPool`-compatible schema payload.

### 3) Tree-based agentic reasoning + operator tree

- Endpoint: `POST /ui/run`
    - Starts a background thread to run `TreeBasedAgenticReasoningAgent`
    - Maintains an operator tree and pushes incremental updates

Operator tree construction rule (string-level matching):

- Root is a fixed `ROOT` node.
- For each newly generated operator chain, we match from root by **normalized operator string equality**.
- On first mismatch, we create a new branch and append all remaining operators on that branch.
- When a `<solution>...</solution>` appears, we add it into the same tree and send a **highlight path** event to the UI.

### 4) Result preview + download

- Result is produced by executing the final solution chain locally (pandas execution via `Executor`).
- Preview endpoint: `GET /ui/trials/{trial_id}/result`
- Download endpoint: `GET /ui/trials/{trial_id}/download` (CSV)

## Quick Start

### 0) Environment

Run from the repository root (the folder that contains `chatapp/` and `src/`).

Minimum dependencies:

- `fastapi`
- `uvicorn`
- `pandas`
- `httpx`
- `python-multipart`

### 1) Load config (select LLM)

ChatApp uses the global config mechanism in [_config/current_config.yaml](../_config/current_config.yaml).

Example (use GPT-5 config):

```bash
python -c "from src.tools.helper import Config; Config.set_current_config('tree_based_agentic_reasoning_gpt5'); cfg=Config.load_current_config(); print(cfg.get('framework'), cfg.get('execute_mode'), cfg.get('llm_name'))"
```

The config YAML file is [_config/_CONFIG_tree_based_agentic_reasoning_gpt5.yaml](../_config/_CONFIG_tree_based_agentic_reasoning_gpt5.yaml).

### 2) Start the server

```bash
export DS_AGENT_API_BASE_URL=http://127.0.0.1:8000
uvicorn chatapp.server:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

### 3) Open the UI

- http://127.0.0.1:8000/

## LLM switching & adding a new LLM

This project switches LLMs **via config YAML** under [_config](../_config/).

### A) Switch LLM (recommended ways)

Option 1: switch via Python (writes `_config/current_config.yaml`):

```bash
python -c "from src.tools.helper import Config; Config.set_current_config('tree_based_agentic_reasoning_claude'); print(Config.load_current_config().get('llm_name'))"
```

Option 2: switch via UI API:

- `GET /ui/configs` lists available options.
- `POST /ui/config` switches the active config.

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/ui/config \
    -H 'Content-Type: application/json' \
    -d '{"configName":"tree_based_agentic_reasoning_gpt5"}'
```

### B) Add a new LLM (OpenAI-compatible)

If your new model can be called through an **OpenAI-compatible** chat-completions API (including local vLLM OpenAI server, many gateways, etc.), you do NOT need to touch `src/`.

Steps:

1) Create a new config YAML under [_config](../_config/).

     Example file name:

     - `_config/_CONFIG_tree_based_agentic_reasoning_myllm.yaml`

     Minimal fields example:

     ```yaml
     agent_max_err_cnt: 5
     execute_mode: rule
     framework: tree_based_agentic_reasoning
     key_file: keys_myllm.txt
     llm_name: my-model-name
     openai_base_url: http://127.0.0.1:8001/v1
     max_explore_op: 50
     max_explore_turn: 5
     name: tree_based_agentic_reasoning_myllm
     ```

     Notes:
     - `openai_base_url` is used to set `OPENAI_BASE_URL` internally.
     - If you are using an Azure-style endpoint, set `api_version` (see existing configs for examples).

2) Create the key file under a new folder at repo root:

     - `./_keys/keys_myllm.txt`

     Put one API key per line. The runtime will rotate keys line-by-line.
     If your endpoint does not require a key, you can put `EMPTY` as the only line.

3) (For Chat UI dropdown) Register this config in [chatapp/configs.py](configs.py):

     Add a new entry into `LLM_CONFIGS`, e.g.:

     ```python
     LLM_CONFIGS["My-LLM"] = "tree_based_agentic_reasoning_myllm"
     ```

     Why: `/ui/config` only accepts config names listed in `LLM_CONFIGS`.

4) Restart the server.

After that, you can select it in the UI (or call `POST /ui/config`).

### C) Add a new LLM (NOT OpenAI-compatible)

If the new LLM does not provide an OpenAI-compatible API, then the calling logic would need a new adapter in `src.tools.helper` / inference layer.
This repo’s ChatApp is intentionally designed to avoid modifying `src/`. In this case, the practical option is:

- Deploy a small gateway that exposes your model as OpenAI-compatible, then follow the steps in **B**.

## Backend endpoints

### UI endpoints

- `GET /` UI page
- `GET /health`
- `GET /ui/configs` list available LLM configs
- `POST /ui/config` switch active LLM config
- `POST /ui/upload` upload tables
- `POST /ui/target_description` submit high-level + schema JSON
- `POST /ui/run` start agent
- `GET /ui/trials/{trial_id}/result` poll for result preview
- `GET /ui/trials/{trial_id}/download` download result CSV
- `WS /ws/{trial_id}` stream events (`chat`, `tree`, `status`, `highlight`, `result`)

### ApiClient-compatible endpoints (minimal subset)

These exist so `TreeBasedAgenticReasoningAgent` can run without a separate Action Sandbox:

- `POST /trials`
- `POST /trials/create_with_task_id`
- `GET /trials`
- `GET /trials/{trial_id}`
- `GET /trials/{trial_id}/tables`
- `DELETE /trials/{trial_id}`
- `POST /trials/{trial_id}/copy`
- `DELETE /trials/{trial_id}/clear`
- `POST /trials/{trial_id}/execute`
- `POST /trials/{trial_id}/step`
- `POST /trials/{trial_id}/simulate`
- `POST /trials/{trial_id}/simulate_evaluate`
- `POST /trials/{trial_id}/evaluate`
- `POST /operators/validate`
- `POST /trials/reward` (best-effort similarity reward)

## Testing (run all)

### 0) Prereqs

- Run from repo root.
- Ensure Python deps are installed.

### 1) Config load sanity

```bash
python -c "from src.tools.helper import Config; Config.set_current_config('tree_based_agentic_reasoning_gpt5'); cfg=Config.load_current_config(); print(cfg.get('framework'), cfg.get('execute_mode'), cfg.get('llm_name'))"
```

### 2) Start server (manual)

```bash
export DS_AGENT_API_BASE_URL=http://127.0.0.1:8000
uvicorn chatapp.server:app --host 0.0.0.0 --port 8000
```

### 3) Open UI

- http://127.0.0.1:8000/

### 4) One-click full smoke (recommended)

This tests:

- Config switching
- Start a temporary uvicorn (random port) and verify `/health`
- ApiClient-compatible endpoints (create/copy/execute/step/simulate/evaluate/reward/validate/delete)
- UI endpoints (`/ui/upload`, `/ui/target_description`, `/ui/run`, `/ui/trials/{id}/result`)

Run:

```bash
bash chatapp/run_all_smoke_tests.sh
```

Or specify config:

```bash
CHATAPP_CONFIG_NAME=tree_based_agentic_reasoning_gpt5 bash chatapp/run_all_smoke_tests.sh
```

Note: `/ui/run` starts the agent in a background thread. If no valid LLM key/endpoint is configured, the agent may fail in the background, but the smoke tests will still validate that the server endpoints are reachable and behave correctly.
