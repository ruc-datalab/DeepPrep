from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, parse_tag_wrapped_string, all_filepaths_in_dir, load_text_file, save_text_file, set_proxy
from src.tools.helper import GPTPOOL, MultiProcesser, Logger, Config
from src.physicalop import *
from app.client import ApiClient
import os

ANALYZE_CODE_AGENT_ERROR_PROMPT = """
下面是我code agent的log记录，请分析该code agent框架错误的原因：

{log_root}

现在，从下面几类原因中选择（如果需要，你可以选择多类错误），并进行简要描述：

A. 探索不充分。一直重复一种错误的思路进行表格转换，不能有效探索新的思路。
B. 不能有效定位错误。当生成错误的表格，从而和target table不能正确匹配时，模型由于没能输出中间表格，无法定位到具体是哪一步出错了。
C. 语法错误。
D. 其他：_____
"""

def analyze_code_agent_error_one_log(log_content: str, saved_analyze_result_path: str, cfg:Config):
    # Recreate logger if needed (or use a simple print/file write)
    logger = Logger(name='Error Analyzer', cfg=cfg)  # Adjust if custom logger needed

    prompt = ANALYZE_CODE_AGENT_ERROR_PROMPT.format(log_root=log_content)
    logger.log(prompt)
    set_proxy(cfg.get('proxy'))
    llm = GPTPOOL(cfg)  # Recreate LLM per process
    out = llm.query(prompt)
    logger.log(out)
    saved_content = log_content + '# ⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️⬆️\n\n' + out
    save_text_file(saved_analyze_result_path, saved_content)

class ErrorAnalyzer(BaseAgent):
    def __init__(self, name: str='Error Analyzer', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPTPOOL(self.cfg)
        self.client = ApiClient()

    def analyze_code_agent_error(self, log_root: str, n: int=1):
        total_prompts = {}
        for fn in all_filepaths_in_dir(log_root):
            base_name = os.path.basename(fn)
            log_content = load_text_file(fn)
            input_log = log_content.split('# Role Definition')[-1].strip()
            input_log = '# ⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️\n\n【system】\n# Role Definition\n\n' + input_log
            total_prompts[base_name] = input_log

        # log_root/../logs_analyze_unmatched
        saved_analyze_result_root = os.path.join(log_root, '../logs_analyze_unmatched')
        os.makedirs(saved_analyze_result_root, exist_ok=True)
        inputs = []
        for base_name, input_log in total_prompts.items():
            saved_analyze_result_path = os.path.join(saved_analyze_result_root, base_name)
            inputs.append((input_log, saved_analyze_result_path, self.cfg))  # Pass cfg
        multi_processer = MultiProcesser(num_processes=n)
        for input in inputs:
            multi_processer.submit_task(analyze_code_agent_error_one_log, *input)  # Call standalone func
        results = multi_processer.wait_for_completion()
    
    def step(self, trial: Trial, error_category:dict, exe_error: Exception=None):
        self._clear_state()
        if exe_error is not None:
            self.last_log = str(exe_error)
        while True:
            try:
                return self._step(trial, error_category)
            except Exception as e:
                self._raise_error(e)

    def _step(self, trial: Trial, error_category:dict):
        output = self._generate(trial, error_category)
        _, error_reason, error_category, error_tag = self._parse_action_result(output)
        return error_category, error_reason, error_tag
    
    def _parse_multiturn_output(self, output: str) -> str:
        """
        Parse the output of the ds agent.
        """
        # Parse the output to get the action
        think = parse_tag_wrapped_string(output, tag='think', hard_replace=['your_think_here'])
        solution = parse_tag_wrapped_string(output, tag='solution', hard_replace=['your_solution_here'])
        action = parse_tag_wrapped_string(output, tag='operator', hard_replace=['your_operator_here'])
        return think, solution, action

    def _generate(self, trial: Trial, error_category:dict) -> str:
        prompt = PromptGenerator.error_analyzer_analyze(trial, error_category, last_error=self.last_log)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)
        return out

    def _parse_action_result(self, output: str) -> str:
        """
        Parse the output of the ds agent.
        """
        # Parse the output to get the action
        think = parse_tag_wrapped_string(output, tag='think', hard_replace=['your_think_here'])
        error_reason = parse_tag_wrapped_string(output, tag='error_reason', hard_replace=['your_error_reason_here'])
        error_category = parse_tag_wrapped_string(output, tag='error_category', hard_replace=['your_error_category_here'])
        error_tag = parse_tag_wrapped_string(output, tag='error_tag', hard_replace=['your_error_tag_here'])
        if error_reason: error_reason = error_reason.strip()
        if error_category: error_category = error_category.strip()
        if error_tag: error_tag = error_tag.strip()
        return think, error_reason, error_category, error_tag
