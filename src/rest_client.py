import requests
from src.auth import get_ms_token


rest_scope   = "https://outlook.office365.com/.default"


def enable_email_forwarding_rest(auth_config, params, token=False):


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
    
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print ('Created!')
        print(f'Error: {response.status_code}')
        print (response.text)    

    else:
        print(f'Error: {response.status_code}')
        print (response.text)    
    


def create_rule_rest(auth_config, params, token=False):

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

    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print ('Created!')
        print(f'Error: {response.status_code}')
        print (response.text)    

    else:
        print(f'Error: {response.status_code}')
        print (response.text)    
    

def modify_folder_permission_rest(tenant_id, params, token, command):

    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'


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
    
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print ('Created!')
        print(f'Error: {response.status_code}')
        print (response.text)    

    else:
        print(f'Error: {response.status_code}')
        print (response.text)    
    
def add_mailbox_delegation_rest(auth_config, params):

    # https://learn.microsoft.com/en-us/exchange/recipients/mailbox-permissions?view=exchserver-2019
    # https://learn.microsoft.com/en-us/powershell/module/exchange/add-mailboxpermission?view=exchange-ps

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
    response = requests.post(rest_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print ('Created!')
        print(f'Error: {response.status_code}')
        print (response.text)    

    else:
        print(f'Error: {response.status_code}')
        print (response.text)    
