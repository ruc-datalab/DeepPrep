
# Action Sandbox

This folder contains the **Action Sandbox** service for DeepPrep.
It exposes the tabular data preparation environment (tasks, trials, operators, execution, evaluation, rewards) as a **FastAPI** HTTP server, so an agent/UI can interact with it through simple API calls.

## What is the Action Sandbox?

Conceptually, the sandbox is a stateful backend that:

- Loads a task (input tables + target table description / ground truth when available)
- Creates an isolated **Trial** (a working session)
- Lets clients **execute** data-prep operators step-by-step
- Supports **simulation** on a copy of the state (no mutation)
- Provides **evaluation** against ground-truth target tables
- Produces **reward signals** (heuristic / partial / optional LLM-as-judge)

Internally, active trials are stored in **Redis** (pickled objects) via `RedisTrialManager`.

## Requirements

- Python environment with project dependencies installed (see repository-level `requirements.txt` / `environment.yml`)
- Redis server

On Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y redis-server
redis-server --daemonize yes
```

## Start the server

Run from the repository root (the folder that contains `app/`):

```bash
nohup python -m uvicorn app.server:app \
	--host 0.0.0.0 \
	--port 6138 \
	--log-level debug \
	--access-log \
	--workers 8 \
	> ./server.log 2>&1 < /dev/null &
```

Notes:

- Make sure `redis-server` is running before starting the API.
- Static files (if present) are served from `app/static`.

## Features

- **Task browsing**: list available splits and task IDs, fetch task details, fetch ground truth
- **Operator catalog**: list available operators, get operator descriptions, validate operator strings
- **Trial lifecycle**:
	- create a trial from (tables + description) or from a benchmark `task_id`
	- copy a trial (fork)
	- inspect current state (history ops, task metadata)
	- delete/clear trials
- **Execution modes**:
	- execute one operator and return the resulting table snapshot
	- add an operator as a persistent step (updates trial state)
	- simulate a sequence of operators on a copy
	- simulate + evaluate on a copy
- **Evaluation**: compare generated tables vs target to determine success
- **Reward**: return a combined reward and a breakdown (heuristic / partial / LLM-as-judge)

Important behavior:

- `POST /trials/{trial_id}/execute` executes an operator **without** appending it to the trial history.
- Use `POST /trials/{trial_id}/step` (or `POST /trials/{trial_id}/explore_step`) when you want execution **and** the operation to be recorded into the trial trajectory.

## API overview

Base URL example: `http://0.0.0.0:6138`

### Tasks

- `GET /tasks`
	- Returns available splits and task IDs.
- `GET /tasks/{split}/{task_id}`
	- Returns task description, schema description, and serialized input tables.
- `GET /tasks/{split}/{task_id}/ground_truth`
	- Returns ground truth operator chain (when available).
- `POST /tasks/record_completion`
	- Appends a JSONL record to `app/completion_records/task_completions.jsonl`.

### Operators

- `GET /operators`
	- Returns available operator classes.
- `GET /operators/descriptions`
	- Returns long-form descriptions per operator.
- `POST /operators/validate`
	- Validates that each operator string can be parsed.

### Trials

- `POST /trials`
	- Create a trial from explicit tables and a target description.
- `POST /trials/create_with_task_id`
	- Create a trial from a benchmark task id.
- `GET /trials`
	- List active trials.
- `GET /trials/{trial_id}`
	- Fetch trial state + history.
- `POST /trials/{trial_id}/copy`
	- Fork a trial.
- `GET /trials/{trial_id}/tables`
	- Fetch all current tables as compact, serialized text.
- `DELETE /trials/{trial_id}` / `DELETE /trials/{trial_id}/clear`
	- Remove a trial.

### Execution / Simulation / Evaluation

- `POST /trials/{trial_id}/execute`
	- Execute a single operator (no history append).
- `POST /trials/{trial_id}/explore_step`
	- Execute a single operator and append to history (UI-oriented).
- `POST /trials/{trial_id}/step`
	- Execute a single operator and append to history (trajectory-oriented).
- `POST /trials/{trial_id}/simulate`
	- Execute a sequence on a copy of the trial; returns (op, obs) history.
- `POST /trials/{trial_id}/simulate_evaluate`
	- Simulate on a copy and evaluate success.
- `POST /trials/{trial_id}/evaluate`
	- Evaluate the current (mutable) trial.

### Reward

- `POST /trials/reward`
	- Input: `trial_id`, `input_string` (a trajectory string containing `<solution>...</solution>`), and `version` (e.g. `v0-v1`, `v0-v1-v2`).
	- Output: total `reward` plus a `detailed_rewards` breakdown.

## Minimal client example

The repository provides a small reference client in `app/client.py`.

```python
from app.client import ApiClient

client = ApiClient(base_url="http://0.0.0.0:6138")

# 1) Create a trial from a benchmark task
trial_id, _ = client.create_trial_with_task_id(task_id="spider_0ad66ebb", split="train")

# 2) Execute and record a step
client.add_step(trial_id, op='Select(table_name="table_1", columns=["col_a"])', mode='rule')

# 3) Evaluate
matched, msg = client.evaluate_trial(trial_id)
print(matched, msg)

client.close()
```

You can also override the server base URL with:

```bash
export DS_AGENT_API_BASE_URL="http://0.0.0.0:6138"
```

## Troubleshooting

- **Redis connection errors**: ensure `redis-server` is running on `localhost:6379`.
- **Large tables**: table outputs are truncated using `gen_tbl_cut_line` / `gen_tbl_cut_col` from the project config.
- **No generated tables**: evaluation and simulate_evaluate require the trial to have generated tables; run steps that produce outputs first.

