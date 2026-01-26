import yaml
import os

def load_config():
    print(f"Current working directory: {os.getcwd()}") 
    config_path = "SR-dev/harvester/member_states/norway/config.yaml"
    print(f"Config path: {config_path}")
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

