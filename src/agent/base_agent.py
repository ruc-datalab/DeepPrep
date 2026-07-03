from src.tools.helper import Config, Logger

class BaseAgent:
    def __init__(self, name: str, cfg=None, log_file='_MAIN'):
        self.cfg = Config.load_base_config() if cfg is None else cfg
        self.logger = Logger(name=name, cfg=self.cfg, log_file=log_file)
        self.name = name
        self.MAX_ERR_CNT = self.cfg.get('agent_max_err_cnt')
        self._clear_state()

    def _clear_state(self):
        self.MAX_ERR_CNT = self.cfg.get('agent_max_err_cnt')
        self.err_raise_cnt = 0
        self.last_log = None

    def _raise_error(self, error_message):
        self.last_log = str(error_message)
        self.logger.log(f'{self.name}:' + str(error_message), level='error')
        self.err_raise_cnt += 1
        if self.err_raise_cnt >= self.MAX_ERR_CNT:
            self.logger.log(f'{self.name}:' + str(error_message), level='error')
            self.err_raise_cnt = 0
            raise ValueError(f'Agent {self.name}: Error raised more than {self.MAX_ERR_CNT} times')
        
