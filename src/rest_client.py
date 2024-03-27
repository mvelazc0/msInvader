import requests

def enable_email_forwarding_rest(tenant_id, params, token):

    rest_endpoint = "https://outlook.office365.com/adminapi/beta/{tenant_id}/InvokeCommand"

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






