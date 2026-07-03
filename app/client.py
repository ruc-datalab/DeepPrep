import logging

# from tools.utils.parse_output import parse_tag_wrapped_string
for h in logging.getLogger().handlers:
    logging.getLogger().removeHandler(h)
logging.basicConfig(level=logging.WARNING)
import httpx, json, time
from typing import List, Dict, Optional, Tuple
import os


def parse_tag_wrapped_string(rsp, tag:str='operator', hard_replace=['your_operator_here']):
    import re
    if f'<{tag}>' not in rsp:
        raise ValueError(f"Tag <{tag}> not found in response")
    if f'</{tag}>' not in rsp:
        raise ValueError(f"Tag </{tag}> not found in response")
    
    if not isinstance(hard_replace, list):
        rsp = rsp.replace(hard_replace, '')
    else:
        for hr in hard_replace:
            rsp = rsp.replace(hr, '')
    # greedily find the first <tag> and the last </tag>
    match = re.search(f'<{tag}>(.*?)</{tag}>', rsp, re.DOTALL)
    return match.group(1) if match else None
    
class ApiClient:
    """
    A client for interacting with the Data Transformation Project API.
    This class provides methods to call the API endpoints defined in `app/main.py`.
    """
    def __init__(self, base_url: str = "http://xxx:xxx", timeout: float = 600.0):
        """
        Initializes the API client.
        :param base_url: The base URL of the API server.
        """
        self.base_url = os.getenv("DS_AGENT_API_BASE_URL", base_url)
        self.timeout = timeout
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            proxies=None,
            trust_env=False
        )
        self.MAX_RETRY = 5
        self.RETRY_DELAY = 0.5
        self.RETRY_DELAY_MULTIPLIER = 2

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def _request(self, method: str, url: str, *, json: dict | None = None, params: dict | None = None, timeout: float | None = None, err_ctx: str = "") -> httpx.Response:
        """
        Internal helper to send HTTP requests with unified retry and exponential backoff.
        It preserves behavior: raise_for_status on success path; re-raise on final failure.
        """
        for i in range(self.MAX_RETRY):
            try:
                resp = self.client.request(method, url, json=json, params=params, timeout=self.timeout if timeout is None else timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                ctx = f"{err_ctx}".strip() or f"{method.upper()} {url}"
                print(f"Error occurred during request [{ctx}]: {e}")
                if i == self.MAX_RETRY - 1:
                    raise
                time.sleep(self.RETRY_DELAY * (self.RETRY_DELAY_MULTIPLIER ** i))

    def create_trial(self, input_tables: List[str], target_description: str, tgt_tbl_path: str, task_id: Optional[str] = None, split: str = 'test') -> Tuple[str, str]:
        url = "/trials"
        data = {
            "input_table_paths": input_tables,
            "target_description": target_description,
            "tgt_tbl_path": tgt_tbl_path,
            "split": split,
        }
        if task_id:
            data["task_id"] = task_id

        response = self._request("POST", url, json=data, err_ctx="creating trial")
        res_data = response.json()
        trial_id, message = res_data['trial_id'], res_data['message']
        return trial_id, message

    def create_trial_with_task_id(self, task_id: str, split: str = 'test') -> Tuple[str, str]:
        url = "/trials/create_with_task_id"
        data = {"task_id": task_id, "split": split}
        response = self._request("POST", url, json=data, err_ctx="creating trial with task_id")
        res_data = response.json()
        trial_id, message = res_data['trial_id'], res_data['message']
        return trial_id, message

    def get_all_trials(self) -> List[Dict]:
        url = "/trials"
        response = self._request("GET", url, err_ctx="getting all trials")
        total_trials_info = response.json()
        return total_trials_info

    def get_trial_state(self, trial_id: str) -> Dict:
        url = f"/trials/{trial_id}"
        response = self._request("GET", url, err_ctx="getting trial state")
        res_data = response.json()
        trial_id_res, task_id = res_data['trial_id'], res_data['task_id']
        target_description = res_data['target_description']
        history_op = res_data['history_op']
        return trial_id_res, task_id, target_description, history_op

    def get_trial_tables(self, trial_id: str) -> Dict[str, str]:
        url = f"/trials/{trial_id}/tables"
        response = self._request("GET", url, err_ctx="getting trial tables")
        res_data = response.json()
        name2dfstr = res_data
        return name2dfstr

    def delete_trial(self, trial_id: str) -> str:
        url = f"/trials/{trial_id}"
        response = self._request("DELETE", url, err_ctx="deleting trial")
        res_data = response.json()
        message = res_data['message']
        return message

    def copy_trial(self, trial_id: str) -> Tuple[str, str, List[str]]:
        url = f"/trials/{trial_id}/copy"
        response = self._request("POST", url, err_ctx="copying trial")
        res_data = response.json()
        trial_id_res, task_id, split = res_data['trial_id'], res_data['task_id'], res_data['split']
        return trial_id_res, task_id, split

    def clear_trial_resources(self, trial_id: str) -> str:
        url = f"/trials/{trial_id}/clear"
        response = self._request("DELETE", url, err_ctx="clearing trial resources")
        res_data = response.json()
        message = res_data['message']
        return message

    def execute_operator(self, trial_id: str, op: str, mode:str='rule') -> Tuple[str, str]:
        url = f"/trials/{trial_id}/execute"
        data = {"op": op, "mode": mode}
        response = self._request("POST", url, json=data, err_ctx="executing operator")
        res_data = response.json()
        op_res, obs = res_data['op'], res_data['obs']
        return op_res, obs

    def add_step(self, trial_id: str, op: str, mode:str='rule') -> str:
        url = f"/trials/{trial_id}/step"
        data = {"op": op, "mode": mode}
        response = self._request("POST", url, json=data, err_ctx="adding step")
        res_data = response.json()
        message = res_data['message']
        return message

    def evaluate_trial(self, trial_id: str) -> Tuple[bool, str]:
        url = f"/trials/{trial_id}/evaluate"
        data = {"trial_id": trial_id}
        response = self._request("POST", url, json=data, err_ctx="evaluating trial")
        res_data = response.json()
        matched, message = res_data['matched'], res_data['message']
        return matched, message

    def simulate_trial(self, trial_id: str, operators: List[str], mode:str='rule') -> List[Dict[str, str]]:
        url = f"/trials/{trial_id}/simulate"
        data = {"operators": operators, "mode": mode}
        response = self._request("POST", url, json=data, err_ctx="simulating trial", timeout=30)
        res_data = response.json()
        history = res_data['history']
        return history

    def simulate_trial_and_evaluate(self, trial_id: str, operators: List[str], mode:str='rule') -> Tuple[bool, str]:
        if 'Terminate' not in operators[-1]:
            return False, "The last operator must be Terminate"
        url = f"/trials/{trial_id}/simulate_evaluate"
        data = {"operators": operators, "mode": mode}
        response = self._request("POST", url, json=data, err_ctx="simulating and evaluating trial")
        res_data = response.json()
        matched, eval_result = res_data['matched'], res_data['message']
        return matched, eval_result

    def get_simulate_trial_exe_obs(self, trial_id: str, operators: List[str], mode:str='rule') -> List[Tuple[str, str]]:
        history = self.simulate_trial(trial_id, operators, mode)
        if history:
            eles = []
            for i, record in enumerate(history):
                op, ob = record['op'], record['obs']
                eles.append((f'** Op {i+1} **: {op}', f'** Output {i+1} **: {ob}'))
            return eles
        return [('Error', str(history))]

    def get_simulate_trial_exe_obs_str(self, trial_id: str, operators: List[str], mode:str='rule', truncate_char_length: int = -1) -> str:
        history = self.simulate_trial(trial_id, operators, mode)
        if history:
            eles = []
            for i, record in enumerate(history):
                op, ob = record['op'], record['obs']
                eles.append(f'** Op {i+1} **: {op}')
                eles.append(f'** Output {i+1} **: {ob}')
                eles.append('---')
            result = '\n'.join(eles)
            if truncate_char_length > 0 and len(result) > truncate_char_length:
                result = result[:truncate_char_length] + "\n... ...\n" + '(Observation is too long, we have truncated it.)'
            return result
        return str(history)

    def get_reward(self, trial_id: str, responses: str, version: str = 'v0-v1') -> float:
        url = f"/trials/reward"
        data = {"trial_id": trial_id, "input_string": responses, "mode": "rule", "version": version}
        # Keep behavior but reuse _request
        r = self._request("POST", url, json=data, err_ctx="getting reward")
        res_obj = r.json()
        reward, detailed_rewards = res_obj.get("reward"), res_obj.get("detailed_rewards", {})
        return reward, detailed_rewards

    def validate_operators(self, operators: List[str]) -> Tuple[bool, List[int]]:
        url = "/operators/validate"
        data = {"operators": operators}
        response = self._request("POST", url, json=data, err_ctx="validating operators")
        res_data = response.json()
        all_valid, invalid_indices = res_data['all_valid'], res_data['invalid_indices']
        return all_valid, invalid_indices

