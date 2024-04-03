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
    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com","")
    logging.info(f"Submitting GET request to {short_endpoint}")
    response = requests.get(graph_endpoint, headers=headers)

    if response.status_code == 200:
        logging.info("200 OK")
        messages = response.json().get('value', [])
        for message in messages[:params['limit']]:
            #print(message.get('subject'), message.get('from'))
            #body_content = message.get('body', {}).get('content', '')
            logging.info(f"Read email with subject: {message.get('subject')}")
            #print("Body:", body_content)

    else:
        logging.error(f"Operation failed with status code {response.status_code }")
        #print (response.text)

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
    
    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com","")
    logging.info(f"Submitting POSt request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        logging.info("201 - Created")
    else:
        logging.error(f"Operation failed with status code {response.status_code }")
        #print (response.text)    