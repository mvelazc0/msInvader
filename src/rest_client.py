import requests

def enable_email_forwarding_rest(tenant_id, params, token):


    tenant_id = tenant_id
    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'


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
            "Identity": params['user']
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
    


def create_rule_rest(tenant_id, params, token):

    rest_endpoint = f'https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand'


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
    