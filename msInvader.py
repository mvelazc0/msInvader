import yaml
from src.ews_client import *
from src.graph_client import *
from src.rest_client import *
from src.auth import *
import logging
import argparse

### Other

tokens = {}
banner = """

                _____                     _           
               |_   _|                   | |          
  _ __ ___  ___  | |  _ ____   ____ _  __| | ___ _ __ 
 | '_ ` _ \/ __| | | | '_ \ \ / / _` |/ _` |/ _ \ '__|
 | | | | | \__ \_| |_| | | \ V / (_| | (_| |  __/ |   
 |_| |_| |_|___/_____|_| |_|\_/ \__,_|\__,_|\___|_|   
                                
                        M365/Azure Adversary Simulation
                        https://github.com/mvelazc0/msInvader
                       
                                   by Mauricio Velazco                                                      
                                             @mvelazco
"""

def load_config(file_path):
    """Load and return the configuration from a YAML file."""
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found at: {file_path}")
        exit(1)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing the YAML file: {e}")
        exit(1)
"""
def setup_logging(level):
    #logging.basicConfig(format='%(asctime)s - [%(levelname)s ]- %(message)s',
    logging.basicConfig(format='%(asctime)s [+] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=level)
"""

def setup_logging(level):

    custom_formats = {
        logging.INFO: "%(asctime)s [+] %(message)s",
        logging.ERROR: "%(asctime)s [!] %(message)s",
        "DEFAULT": "%(asctime)s [%(levelname)s] - %(message)s",
    }    
    custom_time_format = "%Y-%m-%d %H:%M:%S"

    class CustomFormatter(logging.Formatter):

        def __init__(self, fmt=None, datefmt=None, style='%'):
            super().__init__(fmt, datefmt=custom_time_format, style=style)        

        def format(self, record):
            # Set the default format
            self._style._fmt = custom_formats.get(record.levelno, custom_formats["DEFAULT"])
            return super().format(record)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomFormatter())
    root_logger.addHandler(console_handler) 
    root_logger.setLevel(level)


def add_token(session_name, scope, access_token, refresh_token, expiry):

    if session_name not in tokens:
        tokens[session_name] = {}
    tokens[session_name][scope] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expiry": expiry
    }

def get_token(session_name, scope):

    session_tokens = tokens.get(session_name)
    if not session_tokens:
        return None  

    token_info = session_tokens.get(scope)
    if token_info:
        #if token_info["expiry"] > time.time():
        return token_info["access_token"]  
        #else:
            # Token expired; refresh it
        #    return refresh_access_token(session_name, scope, token_info["refresh_token"])
    return None

"""
def refresh_access_token(session_name, scope, refresh_token):
    
    # Simulate a refresh token API call (replace with actual logic)
    new_access_token = f"new_{scope}_access_token_for_{session_name}"
    new_refresh_token = f"new_{scope}_refresh_token_for_{session_name}"
    new_expiry = time.time() + 3600  # 1 hour expiry

    # Update the token storage
    add_token(session_name, scope, new_access_token, new_refresh_token, new_expiry)
    return new_access_token
"""

def main():

    setup_logging(logging.INFO)
    print (banner)

    parser = argparse.ArgumentParser(description='msInvader - M365/Azure Adversary Simulation - https://github.com/mvelazc0/msInvader')

    parser.add_argument('-c', dest='config', type=str, help='Configuration file')
    args = parser.parse_args()

    if args.config:
        config_path = args.config
    else:
        config_path = 'config.yml'    
    
    config = load_config(config_path)

    for session_name, session_details in config["authentication"]["sessions"].items():
        
        print (session_name)
        print (session_details)
        print(graph_scope)
        token = get_ms_token(config['authentication'], session_details['type'], graph_scope)
        add_token(session_name, "graph", token['access_token'], token['refresh_token'], "0")
        
        ews_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], token['refresh_token'], ews_scope)
        add_token(session_name, "ews", ews_token['access_token'], ews_token['refresh_token'], "0")

        rest_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], token['refresh_token'], rest_scope)
        add_token(session_name, "rest", rest_token['access_token'], rest_token['refresh_token'], "0")        
        
        #print(tokens)
        


    logging.info("************* Starting playbook execution *************")

    for playbook in config['playbooks']:
        playbook_name = playbook.get('name', 'Unnamed Playbook')
        logging.info(f"Processing playbook: {playbook_name}")
        

        enabled_techniques = [tech for tech in playbook['techniques'] if tech.get('enabled', False)]
        logging.info(f"Identified {len(enabled_techniques)} enabled technique(s) in playbook '{playbook_name}'")
        
    
        for technique in enabled_techniques:
            
            technique_name = technique['technique']
            parameters = technique['parameters']
            session_name = parameters['session']
            access_method = parameters['access_method']
            technique['parameters']['ews_impersionation'] = False
            if config['authentication']['sessions'][session_name]['type'] == 'service_principal':
                technique['parameters']['ews_impersionation'] = True
                
            if technique['technique'] == 'search_mailbox':

                if technique['parameters']['access_method'] == 'graph':
                    pass
                    #search_mailbox_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

            if technique['technique'] == 'search_onedrive':

                if technique['parameters']['access_method'] == 'graph':
                    pass
                    #search_onedrive_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

            if technique['technique'] == 'read_email':

                if technique['parameters']['access_method'] == 'graph':

                    read_email_graph(config['authentication'], technique['parameters'], tokens[session_name]['graph'])

                #elif technique['parameters']['access_method'] == 'ews':

                #    read_email_ews(config['authentication'], technique['parameters'], ews_token['access_token'])
                
                #elif technique['parameters']['access_method'] == 'rest':
                    # Exchange online management does not support Get-Message on M365
                #    logging.error("Technique method not supported")

            elif technique['technique'] == 'create_rule':

                #if technique['parameters']['access_method'] == 'graph':

                #    create_rule_graph(config['authentication'], technique['parameters'], graph_token['acesss_token'])

                if technique['parameters']['access_method'] == 'ews':
                    
                    create_rule_ews(config['authentication'], technique['parameters'], tokens[session_name]['ews'])

                #elif technique['parameters']['access_method'] == 'rest':

                #    create_rule_rest(config['authentication'], technique['parameters'], rest_token['access_token'])

            """
            elif technique['technique'] == 'enable_email_forwarding':

                if technique['parameters']['access_method'] == 'rest':

                    enable_email_forwarding_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

            elif technique['technique'] == 'add_folder_permission':

                if technique['parameters']['access_method'] == 'rest':

                    modify_folder_permission_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

                if technique['parameters']['access_method'] == 'ews':
        
                    modify_folder_permission_ews(config['authentication'], technique['parameters'], ews_token['access_token'])      

            elif technique['technique'] == 'add_mailbox_delegation':

                if technique['parameters']['access_method'] == 'rest':

                    add_mailbox_delegation_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

            elif technique['technique'] == 'run_compliance_search':

                if technique['parameters']['access_method'] == 'rest':

                    run_compliance_search_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

            elif technique['technique'] == 'create_mailflow_rule':

                if technique['parameters']['access_method'] == 'rest':

                    create_mailflow_rule_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

            elif technique['technique'] == 'password_spray':

                password_spray(technique['parameters'])

            elif technique['technique'] == 'add_application_secret':
                
                add_application_secret_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

            elif technique['technique'] == 'add_service_principal':
                
                add_service_principal(config['authentication'], technique['parameters'], graph_token['access_token'])

            elif technique['technique'] == 'admin_consent':
                
                admin_consent_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

            elif technique['technique'] == 'create_app':
                
                app_id = create_application_registration(config['authentication'], technique['parameters'], graph_token['access_token'])
                app_id = app_id.get('appId')
                technique['parameters']['app_id']= app_id
                add_service_principal(config['authentication'],technique['parameters'], graph_token['access_token'])

            elif technique['technique'] == 'send_mail':
                
                send_email_graph(config['authentication'], technique['parameters'], graph_token['access_token'])
            """                
                
            """
            # Retrieve the token for the session
            token = token_manager.get_token(session_name)
            if not token:
                logging.error(f"No token found for session '{session_name}'. Skipping technique '{technique_name}'.")
                continue
            
            # Execute the technique based on its name and access method
            if technique_name == 'search_mailbox':
                if access_method == 'graph':
                    search_mailbox_graph(parameters, token)
                elif access_method == 'rest':
                    search_mailbox_rest(parameters, token)
                # Add other access methods if necessary
            
            elif technique_name == 'create_rule':
                if access_method == 'graph':
                    create_rule_graph(parameters, token)
                elif access_method == 'rest':
                    create_rule_rest(parameters, token)
                # Add other access methods if necessary   
            """   

    """
    
    enabled_techniques = [tech for tech in config['techniques'] if tech['enabled']]
    methods = list(set([tech['parameters']['access_method'] for tech in enabled_techniques]))

    graph_token = {'access_token': None, 'refresh_token': None}
    ews_token = {'access_token': None, 'refresh_token': None}
    rest_token = {'access_token': None, 'refresh_token': None}

    logging.info(f"Identified {len(enabled_techniques)} enabled technique(s) on configuration file")

    if 'auth_method ' in config['authentication'].keys():
        logging.info(f"Obtaining authentication tokens required to execute simulations")
        for method in methods:
            if method == 'rest':
                rest_token = get_ms_token(config['authentication'], config['authentication']['auth_method'], rest_scope)
            
            elif method == 'ews':
                ews_token = get_ms_token(config['authentication'], config['authentication']['auth_method'], ews_scope)

            elif method == 'graph':
                graph_token= get_ms_token(config['authentication'], config['authentication']['auth_method'], graph_scope)
                #ews_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], ews_scope)

    logging.info("************* Starting technique execution *************")
    
    for technique in enabled_techniques:

        if technique['technique'] == 'search_mailbox':

            if technique['parameters']['access_method'] == 'graph':

                search_mailbox_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

        if technique['technique'] == 'search_onedrive':

            if technique['parameters']['access_method'] == 'graph':

                search_onedrive_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

        if technique['technique'] == 'read_email':

            if technique['parameters']['access_method'] == 'graph':

                read_email_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

            elif technique['parameters']['access_method'] == 'ews':

                read_email_ews(config['authentication'], technique['parameters'], ews_token['access_token'])
            
            elif technique['parameters']['access_method'] == 'rest':
                # Exchange online management does not support Get-Message on M365
                logging.error("Technique method not supported")

        elif technique['technique'] == 'create_rule':

            if technique['parameters']['access_method'] == 'graph':

                create_rule_graph(config['authentication'], technique['parameters'], graph_token['acesss_token'])

            elif technique['parameters']['access_method'] == 'ews':

                create_rule_ews(config['authentication'], technique['parameters'], ews_token['access_token'])

            elif technique['parameters']['access_method'] == 'rest':

                create_rule_rest(config['authentication'], technique['parameters'], rest_token['access_token'])

        elif technique['technique'] == 'enable_email_forwarding':

            if technique['parameters']['access_method'] == 'rest':

                enable_email_forwarding_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

        elif technique['technique'] == 'add_folder_permission':

            if technique['parameters']['access_method'] == 'rest':

                modify_folder_permission_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

            if technique['parameters']['access_method'] == 'ews':
    
                modify_folder_permission_ews(config['authentication'], technique['parameters'], ews_token['access_token'])      

        elif technique['technique'] == 'add_mailbox_delegation':

            if technique['parameters']['access_method'] == 'rest':

                add_mailbox_delegation_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

        elif technique['technique'] == 'run_compliance_search':

            if technique['parameters']['access_method'] == 'rest':

                run_compliance_search_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

        elif technique['technique'] == 'create_mailflow_rule':

            if technique['parameters']['access_method'] == 'rest':

                create_mailflow_rule_rest(config['authentication'], technique['parameters'], rest_token['access_token'])      

        elif technique['technique'] == 'password_spray':

            password_spray(technique['parameters'])

        elif technique['technique'] == 'add_application_secret':
            
            add_application_secret_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

        elif technique['technique'] == 'add_service_principal':
            
            add_service_principal(config['authentication'], technique['parameters'], graph_token['access_token'])

        elif technique['technique'] == 'admin_consent':
            
            admin_consent_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

        elif technique['technique'] == 'create_app':
            
            app_id = create_application_registration(config['authentication'], technique['parameters'], graph_token['access_token'])
            app_id = app_id.get('appId')
            technique['parameters']['app_id']= app_id
            add_service_principal(config['authentication'],technique['parameters'], graph_token['access_token'])

        elif technique['technique'] == 'send_mail':
            
            send_email_graph(config['authentication'], technique['parameters'], graph_token['access_token'])

    """

    logging.info("************* Finished technique execution *************")

    

if __name__ == "__main__":
    main()
        