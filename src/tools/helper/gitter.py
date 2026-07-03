import git
from .config import Config

import logging


logger = logging.getLogger(__name__)


class Gitter:
    
    repo_path = Config.load_base_config().get('git_local_repo')

    @staticmethod
    def set_repo_path(repo_path):
        Gitter.repo_path = repo_path
        Config.load_base_config().set('git_local_repo', repo_path)

    @staticmethod
    def get_repo_path():
        return Gitter.repo_path
    
    @staticmethod
    def get_repo():
        return git.Repo(Gitter.repo_path)

    @staticmethod
    def get_current_branch():
        return Gitter.get_repo().active_branch
    
    @staticmethod
    def get_current_commit():
        return Gitter.get_repo().head.commit
    
    @staticmethod
    def repo_state():
        repo = Gitter.get_repo()
        return repo.git.status()

    @staticmethod
    def check_modified_files():
        repo = Gitter.get_repo()
        # Get all modified files.
        modified_files = [item.a_path for item in repo.index.diff(None)]
        if modified_files:
            logger.info("Files modified before commit:")
            for file in modified_files:
                logger.info("%s", file)
            return True
        else:
            logger.info("No files were modified.")
            return False

    @staticmethod
    def commit_changes(type, msg):
        """Commit changes to the repository

        Args:
            commit_type (str): one of 'feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore'
            description (str): description of the commit
        """
        cfg = Config.load_base_config()
        version = cfg.get('version')

        message = f'[{version}]{type}: {msg}'

        repo = Gitter.get_repo()
        # Add all files, including untracked files.
        repo.git.add(all=True)

        # Check whether there are changes.
        if repo.is_dirty():
            repo.index.commit(message)
        else:
            logger.info("No changes to commit.")

            
    @staticmethod
    def push_changes():
        repo = Gitter.get_repo()
        repo.git.push()


    @staticmethod
    def pull(remote='origin', branch=None):
        repo = Gitter.get_repo()
        if branch is None:
            branch = Gitter.get_current_branch().name
        repo.git.pull(remote, branch)
        logger.info("Pulled updates from %s/%s", remote, branch)
    
    @staticmethod
    def clear_index_cache():
        repo = Gitter.get_repo()
        repo.git.reset()
        logger.info("Cleared Git index cache")