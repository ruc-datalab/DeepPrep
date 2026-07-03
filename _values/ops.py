TOTAL_OP = {
    'Bash': {
        'args':{
            'code': 'necessary',
        },
        'suffix': {}
    },
    'CreateFile': {
        'args':{
            'filepath': 'necessary',
        },
        'suffix': {
            '[code_with_wrapper]': 'necessary',
        }
    },
    'EditFile': {
        'args':{
            'filepath': 'necessary',
        },
        'suffix': {
            '[code_with_wrapper]': 'necessary',
        }
    },
    'LOCAL_DB_SQL': {
        'args':{
            'file_path': 'necessary',
            'command': 'necessary',
            'output': 'necessary',
        },
        'suffix': {}
    },
    'BIGQUERY_EXEC_SQL': {
        'args':{
            'sql_query': 'necessary',
            'is_save': 'necessary',
            'save_path': 'optional',
        },
        'suffix': {}
    },
    'SNOWFLAKE_EXEC_SQL': {
        'args':{
            'sql_query': 'necessary',
            'is_save': 'necessary',
            'save_path': 'optional',
        },
        'suffix': {}
    },
    'SF_GET_TABLES': {
        'args':{
            'database_name': 'necessary',
            'schema_name': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'SF_GET_TABLE_INFO': {
        'args':{
            'database_name': 'necessary',
            'schema_name': 'necessary',
            'table': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'BQ_GET_TABLES': {
        'args':{
            'database_name': 'necessary',
            'dataset_name': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'GET_TABLE_INFO': {
        'args':{
            'database_name': 'necessary',
            'dataset_name': 'necessary',
            'table': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'BQ_SAMPLE_ROWS': {
        'args':{
            'database_name': 'necessary',
            'dataset_name': 'necessary',
            'table': 'necessary',
            'row_number': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'SF_SAMPLE_ROWS': {
        'args':{
            'database_name': 'necessary',
            'schema_name': 'necessary',
            'table': 'necessary',
            'row_number': 'necessary',
            'save_path': 'necessary',
        },
        'suffix': {}
    },
    'Terminate': {
        'args':{
            'output': 'optional',
        },
        'suffix': {}
    }
}


ABBR2TASKTYPE = {
    'bq': 'BIGQUERY',
    'local': 'LOCAL',
    'sf': 'SNOWFLAKE',
    'ch': 'CLICKHOUSE',
    'pg': 'POSTGRESQL',
    'dbt': 'DBT'
}


TASKTYPE2OP = {
    'Bigquery': ['Bash', 'Terminate', 'BIGQUERY_EXEC_SQL', 'BQ_GET_TABLES', 'BQ_GET_TABLE_INFO', 'BQ_SAMPLE_ROWS', 'CreateFile', 'EditFile'],
    'Snowflake': ['Bash', 'Terminate', 'SNOWFLAKE_EXEC_SQL', 'SF_GET_TABLES', 'SF_GET_TABLE_INFO', 'SF_SAMPLE_ROWS', 'CreateFile', 'EditFile'],
    'Local': ['Bash', 'Terminate', 'CreateFile', 'EditFile', 'LOCAL_DB_SQL'],
    'DBT': ['Bash', 'Terminate', 'CreateFile', 'EditFile', 'LOCAL_DB_SQL'],
    'Postgres': ['Bash', 'Terminate', 'CreateFile', 'EditFile'],
    'Clickhouse': ['Bash', 'Terminate', 'CreateFile', 'EditFile'],
}
