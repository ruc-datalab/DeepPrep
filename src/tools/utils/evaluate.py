import re
from typing import List

from .standardize import clean_str
from .parse_output import parse_any_string


import re
import pandas as pd
from typing import List, Union
import os
import pandas as pd


def wikit_if_hit(pred, label):
    pred = pred.lower()
    label = label.lower()
    if '|' in label:
        labs = [clean_str(x) for x in label.split('|')]
        preds = [clean_str(x) for x in pred.split('|')]
        all_match = True
        for l in labs:
            if l not in preds:
                all_match = False
                break
        if all_match:
            return True
    else:
        if clean_str(label) == clean_str(pred) or \
            clean_str(label) in clean_str(pred):
            return True
    return False

def tablefact_if_hit(pred, label):
    pred = str(pred).lower()
    label = str(label).lower()
    pred = parse_any_string(pred)
    if label == '1':
        return pred == 'true'
    else:
        return pred == 'false'

def match_str(s:str, rule: str):
    regex = re.compile(rule)

    if regex.fullmatch(s):
        return True
    return False


def match_str_with_re_rules(s:str, rules: List[str]):
    for rule in rules:
        if match_str(s, rule):
            return True
    return False
    