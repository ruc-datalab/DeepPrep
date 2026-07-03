from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple
import copy

from app.client import ApiClient
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.physicalop import BaseOp, Terminate, auto_parse_op
from src.tools.helper import GPTPOOL, Config
from src.tools.utils import parse_tag_wrapped_string, cal_tokens
from src.physicalop import get_generated_table_name

from .base_agent import BaseAgent
from .self_reflection_agent import SelfReflectionAgent

class MCTSNode:
    """
    Represents a node in the Monte Carlo Tree Search.
    """
    def __init__(self, trial: Trial, parent: Optional[MCTSNode] = None, action: Optional[BaseOp] = None):
        self.trial: Trial = trial
        self.parent: Optional[MCTSNode] = parent
        self.action: Optional[BaseOp] = action
        self.children: List[MCTSNode] = []
        self.visits: int = 0
        self.value: float = 0.0
        self.untried_actions: Optional[List[BaseOp]] = None
        self.is_terminal: bool = trial.is_terminated()

class MCTSAgent(BaseAgent):
    """
    An agent that uses Monte Carlo Tree Search to find a sequence of operations for data transformation.
    """
    def __init__(self, name: str = 'MCTSAgent', cfg: Optional[Config] = None, log_file: str = '_MAIN'):
        super().__init__(name, cfg, log_file)
        self.llm = GPTPOOL(self.cfg)
        self.client: ApiClient = ApiClient()
        self.mode = self.cfg.get('execute_mode')
        self.Nexpansion: int = self.cfg.get('mcts_n_expansion', 3)
        # Texpansion is the exploration constant (C_puct)
        self.Texpansion: float = self.cfg.get('mcts_t_expansion', 1.0)
        self.Treward: float = self.cfg.get('mcts_t_reward', 1.0)
        self.max_search_steps: int = self.cfg.get('mcts_max_steps', 24)

        self.tol_inputs, self.tol_outputs = [], []

        self.mcts_mode = self.cfg.get('mcts_mode', 'train')
        if self.mcts_mode != 'train':
            self.self_reflection_agent = SelfReflectionAgent(name='SelfReflectionAgent', cfg=self.cfg, log_file=log_file)
        
    def initialize_mct(self, trial: Trial):
        root = MCTSNode(trial=trial)
        root.untried_actions = self.get_valid_actions(root.trial)
        best_chain: Optional[List[BaseOp]] = None
        best_score: float = float('-inf')
        self.tol_inputs, self.tol_outputs = [], []
        return root, best_chain, best_score

    def mcts_search(self, trial: Trial) -> Tuple[Optional[List[BaseOp]], float]:
        self.total_chains, self.best_chain, self.best_score, self.root = None, None, None, None
        self.root, self.best_chain, self.best_score = self.initialize_mct(trial)
        self.total_chains = []
        
        for i in range(self.max_search_steps):
            if self.mcts_mode != 'train':
                if self.best_chain and self.best_score and self.best_score > 0:
                    break
            # 1. Selection
            node, _ = self.selection(self.root)
            
            # 2. Expansion
            expanded_nodes = self.expansion(node)
            
            # 3. Simulation & 4. Backpropagation
            # Note: We simulate for each expanded node
            for child in expanded_nodes:
                leaf_node, reward, op_chain = self.simulation(child)
                
                if reward >= 1:
                    self.total_chains.append(op_chain)
                    self.logger.log(f"Step {i}: reward {reward}, op_chain {op_chain}")
                
                self.backpropagation(leaf_node, reward)
                
                if reward > self.best_score:
                    self.best_score = reward
                    self.best_chain = op_chain
            
            # Log tree structure periodically or after updates
            self.log_tree_structure(self.root)
                    
        if self.mcts_mode != 'train':
            self.best_chain, _ = self.select_best_chain_by_value(self.root)
                    
        return self.total_chains, self.best_chain, self.best_score, self.root

    def select_best_chain_by_value(self, root: MCTSNode) -> Tuple[Optional[List[BaseOp]], float]:
        """Selects the best chain based on average value (exploitation)."""
        best_chain: Optional[List[BaseOp]] = None
        best_score: float = float('-inf')

        def traverse(node: MCTSNode, current_chain: List[BaseOp]):
            nonlocal best_chain, best_score
            
            if node.visits > 0 and len(current_chain) > 0:
                score = node.value / node.visits
                
                if score > best_score:
                    best_score = score
                    best_chain = current_chain[:]
                elif score == best_score:
                    if best_chain is None or len(current_chain) > len(best_chain):
                        best_chain = current_chain[:]

            for child in node.children:
                if child.action:
                    current_chain.append(child.action)
                traverse(child, current_chain)
                if child.action:
                    current_chain.pop()

        traverse(root, [])
        
        if best_chain is None:
            best_chain = []
            
        return best_chain, best_score

    def mct_to_json(self, node: MCTSNode) -> dict:
        untried_count = len(node.untried_actions) if node.untried_actions is not None else 'N/A'
        return {
            "operator_str": str(node.action) if node.action else "Root",
            "value": node.value,
            "visits": node.visits,
            "untried_count": untried_count,
            "children_count": len(node.children),
            "children": [self.mct_to_json(child) for child in node.children]
        }

    def selection(self, node: MCTSNode) -> Tuple[MCTSNode, List[MCTSNode]]:
        path = []
        # Keep going down until we find a node that has untried actions or is a leaf
        while node.untried_actions is not None and not node.untried_actions and node.children:
            node = self.uct_select(node)
            path.append(node)
        return node, path
    
    def _action_exist_in_children(self, node: MCTSNode, action: BaseOp) -> bool:
        exist = False
        for child in node.children:
            if str(child.action) == str(action):
                exist = True
                self.logger.log(f"Action {action} already exists in children of node with action {node.action}. Skipping expansion.")
                break
        return exist

    def expansion(self, node: MCTSNode) -> List[MCTSNode]:
        if node.untried_actions is None:
            node.untried_actions = self.get_valid_actions(node.trial)

        if node.is_terminal:
            return []

        num_to_expand = min(self.Nexpansion, len(node.untried_actions))
        
        # Random sample allows exploring diverse paths, 
        # but you could also pick the first K if the LLM returns sorted confidence.
        actions_to_try = random.sample(node.untried_actions, num_to_expand)
        
        expanded_children = []
        for action in actions_to_try:
            node.untried_actions.remove(action)
            
            # Double check if action exists (though untried_actions logic should prevent this)
            if self._action_exist_in_children(node, action):
                continue

            next_trial = self.apply_action(node.trial, action)
            if next_trial is None:
                continue
            
            child_node = MCTSNode(trial=next_trial, parent=node, action=action)
            node.children.append(child_node)
            expanded_children.append(child_node)
        
        return expanded_children

    def simulation(self, node: MCTSNode) -> Tuple[MCTSNode, float, List[BaseOp]]:
        current_trial = node.trial

        if isinstance(node.action, Terminate):
            generated_op_chain: List[BaseOp] = []
        else:
            prompt = PromptGenerator.mcts_agent_rollout(self.cfg, current_trial)
            self.logger.log(prompt)
            out = self.llm.query(prompt)
            self.logger.log(out)

            self.tol_inputs.append(prompt)
            self.tol_outputs.append(out)
            
            actions_str = parse_tag_wrapped_string(out, tag='operator')
            generated_op_chain: List[BaseOp] = []
            if actions_str:
                for s in actions_str.strip().split('-->'):
                    s = s.strip()
                    if not s:
                        continue
                    try:
                        generated_op_chain.append(auto_parse_op(s))
                    except Exception as e:
                        self.logger.log(f'Error parsing operator: {s}. Error: {e}')

            # Ensure chain is terminated properly for evaluation
            if not generated_op_chain or not isinstance(generated_op_chain[-1], Terminate):
                last_table_name = get_generated_table_name(generated_op_chain[-1]) if generated_op_chain else 'table_1'
                generated_op_chain.append(Terminate(result=[last_table_name]))

        # Evaluate and build the tree along the rollout path
        reward, leaf_node = self.evaluate_chain(generated_op_chain, node)
        
        op_chain = self.extract_operator_chain(leaf_node)
        # Ensure the extracted chain is also terminated visually/logically
        if not op_chain or not isinstance(op_chain[-1], Terminate):
            last_table_name = get_generated_table_name(op_chain[-1]) if op_chain else 'table_1'
            op_chain.append(Terminate(result=[last_table_name]))
            
        return leaf_node, reward, op_chain

    def backpropagation(self, node: MCTSNode, reward: float) -> None:
        current_node = node
        while current_node is not None:
            current_node.visits += 1
            current_node.value += reward
            current_node = current_node.parent

    def uct_select(self, node: MCTSNode) -> MCTSNode:
        log_N_parent = math.log(node.visits)

        def uct(child: MCTSNode) -> float:
            if child.visits == 0:
                return float('inf')
            exploitation = child.value / child.visits
            # [FIX] Added self.Texpansion to control exploration rate
            exploration = self.Texpansion * math.sqrt(2 * log_N_parent / child.visits)
            return exploitation + exploration

        return max(node.children, key=uct)

    def get_valid_actions(self, trial: Trial) -> List[BaseOp]:
        prompt = PromptGenerator.mcts_agent_expand(self.cfg, trial)
        self.logger.log(prompt)
        out = self.llm.query(prompt)
        self.logger.log(out)

        self.tol_inputs.append(prompt)
        self.tol_outputs.append(out)
        
        actions_str = parse_tag_wrapped_string(out, tag='operators')
        valid_actions: List[BaseOp] = []
        if not actions_str:
            return valid_actions

        for s in actions_str.split('[SPLIT_FLAG]'):
            s = s.strip()
            if not s:
                continue
            try:
                valid_actions.append(auto_parse_op(s))
            except Exception as e:
                self.logger.log(f'Error parsing operator: {s}. Error: {e}')
        return valid_actions

    def apply_action(self, trial: Trial, action: BaseOp) -> Trial:
        new_trial = copy.deepcopy(trial)
        new_trial_id, _, _ = self.client.copy_trial(trial_id=trial.exp_id)
        new_trial.exp_id = new_trial_id
        try:
            op, obs = self.client.execute_operator(new_trial.exp_id, op=str(action), mode=self.mode)
            self.client.add_step(new_trial.exp_id, op, mode=self.mode)
            new_trial.add_op(auto_parse_op(op), obs)
        except Exception as e:
            self.logger.log(f"Error applying operator: {action}. Error: {e}")
            new_trial = None
            self.client.delete_trial(trial_id=new_trial_id)
        return new_trial

    def is_termination(self, trial: Trial) -> bool:
        return trial.is_terminated()

    def extract_operator_chain(self, node: MCTSNode) -> List[BaseOp]:
        chain: List[BaseOp] = []
        current_node = node
        while current_node.parent is not None:
            if current_node.action:
                chain.append(current_node.action)
            current_node = current_node.parent
        return list(reversed(chain))

    def log_tree_structure(self, node: MCTSNode):
        tree_str = MCTSAgent.generate_tree_str(node)
        self.logger.log(tree_str)

    @staticmethod
    def generate_tree_str(node: MCTSNode, prefix: str = "") -> str:
        action_str = str(node.action) if node.action else "Root"
        untried_count = len(node.untried_actions) if node.untried_actions is not None else 'N/A'
        res = (f"{prefix}- {action_str} "
               f"[V={node.value:.2f}, N={node.visits}, U={untried_count}, C={len(node.children)}]\n")
        for child in node.children:
            res += MCTSAgent.generate_tree_str(child, prefix + "\t")
        return res
    
    def evaluate_chain(self, op_chain: List[BaseOp], node: MCTSNode) -> Tuple[float, MCTSNode]:
        """
        Applies the operator chain. 
        [FIX] Reuses existing nodes if action already exists in children to prevent tree explosion.
        """
        cur_node = node
        for op in op_chain:
            # 1. Check if this action already exists in current node's children
            existing_child = None
            for child in cur_node.children:
                if str(child.action) == str(op):
                    existing_child = child
                    break
            
            if existing_child:
                # Reuse existing node
                cur_node = existing_child
                continue

            # 2. If not exists, apply action and create new node
            new_trial = self.apply_action(cur_node.trial, op)
            if new_trial is None: 
                # If execution fails, append a Terminate node and stop
                self.logger.log(f'Error applying operator: {op}. Rollout stopped.')
                
                # Check if Terminate node exists (edge case)
                term_op = Terminate(result=['table_1'])
                term_child = None
                for child in cur_node.children:
                    if str(child.action) == str(term_op):
                        term_child = child
                        break
                
                if term_child:
                    cur_node = term_child
                else:
                    new_trial = self.apply_action(cur_node.trial, term_op)
                    new_node = MCTSNode(trial=new_trial, parent=cur_node, action=term_op)
                    cur_node.children.append(new_node)
                    cur_node = new_node
                
                return 0.0, cur_node
            
            new_node = MCTSNode(trial=new_trial, parent=cur_node, action=op)
            cur_node.children.append(new_node)
            cur_node = new_node

        if self.mcts_mode == 'train':
            return self.evaluate_chain_by_ground_truth(cur_node)
        else:
            sol_str = '<solution> ' + ' --> '.join([str(op) for op in op_chain]) + ' <solution>'
            obs_str = '<observations> ' + cur_node.trial.seralize_ops_and_observations() + ' <observations>'
            his_op_and_output = sol_str + '\n' + obs_str
            try:
                reflection, solution_correct = self.self_reflection_agent.self_reflection_reflect(cur_node.trial, 1, his_op_and_output)
            except Exception as e:
                self.logger.log(f"Error evaluating chain: {e}, Solution correct: False")
                solution_correct = False
            return 1.0 if solution_correct else 0.0, cur_node

    def evaluate_chain_by_ground_truth(self, cur_node: MCTSNode) -> Tuple[float, MCTSNode]:
        try:
            trial_id_res, task_id, target_description, history_op = self.client.get_trial_state(cur_node.trial.exp_id)
            solution = ' --> '.join([str(op) for op in history_op])
            traj_str = '<solution> ' + solution + ' <solution>'
            reward = self.client.get_reward(cur_node.trial.exp_id, traj_str, version='v0-v1')
            return reward, cur_node
        except Exception as e:
            self.logger.log(f"Error evaluating chain: {e}")
            return 0.0, cur_node
