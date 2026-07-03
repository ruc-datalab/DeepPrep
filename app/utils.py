import os
import json
import re
from typing import List
from src.tools.helper import Config
from src.tools.utils import set_proxy, load_jsonl

def load_his_exps(his_exps_path):
    his_exps = {}
    if os.path.exists(his_exps_path):
        with open(his_exps_path, 'r', encoding='utf-8') as f:
            his_exps = json.load(f)
    return his_exps

def load_gold_dict(eval_gold_path):
    gold_data = load_jsonl(eval_gold_path)
    gold_dict = {entry['instance_id']: entry for entry in gold_data}
    return gold_dict

def load_config_and_paths(cfg: Config):
    proxy = cfg.get("proxy")
    set_proxy(proxy)

    spider2_repo_path = cfg.get('spider2_repo_path')
    default_llm_name = cfg.get("default_llm_name")
    eval_gold_root = os.path.join(spider2_repo_path, 'spider2/evaluation_suite/gold')
    result_root = os.path.join(spider2_repo_path, 'methods/spider-agent/output/_server/results')
    submission_dir = os.path.join(spider2_repo_path, 'methods/spider-agent/output/_server/submission')
    eval_gold_path = os.path.join(eval_gold_root, "spider2_eval.jsonl")
    his_exps_path = os.path.join(cfg.get('filecachedir'), 'app', 'his_exps.json')
    test_path = os.path.join(spider2_repo_path, 'spider2/examples/exist_spider2.jsonl')
    source_data_dir = os.path.dirname(test_path)

    return spider2_repo_path, default_llm_name, eval_gold_root, result_root, submission_dir, eval_gold_path, his_exps_path, test_path, source_data_dir

def load_instanceid2instruction_type(test_path):
    assert os.path.exists(test_path) and test_path.endswith(".jsonl"), f"Invalid test_path, must be a valid jsonl file: {test_path}"
    with open(test_path, "r") as f:
        task_configs = [json.loads(line) for line in f]
    instance_id2instruction = {}
    instance_id2type = {}
    for task_config in task_configs:
        instance_id = task_config["instance_id"]
        instruction = task_config["instruction"]
        type_ = task_config["type"]
        instance_id2instruction[instance_id] = instruction
        instance_id2type[instance_id] = type_
    return instance_id2instruction, instance_id2type

def update_configs(source_data_dir, instance_id, env_config, task_config):
    task_type = None
    if instance_id.startswith("bq") or instance_id.startswith("ga"):
        task_type = 'bq'
    elif instance_id.startswith("local"):
        task_type = 'local'
    elif instance_id.startswith("sf"):
        task_type = 'sf'
    elif instance_id.startswith("ch0"):
        task_type = 'ch'
    elif instance_id.startswith("postgres"):
        task_type = 'pg'
    else:
        task_type = 'dbt'

    if task_type == 'pg':
        env_config["image_name"] = "spider_agent_postgres-image"
        task_config['config'] = [{"type": "copy_all_subfiles_postgres", "parameters": {"dirs": [os.path.join(source_data_dir, instance_id)]}}]
    elif task_type == 'ch':
        env_config["image_name"] = "spider_agent_clickhouse-image"
        task_config['config'] = [{"type": "copy_all_subfiles_clickhouse", "parameters": {"dirs": [os.path.join(source_data_dir, instance_id)]}}]
    else:
        env_config["image_name"] = "spider_agent-image"
        task_config['config'] = [{"type": "copy_or_link_all_subfiles", "parameters": {"dirs": [os.path.join(source_data_dir, instance_id)]}}]

    return env_config, task_config

def get_configs(source_data_dir, instance_id, exp_id, instance_id2instruction, instance_id2type):
    task_config = {
        'instance_id': instance_id,
        'instruction': instance_id2instruction[instance_id] if instance_id in instance_id2instruction else '',
        'type': instance_id2type[instance_id] if instance_id in instance_id2type else '',
    }
    env_config = {
        "init_args": {
            "name": exp_id,
            "work_dir": "/workspace",
        },
    }

    env_config, task_config = update_configs(source_data_dir, instance_id, env_config, task_config)
    return env_config, task_config

    