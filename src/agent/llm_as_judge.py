import uuid, copy, re, random, json, os

from .base_agent import BaseAgent
from src.tools.utils import parse_any_string, df_to_cotable, set_proxy, unset_proxy, save_json
from src.tools.helper import GPTPOOL
from src.data.trial import Trial

LLM_AS_JUDGE_PROMPT = """
# Role Definition

You are an expert evaluator for automated data preparation systems. Your task is to meticulously assess the quality of a generated agent trajectory for a complex table-to-table transformation task.
You will be given the task description, which includes the initial input tables and the target table schema. You will also be provided with the complete agent trajectory, which consists of a sequence of think and explore steps, culminating in a final solution.
Please evaluate the full trajectory across the following four dimensions, each scored on a scale from 1 (Poor) to 5 (Excellent). Use the detailed guidelines below to calibrate your evaluation.

# Evaluation Dimensions and Scoring Guidelines

## Think Quality: Strategic Reasoning
This dimension assesses the agent's ability to understand the overall task, decompose it into logical sub-problems, and formulate an efficient, high-level plan.

- **1 (Poor)**: The reasoning is chaotic, illogical, repetitive, or completely misses the goal. The agent shows no sign of a coherent plan, and its thoughts are random or irrelevant.
- **2 (Weak)**: The agent shows minimal understanding of the task. The plan is fundamentally flawed, illogical, or addresses only a trivial and irrelevant part of the problem.
- **3 (Fair)**: The reasoning is partially logical but may be inefficient, short-sighted, or take unnecessary detours. The agent understands the immediate next step but lacks a clear long-term strategy.
- **4 (Good)**: The reasoning is logical and forms a viable path to the solution. The plan is mostly complete and effective but may contain minor inefficiencies or could be slightly better optimized.
- **5 (Excellent)**: The reasoning demonstrates a clear, insightful, and efficient top-down strategy. The agent accurately decomposes the complex problem into a sequence of logical, manageable steps, always keeping the final target schema in mind.

## Think Quality: Consistency with Action
This dimension measures how faithfully the agent's explore action implements the plan articulated in the preceding think step.

- **1 (Poor)**: The action (explore block) is completely disconnected from or contradicts the preceding thought (think block).
- **2 (Weak)**: The action is loosely related to the thought but has major inconsistencies. For example, it uses a completely different operator than planned, or the parameters are fundamentally incorrect, failing to achieve the stated intention.
- **3 (Fair)**: The action is generally aligned with the thought but has noticeable discrepancies. For example, it might miss a step mentioned in the plan, use incorrect parameters, or include an unplanned operation.
- **4 (Good)**: The action accurately implements the core intention of the thought with only negligible imperfections, such as a minor typo in a comment or a non-critical parameter choice that doesn't affect the outcome.
- **5 (Excellent)**: The action is a perfect and precise execution of the plan articulated in the think block. The generated operator chain directly and accurately implements the agent's stated intention.

## Framework Capability: Exploration
This dimension evaluates the agent's ability to effectively use the multi-turn think-explore loop to incrementally build a solution and navigate the operator space.

- **1 (Poor)**: The agent fails to use the exploratory nature of the framework. It either attempts to solve the entire problem in one step, gets permanently stuck, or gives up after the first try.
- **2 (Weak)**: The agent uses multiple turns but makes little to no meaningful progress. It may get stuck in a repetitive loop, making the same mistakes, or its exploration is aimless and does not build upon previous steps.
- **3 (Fair)**: The agent uses the think-explore loop to make progress, but does so inefficiently. It may take an excessive number of turns to solve a simple sub-problem or explore paths that are clearly dead ends.
- **4 (Good)**: The agent effectively uses the think-explore loop to build the solution. It makes consistent progress, even if it occasionally explores a minor, unnecessary side-path before reaching the correct sequence.
- **5 (Excellent)**: The agent intelligently leverages the think-explore loop to make steady, incremental progress. It uses intermediate results to inform its next steps, efficiently navigating the complex operator space to discover a valid solution path.

## Framework Capability: RollBack & Debug
This dimension assesses the agent's ability to recognize when an action has failed or produced an incorrect result, diagnose the root cause, and formulate a corrective action.

- **1 (Poor)**: The agent completely ignores obvious errors, NaN values, or incorrect intermediate table schemas from a previous step, proceeding down a flawed path.
- **2 (Weak)**: The agent acknowledges an error occurred but makes no meaningful attempt to diagnose or correct it. It either ignores the implication of the error or abandons the problematic path without trying to fix it.
- **3 (Fair)**: The agent notices that something went wrong but either fails to identify the correct root cause or its attempt to fix the problem is incorrect or incomplete. The debugging attempt is a guess rather than a targeted fix.
- **4 (Good)**: The agent correctly identifies the error and implements a generally effective fix. The correction successfully resolves the main issue, although it might be slightly suboptimal or miss a secondary, related problem.
- **5 (Excellent)**: The agent accurately identifies the specific reason for a previous failure, articulates a clear debugging plan, and executes a precise, corrective action.

# Task Description

## Input Tables

{input_tables}

## Target Table

{target_table}

# Agent Trajectory

{trajectory_str}

Directly return your evaluation in the following JSON format. Do not provide any other text or explanation.
{{
  "Think_Quality_StrategicReasoning": <score_1_to_5>,
  "Think_Quality_Consistency_with_Action": <score_1_to_5>,
  "Framework_Capability_Exploration": <score_1_to_5>,
  "Framework_Capability_RollBack_Debug": <score_1_to_5>
}}
""".strip()


def simple_query(key: str, base_url: str, model: str, messages: list, temperature: float = 0.01, max_tokens: int = 50000) -> str:
    from openai import OpenAI
    import os
    os.environ["OPENAI_API_KEY"] = key
    client = OpenAI(
        api_key=key,
        base_url=base_url,
        timeout=1000
    )
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    ans = completion.choices[0].message.content
    return ans

class LLMAsJudge(BaseAgent):
    def __init__(self, name: str='LLM As Judge', cfg=None, log_file='_MAIN'):
        super().__init__(name, cfg, log_file)
        self.name = name
        self.llm = GPTPOOL(self.cfg)

    def judge(self, trial: Trial, trajectory_str: str, save_reward: bool=False):
        self._clear_state()
        self.MAX_ERR_CNT = 5
        while True:
            try:
                llm_reward = self._judge(trial, trajectory_str, save_reward=save_reward)
                return llm_reward
            except Exception as e:
                self._raise_error(e)

    def _judge(self, trial: Trial, trajectory_str: str, save_reward: bool=False):
        output = self._generate(trial, trajectory_str)
        data = self._parse_json_data(output)
        reward = self._calculate_reward(data)

        if save_reward and data:
            data['llm_reward'] = reward
            save_json(a=data, 
                        fn=os.path.join(self.cfg.get('filecachedir'), f"versions", self.cfg.get_version(), 'saved_reward', f"{trial.exp_id}.json"))
        return reward

    def _calculate_reward(self, data):
        def reward_mapping(score):
            # mapping score (1~5) to [0, 0.25, 0.5, 0.75, 1]
            return (score - 1) / 4

        t1 = data['Think_Quality_StrategicReasoning']
        t2 = data['Think_Quality_Consistency_with_Action']
        f1 = data['Framework_Capability_Exploration']
        f2 = data['Framework_Capability_RollBack_Debug']

        if not(1 <= t1 <= 5 and 1 <= t2 <= 5 and 1 <= f1 <= 5 and 1 <= f2 <= 5):
            raise ValueError(f"The scores are not in the range of 1 to 5, the scores are: {t1}, {t2}, {f1}, {f2}")

        t1 = reward_mapping(t1)
        t2 = reward_mapping(t2)
        f1 = reward_mapping(f1)
        f2 = reward_mapping(f2)

        reward = (t1 * t2 + (0.5 * f1 + 0.5 * f2)) / 2
        return reward

    def _parse_json_data(self, output: str):
        json_str = parse_any_string(output, code_type='json')
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError(f"Your output: {json_str} cannot be parsed as JSON, please check your output format.")
        if not isinstance(data, dict):
            raise ValueError(f"Your output: {json_str} is not a dictionary, please check your output format.")

        #! whether it contains the keys
        tol_keys = ['Think_Quality_StrategicReasoning', 'Framework_Capability_Exploration', 'Framework_Capability_RollBack_Debug']
        not_in_keys = []
        for key in tol_keys:
            if key not in data.keys():
                not_in_keys.append(key)
        if len(not_in_keys) > 0:
            raise ValueError(f"Your output: {json_str} does not contain the following keys: {not_in_keys}, please check your output format.")
        return data

    def _generate(self, trial: Trial, trajectory_str: str):
        input_tables = trial.serialize_input_tables()
        if len(input_tables) > 10000:
            input_tables = input_tables[:10000] + '...'

        target_table = trial.tgt_tbl
        target_table_str = df_to_cotable(target_table)
        if len(target_table_str) > 10000:
            target_table_str = target_table_str[:10000] + '...'

        prompt = LLM_AS_JUDGE_PROMPT.format(input_tables=input_tables, target_table=target_table_str, trajectory_str=trajectory_str)
        self.logger.log(prompt)
        set_proxy(self.cfg.get('proxy'))
        out = self.llm.query(prompt)
        unset_proxy()
        self.logger.log(out)
        return out