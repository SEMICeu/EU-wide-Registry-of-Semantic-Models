import yaml
import os

def load_config():
    print(f"Current working directory: {os.getcwd()}") 
    config_path = "SR-dev/harvester/member_states/norway/config.yaml"
    print(f"Config path: {config_path}")
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

config = load_config()

SOURCE_ACCES_URL = f"{config['graphDB_host']}/repositories/{config['graphDB_source_repo_name']}"
TARGET_ACCES_URL = f"{config['graphDB_host']}/repositories/{config['graphDB_target_repo_name']}"
PROVENANCE_ACCES_URL = f"{config['graphDB_host']}/repositories/{config['graphDB_provenance_repo_name']}"