from __future__ import annotations

from typing import Dict, List, Optional


# UI label -> Config(name=...) name
LLM_CONFIGS: Dict[str, str] = {
    "Gpt-5": "tree_based_agentic_reasoning_gpt5",
    "Claude-4": "tree_based_agentic_reasoning_claude",
    "Doubao-Seed-1.6-Thinking": "tree_based_agentic_reasoning_doubao",
    # NOTE: config file name in `_config/` is `_CONFIG_tree_based_agentic_reasoning_doubao_flash.yaml`
    "Doubao-Seed-1.6-flash": "tree_based_agentic_reasoning_doubao_flash",
    "DeepSeek-R1": "tree_based_agentic_reasoning_r1",
    "DeepSeek-V3.1": "tree_based_agentic_reasoning_v3.1",
}


DEFAULT_CONFIG_NAME = "tree_based_agentic_reasoning_gpt5"


def list_llm_options() -> List[dict]:
    return [{"label": label, "configName": name} for label, name in LLM_CONFIGS.items()]


def label_for_config_name(config_name: str) -> Optional[str]:
    for label, name in LLM_CONFIGS.items():
        if name == config_name:
            return label
    return None


def resolve_config_name(*, label: Optional[str] = None, config_name: Optional[str] = None) -> Optional[str]:
    if config_name:
        # ensure it is one of the known configs
        if config_name in set(LLM_CONFIGS.values()):
            return config_name
        return None
    if label:
        return LLM_CONFIGS.get(label)
    return None
