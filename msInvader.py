import yaml
from src.ews_client import *
from src.graph_client import *
from src.rest_client import *
from src.keyvault_client import *
from src.vm_client import *
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

#TODO: Need to re-implement this
def refresh_tokens(config, session_name):

        logging.info("Refresing client credential tokens after assign_app_role")

        session_details= config['authentication']['sessions'][session_name]
    
        graph_token = get_ms_token(config['authentication'], session_details, graph_scope)
        add_token(session_name, "graph", graph_token['access_token'], "0", "0")
        
        ews_token = get_ms_token(config['authentication'], session_details, ews_scope)
        add_token(session_name, "ews", ews_token['access_token'], "0", "0")

        rest_token = get_ms_token(config['authentication'], session_details, rest_scope)
        add_token(session_name, "ews", rest_token['access_token'], "0", "0")    

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
        
        if session_details['type'] != 'client_credentials':
            graph_token = get_ms_token(config['authentication'], session_details, graph_scope)
            add_token(session_name, "graph", graph_token['access_token'], graph_token['refresh_token'], "0")
            
            ews_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], ews_scope)
            add_token(session_name, "ews", ews_token['access_token'], ews_token['refresh_token'], "0")

            rest_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], rest_scope)
            add_token(session_name, "rest", rest_token['access_token'], rest_token['refresh_token'], "0")        
            
            keyvault_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], keyvault_scope)
            add_token(session_name, "keyvault", keyvault_token['access_token'], keyvault_token['refresh_token'], "0")        
            #print(keyvault_token)
        
        else:
            graph_token = get_ms_token(config['authentication'], session_details, graph_scope)
            add_token(session_name, "graph", graph_token['access_token'], "0", "0")
            
            ews_token = get_ms_token(config['authentication'], session_details, ews_scope)
            add_token(session_name, "ews", ews_token['access_token'], "0", "0")
 
            rest_token = get_ms_token(config['authentication'], session_details, rest_scope)
            add_token(session_name, "ews", rest_token['access_token'], "0", "0")
            

            
        
    logging.info("************* Starting playbook execution *************")

    for playbook in config['playbooks']:
        
        playbook_name = playbook.get('name', 'Unnamed Playbook')
        sleep = playbook.get('sleep', 0)
        jitter = playbook.get('jitter', 0)
        
        logging.info(f"Processing playbook: {playbook_name}")
        

        enabled_techniques = [tech for tech in playbook['techniques'] if tech.get('enabled', False)]
        logging.info(f"Identified {len(enabled_techniques)} enabled technique(s) in playbook '{playbook_name}'")
        
    
        #for technique in enabled_techniques:
        for index, technique in enumerate(enabled_techniques):

            technique_name = technique['technique']
            parameters = technique['parameters']
            session_name = parameters.get('session', 'nosession')
            #session_name = parameters['session']
            access_method = parameters['access_method']
            parameters['ews_impersonation'] = False

            
            if session_name != 'nosession' and config['authentication']['sessions'][session_name]['type'] == 'client_credentials':
                parameters['ews_impersonation'] = True
                
            if technique_name == 'search_email':

                if access_method == 'graph':
                    #W
                    search_email_graph(config['authentication'], parameters, tokens[session_name]['graph'])

            if technique_name == 'search_onedrive':
                
                if access_method == 'graph':
                    #W
                    search_onedrive_graph(config['authentication'], parameters, tokens[session_name]['graph'])

            if technique_name == 'read_email':
                
                if access_method == 'graph':
                    #W
                    read_email_graph(config['authentication'], parameters, tokens[session_name]['graph'])

                elif access_method == 'ews':
                    #W
                    read_email_ews2(config['authentication'], parameters, tokens[session_name]['ews'])
                
                #elif access_method == 'rest':
                    # Exchange online management does not support Get-Message on M365
                #    logging.error("Technique method not supported")

            elif technique_name == 'create_rule':

                if access_method == 'graph':
                    #NW
                    create_rule_graph(config['authentication'], parameters, tokens[session_name]['graph'])

                if access_method == 'ews':
                    #W
                    create_rule_ews2(config['authentication'], parameters, tokens[session_name]['ews'])

                elif access_method == 'rest':
                    #W
                    create_rule_rest(config['authentication'], parameters, tokens[session_name]['rest'])

            elif technique_name == 'enable_email_forwarding':

                if access_method == 'rest':
                    #W
                    enable_email_forwarding_rest(config['authentication'], parameters, tokens[session_name]['rest'])      

            elif technique_name == 'add_folder_permission':

                if access_method == 'rest':
                    #W
                    modify_folder_permission_rest(config['authentication'], parameters, tokens[session_name]['rest'])      

                if access_method == 'ews':
                    #W
                    modify_folder_permission_ews(config['authentication'], parameters, tokens[session_name]['ews'])      

            elif technique_name == 'add_mailbox_delegation':

                if access_method == 'rest':
                    #W. 
                    # Requires exchange admin
                    add_mailbox_delegation_rest(config['authentication'], parameters, tokens[session_name]['rest'])      

            elif technique_name == 'run_compliance_search':

                if access_method == 'rest':
                    #NW
                    # Requires exchange admin
                    run_compliance_search_rest(config['authentication'], parameters, tokens[session_name]['rest'])      

            elif technique_name == 'create_mailflow_rule':

                if access_method == 'rest':
                    #W
                    create_mailflow_rule_rest(config['authentication'], parameters, tokens[session_name]['rest'])      

            elif technique_name == 'password_spray':
                #W
                password_spray(technique['parameters'])

            elif technique_name == 'add_application_secret':
                #W
                add_application_secret_graph(config['authentication'], parameters, tokens[session_name]['graph'])

            elif technique_name == 'add_service_principal':
                
                add_service_principal(config['authentication'], parameters, tokens[session_name]['graph'])

            elif technique_name == 'admin_consent':
                
                admin_consent_graph(config['authentication'], parameters, tokens[session_name]['graph'])

            elif technique_name == 'create_app':
                
                app_id = create_application_registration(config['authentication'], technique['parameters'], tokens[session_name]['graph'])
                app_id = app_id.get('appId')
                technique['parameters']['app_id']= app_id
                add_service_principal(config['authentication'],parameters, tokens[session_name]['graph'])

            elif technique_name == 'send_mail':
                ##
                send_email_graph(config['authentication'], parameters, tokens[session_name]['graph'])  
                

            elif technique_name == 'enumerate_users':
                #W
                enumerate_entities(config['authentication'], parameters, "users", tokens[session_name]['graph'])                  

            elif technique_name == 'enumerate_groups':
                #W
                enumerate_entities(config['authentication'], parameters, "groups", tokens[session_name]['graph'])    
                
            elif technique_name == 'enumerate_applications':
                #W
                enumerate_entities(config['authentication'], parameters, "applications", tokens[session_name]['graph'])    
                
            elif technique_name == 'enumerate_service_principals':
                #W
                enumerate_entities(config['authentication'], parameters, "service_principals", tokens[session_name]['graph']) 

            elif technique_name == 'enumerate_directory_roles':
                #W
                enumerate_entities(config['authentication'], parameters, "directory_roles", tokens[session_name]['graph']) 

            elif technique_name == 'change_password':
                #W
                change_user_password(config['authentication'], parameters, tokens[session_name]['graph']) 
  
            elif technique_name == 'assign_app_role':
                #W
                assign_app_role2(config['authentication'], parameters, tokens[session_name]['graph']) 
                time.sleep(20)
                refresh_tokens(config, session_name )

            elif technique_name == 'create_user':
                #W
                create_user_graph(config['authentication'], parameters, tokens[session_name]['graph']) 

            elif technique_name == 'assign_entra_role':
                #W
                assign_entra_role_graph(config['authentication'], parameters, tokens[session_name]['graph']) 

            elif technique_name == 'list_key_vaults':
                
                list_key_vaults(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'list_keyvault_items':
                
                list_keyvault_items(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'access_key_vault_item':
                
                access_key_vault_item(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'add_keyvault_access_policy':
                
                add_keyvault_access_policy(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'execute_command':
                
                vm_execute_command(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'list_extensions':
                
                vm_list_extensions(config['authentication'], parameters, tokens[session_name]['keyvault'])                 
                
            # Apply sleep only if this is not the last technique
            if index < len(enabled_techniques) - 1:
                if sleep is not None:
                    if jitter is not None:
                        time.sleep(sleep + random.uniform(0, jitter))
                    else:
                        time.sleep(sleep)

    logging.info("************* Finished technique execution *************")

    

if __name__ == "__main__":
    main()
        