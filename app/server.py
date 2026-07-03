import os, sys, uuid, re, shutil, copy
from pebble import ProcessPool
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import warnings
import redis
import pickle
warnings.simplefilter(action='ignore', category=FutureWarning)

# This is a workaround to make the local src packages available to the FastAPI app
# In a production environment, this would be handled by a proper package installation.
print(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.physicalop.data_transform import CodeGeneration
from src.data import Task, Trial
from src.tools.helper import Config, Logger
from src.tools.utils import df_to_cotable,unset_proxy, parse_tag_wrapped_string, get_benchmark_from_task_id
from src.agent import LLMAsJudge
from src.physicalop import auto_parse_op, BaseOp, PARROT_OP
from src.module import Executor, Evaluator, OpGraph, OpStatus
from src.data import DataPool

unset_proxy()

# --- Redis-backed Trial Manager ---
class RedisTrialManager:
    def __init__(self, host='localhost', port=6379, db=0):
        self._redis = redis.Redis(host=host, port=port, db=db)

    def __setitem__(self, key, value):
        self._redis.set(key, pickle.dumps(value))

    def __getitem__(self, key):
        value = self._redis.get(key)
        if value is None:
            raise KeyError(key)
        return pickle.loads(value)

    def __delitem__(self, key):
        self._redis.delete(key)

    def __contains__(self, key):
        return self._redis.exists(key)

    def keys(self):
        return [key.decode('utf-8') for key in self._redis.keys('*')]
    
    def items(self):
        keys = self.keys()
        return [(key, self[key]) for key in keys]

cfg = Config(name='total_llms')
cfg.set('version', 'server', save=False)
logger = Logger(name='Server', log_file='_SERVER', cfg=cfg)

# --- Application Setup ---
app = FastAPI(
    title="AutoPrep2.0",
    description="A web server for interacting with the Data Transformation Project.",
    version="2.0.0"
)

# --- In-Memory Storage ---
# This will act as our simple in-memory database for active trials.
# The key is the trial_id, and the value is a dictionary acting as an adapter.
TRIAL_MANAGER = RedisTrialManager()

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

executor = Executor(cfg=cfg, debug=False)
evaluator = Evaluator(cfg=cfg, debug=False)

# --- Pydantic Models for API Data Validation ---
class CreateTrialRequest(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    input_table_paths: List[str]
    tgt_tbl_path: str
    target_description: str
    split: str = 'test'
    trial_id: str = None

class CreateTrialWithIdRequest(BaseModel):
    trial_id: str
    input_table_paths: List[str]
    tgt_tbl_path: str
    target_description: str
    split: str = 'test'

class CreateTrialWithTaskIdRequest(BaseModel):
    task_id: str
    split: str = 'test'

class CreateTrialResponse(BaseModel):
    trial_id: str
    message: str

class TrialInfo(BaseModel):
    trial_id: str
    task_id: str
    split: str

class TrialState(BaseModel):
    trial_id: str
    task_id: str
    target_description: str
    history_op: List[str]

class ExecuteRequest(BaseModel):
    op: str
    mode: str = 'rule'

class ExecuteResponse(BaseModel):
    op: str
    obs: str

class ExploreStepResponse(BaseModel):
    op: str
    obs: str

class SimulateRequest(BaseModel):
    operators: List[str]
    mode: str = 'rule'

class SimulateResponse(BaseModel):
    history: List[Dict]

class EvaluateRequest(BaseModel):
    trial_id: str

class EvaluateResponse(BaseModel):
    matched: bool
    message: str

class RewardRequest(BaseModel):
    trial_id: str
    input_string: str
    mode: str = 'rule'
    version: str = 'v0'

class RewardResponse(BaseModel):
    reward: float
    detailed_rewards: Dict[str, float]

class ValidateOperatorsRequest(BaseModel):
    operators: List[str]

class ValidateOperatorsResponse(BaseModel):
    all_valid: bool
    invalid_indices: List[int]

class TasksInfoResponse(BaseModel):
    splits: Dict[str, List[str]]

# --- API Endpoints ---

@app.get("/tasks", response_model=TasksInfoResponse)
def get_tasks_info():
    """
    Returns a list of available splits and their corresponding task IDs.
    """
    benchmark_data = {}
    splits_data = {}
    for benchmark, tbl_schema_description in DataPool.tbl_schema_description.items():
        for split, tasks in tbl_schema_description.items():
            splits_data[split] = list(tasks.keys())
            benchmark_data[benchmark] = {
                "splits": splits_data,
            }
    return {"splits": splits_data}

@app.get("/tasks/{split}/{task_id}")
def get_task_details(split: str, task_id: str):
    """
    Returns task details including input tables, target description, and schema description.
    """
    try:
        benchmark = get_benchmark_from_task_id(task_id)
        # Get task info from DataPool
        if split not in DataPool.tbl_schema_description[benchmark]:
            raise HTTPException(status_code=404, detail=f"Split '{split}' not found")
        
        if task_id not in DataPool.tbl_schema_description[benchmark][split]:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in split '{split}'")
        
        # Create a temporary trial to get input tables
        trial = Trial.load_trial(task_id=task_id, split=split)
        
        # Get schema description
        schema_desc = Trial.generate_schema_description(trial.task)
        
        # Get input tables as formatted strings
        input_tables = trial.serialize_input_tables()
        
        # Get task description from schema
        task_description = DataPool.tbl_schema_description[benchmark][split][task_id]['Task Description']
        
        return {
            "task_id": task_id,
            "split": split,
            "task_description": task_description,
            "schema_description": schema_desc,
            "input_tables": input_tables,
            "input_table_names": trial.task.inp_tbl_names,
            "target_table_name": trial.task.tgt_tbl_name
        }
    except Exception as e:
        logger.log(f"Error loading task details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading task details: {str(e)}")

@app.get("/")
async def read_index():
    return FileResponse('app/static/index.html')

@app.get("/operators", response_model=List[str])
def get_available_operators():
    """
    Returns a list of available operator names.
    """
    return PARROT_OP

@app.get("/operators/descriptions")
def get_operator_descriptions():
    """
    Returns detailed descriptions of all available operators.
    """
    try:
        descriptions = []
        for op_class in PARROT_OP:
            try:
                description = op_class.get_action_description()
                descriptions.append({
                    "name": op_class.__name__,
                    "description": description
                })
            except Exception as e:
                # Fallback if get_action_description fails
                descriptions.append({
                    "name": op_class.__name__,
                    "description": f"## {op_class.__name__} Operator\n\n* Description: {op_class.__name__} operation for data transformation."
                })
        return descriptions
    except Exception as e:
        # Return basic operator names as fallback
        return [{"name": str(op), "description": f"## {str(op)} Operator\n\n* Description: {str(op)} operation for data transformation."} for op in PARROT_OP]

@app.post("/operators/validate", response_model=ValidateOperatorsResponse)
def validate_operators(request: ValidateOperatorsRequest):
    """
    Validates whether all operators in the provided list can be parsed successfully.
    Returns True if all operators are valid, False otherwise, along with indices of invalid operators.
    """
    invalid_indices = []

    for i, operator in enumerate(request.operators):
        try:
            auto_parse_op(operator)
        except Exception as e:
            invalid_indices.append(i)

    all_valid = len(invalid_indices) == 0
    return {"all_valid": all_valid, "invalid_indices": invalid_indices}

@app.get("/tasks/{split}/{task_id}/ground_truth")
def get_ground_truth(split: str, task_id: str):
    """
    Returns the ground truth solution for a specific task.
    """
    try:
        benchmark = get_benchmark_from_task_id(task_id)
        if split not in DataPool.ground_truth[benchmark]:
            raise HTTPException(status_code=404, detail=f"Split '{split}' not found in ground truth")
        
        if task_id not in DataPool.ground_truth[benchmark][split]:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in split '{split}' ground truth")
        
        ground_truth_ops = DataPool.ground_truth[benchmark][split][task_id]
        ground_truth_str = " --> ".join([str(op) for op in ground_truth_ops])
        
        return {
            "task_id": task_id,
            "split": split,
            "ground_truth": ground_truth_str,
            "operations": [str(op) for op in ground_truth_ops]
        }
    except Exception as e:
        logger.log(f"Error loading ground truth: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading ground truth: {str(e)}")

class TaskCompletionRecord(BaseModel):
    task_id: str
    split: str
    completion_time: str
    exploration_count: int
    is_correct: bool
    user_solution: str

@app.post("/tasks/record_completion")
def record_task_completion(request: TaskCompletionRecord):
    """
    Records task completion time and details to a file.
    """
    try:
        import datetime
        import json
        
        # Create completion record
        record = {
            "task_id": request.task_id,
            "split": request.split,
            "completion_time": request.completion_time,
            "exploration_count": request.exploration_count,
            "is_correct": request.is_correct,
            "user_solution": request.user_solution,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Ensure the directory exists
        os.makedirs("app/completion_records", exist_ok=True)
        
        # Save to file (append mode)
        filename = f"app/completion_records/task_completions.jsonl"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        return {"message": "Task completion recorded successfully", "record": record}
    
    except Exception as e:
        logger.log(f"Error recording completion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording completion: {str(e)}")

@app.post("/trials", response_model=CreateTrialResponse, status_code=201)
def create_trial(request: CreateTrialRequest):
    """
    Creates a new data transformation trial.
    """

    # Adapter Logic: We use the existing Task and Trial classes without modification.
    # To conform to the Task constructor, we provide placeholder values for arguments
    # that are not relevant in this API-driven workflow.
    if request.target_description is not None and len(request.target_description) == 0:
        request.target_description = None
    task = Task(
        id=request.task_id,
        inp_tbl_names=request.input_table_paths,
        tgt_tbl_description=request.target_description,
        tgt_tbl_name=request.tgt_tbl_path,
        split=request.split,
    )
    
    trial_id = f"{task.id}_{uuid.uuid4().hex}" if request.trial_id is None else request.trial_id

    trial = Trial(exp_id=trial_id, task=task)
    
    try:
        trial.load(task=task)
    except Exception as e:
        logger.log(f"Failed to load input tables: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to load input tables: {e}")

    TRIAL_MANAGER[trial_id] = trial

    return {
        "trial_id": trial_id,
        "message": "Trial created successfully."
    }

@app.post("/trials/create_with_task_id", response_model=CreateTrialResponse, status_code=201)
def create_trial_with_task_id(request: CreateTrialWithTaskIdRequest):
    """
    Creates a new data transformation trial from a task_id.
    """
    try:
        trial = Trial.load_trial(task_id=request.task_id, split=request.split)
    except KeyError:
        logger.log(f"Task with id '{request.task_id}' not found in split '{request.split}'.")
        raise HTTPException(status_code=404, detail=f"Task with id '{request.task_id}' not found in split '{request.split}'.")
    except Exception as e:
        logger.log(f"Failed to load trial: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to load trial: {e}")

    trial_id = trial.exp_id
    TRIAL_MANAGER[trial_id] = trial

    return {
        "trial_id": trial_id,
        "message": "Trial created successfully from task_id."
    }

@app.get("/trials", response_model=List[TrialInfo])
def get_all_trials():
    """
    Retrieves a list of all active trials.
    """
    return [
        {"trial_id": tid, "task_id": trial.task.id, "split": trial.task.split}
        for tid, trial in TRIAL_MANAGER.items()
    ]

@app.get("/trials/{trial_id}", response_model=TrialState)
def get_trial_state(trial_id: str):
    """
    Retrieves the complete current state of a specific trial.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    trial: Trial = TRIAL_MANAGER[trial_id]
    
    history_op = [str(op) for op in trial.ops]

    task_id = trial.task.id
    benchmark = get_benchmark_from_task_id(task_id)

    ret_data = {
        "trial_id": trial_id,
        "task_id": trial.task.id,
        "target_description": DataPool.tbl_schema_description[benchmark][trial.task.split][trial.task.id]['Task Description'] if trial.task.split in DataPool.tbl_schema_description[benchmark] and trial.task.id in DataPool.tbl_schema_description[benchmark][trial.task.split] else 'NO_TARGET_DESCRIPTION',
        "history_op": history_op,
    }

    return ret_data

@app.post("/trials/{trial_id}/copy", response_model=TrialInfo, status_code=201)
def copy_trial(trial_id: str):
    """
    Creates a copy of an existing trial.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    original_trial: Trial = TRIAL_MANAGER[trial_id]

    # Create a new trial ID
    new_trial_id = f"{original_trial.task.id}_{uuid.uuid4().hex}"
    
    new_trial = copy.deepcopy(original_trial)
    new_trial.exp_id = new_trial_id

    TRIAL_MANAGER[new_trial_id] = new_trial

    history_op = [str(op) for op in new_trial.ops]

    return {
        "trial_id": new_trial_id,
        "task_id": new_trial.task.id,
        "split": new_trial.task.split,
    }

@app.get("/trials/{trial_id}/tables", response_model=Dict[str, str])
def get_trial_tables(trial_id: str):
    """
    Retrieves all tables within a specific trial, serialized as JSON strings.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    trial: Trial = TRIAL_MANAGER[trial_id]
    return {
        name: df_to_cotable(df, cut_line=cfg.get('gen_tbl_cut_line'), cut_col=cfg.get('gen_tbl_cut_col'))
        for name, df in trial.tables.items()
    }

@app.delete("/trials/{trial_id}", status_code=200)
def delete_trial(trial_id: str):
    """
    Deletes a trial and removes it from server memory.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    TRIAL_MANAGER[trial_id] = None
    del TRIAL_MANAGER[trial_id]
    return {"message": f"Trial {trial_id} deleted successfully."}

@app.delete("/trials/{trial_id}/clear", status_code=200)
def clear_trial_resources(trial_id: str):
    """
    Deletes a trial, including in-memory objects and associated file-system resources.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    # Delete from memory
    del TRIAL_MANAGER[trial_id]
    
    message = f"Trial {trial_id} deleted from memory."

    return {"message": message}

@app.post("/trials/{trial_id}/explore_step", response_model=ExploreStepResponse)
def explore_step(trial_id: str, request: ExecuteRequest):
    """
    Executes a single operation, adds it to the trial's history,
    and returns the observation. This is for UI interaction.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    trial: Trial = TRIAL_MANAGER[trial_id]
    
    try:
        op_string = request.op
        mode = request.mode
        op_object: BaseOp = auto_parse_op(op_string)
        
        out_tblname, out_tbl = executor.execute_op(op_object, trial, mode)
        executor.step_op(op_object, trial, out_tblname, out_tbl)
        
        observation = f'Name: "{out_tblname}"\n{df_to_cotable(out_tbl, cut_line=cfg.get("gen_tbl_cut_line"), cut_col=cfg.get("gen_tbl_cut_col"))}'

    except Exception as e:
        logger.log(f"Failed to execute operator: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to execute operator: {e}")

    return {"op": str(op_object), "obs": observation}

@app.post("/trials/{trial_id}/execute", response_model=ExecuteResponse)
def execute_operator(trial_id: str, request: ExecuteRequest):
    """
    Executes a single, user-specified operation on the trial's data.
    After execution, the CriticAgent is used to evaluate the outcome.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    trial: Trial = TRIAL_MANAGER[trial_id]
    
    # --- Execution ---
    try:
        # Use auto_parse_op to convert the request into a physical operation object
        op_string = request.op
        mode = request.mode
        op_object: BaseOp = auto_parse_op(op_string)
        
        # The executor mutates the tables inside the trial_obj directly
        out_tblname, out_tbl = executor.execute_op(op_object, trial, mode)
        observation = f'Name: "{out_tblname}"\n{df_to_cotable(out_tbl, cut_line=cfg.get("gen_tbl_cut_line"), cut_col=cfg.get("gen_tbl_cut_col"))}'

    except Exception as e:
        logger.log(f"Failed to execute operator: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to execute operator: {e}")

    return {"op": str(op_object), "obs": observation}

@app.post("/trials/{trial_id}/simulate", response_model=SimulateResponse)
def simulate_trial(trial_id: str, request: SimulateRequest):
    """
    Simulates a sequence of operations on a copy of a trial and returns the resulting history.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    original_trial: Trial = TRIAL_MANAGER[trial_id]

    # Create a deep copy of the trial to avoid modifying the original
    new_trial = Trial(exp_id=f"sim_{uuid.uuid4().hex}", task=original_trial.task)
    new_trial.tables = {name: df.copy() for name, df in original_trial.tables.items()}
    new_trial.ops = list(original_trial.ops)
    new_trial.obs = list(original_trial.obs)
    # trial.generated_tbls is a dict
    new_trial.generated_tbls = dict(original_trial.generated_tbls) if original_trial.generated_tbls else {}

    mode = request.mode
    for i in range(len(request.operators)):
        try:
            op_object: BaseOp = auto_parse_op(request.operators[i])
            out_tblname, out_tbl = executor.execute_op(op_object, new_trial, mode)
            executor.step_op(op_object, new_trial, out_tblname, out_tbl)
        except Exception as e:
            logger.log(f"Failed to execute operator: {e}")
            obs = f'Error raised when executing operator {i+1}: {str(request.operators[i])}. Error: {str(e)}\n Since the error is raised, the following operators will not be executed!'
            new_trial.add_op(request.operators[i], obs)
            break

    history = [
        {"op": str(op), "obs": obs}
        for op, obs in zip(new_trial.ops, new_trial.obs)
    ]

    del new_trial

    return {"history": history}

@app.post("/trials/{trial_id}/simulate_evaluate", response_model=EvaluateResponse)
def simulate_trial_evaluate(trial_id: str, request: SimulateRequest):
    """
    Simulates a sequence of operations on a copy of a trial and returns the resulting history.
    """

    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    original_trial: Trial = TRIAL_MANAGER[trial_id]
    if original_trial.generated_tbls is None:
        raise HTTPException(status_code=400, detail="No generated tables found")

    # Create a deep copy of the trial to avoid modifying the original
    new_trial = Trial(exp_id=f"sim_{uuid.uuid4().hex}", task=original_trial.task)
    new_trial.tables = {name: df.copy() for name, df in original_trial.tables.items()}
    new_trial.ops = list(original_trial.ops)
    new_trial.obs = list(original_trial.obs)
    # trial.generated_tbls is a dict
    new_trial.generated_tbls = dict(original_trial.generated_tbls) if original_trial.generated_tbls else {}
    new_trial.tgt_tbl = original_trial.tgt_tbl.copy()
    
    mode = request.mode
    for i in range(len(request.operators)):
        try:
            op_object: BaseOp = auto_parse_op(request.operators[i])
            out_tblname, out_tbl = executor.execute_op(op_object, new_trial, mode)
            executor.step_op(op_object, new_trial, out_tblname, out_tbl)
        except Exception as e:
            logger.log(f"Failed to execute operator: {e}")
            error_message = f'Error raised when executing operator {i+1}: {str(request.operators[i])}. Error: {str(e)}'
            del new_trial
            return {"matched": False, "message": error_message}

    matched, message = evaluator.evaluate_trial_tables(new_trial)
    del new_trial
    return {"matched": matched, "message": message}

# add step api, to add the op and obs to the trial
@app.post("/trials/{trial_id}/step", status_code=200)
def add_step(trial_id: str, request: ExecuteRequest):
    """
    Adds a step to the trial.
    """
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")

    trial: Trial = TRIAL_MANAGER[trial_id]
    mode = request.mode

    # first execute the op to get the tbl_name and tbl_obj
    try:
        op_string = request.op
        op_object: BaseOp = auto_parse_op(op_string)
        out_tblname, out_tbl = executor.execute_op(op_object, trial, mode)
        executor.step_op(op_object, trial, out_tblname, out_tbl)
        # update the trial in the TRIAL_MANAGER
        TRIAL_MANAGER[trial_id] = trial
    except Exception as e:
        logger.log(f"Failed to execute operator: {e}")
        # raise HTTPException(status_code=400, detail=f"Failed to execute operator: {e}")
        return {"message": f"Failed to execute operator: {e}"}
    
    return {"message": "Step added successfully."}

@app.post("/trials/{trial_id}/evaluate", response_model=EvaluateResponse)
def evaluate_trial(request: EvaluateRequest):
    """
    Evaluates one or more of a trial's generated tables against a provided target table.
    """
    trial_id = request.trial_id
    if trial_id not in TRIAL_MANAGER:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    trial: Trial = TRIAL_MANAGER[trial_id]
    if trial.generated_tbls is None:
        raise HTTPException(status_code=400, detail="No generated tables found")

    matched, message = evaluator.evaluate_trial_tables(trial)

    return {"matched": matched, "message": message}

def parse_his_operators_and_solution(trajectory_str: str):

    his_operators = []
    solution = None
    SOLUTION_TAG_BEGIN, SOLUTION_TAG_END = '<solution>', '</solution>'
    OPERATOR_TAG_BEGIN, OPERATOR_TAG_END = '<operator>', '</operator>'
    OBSERVATION_TAG_BEGIN, OBSERVATION_TAG_END = '<observation>', '</observation>'

    solution_beg_idx = trajectory_str.rfind(SOLUTION_TAG_BEGIN)
    solution_end_idx = trajectory_str.find(SOLUTION_TAG_END, solution_beg_idx)
    if solution_beg_idx == -1 or solution_end_idx == -1 or solution_beg_idx > solution_end_idx:
        raise Exception(f"Invalid trajectory string: The solution tag is not found!")
    solution = trajectory_str[solution_beg_idx + len(SOLUTION_TAG_BEGIN):solution_end_idx]
    solution = [op.strip() for op in solution.split('-->') if op.strip() != '']
    if len(solution) == 0:
        raise Exception(f"Empty Solution!")

    # operator_strs = re.findall(r'<operator>(.*?)</operator>', trajectory_str, re.S)   
    # if not operator_strs:
    #     operator_strs = []

    # his_operators = [[op.strip() for op in op_str.split('-->')] for op_str in operator_strs if op_str is not None and op_str.strip() != '']

    return his_operators, solution

def get_success_reward_encourage_explore(graph: OpGraph, explore_turn: int, cfg: Config):   
    ratio = 0.0
    success_exe_leafs = graph.get_success_exe_leaf()
    ratio += len(success_exe_leafs) / (explore_turn + 1)
    ratio += explore_turn / cfg.get('max_explore_turn')
    ratio /= 2
    reward = 1 + ratio
    return reward

def get_reward0712(graph: OpGraph, cfg: Config):
    def sigmoid_projection(x, k=4):
        z = k * (2 * x - 1)
        sig = 1 / (1 + np.exp(-z))
        ret = (sig - 1/(1+np.exp(k))) / (1 - 2/(1+np.exp(k)))
        return float(ret)
    
    benchmark = get_benchmark_from_task_id(graph.task_id)
    gt = DataPool.ground_truth[benchmark][graph.split][graph.task_id]
    ratio1 = len(graph.history_turns) / cfg.get('max_explore_turn')
    ratio2 = sigmoid_projection(len(gt) / DataPool.max_op_len[benchmark])
    delta = abs(ratio1 - ratio2)
    r1 = -delta + 1

    success_exe_cnt = 0
    for vertex in graph.vertices:
        if vertex.status == OpStatus.BelongToSolution or vertex.status == OpStatus.ExecutionSuccess or vertex.status == OpStatus.BelongToCorrectSolution:
            success_exe_cnt += 1
    ratio3 = success_exe_cnt / (len(graph.vertices) - 1)
    if ratio3 < 0.6: ratio3 = 0
    else: ratio3 = (ratio3 - 0.5) / 0.5
    r2 = ratio3

    reward = 1 + (r1 + r2) / 2

    return reward

def reward_similarity_with_ground_truth(solution: List[str], ground_truth: List[BaseOp]):
    if len(solution) == 0:
        return 0
    sol = copy.deepcopy(solution)
    gth = copy.deepcopy([str(x) for x in ground_truth])

    # we do not compare Terminate operator
    if 'Terminate' in sol[-1]: sol = sol[:-1]
    if 'Terminate' in gth[-1]: gth = gth[:-1]

    if len(sol) == 0 or len(gth) == 0:
        return 0
    
    # calculate the matched operator
    matched_cnt = 0
    for i in range(min(len(sol), len(gth))):
        sol_op_str = sol[i]
        gth_op_str = gth[i]
        try:
            sol_op = auto_parse_op(sol_op_str)
            gth_op = auto_parse_op(gth_op_str)
        except Exception as e:
            break
        
        if str(sol_op) == str(gth_op):
            matched_cnt += 1
        else:
            break
    
    return matched_cnt / len(gth)

def get_heuristic_reward(trial_id, version, trajectory_str):
    v0_reward, v1_reward = 0.0, 0.0
    if 'v0' not in version:
        return v0_reward, v1_reward
    try:
        if trial_id not in TRIAL_MANAGER:
            raise HTTPException(status_code=404, detail="Trial not found")
        trial: Trial = TRIAL_MANAGER[trial_id]
        try:
            his_operators, solution = parse_his_operators_and_solution(trajectory_str)
            logger.log(f'【his_operators】: {his_operators}\n【solution】: {solution}')
        except Exception as e:
            v0_reward = -1.0
            return v0_reward, v1_reward

        # simulate and evaluate the trial
        new_trial = Trial.load_trial(task_id=trial.task.id, split=trial.task.split)

        op_obj_list = []
        reward = 0.0
        for op in solution:
            try:
                op_object: BaseOp = auto_parse_op(op)
                op_obj_list.append(op_object)
            except Exception as e:
                reward -= 0.1
        if reward < 0:
            del new_trial
            v0_reward = 0.0
            return v0_reward, v1_reward

        for op_object in op_obj_list:
            try:
                out_tblname, out_tbl = executor.execute_op(op_object, new_trial)
                executor.step_op(op_object, new_trial, out_tblname, out_tbl)
            except Exception as e:
                v0_reward = 0.0
                del new_trial
                return v0_reward, v1_reward

        try:
            matched, _ = evaluator.evaluate_trial_tables(new_trial)
        except Exception as e:
            matched = False

        if not matched:
            v0_reward = 0.0
            if 'v1' in version:
                v1_reward = evaluator.calculate_similarity_reward(new_trial)
            del new_trial
            return v0_reward, v1_reward
            
        v0_reward = 2.0
        # if any([True for op in solution if 'CodeGeneration' in op]): v0_reward -= 0.5 #!
        del new_trial
        return v0_reward, v1_reward

    except Exception as e:
        v0_reward = -1.0
        logger.log(f"Error parsing trial {trial_id},  trajectory string: {trajectory_str}, Error getting reward: {e}, Reward: {v0_reward}")
        return v0_reward, v1_reward
    
def get_llm_as_judge_reward(trial: Trial, trajectory_str: str, version: str):
    if 'v2' not in version:
        return 0.0
    
    llm_judger = LLMAsJudge(cfg=cfg, log_file=f'{trial.exp_id}_LLMAsJudge')
    
    with ProcessPool(max_workers=128) as pool:
        future = pool.schedule(llm_judger.judge, args=[trial, trajectory_str, True], timeout=600)
        try:
            llm_reward = future.result()
        except TimeoutError:
            llm_reward = 0.5
            logger.log(f"LLM As Judge timed out for trial {trial.exp_id}")
        except Exception as e:
            llm_reward = 0.5
            logger.log(f"Fail to get reward from LLM As Judge for trial {trial.exp_id}: {e}")
            
    return llm_reward

@app.post("/trials/reward", response_model=RewardResponse)
def get_reward(request: RewardRequest):
    trial_id, trajectory_str, version = request.trial_id, request.input_string, request.version

    if trial_id not in TRIAL_MANAGER:
        raise ValueError(f"Trial {trial_id} not found!")
    trial: Trial = TRIAL_MANAGER[trial_id]
    new_trial = Trial.load_trial(task_id=trial.task.id, split=trial.task.split)
    
    v0_reward, v1_reward = get_heuristic_reward(trial_id, version, trajectory_str)
    v2_reward = get_llm_as_judge_reward(new_trial, trajectory_str, version)
    try:
        logger.log(f"Get reward for trial {trial_id} with Trajectory:\n{trajectory_str}, v0_reward: {v0_reward}, v1_reward: {v1_reward}, v2_reward: {v2_reward}")
    except Exception as e:
        pass
    
    return {"reward": v0_reward + v2_reward + v1_reward, 'detailed_rewards': {'heuristic_reward': v0_reward, 'partial_reward': v1_reward, 'llm_as_judge_reward': v2_reward}}
