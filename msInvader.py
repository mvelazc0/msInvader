import yaml
from src.ews_client import *
from src.graph_client import *
from src.rest_client import *
from src.keyvault_client import *
from src.vm_client import *
from src.arm_client import *
from src.device_client import *
from src.auth import *
from src.engine import RunContext, resolve_params, validate_playbook, build_credential, ReferenceError
from src.registry import TECHNIQUES
from src.auth_techniques import (
    password_auth,
    device_code_auth,
    client_credentials_auth,
    refresh_token_auth,
)
import logging
import argparse
import time
import random

### Other

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


def main():

    setup_logging(logging.INFO)
    print (banner)

    parser = argparse.ArgumentParser(description='msInvader - M365/Azure Adversary Simulation - https://github.com/mvelazc0/msInvader')

    parser.add_argument('-c', dest='config', type=str, help='Configuration file')
    parser.add_argument('--artifact-dir', dest='artifact_dir', type=str, default=None,
                        help='Directory to dump run artifacts to, and to fall back to when '
                             'resolving ${artifact.field} references (development/debugging)')
    parser.add_argument('--validate-only', dest='validate_only', action='store_true',
                        help='Load the playbook, validate every reference and required '
                             'parameter, then exit without authenticating or calling any API')
    args = parser.parse_args()

    if args.config:
        config_path = args.config
    else:
        config_path = 'config.yml'

    config = load_config(config_path)

    if args.validate_only:
        errors = validate_playbook(config, TECHNIQUES)
        for error in errors:
            logging.error(error)
        if errors:
            logging.error(f"Validation failed with {len(errors)} error(s)")
            exit(1)
        logging.info("Validation passed")
        exit(0)

    # Per-run artifact store for technique chaining. A pass-through for playbooks
    # that carry no ${artifact.field} references.
    ctx = RunContext(artifact_dir=args.artifact_dir)


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
            access_method = parameters.get('access_method')
            parameters['ews_impersonation'] = False

            # Resolve ${artifact.field} references in the step's parameters. For a
            # step with no references this returns the parameters unchanged and an
            # empty provenance map.
            try:
                resolved_params, provenance = resolve_params(parameters, ctx)
            except ReferenceError as exc:
                logging.error(f"Step {index + 1} ({technique_name}), {exc}")
                exit(1)
            parameters.update(resolved_params)

            # Build the token this technique receives from its credential
            # parameter. The source artifact's audience is checked against the
            # technique's declared scope; a mismatch mints a scoped token from
            # the artifact's refresh token. ews_impersonation follows the
            # source artifact's flow.
            contract = TECHNIQUES.get(technique_name, {})
            cred = None
            _scope = contract.get('scope')
            if isinstance(_scope, dict):
                _scope = _scope.get(access_method)
            if contract.get('credential') and _scope is not None:
                _cred_param = contract['credential']
                cred, parameters['ews_impersonation'] = build_credential(
                    parameters.get(_cred_param), provenance.get(_cred_param), ctx, _scope)

            # A technique that produces an artifact assigns the returned dict here;
            # a terminal technique leaves it None and the output handling below is
            # a no-op.
            technique_result = None

            if technique_name == 'search_email':

                if access_method == 'graph':
                    #W
                    search_email_graph(config['authentication'], parameters, cred)

            if technique_name == 'search_onedrive':
                
                if access_method == 'graph':
                    #W
                    search_onedrive_graph(config['authentication'], parameters, cred)

            if technique_name == 'read_email':
                
                if access_method == 'graph':
                    #W
                    read_email_graph2(config['authentication'], parameters, cred)

                elif access_method == 'ews':
                    #W
                    read_email_ews2(config['authentication'], parameters, cred)
                
                #elif access_method == 'rest':
                    # Exchange online management does not support Get-Message on M365
                #    logging.error("Technique method not supported")

            elif technique_name == 'create_rule':

                if access_method == 'graph':
                    #NW
                    create_rule_graph(config['authentication'], parameters, cred)

                if access_method == 'ews':
                    #W
                    create_rule_ews2(config['authentication'], parameters, cred)

                elif access_method == 'rest':
                    #W
                    create_rule_rest(config['authentication'], parameters, cred)

            elif technique_name == 'enable_email_forwarding':

                if access_method == 'rest':
                    #W
                    enable_email_forwarding_rest(config['authentication'], parameters, cred)      

            elif technique_name == 'add_folder_permission':

                if access_method == 'rest':
                    #W
                    modify_folder_permission_rest(config['authentication'], parameters, cred)      

                if access_method == 'ews':
                    #W
                    modify_folder_permission_ews(config['authentication'], parameters, cred)      

            elif technique_name == 'add_mailbox_delegation':

                if access_method == 'rest':
                    #W. 
                    # Requires exchange admin
                    add_mailbox_delegation_rest(config['authentication'], parameters, cred)      

            elif technique_name == 'run_compliance_search':

                if access_method == 'rest':
                    #NW
                    # Requires exchange admin
                    run_compliance_search_rest(config['authentication'], parameters, cred)      

            elif technique_name == 'create_mailflow_rule':

                if access_method == 'rest':
                    #W
                    create_mailflow_rule_rest(config['authentication'], parameters, cred)      

            elif technique_name == 'password_spray':
                #W
                password_spray(technique['parameters'])

            elif technique_name == 'add_application_secret':
                #W
                technique_result = add_application_secret_graph(config['authentication'], parameters, cred)

            elif technique_name == 'add_service_principal':
                
                technique_result = add_service_principal(config['authentication'], parameters, cred)

            elif technique_name == 'admin_consent':
                
                admin_consent_graph(config['authentication'], parameters, cred)

            elif technique_name == 'create_app_registration':
                technique_result = create_application_registration(config['authentication'], parameters, cred)

            elif technique_name == 'send_mail':
                ##
                send_email_graph(config['authentication'], parameters, cred)  
                

            elif technique_name == 'enumerate_users':
                #W
                enumerate_entities(config['authentication'], parameters, "users", cred)                  

            elif technique_name == 'enumerate_groups':
                #W
                enumerate_entities(config['authentication'], parameters, "groups", cred)    
                
            elif technique_name == 'enumerate_applications':
                #W
                enumerate_entities(config['authentication'], parameters, "applications", cred)    
                
            elif technique_name == 'enumerate_service_principals':
                #W
                enumerate_entities(config['authentication'], parameters, "service_principals", cred) 

            elif technique_name == 'enumerate_directory_roles':
                #W
                enumerate_entities(config['authentication'], parameters, "directory_roles", cred) 

            elif technique_name == 'change_user_password':
                #W
                change_user_password(config['authentication'], parameters, cred) 
  
            elif technique_name == 'assign_app_role':
                #W
                assign_app_role2(config['authentication'], parameters, cred)

            elif technique_name == 'create_user':
                #W
                technique_result = create_user_graph(config['authentication'], parameters, cred) 

            elif technique_name == 'assign_entra_role':
                #W
                assign_entra_role_graph(config['authentication'], parameters, cred) 

            elif technique_name == 'list_key_vaults':
                
                list_key_vaults(config['authentication'], parameters, cred) 

            elif technique_name == 'list_keyvault_items':
                
                list_keyvault_items(config['authentication'], parameters, cred) 

            elif technique_name == 'access_key_vault_item':
                
                access_key_vault_item(config['authentication'], parameters, cred) 

            elif technique_name == 'add_keyvault_access_policy':
                
                add_keyvault_access_policy(config['authentication'], parameters, cred) 

            elif technique_name == 'list_keyvault_access_policies':
                
                list_keyvault_access_policies(config['authentication'], parameters, cred) 

            elif technique_name == 'execute_command':
                
                vm_execute_command(config['authentication'], parameters, cred) 

            elif technique_name == 'execute_custom_script':
                
                execute_custom_script(config['authentication'], parameters, cred) 

            elif technique_name == 'reset_password':
                
                vm_reset_password(config['authentication'], parameters, cred) 

            elif technique_name == 'list_extensions':
                
                vm_list_extensions(config['authentication'], parameters, cred)                 
                
            elif technique_name == 'delete_extension':
                
                vm_remove_extension(config['authentication'], parameters, cred) 

            elif technique_name == 'enumerate_arm_role_assignments':
                
                enumerate_arm_role_assignments(config['authentication'], parameters, cred) 
                
            elif technique_name == 'enumerate_arm_resources':
                
                enumerate_arm_resources(config['authentication'], parameters, cred)                 

            elif technique_name == 'enumerate_privileged_arm_role_holders':
                
                enumerate_privileged_arm_role_holders(config['authentication'], parameters, cred)      

            elif technique_name == 'enumerate_app_role_assignments':

                enumerate_app_role_assignments(config['authentication'], parameters, cred)

            elif technique_name == 'register_device':
                technique_result = register_device(
                    config['authentication'], parameters,
                    {'access_token': parameters.get('access_token')},
                )
                if technique_result is not None:
                    logging.info("Waiting 5 seconds for device to propagate in Entra ID...")
                    time.sleep(5)

            elif technique_name == 'get_prt_with_refresh_token':
                parameters.setdefault('tenant_id', config['authentication']['tenant_id'])
                technique_result = get_prt_with_refresh_token(parameters)

            elif technique_name == 'get_token_with_prt':
                parameters.setdefault('tenant_id', config['authentication']['tenant_id'])
                technique_result = get_token_with_prt(parameters)

            elif technique_name == 'create_whfb_key':
                technique_result = create_whfb_key(parameters)
                if technique_result is not None:
                    logging.info("Waiting 5 seconds for Windows Hello key to propagate in Entra ID...")
                    time.sleep(5)

            elif technique_name == 'get_prt_with_whfb_key':
                parameters.setdefault('tenant_id', config['authentication']['tenant_id'])
                technique_result = get_prt_with_whfb_key(parameters)

            elif technique_name == 'password_auth':
                technique_result = password_auth(config['authentication'], parameters)

            elif technique_name == 'device_code_auth':
                technique_result = device_code_auth(config['authentication'], parameters)

            elif technique_name == 'client_credentials_auth':
                technique_result = client_credentials_auth(config['authentication'], parameters)

            elif technique_name == 'refresh_token_auth':
                technique_result = refresh_token_auth(config['authentication'], parameters)

            # Store the step's artifact under `output:` and/or write it to
            # `save_to_disk:`. Skipped when the technique returned nothing.
            output_name = technique.get('output')
            save_to_disk = technique.get('save_to_disk')
            if technique_result is not None:
                ctx.put(output_name or technique_name, technique_result,
                        save_to_disk=save_to_disk)
            elif output_name or save_to_disk:
                logging.debug(
                    f"Step {index + 1} ({technique_name}) declares output/save_to_disk "
                    f"but returned no artifact"
                )

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
        
