import requests
from src.auth import get_ms_token
import logging


rest_scope   = "https://outlook.office365.com/.default"

security_compliance_scope = "https://nam11b.ps.compliance.protection.outlook.com/.default"


def enable_email_forwarding_rest(auth_config, params, token=False):

    logging.info("Running the enable_email_forwarding technique using the REST API")

    tenant_id = auth_config['tenant_id']

    tenant_id = tenant_id
    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'

    if not token:
        token =  get_ms_token(auth_config, params['auth_type'], rest_scope)

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
    "CmdletInput": {
        "CmdletName": "Set-Mailbox",
        "Parameters": {
            "ForwardingSmtpAddress": params['forward_to'],
            "DeliverToMailboxAndForward": True,
            "Identity": params['mailbox']
            }
        }
    }
    logging.info("Calling the Set-Mailbox operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        #print(f'Error: {response.status_code}')
        logging.error(f"Set-Mailbox operation failed with status code {response.status_code }")
        #print (response.text)    
    

def create_rule_rest(auth_config, params, token=False):

    logging.info("Running the create_rule technique using the REST API")

    tenant_id = auth_config['tenant_id']

    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'

    if not token:
        token = get_ms_token(auth_config, params['auth_type'], rest_scope)

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
    "CmdletInput": {
        "CmdletName": "New-InboxRule",
        "Parameters": {
            "Name": params['rule_name'],
            "BodyContainsWords": params['body_contains'],
            "ForwardTo": params['forward_to']
            }
        }
    }
    logging.info("Calling the New-InboxRule operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print ('Created!')
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        logging.error(f"New-InboxRule operation failed with status code {response.status_code }")
        #print(f'Error: {response.status_code}')
        #print (response.text)    
    

def modify_folder_permission_rest(auth_config, params, token=False):

    logging.info("Running the add_folder_permission technique using the REST API")

    tenant_id = auth_config['tenant_id']
    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'

    if params['grantee'].lower() in ['default', 'anonymous']:
        command = "Set-MailboxFolderPermission"
    else:
        command = "Add-MailboxFolderPermission"

    if not token:
        token = get_ms_token(auth_config, params['auth_type'], rest_scope)

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
    "CmdletInput": {
        "CmdletName": command,
        "Parameters": {
            "AccessRights": params['access_rights'],
            "User": params['grantee'],
            "Identity": params['mailbox']+":\\"+params['folder']
            }
        }
    }
    logging.info(f"Calling the {command} operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print ('Created!')
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        logging.error(f"{command} operation failed with status code {response.status_code }")
        #print(f'Error: {response.status_code}')
        #print (response.text)    
    
def add_mailbox_delegation_rest(auth_config, params):

    # https://learn.microsoft.com/en-us/exchange/recipients/mailbox-permissions?view=exchserver-2019
    # https://learn.microsoft.com/en-us/powershell/module/exchange/add-mailboxpermission?view=exchange-ps

    logging.info("Running the add_mailbox_delegation technique using the REST API")


    tenant_id = auth_config['tenant_id']

    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'


    token = get_ms_token(auth_config, params['auth_type'], rest_scope)


    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
    "CmdletInput": {
        "CmdletName": "Add-MailboxPermission",
        "Parameters": {
            "AccessRights": params['access_rights'],
            "User": params['grantee'],
            "Identity": params['mailbox']
            }
        }
    }
    logging.info(f"Calling the Add-MailboxPermission operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print ('Created!')
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        logging.error(f"Add-MailboxPermission operation failed with status code {response.status_code }")
        #print(f'Error: {response.status_code}')
        #print (response.text)    


def run_compliance_search_rest(auth_config, params):

    # https://learn.microsoft.com/en-us/exchange/recipients/mailbox-permissions?view=exchserver-2019
    # https://learn.microsoft.com/en-us/powershell/module/exchange/add-mailboxpermission?view=exchange-ps

    logging.info("Running the run_compliance_search technique using the REST API")


    tenant_id = auth_config['tenant_id']

    #rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'
    rest_endpoint = f'https://nam11b.ps.compliance.protection.outlook.com/adminapi/beta/{tenant_id}/InvokeCommand'

    #token = get_ms_token(auth_config, params['auth_type'], security_compliance_scope)
    token = get_ms_token(auth_config, params['auth_type'], rest_scope)

    #{"CmdletInput":{"CmdletName":"New-ComplianceSearch","Parameters":{"ContentMatchQuery":"password","ExchangeLocation":["All"],"Name":"pws3 Search"}}}

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
    "CmdletInput": {
        "CmdletName": "New-ComplianceSearch",
        "Parameters": {
            "ContentMatchQuery": params['keyword'],
            "ExchangeLocation": ["All"],
            "Name": params['name']
            }
        }
    }
    logging.info(f"Calling the New-ComplianceSearch operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print ('Created!')
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        logging.error(f"New-ComplianceSearch operation failed with status code {response.status_code }")
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    data = {
    "CmdletInput": {
        "CmdletName": "Start-ComplianceSearch",
        "Parameters": {
            "Identity": params['name']
            }
        }
    }        
    logging.info(f"Calling the Start-ComplianceSearch operation on the REST API")
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 - OK")
        #print ('Created!')
        #print(f'Error: {response.status_code}')
        #print (response.text)    

    else:
        logging.error(f"New-ComplianceSearch operation failed with status code {response.status_code }")
        #print(f'Error: {response.status_code}')
        #print (response.text)   