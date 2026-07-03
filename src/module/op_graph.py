from typing import List, Optional, Dict, Set, Any
import copy
import uuid
from graphviz import Digraph
from .executor import Executor
from .evaluator import Evaluator
from src.data.trial import Trial
from src.physicalop import auto_parse_op

class OpStatus:
    Unknown = "Unknown"
    CannotBeParsed = "CannotBeParsed"
    ExecutionFailed = "ExecutionFailed"
    OperatorAfterWrongOperator = "OperatorAfterWrongOperator"
    ExecutionSuccess = "ExecutionSuccess"
    BelongToSolution = "BelongToSolution"
    BelongToCorrectSolution = "BelongToCorrectSolution"

class Vertex:
    def __init__(self, operation_str: str, turn_idx: int, vertex_idx: int, status: str=OpStatus.Unknown):
        """The turn_idx and vertex_idx are all start from 1"""
        self.operation_str = operation_str
        self.turn_idx = turn_idx
        self.vertex_idx = vertex_idx
        self.status = status

        self.predecessors: List['Vertex'] = []  # Operations that come the previous this one
        self.successors: List['Vertex'] = []    # Operations that come the next this one

    def set_status(self, status: str):
        self.status = status

    def get_status(self) -> str:
        return self.status
        
    def add_predecessor(self, predecessor: 'Vertex'):
        """Add a predecessor vertex (operation that feeds into this one)."""
        if predecessor not in self.predecessors:
            self.predecessors.append(predecessor)
        if self not in predecessor.successors:
            predecessor.successors.append(self)
            
    def add_successor(self, successor: 'Vertex'):
        """Add a successor vertex (operation that this one feeds into)."""
        if successor not in self.successors:
            self.successors.append(successor)
        if self not in successor.predecessors:
            successor.predecessors.append(self)
            
    def remove_predecessor(self, predecessor: 'Vertex'):
        """Remove a predecessor vertex."""
        if predecessor in self.predecessors:
            self.predecessors.remove(predecessor)
        if self in predecessor.successors:
            predecessor.successors.remove(self)
            
    def remove_successor(self, successor: 'Vertex'):
        """Remove a successor vertex."""
        if successor in self.successors:
            self.successors.remove(successor)
        if self in successor.predecessors:
            successor.predecessors.remove(self)
            
    def __str__(self):
        return f"@turn_{self.turn_idx}:vertex_{self.vertex_idx}:{self.operation_str}"
        
    def __repr__(self):
        return self.__str__()
    
    def get_vertex_idx(self):
        return f"@turn_{self.turn_idx}:vertex_{self.vertex_idx}:{self.operation_str}"
    
    def __eq__(self, other: 'Vertex'):
        return self.get_vertex_idx() == other.get_vertex_idx()
    
    def __hash__(self):
        return hash(self.get_vertex_idx())

class OpGraph:
    def __init__(self, cfg, task_id: str, split: str, history_turns: List[List[str]], final_solution: List[str]=None, matched: bool=None):
        """
        Initialize an operation graph with history turns and final solution.
        
        Args:
            history_turns: List of turns, each turn is a list of operation strings
            final_solution: List of operation strings representing the final solution path
        """
        self.start_vertex: Vertex = self._create_start_vertex()
        self.vertices: List[Vertex] = [self.start_vertex]

        self.task_id = task_id
        self.split = split
        self.matched = matched
        self.executor = Executor(cfg=cfg, debug=False)
        self.evaluator = Evaluator(cfg=cfg, debug=False)

        self._initialize_the_explore_tree(history_turns, final_solution, matched)
        self.final_solution = final_solution
        
        # # Step 1: Build the graph structure
        # self._build_graph_structure(history_turns, final_solution)
        
        # # Step 2: Label the graph using client
        # self._label_graph_with_client(history_turns, final_solution)

    def add_turn_to_explore_tree(self, op_chain: List[str], cur_turn: int, is_solution: bool=False, matched: bool=None):
        if is_solution and matched is None:
            raise ValueError("matched is required when is_solution is True")
        new_trial = Trial.load_trial(task_id=self.task_id, split=self.split)

        current_vertex = self.start_vertex
        exe_wrong = False
        
        for op_idx, op_str in enumerate(op_chain):
            # get the status of the current vertex
            status = OpStatus.Unknown
            if exe_wrong:
                status = OpStatus.OperatorAfterWrongOperator
            else:
                try:
                    obj = None
                    obj = auto_parse_op(op_str)
                    out_tblname, out_tbl = self.executor.execute_op(obj, new_trial)
                    self.executor.step_op(obj, new_trial, out_tblname, out_tbl)
                    status = OpStatus.ExecutionSuccess
                    if is_solution:
                        if matched: status = OpStatus.BelongToCorrectSolution
                        else: status = OpStatus.BelongToSolution
                except Exception as e:
                    exe_wrong = True
                    if obj is None: status = OpStatus.CannotBeParsed
                    else: status = OpStatus.ExecutionFailed

            layer = op_idx + 1  # Layer in the tree

            # Find if a successor with the same operation string already exists
            found_successor = None
            for successor in current_vertex.successors:
                if successor.operation_str == op_str:
                    found_successor = successor
                    break
            
            if found_successor:
                # Move to the existing vertex
                current_vertex = found_successor
            else:
                # Create a new vertex if no matching successor is found
                new_vertex = Vertex(
                    operation_str=op_str,
                    turn_idx=cur_turn,  # The turn index when this vertex is first created
                    vertex_idx=layer,
                    status=status
                )

                self.vertices.append(new_vertex)
                current_vertex.add_successor(new_vertex)

                # Move to the newly created vertex
                current_vertex = new_vertex

    def _initialize_the_explore_tree(self, history_turns: List[List[str]], final_solution: List[str], matched: bool):
        # Clean 'Terminate' operation and store history
        cleaned_history_turns = []
        for op_chain in history_turns:
            if op_chain and 'Terminate' in op_chain[-1]:
                cleaned_history_turns.append(op_chain[:-1])
            else:
                cleaned_history_turns.append(op_chain)
        self.history_turns = cleaned_history_turns

        # Build the exploration tree
        for turn_idx, op_chain in enumerate(self.history_turns):
            self.add_turn_to_explore_tree(op_chain, turn_idx + 1, is_solution=False, matched=matched)

        if final_solution is not None:
            self.add_turn_to_explore_tree(final_solution, len(self.history_turns) + 1, is_solution=True, matched=matched)

    def _create_start_vertex(self) -> Vertex:
        """Create the initial start vertex."""
        return Vertex("START()", 0, 0)
    
    # get the leaf number which is successfully executed
    def get_success_exe_leaf(self):
        leafs = [self.start_vertex]
        visited = {str(v): 0 for v in self.vertices}
        # BFS to find the next possible executable leafs
        while True:
            to_break = True
            for from_v in copy.deepcopy(leafs):
                if visited[str(from_v)] == 1:
                    continue
                for to_v in from_v.successors:
                    if to_v.status == OpStatus.ExecutionSuccess or to_v.status == OpStatus.BelongToCorrectSolution or to_v.status == OpStatus.BelongToSolution:
                        if from_v in leafs:
                            leafs.remove(from_v)
                        leafs.append(to_v)
                        to_break = False
                visited[str(from_v)] = 1
            if to_break:
                break
        return leafs

    def visualize(self, output_filename: str = 'op_graph', view: bool = False):
        """
        Generates a visualization of the graph across all turns.
        A node's color is determined by the status of its last turn.
        
        Args:
            output_filename: The name of the output file (without extension).
            view: If True, opens the generated graph visualization.
        """
        print(self.matched)
        dot = Digraph(comment='Operation Graph')
        
        # dot.attr(label='Operation Graph - All Turns', labelloc='t', fontsize='20')

        status_colors = {
            OpStatus.CannotBeParsed: '#ecf0f1', # light gray
            OpStatus.ExecutionFailed: '#d98880', # orange
            OpStatus.OperatorAfterWrongOperator: '#d7bde2', # purple
            OpStatus.ExecutionSuccess: '#aed6f1', # blue
            OpStatus.BelongToCorrectSolution: '#f9e79f', # yellow
            OpStatus.BelongToSolution: '#d4ac0d', # dark yellow
        }

        node_ids = {vertex: f"node{i}" for i, vertex in enumerate(self.vertices)}

        # Add nodes
        for vertex in self.vertices:
            node_id = node_ids[vertex]
            color = 'lightgrey'  # Default color
            
            label = str(vertex)
            color = status_colors.get(vertex.status, 'lightgrey')
            dot.node(node_id, label, color=color, style='filled', shape='box')

        # Add edges
        for vertex in self.vertices:
            for successor in vertex.successors:
                dot.edge(node_ids[vertex], node_ids[successor])
                
        # Render the graph
        try:
            # save to file
            dot.render(f'./_tmp/figures/{output_filename}', view=view, format='pdf', cleanup=True)
            print(f"Graph saved to {output_filename}.pdf")
        except Exception as e:
            print(f"Error rendering graph: {e}")
            print("Please make sure Graphviz is installed and in your system's PATH.")

        return dot