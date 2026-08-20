from __future__ import annotations

import os
import uuid
import shutil
import json
from typing import List, Optional, Dict, Any

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src.tools.helper import Config
from src.physicalop import auto_parse_op
from src.module.executor import Executor
from src.module.evaluator import Evaluator
from src.data.trial import Trial

from chatapp.state import InMemoryStore, TrialEventHub, df_preview, load_tables_from_paths, make_trial_from_uploaded_tables
from chatapp.agent_runner import start_runner_in_background

def _chatapp_configs():
    import importlib

    return importlib.import_module("chatapp.configs")


APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
UPLOAD_BASE_DIR = os.path.join(APP_DIR, "uploads")

os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)

# Ensure the tree-based agentic reasoning agent's ApiClient talks to this server by default.
os.environ.setdefault("DS_AGENT_API_BASE_URL", "http://127.0.0.1:8000")

app = FastAPI(title="AutoPrep2 ChatApp")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

store = InMemoryStore()
hub = TrialEventHub()


def _get_cfg() -> Config:
    """Return the active config for chatapp.

    This respects `_config/current_config.yaml` so tests (and users) can switch
    configs by calling `Config.set_current_config(name)`.
    """
    # IMPORTANT: Config.load_current_config() instantiates Config(name=...),
    # which also writes current_config.yaml. That's OK for this chatapp.
    try:
        return Config.load_current_config()
    except Exception:
        # Fallback to a known default if current_config.yaml is missing/bad.
        return Config(_chatapp_configs().DEFAULT_CONFIG_NAME)


@app.get("/ui/configs")
def ui_configs():
    """List available LLM choices and report current selection."""
    m = _chatapp_configs()
    try:
        cfg = Config.load_current_config()
        active_name = cfg.name
        max_turn = cfg.get("max_explore_turn")
    except Exception:
        active_name = m.DEFAULT_CONFIG_NAME
        max_turn = None
    return {
        "options": m.list_llm_options(),
        "activeConfigName": active_name,
        "activeLabel": m.label_for_config_name(active_name),
        "maxExploreTurn": max_turn,
    }


@app.post("/ui/config")
def ui_set_config(payload: dict):
    """Set current config (switches LLM backbone)."""
    m = _chatapp_configs()
    config_name = m.resolve_config_name(
        label=payload.get("label"),
        config_name=payload.get("configName"),
    )
    if not config_name:
        return JSONResponse(
            {
                "ok": False,
                "error": "Unknown config. Use one of /ui/configs options.",
                "options": m.list_llm_options(),
            },
            status_code=400,
        )

    try:
        cfg = Config(config_name)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    return {
        "ok": True,
        "activeConfigName": cfg.name,
        "activeLabel": m.label_for_config_name(cfg.name),
        "maxExploreTurn": cfg.get("max_explore_turn"),
    }


def _format_target_description(high_level: str, schema_json: str) -> str:
    # Keep it simple and close to Trial.generate_schema_description output style.
    lines: List[str] = []
    high_level = (high_level or "").strip()
    schema_json = (schema_json or "").strip()

    if high_level:
        lines.append(f"We transform the input tables to complete the task: {high_level}")
    else:
        lines.append("We transform the input tables to complete the task.")

    lines.append("The column schema of the target table is as follows:")
    if schema_json:
        lines.append(schema_json)
    else:
        lines.append("(No schema details provided.)")

    return "\n".join(lines)


def _build_schema_payload(high_level: str, schema_json: str) -> dict:
    """Build a DataPool-compatible schema payload.

    `Trial.generate_schema_description` expects:
      {
        "Task Description": str,
        "Column Schema": {
           col: {"description": str, "requirements": [str, ...]?}, ...
        }
      }
    """
    high_level = (high_level or "").strip() or "(no high-level task provided)"
    schema_json = (schema_json or "").strip()

    if not schema_json:
        return {"Task Description": high_level, "Column Schema": {}}

    try:
        obj = json.loads(schema_json)
        # If user already provides the exact structure, accept it.
        if isinstance(obj, dict) and "Task Description" in obj and "Column Schema" in obj:
            return obj
        # If user provides {col: {description, requirements}}, wrap it.
        if isinstance(obj, dict):
            col_schema = {}
            for col, meta in obj.items():
                if isinstance(meta, dict):
                    desc = str(meta.get("description", "")).strip() or str(meta)
                    req = meta.get("requirements", [])
                    if isinstance(req, str):
                        req = [req]
                    if not isinstance(req, list):
                        req = [str(req)]
                    col_schema[str(col)] = {"description": desc, "requirements": [str(x) for x in req]}
                else:
                    col_schema[str(col)] = {"description": str(meta), "requirements": []}
            return {"Task Description": high_level, "Column Schema": col_schema}
    except Exception:
        pass

    # Fallback: keep raw schema text as a single pseudo-column so it shows up in prompt.
    return {
        "Task Description": high_level,
        "Column Schema": {
            "TARGET_SCHEMA": {
                "description": schema_json,
                "requirements": [],
            }
        },
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"ok": True}


# ---------- UI endpoints ----------

@app.post("/ui/upload")
async def ui_upload(files: List[UploadFile] = File(...)):
    sess = store.create_upload_session(UPLOAD_BASE_DIR)

    saved_paths: List[str] = []
    tables: Dict[str, pd.DataFrame] = {}

    for f in files:
        filename = os.path.basename(f.filename)
        path = os.path.join(sess.upload_dir, filename)
        with open(path, "wb") as out:
            out.write(await f.read())
        saved_paths.append(path)

    # Load into pandas and normalize names to table_1/table_2
    tables = load_tables_from_paths(saved_paths)
    sess.file_paths = saved_paths
    sess.tables = tables

    previews = []
    for name, df in tables.items():
        previews.append({"name": name, **df_preview(df)})

    return {"uploadId": sess.session_id, "tables": previews}


@app.post("/ui/target_description")
async def ui_target_description(
    uploadId: str = Form(...),
    highLevel: str = Form(""),
    schemaJson: str = Form(""),
):
    sess = store.get_upload_session(uploadId)
    desc = _format_target_description(highLevel, schemaJson)
    schema_payload = _build_schema_payload(highLevel, schemaJson)
    # store it on the upload session object dynamically
    setattr(sess, "target_description", desc)
    setattr(sess, "target_schema_payload", schema_payload)
    return {"targetDescription": desc}


@app.post("/ui/run")
async def ui_run(
    uploadId: str = Form(...),
    maxExploreTurn: Optional[str] = Form(None),
):
    sess = store.get_upload_session(uploadId)
    target_description: str = getattr(sess, "target_description", "None")
    schema_payload: dict | None = getattr(sess, "target_schema_payload", None)

    trial_id = str(uuid.uuid4())
    state = make_trial_from_uploaded_tables(
        trial_id=trial_id,
        tables=sess.tables,
        target_description=target_description,
        schema_payload=schema_payload,
    )
    store.put_trial(state)

    cfg = _get_cfg()
    if maxExploreTurn is not None and str(maxExploreTurn).strip() != "":
        try:
            cfg.set("max_explore_turn", int(str(maxExploreTurn).strip()), save=False)
        except Exception:
            pass
    start_runner_in_background(cfg=cfg, store=store, hub=hub, trial_id=trial_id)

    return {"trialId": trial_id}


@app.get("/ui/trials/{trial_id}/result")
def ui_result(trial_id: str):
    st = store.get_trial(trial_id)
    if st.result_df is None:
        return JSONResponse({"ready": False})
    return {
        "ready": True,
        "tableName": st.result_table_name,
        "preview": df_preview(st.result_df),
    }


@app.get("/ui/trials/{trial_id}/download")
def ui_download(trial_id: str):
    st = store.get_trial(trial_id)
    if st.result_df is None:
        return JSONResponse({"error": "Result not ready"}, status_code=400)
    csv_bytes = st.result_df.to_csv(index=False).encode("utf-8")
    filename = f"{trial_id}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.websocket("/ws/{trial_id}")
async def ws(trial_id: str, websocket: WebSocket):
    await websocket.accept()
    q = hub.subscribe(trial_id)
    try:
        while True:
            event = await __import__("asyncio").to_thread(q.get)
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(trial_id, q)


# ---------- ApiClient-compatible endpoints (minimal subset) ----------

@app.post("/trials")
def create_trial(payload: dict):
    input_paths: List[str] = payload.get("input_table_paths") or []
    target_description: str = payload.get("target_description") or "None"

    trial_id = str(uuid.uuid4())

    # If file paths exist, load from them. Otherwise, fall back to dataset-style Trial.load.
    any_exists = any(os.path.exists(p) for p in input_paths)
    if any_exists:
        tables = load_tables_from_paths(input_paths)
        state = make_trial_from_uploaded_tables(trial_id=trial_id, tables=tables, target_description=target_description)
        store.put_trial(state)
        return {"trial_id": trial_id, "message": "Trial created."}

    # Dataset-style (best-effort): task_id + split
    task_id = payload.get("task_id")
    split = payload.get("split", "test")
    if task_id:
        trial = Trial.load_trial(task_id=task_id, split=split, exp_id=trial_id)
        trial.task.tgt_tbl_description = target_description
        state = make_trial_from_uploaded_tables(trial_id=trial_id, tables=trial.tables, target_description=target_description)
        state.trial.tgt_tbl = trial.tgt_tbl
        store.put_trial(state)
        return {"trial_id": trial_id, "message": "Trial created."}

    return JSONResponse({"error": "Unable to create trial"}, status_code=400)


@app.post("/trials/create_with_task_id")
def create_trial_with_task_id(payload: dict):
    task_id = payload["task_id"]
    split = payload.get("split", "test")
    trial_id = str(uuid.uuid4())
    trial = Trial.load_trial(task_id=task_id, split=split, exp_id=trial_id)
    state = make_trial_from_uploaded_tables(trial_id=trial_id, tables=trial.tables, target_description=trial.task.tgt_tbl_description or "None")
    state.trial.tgt_tbl = trial.tgt_tbl
    store.put_trial(state)
    return {"trial_id": trial_id, "message": "Trial created."}


@app.get("/trials")
def get_all_trials():
    # Lightweight listing
    return [{"trial_id": tid} for tid in list(store.trials.keys())]


@app.get("/trials/{trial_id}")
def get_trial_state(trial_id: str):
    st = store.get_trial(trial_id)
    return {
        "trial_id": trial_id,
        "task_id": st.task.id,
        "target_description": st.target_description,
        "history_op": st.history_op,
    }


@app.get("/trials/{trial_id}/tables")
def get_trial_tables(trial_id: str):
    st = store.get_trial(trial_id)
    out = {}
    for name, df in st.trial.tables.items():
        out[name] = df.head(20).to_csv(index=False)
    return out


@app.delete("/trials/{trial_id}")
def delete_trial(trial_id: str):
    store.delete_trial(trial_id)
    return {"message": "Trial deleted."}


@app.post("/trials/{trial_id}/copy")
def copy_trial(trial_id: str):
    import copy

    st = store.get_trial(trial_id)
    new_id = str(uuid.uuid4())
    new_state = copy.deepcopy(st)
    new_state.trial_id = new_id
    new_state.trial.exp_id = new_id
    new_state.history_op = list(st.history_op)
    store.put_trial(new_state)
    return {"trial_id": new_id, "task_id": new_state.task.id, "split": new_state.task.split}


@app.delete("/trials/{trial_id}/clear")
def clear_trial(trial_id: str):
    st = store.get_trial(trial_id)
    st.trial.clear_ops()
    st.history_op = []
    return {"message": "Trial cleared."}


@app.post("/trials/{trial_id}/execute")
def execute_operator(trial_id: str, payload: dict):
    import copy

    op_str = payload["op"]
    mode = payload.get("mode", "rule")
    st = store.get_trial(trial_id)
    tmp = copy.deepcopy(st.trial)

    op = auto_parse_op(op_str)
    executor = Executor(cfg=_get_cfg(), debug=False, log_file=f"CHATAPP_{trial_id}")
    out_name, out_df = executor.execute_op(op, tmp, mode=mode)
    obs = executor.step_op(op, tmp, out_name, out_df)
    return {"op": op_str, "obs": obs}


@app.post("/trials/{trial_id}/step")
def add_step(trial_id: str, payload: dict):
    op_str = payload["op"]
    mode = payload.get("mode", "rule")
    st = store.get_trial(trial_id)

    op = auto_parse_op(op_str)
    executor = Executor(cfg=_get_cfg(), debug=False, log_file=f"CHATAPP_{trial_id}")
    out_name, out_df = executor.execute_op(op, st.trial, mode=mode)
    executor.step_op(op, st.trial, out_name, out_df)
    st.history_op.append(op_str)
    return {"message": "Step added successfully."}


@app.post("/trials/{trial_id}/simulate")
def simulate_trial(trial_id: str, payload: dict):
    import copy

    operators: List[str] = payload.get("operators") or []
    mode = payload.get("mode", "rule")
    st = store.get_trial(trial_id)
    tmp = copy.deepcopy(st.trial)

    executor = Executor(cfg=_get_cfg(), debug=False, log_file=f"CHATAPP_{trial_id}")
    history = []
    for i, op_str in enumerate(operators):
        op = auto_parse_op(op_str)
        try:
            out_name, out_df = executor.execute_op(op, tmp, mode=mode)
            obs = executor.step_op(op, tmp, out_name, out_df)
        except Exception as e:
            obs = f'Error raised when executing operator {i+1}: {op_str}. Error: {str(e)}\n Since the error is raised, the following operators will not be executed!'
            out_name = 'Error'
            out_df = None

        history.append(
            {
                "op": op_str,
                "obs": obs,
                "out_table": out_name,
                "out_preview": df_preview(out_df) if out_df is not None else {"columns": [], "rows": [], "shape": [0, 0]},
            }
        )
    return {"history": history}


@app.post("/trials/{trial_id}/evaluate")
def evaluate_trial(trial_id: str, payload: dict):
    st = store.get_trial(trial_id)
    if st.trial.tgt_tbl is None:
        return {"matched": False, "message": "No target table available; evaluation skipped."}
    evaluator = Evaluator(cfg=_get_cfg(), debug=False, log_file=f"CHATAPP_{trial_id}")
    matched, msg = evaluator.evaluate_trial_tables(st.trial)
    return {"matched": bool(matched), "message": msg}


@app.post("/trials/{trial_id}/simulate_evaluate")
def simulate_trial_and_evaluate(trial_id: str, payload: dict):
    # best-effort: simulate then evaluate if possible
    sim = simulate_trial(trial_id, payload)
    ev = evaluate_trial(trial_id, {"trial_id": trial_id})
    return {"matched": ev["matched"], "message": ev["message"], "history": sim["history"]}


@app.post("/operators/validate")
def validate_operators(payload: dict):
    ops: List[str] = payload.get("operators") or []
    invalid = []
    for i, op_str in enumerate(ops):
        try:
            auto_parse_op(op_str)
        except Exception:
            invalid.append(i)
    return {"all_valid": len(invalid) == 0, "invalid_indices": invalid}


@app.post("/trials/reward")
def get_reward(payload: dict):
    """ApiClient compatibility endpoint.

    Best-effort: if a target table exists, return Evaluator similarity reward;
    otherwise return -1.0.
    """
    trial_id = payload.get("trial_id")
    if not trial_id:
        return JSONResponse({"error": "trial_id required"}, status_code=400)

    st = store.get_trial(trial_id)
    if st.trial.tgt_tbl is None:
        return {"reward": -1.0, "detailed_rewards": {"reason": "no_target_table"}}

    evaluator = Evaluator(cfg=_get_cfg(), debug=False, log_file=f"CHATAPP_{trial_id}")
    reward = float(evaluator.calculate_similarity_reward(st.trial))
    return {"reward": reward, "detailed_rewards": {"similarity": reward}}
