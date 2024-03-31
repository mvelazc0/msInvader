import yaml
from src.ews_client import *
from src.graph_client import *
from src.rest_client import *
from src.auth import *
import logging
import argparse

### Other


banner = """

                _____                     _           
               |_   _|                   | |          
  _ __ ___  ___  | |  _ ____   ____ _  __| | ___ _ __ 
 | '_ ` _ \/ __| | | | '_ \ \ / / _` |/ _` |/ _ \ '__|
 | | | | | \__ \_| |_| | | \ V / (_| | (_| |  __/ |   
 |_| |_| |_|___/_____|_| |_|\_/ \__,_|\__,_|\___|_|   

                                                       
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
    
    class CustomFormatter(logging.Formatter):
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

    parser = argparse.ArgumentParser(description='msInvader - https://github.com/mvelazc0/msInvader')

    parser.add_argument('-c', dest='config', type=str, help='Configuration file')
    args = parser.parse_args()

    if args.config:
        config_path = args.config
    else:
        config_path = 'config.yml'    
    
    config = load_config(config_path)
    enabled_techniques = [tech for tech in config['techniques'] if tech['enabled']]
    logging.info(f"Identified {len(enabled_techniques)} enabled technique(s) on configuration file")

    ews_scope   = "https://outlook.office365.com/.default"
    graph_scope = "https://graph.microsoft.com/.default"
    #graph_scope = "https://graph.microsoft.com/MailboxSettings.ReadWrite"
    #graph_scope = "MailboxSettings.ReadWrite"
    logging.info("Starting technique execution")

    for technique in enabled_techniques:

        if technique['technique'] == 'read_email':

            if technique['parameters']['method'] == 'graph':

                #token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], graph_scope)
                #read_email_graph(technique['parameters'], token)
                read_email_graph(config['authentication'], technique['parameters'])

            elif technique['parameters']['method'] == 'ews':

                #token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                read_email_ews(config['authentication'], technique['parameters'])


        elif technique['technique'] == 'create_rule':

            if technique['parameters']['method'] == 'graph':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], graph_scope)
                create_rule_graph(technique['parameters'], token)

            elif technique['parameters']['method'] == 'ews':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                create_rule_ews(technique['parameters'], token)

            elif technique['parameters']['method'] == 'rest':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                create_rule_rest(config['authentication']['tenant_id'], technique['parameters'], token)

        elif technique['technique'] == 'enable_email_forwarding':

            if technique['parameters']['method'] == 'rest':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                enable_email_forwarding_rest(config['authentication']['tenant_id'], technique['parameters'], token)      

        elif technique['technique'] == 'add_folder_permission':

            if technique['parameters']['method'] == 'rest':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                modify_folder_permission_rest(config['authentication']['tenant_id'], technique['parameters'], token, "Add-MailboxFolderPermission")      

            if technique['parameters']['method'] == 'ews':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                modify_folder_permission_ews(technique['parameters'], token)      

        elif technique['technique'] == 'set_folder_permission':

            if technique['parameters']['method'] == 'rest':

                token = get_ms_token(config['authentication'], technique['parameters']['auth_type'], ews_scope)
                modify_folder_permission_rest(config['authentication']['tenant_id'], technique['parameters'], token, "Set-MailboxFolderPermission")      


if __name__ == "__main__":
    main()
        