import uuid, copy, re, random
import os

from .base_agent import BaseAgent
from src.data import Task, Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, load_text_file, open_json, save_json
from src.tools.helper import GPTPOOL
from src.physicalop import *

class ThinkAgent(BaseAgent): 
    def __init__(self, name: str='Think Agent', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)
        # Load the tree-based agentic reasoning trajectory-rewrite prompt.
        self.TREE_BASED_AGENTIC_REASONING_PROMPT = load_text_file(
            os.path.join(
                os.path.dirname(__file__),
                '..',
                'prompt',
                'others',
                'gen_think_for_tree_based_agentic_reasoning.md',
            )
        )

    def generate_think_for_tree_based_agentic_reasoning(self, traj_dict: dict, save_name: str):
        save_path = os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_think', f"{save_name}.json")
        if os.path.exists(save_path):
            return open_json(save_path)

        self._clear_state()
        self.MAX_ERR_CNT = 5
        while True:
            try:
                traj_dict = self._step(traj_dict)
                save_json(traj_dict, save_path)
                return traj_dict
            except Exception as e:
                self._raise_error(e)

    def _step(self, traj_dict: dict):
        output = self._generate(traj_dict)
        think_obj = self._parse_output(traj_dict, output)
        updated_traj_dict = self._update_traj_dict(traj_dict, think_obj)
        return updated_traj_dict

    def _update_traj_dict(self, traj_dict: dict, think_obj: dict):
        for turn in think_obj.keys():
            traj_dict[turn]['think'] = think_obj[turn]['think']
        return traj_dict

    def _generate(self, traj_dict: dict):
        prompt = self.TREE_BASED_AGENTIC_REASONING_PROMPT.replace('[json_data_for_traj]', json.dumps(traj_dict, indent=2))
        prompt = prompt.replace('[last_error]', ' and try to avoid the last error: ' + self.last_log if self.last_log else '')
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_output(self, traj_dict: dict, output: str) -> str:
        def check_valid(traj_dict: dict, obj: dict):
            for turn in traj_dict.keys():
                if turn not in obj.keys():
                    raise ValueError(f"The key `{turn}` is not found in the return json object")
                if 'think' not in obj[turn].keys():
                    raise ValueError(f"The processed think for turn `{turn}` is not found in the return json object (Missing key `think` for obj['{turn}'])")
                if len(obj[turn]['think']) == 0:
                    raise ValueError(f"The processed think for turn `{turn}` is not found in the return json object (Empty think)")

            for turn in obj.keys():
                if turn not in traj_dict.keys():
                    raise ValueError(f"You have generated a turn `{turn}` that is not in the original trajectory! Please check your output again!")

        code_str = parse_any_string(output, code_type='json')
        try:
            think_for_traj_obj = json.loads(code_str)
        except Exception as e:
            raise ValueError(f"Fail to parse the output as a json object, Try to generate a correct output with valid json format!")

        check_valid(traj_dict, think_for_traj_obj)
        return think_for_traj_obj
