from src.tools import Gitter, Config

import logging


logger = logging.getLogger(__name__)


cfg = Config.load_base_config()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

update_version = input("Update Version? (y/n): ").strip().lower()
if update_version == 'e':
    exit(0)
if update_version == 'y':
    udpate_level = input("Update level (1: major, 2: minor, 3: patch): ").strip()
    if udpate_level == 'e':
        exit(0)
    if udpate_level not in ['1', '2', '3']:
        logger.warning("Invalid level. Defaulting to patch.")
        udpate_level = '3'
    cfg.move_next_version(level=int(udpate_level))

logger.info("Current Version: %s", cfg.get('version'))

current_commit = Gitter.get_current_commit()
current_branch = Gitter.get_current_branch()
logger.info("Current commit `%s` on branch `%s`.", current_commit, current_branch)

modified_files = Gitter.check_modified_files()
logger.info("Modified Files: %s", modified_files)

if modified_files:
    commit_type = input("Input commit type (e.g., feat, fix, docs, style, refactor, perf, test): ").strip()
    if commit_type == 'e':
        exit(0)
    comment = input("Commit comment: ").strip()
    if comment == 'e':
        exit(0)
    Gitter.commit_changes(type=commit_type, msg=comment)
else:
    logger.info("No modified files to commit.")

# Ask whether to push.
push = input("Push to Remote? (y/n): ").strip().lower()
if push == 'e':
    exit(0)
if push == 'y':
    Gitter.push_changes()
else:
    logger.info("No push made.")