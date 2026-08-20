from __future__ import annotations

import os
import sys
import time
import json
import socket
import tempfile
import subprocess
from pathlib import Path

import httpx
import pandas as pd

from src.tools.helper import Config
from app.client import ApiClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_http_ok(url: str, timeout_s: float = 20.0) -> None:
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < timeout_s:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"Server not ready: {url} (last_err={last_err})")


def _run(cmd: list[str], *, env: dict[str, str], cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _make_sample_csv(path: Path) -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "value": ["a", "b", "c"],
        }
    )
    df.to_csv(path, index=False)


def test_config_load(config_name: str) -> None:
    _print_section("1) Config load")
    Config.set_current_config(config_name)
    cfg = Config.load_current_config()

    print("current_config:", config_name)
    print("cfg.name:", cfg.get("name"))
    print("cfg.framework:", cfg.get("framework"))
    print("cfg.execute_mode:", cfg.get("execute_mode"))
    if cfg.get("framework") is None:
        raise AssertionError("Config did not load/merge correctly")


def test_server_and_apiclient(base_url: str) -> None:
    _print_section("2) Server health")
    r = httpx.get(f"{base_url}/health", timeout=5.0)
    r.raise_for_status()
    assert r.json().get("ok") is True

    _print_section("3) ApiClient compatibility")
    os.environ["DS_AGENT_API_BASE_URL"] = base_url
    client = ApiClient(base_url=base_url)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = td_path / "table.csv"
        _make_sample_csv(csv_path)

        trial_id, msg = client.create_trial(
            input_tables=[str(csv_path)],
            target_description="test target description",
            tgt_tbl_path=str(td_path / "target.csv"),
            task_id=None,
            split="test",
        )
        print("create_trial:", trial_id, msg)

        trials = client.get_all_trials()
        assert any(x.get("trial_id") == trial_id for x in trials)

        trial_id_res, task_id, target_desc, history_op = client.get_trial_state(trial_id)
        assert trial_id_res == trial_id
        assert isinstance(task_id, str)
        assert isinstance(target_desc, str)
        assert isinstance(history_op, list)

        tables = client.get_trial_tables(trial_id)
        assert isinstance(tables, dict) and len(tables) >= 1

        # validate operators
        valid, invalid_idx = client.validate_operators(["Terminate(result=['table_1'])"])
        assert valid is True and invalid_idx == []

        # execute/step/simulate
        op_res, obs = client.execute_operator(trial_id, "Terminate(result=['table_1'])", mode="rule")
        assert "Terminate" in op_res
        assert isinstance(obs, str)

        step_msg = client.add_step(trial_id, "Terminate(result=['table_1'])", mode="rule")
        assert isinstance(step_msg, str)

        history = client.simulate_trial(trial_id, ["Terminate(result=['table_1'])"], mode="rule")
        assert isinstance(history, list) and len(history) == 1

        matched, eval_msg = client.evaluate_trial(trial_id)
        assert isinstance(matched, bool)
        assert isinstance(eval_msg, str)

        matched2, msg2 = client.simulate_trial_and_evaluate(trial_id, ["Terminate(result=['table_1'])"], mode="rule")
        assert isinstance(matched2, bool)
        assert isinstance(msg2, str)

        reward, detailed = client.get_reward(trial_id, responses="", version="v0-v1")
        assert isinstance(reward, float)
        assert isinstance(detailed, dict)

        # copy/clear/delete
        copied_id, copied_task_id, copied_split = client.copy_trial(trial_id)
        assert isinstance(copied_id, str) and copied_id != trial_id
        assert isinstance(copied_task_id, str)
        assert isinstance(copied_split, str)

        clear_msg = client.clear_trial_resources(trial_id)
        assert isinstance(clear_msg, str)

        del_msg = client.delete_trial(trial_id)
        assert isinstance(del_msg, str)

    client.close()
    print("ApiClient smoke: OK")


def test_ui_endpoints(base_url: str) -> None:
    _print_section("4) UI endpoints")
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        csv_path = td_path / "ui_table.csv"
        _make_sample_csv(csv_path)

        with open(csv_path, "rb") as f:
            files = [("files", ("ui_table.csv", f, "text/csv"))]
            r = httpx.post(f"{base_url}/ui/upload", files=files, timeout=20.0)
            r.raise_for_status()
            upload = r.json()

        upload_id = upload["uploadId"]
        assert upload_id

        r = httpx.post(
            f"{base_url}/ui/target_description",
            data={
                "uploadId": upload_id,
                "highLevel": "make a target table",
                "schemaJson": json.dumps({"columns": [{"name": "id"}, {"name": "value"}]}),
            },
            timeout=10.0,
        )
        r.raise_for_status()

        # Kick off runner (may fail later due to missing LLM creds; endpoint should respond quickly)
        r = httpx.post(f"{base_url}/ui/run", data={"uploadId": upload_id}, timeout=10.0)
        r.raise_for_status()
        trial_id = r.json()["trialId"]
        assert trial_id

        # Result may or may not be ready; just ensure endpoint returns JSON.
        time.sleep(0.5)
        r = httpx.get(f"{base_url}/ui/trials/{trial_id}/result", timeout=10.0)
        r.raise_for_status()
        assert isinstance(r.json(), dict)

    print("UI endpoints smoke: OK")


def main() -> int:
    config_name = os.environ.get("CHATAPP_CONFIG_NAME", "tree_based_agentic_reasoning_gpt5")
    port = int(os.environ.get("CHATAPP_PORT", "0")) or _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"

    test_config_load(config_name)

    _print_section("Starting uvicorn")
    env = os.environ.copy()
    env["DS_AGENT_API_BASE_URL"] = base_url

    # Run uvicorn in a subprocess.
    proc = _run(
        [sys.executable, "-m", "uvicorn", "chatapp.server:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        cwd=REPO_ROOT,
    )

    try:
        _wait_http_ok(f"{base_url}/health", timeout_s=30.0)
        print("server_ready:", base_url)

        test_server_and_apiclient(base_url)
        test_ui_endpoints(base_url)

        print("\nALL SMOKE TESTS PASSED")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()

        if proc.stdout:
            out = proc.stdout.read()[-8000:]
            if out:
                _print_section("uvicorn last logs")
                print(out)


if __name__ == "__main__":
    raise SystemExit(main())
