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

    parser = argparse.ArgumentParser(description='msInvader - M365 Adersary Simulation - https://github.com/mvelazc0/msInvader')

    parser.add_argument('-c', dest='config', type=str, help='Configuration file')
    args = parser.parse_args()

    if args.config:
        config_path = args.config
    else:
        config_path = 'config.yml'    
    
    config = load_config(config_path)
    enabled_techniques = [tech for tech in config['techniques'] if tech['enabled']]
    logging.info(f"Identified {len(enabled_techniques)} enabled technique(s) on configuration file")
    logging.info("Starting technique execution")

    for technique in enabled_techniques:

        if technique['technique'] == 'read_email':

            if technique['parameters']['method'] == 'graph':

                read_email_graph(config['authentication'], technique['parameters'])

            elif technique['parameters']['method'] == 'ews':

                read_email_ews(config['authentication'], technique['parameters'])
            
            elif technique['parameters']['method'] == 'rest':
                # Exchange online management does not support Get-Message on M365
                logging.error("Technique method not supported")

        elif technique['technique'] == 'create_rule':

            if technique['parameters']['method'] == 'graph':

                create_rule_graph(config['authentication'], technique['parameters'])

            elif technique['parameters']['method'] == 'ews':

                create_rule_ews(config['authentication'], technique['parameters'])

            elif technique['parameters']['method'] == 'rest':

                create_rule_rest(config['authentication'], technique['parameters'])

        elif technique['technique'] == 'enable_email_forwarding':

            if technique['parameters']['method'] == 'rest':

                enable_email_forwarding_rest(config['authentication'], technique['parameters'])      

        elif technique['technique'] == 'add_folder_permission':

            if technique['parameters']['method'] == 'rest':

                modify_folder_permission_rest(config['authentication'], technique['parameters'])      

            if technique['parameters']['method'] == 'ews':
    
                modify_folder_permission_ews(config['authentication'], technique['parameters'])      

        elif technique['technique'] == 'add_mailbox_delegation':

            if technique['parameters']['method'] == 'rest':

                add_mailbox_delegation_rest(config['authentication'], technique['parameters'])      

        elif technique['technique'] == 'run_compliance_search':

            if technique['parameters']['method'] == 'rest':

                run_compliance_search_rest(config['authentication'], technique['parameters'])      



if __name__ == "__main__":
    main()
        