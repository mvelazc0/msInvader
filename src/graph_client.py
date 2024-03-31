import requests
import logging
from src.auth import get_ms_token

### Graph

graph_scope = "https://graph.microsoft.com/.default"

def read_email_graph(auth_config, params):

    logging.info("Running the read_email technique using the Graph API")

    token = get_ms_token(auth_config, params['auth_type'], graph_scope)

    mailbox = params['mailbox']
    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/Inbox/messages'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(graph_endpoint, headers=headers)

    if response.status_code == 200:
        print ("OK!")
        messages = response.json().get('value', [])
        for message in messages:
            print(message.get('subject'), message.get('from'))
            body_content = message.get('body', {}).get('content', '')
            #print("Body:", body_content)

    else:
        print (response.status_code)
        print (response.text)

def create_rule_graph(auth_config, params):

    logging.info("Running the create_rule technique using the Graph API")

    #graph_scope = "https://graph.microsoft.com/MailboxSettings.ReadWrite"
    #graph_scope = "MailboxSettings.ReadWrite"

    #https://learn.microsoft.com/en-us/graph/api/resources/messageruleactions?view=graph-rest-1.0
    mailbox = params['mailbox']
    rule_name = params['rule_name']
    forward_to = params ['forward_to']
    body_contains = params ['body_contains']

    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/Inbox/messageRules'
    #graph_endpoint = f'https://graph.microsoft.com/v1.0/users/me/mailFolders/Inbox/messageRules'

    token = get_ms_token(auth_config, params['auth_type'], graph_scope)

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    data = {
        "displayName": rule_name,
        "sequence": 1,
        "isEnabled": True,
        "conditions": {
            "bodyContains": [
            body_contains 
            ]
        },
        "actions": {
            "forwardTo": [
            {
                "emailAddress": {
                    "address": forward_to 
                }
            }
            ],
            "stopProcessingRules": True
        }
    }

    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print ('Created!')
    else:
        print(f'Error: {response.status_code}')
        print (response.text)    
