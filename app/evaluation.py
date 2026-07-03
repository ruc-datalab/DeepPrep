from evaluation_suite.eval_utils import number_match, string_match, table_match, duckdb_match, tables_match, get_bigquery_sql_result
import os
from typing import List

def evaluate(eval_gold_root, exp_id, instance_id, metadata, gold_dict, result_root):
    gold_script_data = gold_dict[instance_id]
    data = {**gold_script_data, **metadata}

    output_dict = data
    eval_metadata = data['evaluation']
        
    if not isinstance(eval_metadata, list):
        eval_metadatas = [eval_metadata]
    else:
        eval_metadatas = eval_metadata
        
    score = 0
    if data['answer_type'] == 'answer':
        temp_scores = []
        for eval_metadata in eval_metadatas:
            try:
                if eval_metadata['func'] == 'string_match':
                    score = string_match(data['answer_or_path'], **eval_metadata['parameters'])
                elif eval_metadata['func'] == 'number_match':
                    score = number_match(data['answer_or_path'], **eval_metadata['parameters'])
                temp_scores.append(score)
            except:
                import pdb; pdb.set_trace()
        score = max(temp_scores)
                    
    elif data['answer_type'] == 'file':
        if data['answer_or_path'].endswith('.sql'):
            sql_query = open(os.path.join(result_root, exp_id, data['answer_or_path']), 'r').read()
            get_bigquery_sql_result(sql_query, is_save=True, save_dir=os.path.join(result_root, exp_id), save_file='pred_result.csv')
            data['answer_or_path'] = 'pred_result.csv'

        for eval_metadata in eval_metadatas:
            if eval_metadata['func'] == 'table_match':
                if isinstance(eval_metadata['parameters']['gold'], str):
                    eval_metadata['parameters']['gold'] = os.path.join(eval_gold_root, instance_id, eval_metadata['parameters']['gold'])
                elif isinstance(eval_metadata['parameters']['gold'], List):
                    eval_metadata['parameters']['gold'] = [os.path.join(eval_gold_root, instance_id, gold_file) for gold_file in eval_metadata['parameters']['gold']]
                try:
                    score = table_match(os.path.join(result_root, exp_id, data['answer_or_path']), **eval_metadata['parameters'])
                except:
                    print(f"ERROR: {exp_id}")
                    score = 0
            elif eval_metadata['func'] == 'duckdb_match':
                eval_metadata['parameters']['gold'] = os.path.join(eval_gold_root, instance_id, eval_metadata['parameters']['gold'])
                try:
                    score = duckdb_match(os.path.join(result_root, exp_id, data['answer_or_path']), **eval_metadata['parameters'])    
                except:
                    score = 0
        
    elif data['answer_type'] == 'files':
        eval_metadata['parameters']['gold'] = [ os.path.join(eval_gold_root, instance_id, gold_item) for gold_item in eval_metadata['parameters']['gold']   ]
        results_data = [os.path.join(result_root,exp_id, path) for path in  data['answer_or_path']]
        score = tables_match(results_data, **eval_metadata['parameters'])

    if score == 1:
        print(data)   
                    
    output_dict['score'] = score
    
    return output_dict
    