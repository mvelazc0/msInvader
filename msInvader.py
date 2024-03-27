import yaml
from src.ews_client import *
from src.graph_client import *
from src.auth import *

### Other

def load_config(file_path):
    """Load and return the configuration from a YAML file."""
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        print(f"Configuration file not found at: {file_path}")
        exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing the YAML file: {e}")
        exit(1)

def main():
    config_path = 'config.yml'
    config = load_config(config_path)

    # Accessing specific configuration parameters
    #client_id = config['application_id']
    #tenant_id = config['tenant_id']
    #client_secret = config['client_secret']

    # Print these values to verify they are loaded
    #print(f"Application ID: {client_id}")
    #print(f"Tenant ID: {tenant_id}")
    #print(f"Client Secret: {client_secret}")

    ews_scope   = "https://outlook.office365.com/.default"
    graph_scope = "https://graph.microsoft.com/.default"


    # Proceeding with technique application as before
    for technique in config['techniques']:
        if technique['enabled'] == True and technique['technique'] == 'read_email_with_graph':
            token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], graph_scope)
            read_email_with_graph(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'read_email_with_ews':
            token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
            read_email_with_ews(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'create_rule_with_graph':
            token = get_ms_token(config['authentication'], technique['auth_type'])
            create_rule_with_graph(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'enable_email_forwarding_ews':
            token = get_ms_token(config['authentication'], technique['auth_type'])
            enable_email_forwarding_with_ews(technique['parameters'], token)            
            
if __name__ == "__main__":
    main()
        