import requests

### Graph

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
