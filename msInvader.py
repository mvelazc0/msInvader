import yaml
import requests

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

def setup_graph_authentication(tenant_id, client_id, client_secret ):

    scope = 'https://graph.microsoft.com/.default'

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope
    }

    token_r = requests.post(token_url, data=token_data)
    return token_r.json().get('access_token')


def read_email_with_graph(params, token):

    user_email = params['user']
    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/Inbox/messages'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(graph_endpoint, headers=headers)

    if response.status_code == 200:
        print ("OK!")
        messages = response.json().get('value', [])
        for message in messages:
            print(message.get('subject'), message.get('from'))
            body_content = message.get('body', {}).get('content', '')
            #print("Body:", body_content)
    

def main():
    config_path = 'config.yaml'
    config = load_config(config_path)

    # Accessing specific configuration parameters
    client_id = config['application_id']
    tenant_id = config['tenant_id']
    client_secret = config['client_secret']

    # Print these values to verify they are loaded
    print(f"Application ID: {client_id}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Client Secret: {client_secret}")

    token = setup_graph_authentication(tenant_id, client_id, client_secret )


    # Proceeding with technique application as before
    for technique in config['techniques']:
        if technique['technique'] == 'read_email_with_graph':
            read_email_with_graph(technique['parameters'], token)
        # Add more elif branches for other techniques.
            
if __name__ == "__main__":
    main()
        