import os
import sys
import copy

import yaml

from _values import CONFIG_PATH, TMP_PATH
from src.tools.utils import clean_filename

class Config:
    def __init__(self, name: str = "default", parallel: bool = False):
        self.config_file_path = os.path.join(CONFIG_PATH, f"_CONFIG_{name}.yaml")
        if not os.path.exists(CONFIG_PATH):
            raise Exception(
                f"Target config directory does not exist at {CONFIG_PATH} :: Something is wrong with the installation."
            )

        if not os.path.exists(self.config_file_path):
            raise Exception(f"Config file {self.config_file_path} does not exist.")

        self.config = self._load_config()
        if "filecachedir" not in self.config:
            # Get the system's temporary directory
            temp_dir = TMP_PATH
            file_cache_dir = os.path.join(temp_dir, "mp")
            self.config["filecachedir"] = file_cache_dir
            self._save_config()

        self.name = name
        self.set_current_config(self.name)
    
    @staticmethod
    def move_next_version(level=3):
        cur_cfg = Config.load_base_config()
        version = cur_cfg.get('version')
        original_version = copy.deepcopy(version)
        vers = [int(x) for x in version.split('.')]
        vers[level-1] += 1
        # all level after level-1 should be reset to 0
        for i in range(level, len(vers)):
            vers[i] = 0
        new_version = '.'.join([str(x) for x in vers])
        cur_cfg.set('version', new_version)
        cur_cfg._save_config()
        print(f"Version updated from {original_version} to {new_version}")
    
    @staticmethod
    def load_current_config():
        current_config_path = os.path.join(CONFIG_PATH, "current_config.yaml")
        if os.path.exists(current_config_path):
            with open(current_config_path, "r", encoding='utf-8') as f:
                current_config_dict = yaml.safe_load(f)
            config_name = current_config_dict.get("current_config_name")
        else:
            config_name = "default"

        return Config(name=config_name)
    
    @staticmethod
    def load_base_config():
        return Config()

    @staticmethod
    def set_current_config(name:str):
        current_config_dict = {"current_config_name": name}
        current_config_path = os.path.join(CONFIG_PATH, "current_config.yaml")
        with open(current_config_path, "w", encoding='utf-8') as f:
            yaml.dump(current_config_dict, f)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def get_version(self):
        return self.config.get("version")

    def set(self, key, value, save=False):
        self.config[key] = value
        if save:
            self._save_config()

    def remove_config(self):
        # check to ensure you don't delete default config
        if self.name == "default":
            raise Exception("Cannot remove default config.")

        # reset current config if this config was the current config
        current_config_path = os.path.join(CONFIG_PATH, "current_config.yaml")
        current_config_dict = {}
        with open(current_config_path, encoding='utf-8') as f:
            current_config_dict = yaml.safe_load(f)

        if current_config_dict["current_config_name"] == self.name:
            current_config_dict["current_config_name"] = "default"

            with open(current_config_path, "w", encoding='utf-8') as f:
                yaml.dump(current_config_dict, f)

        # delete config file
        os.remove(self.config_file_path)

    def _load_config(self):
        """Load YAML configuration from the specified path."""
        try:
            # first load base_config.yaml
            base_config_path = os.path.join(CONFIG_PATH, "base_config.yaml")
            with open(base_config_path, encoding='utf-8') as file:
                base_config = yaml.safe_load(file)
            # then load the config file
            with open(self.config_file_path, encoding='utf-8') as file:
                config = yaml.safe_load(file)
            # merge the two configs, base_config will be overwritten by config
            for k, v in config.items():
                base_config[k] = v
            return base_config
        except Exception as e:
            print(f"Error loading configuration file: {e}")
            sys.exit(1)

    def _save_config(self):
        try:
            # overwrite the key exist in the config file
            with open(self.config_file_path, "r", encoding='utf-8') as file:
                config_dict = yaml.safe_load(file)
            for key, value in self.config.items():
                if key in config_dict:
                    config_dict[key] = value
            with open(self.config_file_path, "w", encoding='utf-8') as file:
                yaml.dump(config_dict, file)


            # save base_config.yaml
            with open(os.path.join(CONFIG_PATH, "base_config.yaml"), "r", encoding='utf-8') as file:
                base_config_dict = yaml.safe_load(file)
            for key, value in self.config.items():
                if key in base_config_dict:
                    base_config_dict[key] = value
            with open(os.path.join(CONFIG_PATH, "base_config.yaml"), "w", encoding='utf-8') as file:
                yaml.dump(base_config_dict, file)
        except Exception as e:
            print(f"Error saving configuration file: {e}")
            sys.exit(1)

    def __str__(self):
        return yaml.dump(self.config)