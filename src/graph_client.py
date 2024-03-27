

### Graph

def get_ms_token_client(tenant_id, client_id, client_secret, scope):

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope
    }

    token_r = requests.post(token_url, data=token_data)
    return token_r.json().get('access_token')


def get_ms_token_username_pass(tenant_id, username, password, scope):

    print ("[!] Using password grant type")
    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    token_data = {

        #'client_id': '1950a258-227b-4e31-a9cf-717495945fc2', # Microsoft Azure PowerShell
        'client_id': '00b41c95-dab0-4487-9791-b9d2c32c80f2',  # Office 365 Management. Works to read emails
        #'client_id': '00000002-0000-0ff1-ce00-000000000000', # Office 365 Exchange Online
        #'client_id': '00000006-0000-0ff1-ce00-000000000000', # Microsoft Office 365 Portal


        'grant_type': 'password',
        'username': username,
        'password': password,
        'scope': scope
    }

    token_r = requests.post(token_url, data=token_data)
    return token_r.json().get('access_token')


def get_ms_token(auth, auth_type, scope):
    
    if auth_type == 1:
        return get_ms_token_username_pass(auth['tenant_id'] , auth['username'], auth['password'], scope)
    elif auth_type == 2:
        return get_ms_token_client()
    elif auth_type == 3:
        return get_ms_token_client()

def read_email_with_graph(params, token):

    print ("reading emails with graph")
    user_email = params['user']
    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/Inbox/messages'

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

def create_rule_with_graph(params, token):

    #https://learn.microsoft.com/en-us/graph/api/resources/messageruleactions?view=graph-rest-1.0
    user_email = params['user']
    rule_name = params['rule_name']
    forward_to = params ['forward_to']
    body_contains = params ['body_contains']


    graph_endpoint = f'https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/Inbox/messageRules'

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
