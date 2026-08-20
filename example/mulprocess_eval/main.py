import os, sys, random, argparse
import time
# print(os.path.dirname(os.path.abspath(__file__)))
# os.chdir(os.path.dirname(os.path.abspath(__file__)))
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.data import Task, Trial
from src.framework import *
from src.physicalop import *
from src.tools.utils import save_pickle, load_jsonl, unset_proxy, all_filepaths_in_dir, load_pickle, set_proxy
from src.tools.helper import MultiProcesser, Logger, Config
from typing import List
# random.seed(time.time())
random.seed(914)

def load_tasks(args):
    processed_tasks = []
    for fn in all_filepaths_in_dir(os.path.join(cfg.get('filecachedir'), f"versions", cfg.get_version(), 'saved_trials')):
        base_name = os.path.basename(fn)
        task_id = base_name.split('.')[0]
        processed_tasks.append(task_id)

    tasks = []
    inses = load_jsonl(os.path.join(cfg.get('data_root'), cfg.get('benchmark'), f"{args.split}/benchmark.jsonl"))
    for ins in inses:
        id = ins["task_id"]
        if id in processed_tasks:
            continue
        inp_tbls = ins["input_table"]
        tgt_tbl = ins["target_table"]
        tgt_tbl_description = ins["question"] if "question" in ins else ins["intent"]
        if os.path.exists(os.path.join(cfg.get('filecachedir'), f"versions", cfg.get_version(), 'saved_trials', f"{id}.pkl")):
            log.log(f"Task {id} already exists, skipping...")
            continue
        task = Task(id=id, inp_tbl_names=inp_tbls, tgt_tbl_name=tgt_tbl, 
                    split=args.split, tgt_tbl_description=tgt_tbl_description)
        tasks.append((task,))
    log.log(f"Loaded {len(tasks)} tasks.")
    return tasks

def process_one_task(task: Task):
    try:
        framework = cfg.get('framework')
        if framework == "tree_based_agentic_reasoning":
            mas = TreeBasedAgenticReasoning(cfg, log_file=task.id)
        else:
            raise ValueError(f"Unknown framework: {framework}")
        trial = mas.run(task)
    except Exception as e:
        log.log(f"Error processing task {task.id}: {e}")
        trial = None
    return trial

def print_final_result():
    hit, success_process = 0, 0
    total = len(load_jsonl(os.path.join(cfg.get('data_root'), cfg.get('benchmark'), f"{args.split}/benchmark.jsonl"))) if args.limit == -1 else args.limit
    # load all trials
    fns = all_filepaths_in_dir(os.path.join(cfg.get('filecachedir'), f"versions", cfg.get_version(), 'saved_trials'))
    for fn in fns:
        try:
            trial = load_pickle(fn)
            # if has attribute matched and is True
            if hasattr(trial, 'matched') and trial.matched:
                hit += 1
            success_process += 1
        except Exception as e:
            log.log(f"Error loading trial {fn}: {e}")
            continue
    log.log(f"Hit: {hit}, Total: {success_process}, Accuracy: {hit/total}")

parser = argparse.ArgumentParser(description="select bq or sf")

parser.add_argument("--cfg", type=str, default="tree_based_agentic_reasoning_doubao", help="Config name")
parser.add_argument("--benchmark", type=str, default="", help="benchmark name")
parser.add_argument("--max_turn", type=int, default=-1, help="maximum number of turns")
parser.add_argument("--v_name", type=str, default="", help="version of the agent")
parser.add_argument("--n", type=int, default=1, help="number of processes to use")
parser.add_argument("--limit", type=int, default=-1, help="number of instances to process")
parser.add_argument("--nextv", action='store_true', help="enable next version mode")
parser.add_argument("--split", type=str, default="test", help="split of the data")
parser.add_argument("--dt", type=str, default="", help="This is the date of the data")
args = parser.parse_args()

if args.cfg == "":
    cfg = Config.load_base_config()
else:
    cfg = Config(name=args.cfg)

set_proxy(cfg.get('proxy'))

# get mm-dd-hhmm value of the today
if args.dt == "":
    today = time.strftime("%m%d-%H%M")
else:
    today = args.dt
if args.benchmark != "":
    cfg.set("benchmark", args.benchmark)

llm_name = 'llm_group' + '_' + cfg.get('real_llm_name')[0] if isinstance(cfg.get('llm_name'), list) else cfg.get('llm_name').split('-')[0]
if llm_name == 'ep':
    llm_name = args.cfg.split('_')[-1]
cfg.set("version", f"{today}-{cfg.get('benchmark')}-{args.split}-{'total' if args.limit == -1 else args.limit}-{cfg.get('framework')}-exe_{cfg.get('execute_mode')}-{llm_name}", False)

if cfg.get('framework') == 'tree_based_agentic_reasoning' and args.max_turn > 0:
    if args.max_turn > 6:
        cfg.set("max_input_limit", 60000)
    cfg.set("max_explore_turn", args.max_turn)
    cfg.set("version", f"{cfg.get('version')}-turn{args.max_turn}")

log = Logger(name="_MAIN", cfg=cfg)
log.log(str(cfg))
Logger.save_args_files(cfg=cfg, arg_dict={'main_args': args}, files_to_save=['./example/mulprocess_eval/main.py', './src'])
tasks = load_tasks(args)
random.shuffle(tasks)
if args.limit > 0:
    tasks = tasks[:args.limit]
multi_processer = MultiProcesser(num_processes=args.n)
for t in tasks:
    multi_processer.submit_task(process_one_task, *t)
results = multi_processer.wait_for_completion()
print_final_result()












