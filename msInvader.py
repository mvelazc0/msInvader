import yaml
import json
from src.ews_client import *
from src.graph_client import *
from src.rest_client import *
from src.keyvault_client import *
from src.vm_client import *
from src.arm_client import *
from src.device_client import *
from src.auth import *
from src.graph_client import prt_scope, graph_scope
import logging
import argparse
import time
import random

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

    # Persist tokens to disk for debugging
    save_tokens_to_disk(session_name, scope, access_token, refresh_token)


def save_tokens_to_disk(session_name, scope, access_token, refresh_token):
    """Save tokens to disk for debugging/reuse without re-authentication"""
    import json
    from datetime import datetime

    token_file = f"tokens_{session_name}_{scope.replace('/', '_').replace('.', '_').replace(':', '')}.json"

    token_data = {
        "session": session_name,
        "scope": scope,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "saved_at": datetime.utcnow().isoformat()
    }

    try:
        with open(token_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        logging.debug(f"Tokens saved to {token_file}")
    except Exception as e:
        logging.error(f"Failed to save tokens to disk: {e}")

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

    """
    for session_name, session_details in config["authentication"]["sessions"].items():
        
        if session_details['type'] != 'client_credentials':
            # Use custom scope if specified in session config, otherwise default to graph_scope
            scope = session_details.get('scope', graph_scope)
            graph_token = get_ms_token(config['authentication'], session_details, scope)
            add_token(session_name, "graph", graph_token['access_token'], graph_token['refresh_token'], "0")

            #ews_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], ews_scope)
            #add_token(session_name, "ews", ews_token['access_token'], ews_token['refresh_token'], "0")

            #rest_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], rest_scope)
            #add_token(session_name, "rest", rest_token['access_token'], rest_token['refresh_token'], "0")

            #arm_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], arm_scope)
            #add_token(session_name, "arm", arm_token['access_token'], arm_token['refresh_token'], "0")

            ##keyvault_token = get_new_token_with_refresh_token(config['authentication']['tenant_id'], graph_token['refresh_token'], keyvault_scope)
            #dd_token(session_name, "keyvault", keyvault_token['access_token'], keyvault_token['refresh_token'], "0")
        
        else:
            graph_token = get_ms_token(config['authentication'], session_details, graph_scope)
            add_token(session_name, "graph", graph_token['access_token'], "0", "0")
            
            ews_token = get_ms_token(config['authentication'], session_details, ews_scope)
            add_token(session_name, "ews", ews_token['access_token'], "0", "0")
 
            rest_token = get_ms_token(config['authentication'], session_details, rest_scope)
            add_token(session_name, "ews", rest_token['access_token'], "0", "0")
    """            

            
        
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
            access_method = parameters.get('access_method')
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
                    read_email_graph2(config['authentication'], parameters, tokens[session_name]['graph'])

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

            elif technique_name == 'change_user_password':
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
                
                list_key_vaults(config['authentication'], parameters, tokens[session_name]['arm']) 

            elif technique_name == 'list_keyvault_items':
                
                list_keyvault_items(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'access_key_vault_item':
                
                access_key_vault_item(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'add_keyvault_access_policy':
                
                add_keyvault_access_policy(config['authentication'], parameters, tokens[session_name]['arm']) 

            elif technique_name == 'list_keyvault_access_policies':
                
                list_keyvault_access_policies(config['authentication'], parameters, tokens[session_name]['arm']) 

            elif technique_name == 'execute_command':
                
                vm_execute_command(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'execute_custom_script':
                
                execute_custom_script(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'reset_password':
                
                vm_reset_password(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'list_extensions':
                
                vm_list_extensions(config['authentication'], parameters, tokens[session_name]['keyvault'])                 
                
            elif technique_name == 'delete_extension':
                
                vm_remove_extension(config['authentication'], parameters, tokens[session_name]['keyvault']) 

            elif technique_name == 'enumerate_arm_role_assignments':
                
                enumerate_arm_role_assignments(config['authentication'], parameters, tokens[session_name]['arm']) 
                
            elif technique_name == 'enumerate_arm_resources':
                
                enumerate_arm_resources(config['authentication'], parameters, tokens[session_name]['arm'])                 

            elif technique_name == 'enumerate_privileged_arm_role_holders':
                
                enumerate_privileged_arm_role_holders(config['authentication'], parameters, tokens[session_name]['arm'])      

            elif technique_name == 'enumerate_app_role_assignments':

                enumerate_app_role_assignments(config['authentication'], parameters, tokens[session_name]['graph'])

            elif technique_name == 'register_device':

                # Use access token from session instead of doing device code auth again
                if session_name in tokens and 'graph' in tokens[session_name]:
                    access_token = tokens[session_name]['graph'].get('access_token')
                    if access_token:
                        # Pass as token dict in same format as get_drs_token_device_code returns
                        drs_token = {'access_token': access_token}
                        register_device(config['authentication'], parameters, drs_token)
                    else:
                        logging.error(f"No access_token in session '{session_name}' for register_device")
                else:
                    logging.error(f"No tokens available in session '{session_name}' for register_device")

                # # COMMENTED OUT: Alternative approach - do device code auth again for DRS token
                # drs_username = config['authentication']['sessions'][session_name]['username']
                # drs_token = get_drs_token_device_code(config['authentication']['tenant_id'], drs_username)
                # if drs_token:
                #     register_device(config['authentication'], parameters, drs_token)
                # else:
                #     logging.error("Failed to obtain a DRS-scoped token; skipping register_device.")

            elif technique_name == 'get_prt_with_refresh_token':

                # Load refresh_token from file if specified
                if 'refresh_token_file' in parameters and 'refresh_token' not in parameters:
                    try:
                        with open(parameters['refresh_token_file'], 'r') as f:
                            token_data = json.load(f)
                        if 'refresh_token' in token_data:
                            parameters['refresh_token'] = token_data['refresh_token']
                            logging.debug(f"Loaded refresh_token from {parameters['refresh_token_file']}")
                        else:
                            logging.error(f"No 'refresh_token' field in {parameters['refresh_token_file']}")
                    except FileNotFoundError:
                        logging.error(f"refresh_token_file not found: {parameters['refresh_token_file']}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse {parameters['refresh_token_file']}: {e}")

                # Auto-inject refresh_token from session if not provided and not from file
                if 'refresh_token' not in parameters and session_name in tokens:
                    if 'graph' in tokens[session_name]:
                        parameters['refresh_token'] = tokens[session_name]['graph'].get('refresh_token')
                        logging.debug(f"Injected refresh_token from session '{session_name}' into get_prt_with_refresh_token")

                get_prt_with_refresh_token(parameters)

            elif technique_name == 'get_token_with_prt':

                get_token_with_prt(parameters)

            elif technique_name == 'get_prt_with_whfb_key':

                get_prt_with_whfb_key(parameters)

            elif technique_name == 'create_whfb_key':

                # Load access_token from file if specified
                if 'access_token_file' in parameters and 'access_token' not in parameters:
                    try:
                        with open(parameters['access_token_file'], 'r') as f:
                            token_data = json.load(f)
                        if 'access_token' in token_data:
                            parameters['access_token'] = token_data['access_token']
                            logging.debug(f"Loaded access_token from {parameters['access_token_file']}")
                        else:
                            logging.error(f"No 'access_token' field in {parameters['access_token_file']}")
                    except FileNotFoundError:
                        logging.error(f"access_token_file not found: {parameters['access_token_file']}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse {parameters['access_token_file']}: {e}")

                # Pass access token from session to the technique if not already provided
                if 'access_token' not in parameters and session_name in tokens and 'graph' in tokens[session_name]:
                    parameters['access_token'] = tokens[session_name]['graph']['access_token']
                    logging.debug(f"Injected access_token from session '{session_name}' into create_whfb_key")

                if 'access_token' in parameters:
                    create_whfb_key(parameters)
                else:
                    logging.error(f"No access token available for Windows Hello key registration")

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
        
