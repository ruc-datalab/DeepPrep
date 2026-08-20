from __future__ import annotations

import io
import os
import uuid
import queue
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import pandas as pd

from src.data.task import Task
from src.data.trial import Trial
from src.tools.helper import Config
from src.tools.utils.funcs import get_benchmark_from_task_id


def _safe_read_table(path: str) -> pd.DataFrame:
    lower = path.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(path, na_values=["<NA>", "NA", "nan", "NaN", "N/A", "n/a", "null", "None", "none"])
    if lower.endswith(".pkl") or lower.endswith(".pickle"):
        obj = pd.read_pickle(path)
        # common cases
        if isinstance(obj, pd.DataFrame):
            return obj
        if isinstance(obj, dict):
            # pick the first dataframe-like
            for v in obj.values():
                if isinstance(v, pd.DataFrame):
                    return v
        raise ValueError(f"Unsupported pickle content type: {type(obj)}")
    if lower.endswith(".parquet"):
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {os.path.basename(path)}")


def df_preview(df: pd.DataFrame, max_rows: int = 20, max_cols: int = 20) -> dict:
    df2 = df.copy()
    df2.columns = df2.columns.astype(str)
    cols = list(df2.columns[:max_cols])
    df2 = df2[cols]
    rows = df2.head(max_rows).fillna("").astype(str).values.tolist()
    return {
        "columns": cols,
        "rows": rows,
        "shape": [int(df.shape[0]), int(df.shape[1])],
    }


class TrialEventHub:
    """Simple thread-safe pub/sub using queue.Queue.

    Each websocket subscribes and blocks on its own queue.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subs: Dict[str, List[queue.Queue]] = {}

    def subscribe(self, trial_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.setdefault(trial_id, []).append(q)
        return q

    def unsubscribe(self, trial_id: str, q: queue.Queue) -> None:
        with self._lock:
            if trial_id not in self._subs:
                return
            self._subs[trial_id] = [x for x in self._subs[trial_id] if x is not q]
            if not self._subs[trial_id]:
                self._subs.pop(trial_id, None)

    def publish(self, trial_id: str, event: dict) -> None:
        with self._lock:
            subs = list(self._subs.get(trial_id, []))
        for q in subs:
            q.put(event)


@dataclass
class UploadSession:
    session_id: str
    upload_dir: str
    file_paths: List[str] = field(default_factory=list)
    tables: Dict[str, pd.DataFrame] = field(default_factory=dict)


@dataclass
class TrialState:
    trial_id: str
    trial: Trial
    task: Task
    target_description: str
    history_op: List[str] = field(default_factory=list)
    result_df: Optional[pd.DataFrame] = None
    result_table_name: Optional[str] = None


class InMemoryStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.uploads: Dict[str, UploadSession] = {}
        self.trials: Dict[str, TrialState] = {}

    def create_upload_session(self, base_dir: str) -> UploadSession:
        session_id = str(uuid.uuid4())
        upload_dir = os.path.join(base_dir, session_id)
        os.makedirs(upload_dir, exist_ok=True)
        sess = UploadSession(session_id=session_id, upload_dir=upload_dir)
        with self._lock:
            self.uploads[session_id] = sess
        return sess

    def get_upload_session(self, session_id: str) -> UploadSession:
        with self._lock:
            return self.uploads[session_id]

    def put_trial(self, state: TrialState) -> None:
        with self._lock:
            self.trials[state.trial_id] = state

    def get_trial(self, trial_id: str) -> TrialState:
        with self._lock:
            return self.trials[trial_id]

    def delete_trial(self, trial_id: str) -> None:
        with self._lock:
            self.trials.pop(trial_id, None)


def make_trial_from_uploaded_tables(
    *,
    trial_id: str,
    tables: Dict[str, pd.DataFrame],
    target_description: str,
    schema_payload: Optional[dict] = None,
) -> TrialState:
    # IMPORTANT: `Trial.generate_schema_description` calls `get_benchmark_from_task_id(task.id)`.
    # That helper throws if task_id contains '_' but is not spider_/bird_.
    # So we must avoid '_' in user-created task ids.
    safe_task_id = f"user{trial_id}"  # no underscore

    task = Task(
        id=safe_task_id,
        inp_tbl_names=list(tables.keys()),
        tgt_tbl_name=None,
        tgt_tbl_description=target_description,
        split="user",
    )

    # Inject user-provided schema into DataPool so `Trial.generate_schema_description(task)` works.
    if schema_payload is not None:
        benchmark = get_benchmark_from_task_id(task.id)
        try:
            from src.data.trial import DataPool

            if benchmark not in DataPool.tbl_schema_description:
                DataPool.tbl_schema_description[benchmark] = {}
            if task.split not in DataPool.tbl_schema_description[benchmark]:
                DataPool.tbl_schema_description[benchmark][task.split] = {}
            DataPool.tbl_schema_description[benchmark][task.split][task.id] = schema_payload
        except Exception:
            # Best-effort: if injection fails, the reasoning agent will fall back to 'None'.
            pass
    trial = Trial(exp_id=trial_id, task=task)
    trial.tables = {k: v.copy() for k, v in tables.items()}
    trial.tgt_tbl = None
    trial.generated_tbls = {}
    trial.recording = {}
    return TrialState(trial_id=trial_id, trial=trial, task=task, target_description=target_description)


def load_tables_from_paths(paths: List[str]) -> Dict[str, pd.DataFrame]:
    tables: Dict[str, pd.DataFrame] = {}
    for i, path in enumerate(paths):
        df = _safe_read_table(path)
        tables[f"table_{i+1}"] = df
    return tables
