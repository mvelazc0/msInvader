import requests
from xml.etree import ElementTree as ET
from src.auth import get_ms_token
import logging


ews_scope   = "https://outlook.office365.com/.default"
ews_url = "https://outlook.office365.com/EWS/Exchange.asmx"

## Functions to create SOAP requets XMLs

def create_find_item_soap_request(mailbox, impersonation=False):

    exchange_impersonation = f"""
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>""" if impersonation else ""

    return f"""
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016"/>
            {exchange_impersonation}
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
    """.strip()
                      
def create_get_item_soap_request(item_id, mailbox, impersonation=False):
    exchange_impersonation = f"""
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>""" if impersonation else ""

    return f"""
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2013"/>
            {exchange_impersonation}
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
    """.strip()

def create_forwarding_rule_soap_request(mailbox, forward_to, rule_name, body_contains, impersonation=False):
    """
    Generates SOAP XML for creating a forwarding rule in EWS.

    :param forward_to: The email address to forward emails to.
    :param rule_name: The name of the forwarding rule.
    :param body_contains: A string that must be contained in the email body to trigger the rule.
    :return: A string containing the SOAP XML.
    """

    exchange_impersonation = f"""
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>""" if impersonation else ""

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016" />
            {exchange_impersonation}
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
    
def create_moving_rule_soap_request(mailbox, destination_folder, rule_name, body_contains, impersonation=False):
    """
    Generates SOAP XML for creating a rule that moves emails with using EWS.

    :param forward_to: The email address to forward emails to.
    :param rule_name: The name of the forwarding rule.
    :param body_contains: A string that must be contained in the email body to trigger the rule.
    :return: A string containing the SOAP XML.
    """
    destination_folder=(destination_folder.lower()).replace(" ", "")

    exchange_impersonation = f"""
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>""" if impersonation else ""

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016" />
            {exchange_impersonation}
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
                                <t:MoveToFolder>
                                    <t:DistinguishedFolderId Id="{destination_folder}" />
                                </t:MoveToFolder>
                            </t:Actions>
                        </t:Rule>
                    </t:CreateRuleOperation>
                </m:Operations>
            </m:UpdateInboxRules>
        </soap:Body>
    </soap:Envelope>'''    

def enable_email_forwarding_soap_request(mailbox, forwarding_address, impersonation=False):

    exchange_impersonation = f"""
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>""" if impersonation else ""

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
      <soap:Header>
        <t:RequestServerVersion Version="Exchange2016" />
        {exchange_impersonation}
      </soap:Header>
      <soap:Body>
        <UpdateInboxRules xmlns="http://schemas.microsoft.com/exchange/services/2006/messages"
                          xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
          <MailboxSmtpAddress>{mailbox}</MailboxSmtpAddress>
          <Operations>
            <t:SetMailbox>
              <t:EmailAddresses>
                <t:Entry Key="ForwardingSmtpAddress">{forwarding_address}</t:Entry>
              </t:EmailAddresses>
            </t:SetMailbox>
          </Operations>
        </UpdateInboxRules>
      </soap:Body>
    </soap:Envelope>'''

def create_find_folder_soap_request(mailbox, folder_name, impersonation=False):
    # https://learn.microsoft.com/en-us/exchange/client-developer/exchange-web-services/how-to-set-folder-permissions-for-another-user-by-using-ews-in-exchange

    folder_name = str.lower(folder_name)

    impersonation_header = ""

    if impersonation:
        impersonation_header = f'''
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrincipalName>{mailbox}</t:PrincipalName>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>'''

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016"/>
            {impersonation_header}
        </soap:Header>
        <soap:Body>
            <m:GetFolder>
                <m:FolderShape>
                <t:BaseShape>IdOnly</t:BaseShape>
                <t:AdditionalProperties>
                    <t:FieldURI FieldURI="folder:PermissionSet" />
                </t:AdditionalProperties>
                </m:FolderShape>
                <m:FolderIds>
                <t:DistinguishedFolderId Id="{folder_name}" />
                </m:FolderIds>
            </m:GetFolder>
        </soap:Body>
    </soap:Envelope>'''

def modify_folder_permissions_soap_request(mailbox, folder_id, grantee, access_rights, impersonation= False):

    # https://learn.microsoft.com/en-us/exchange/client-developer/exchange-web-services/how-to-set-folder-permissions-for-another-user-by-using-ews-in-exchange
    
    user_id = ""
    if grantee.lower() in ['default', 'anonymous']:
        user_id = f'''<t:DistinguishedUser>{grantee}</t:DistinguishedUser>'''
    else:
        user_id = f'''<t:PrimarySmtpAddress>{grantee}</t:PrimarySmtpAddress>'''

    impersonation_header = ""
    
    if impersonation:
        impersonation_header = f'''
        <t:ExchangeImpersonation>
            <t:ConnectingSID>
                <t:PrincipalName>{mailbox}</t:PrincipalName>
            </t:ConnectingSID>
        </t:ExchangeImpersonation>'''

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
                xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
                xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Header>
            <t:RequestServerVersion Version="Exchange2016" />
            {impersonation_header}
        </soap:Header>
        <soap:Body>
            <m:UpdateFolder>
                <m:FolderChanges>
                    <t:FolderChange>
                        <t:FolderId Id="{folder_id}" />
                        <t:Updates>
                            <t:SetFolderField>
                                <t:FieldURI FieldURI="folder:PermissionSet" />
                                <t:Folder>
                                    <t:PermissionSet>
                                        <t:Permissions>
                                            <t:Permission>
                                                <t:UserId>
                                                    {user_id}
                                                </t:UserId>
                                                <t:PermissionLevel>{access_rights}</t:PermissionLevel>
                                            </t:Permission>
                                        </t:Permissions>
                                    </t:PermissionSet>
                                </t:Folder>
                            </t:SetFolderField>
                        </t:Updates>
                    </t:FolderChange>
                </m:FolderChanges>
            </m:UpdateFolder>
        </soap:Body>
    </soap:Envelope>'''

## Functions to execute techniques

def read_email_ews(auth_config, params, token=False):

    logging.info("Running the read_email technique using the EWS API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], ews_scope)

    mailbox= params['mailbox']

    # Headers
    access_token = token['access_token']
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    # Step 1: FindItem request to get email IDs

    # Check if we need exchange impersonation headers
    if params['ews_impersonation']:
        find_item_request = create_find_item_soap_request(mailbox, True)

    else:
        find_item_request = create_find_item_soap_request(mailbox)

    logging.info("Calling the FindItem operation on the EWS API")
    find_item_response = requests.post(ews_url, headers=headers, data=find_item_request)
    if find_item_response.status_code == 200:
        logging.info("200 OK")
    else:
        logging.error(f"FindItem operation failed with status code {find_item_response.status_code }")
        #print(find_item_response.status_code)
        print(find_item_response.text)
    find_item_root = ET.fromstring(find_item_response.content)

    # Extract ItemIds from FindItem response (update based on actual XML structure)
    item_ids = []
    for elem in find_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}ItemId'):
        item_ids.append(elem.attrib['Id'])


    # Step 2: GetItem requests to read emails
    logging.info("Calling the GetItem operation on the EWS API for found emails")
    for item_id in item_ids[:params['limit']]:

        # Check if we need exchange impersonation headers
        if params['ews_impersonation']:
            get_item_request = create_get_item_soap_request(item_id, mailbox, True)

        else:
            get_item_request = create_get_item_soap_request(item_id, mailbox)        

        #logging.info("Calling the GetItem operation on the EWS API")
        get_item_response = requests.post(ews_url, headers=headers, data=get_item_request)
        get_item_root = ET.fromstring(get_item_response.content)

        # Extract email details from GetItem response (update based on actual XML structure)
        for message in get_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}Message'):
            subject = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Subject').text
            body = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Body').text
            logging.info(f"Read email with subject: {subject}")
            #print(f"Subject: {subject}\nBody: {body}\n")


def read_email_ews2(auth_config, params, token=False):
    logging.info("Running the read_email technique using the EWS API")

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], ews_scope)

    mailboxes = params['mailbox']
    if not isinstance(mailboxes, list):  
        mailboxes = [mailboxes]

    access_token = token['access_token']
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    for mailbox in mailboxes:
        logging.info(f"Processing mailbox: {mailbox}")

        # Step 1: FindItem request to get email IDs
        if params.get('ews_impersonation'):
            find_item_request = create_find_item_soap_request(mailbox, True)
        else:
            find_item_request = create_find_item_soap_request(mailbox)

        logging.info("Calling the FindItem operation on the EWS API")
        find_item_response = requests.post(ews_url, headers=headers, data=find_item_request)
        if find_item_response.status_code == 200:
            logging.info("200 OK")
        else:
            logging.error(f"FindItem operation failed with status code {find_item_response.status_code}")
            print(find_item_response.text)
            continue

        find_item_root = ET.fromstring(find_item_response.content)

        # Extract ItemIds from FindItem response (update based on actual XML structure)
        item_ids = []
        for elem in find_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}ItemId'):
            item_ids.append(elem.attrib['Id'])

        # Step 2: GetItem requests to read emails
        logging.info(f"Calling the GetItem operation on the EWS API for found emails in {mailbox}")
        for item_id in item_ids[:params['limit']]:
            if params.get('ews_impersonation'):
                get_item_request = create_get_item_soap_request(item_id, mailbox, True)
            else:
                get_item_request = create_get_item_soap_request(item_id, mailbox)

            get_item_response = requests.post(ews_url, headers=headers, data=get_item_request)
            if get_item_response.status_code != 200:
                logging.error(f"GetItem operation failed with status code {get_item_response.status_code}")
                print(get_item_response.text)
                continue

            get_item_root = ET.fromstring(get_item_response.content)

            # Extract email details from GetItem response (update based on actual XML structure)
            for message in get_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}Message'):
                subject = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Subject').text
                body = message.find('{http://schemas.microsoft.com/exchange/services/2006/types}Body').text
                logging.info(f"Read email with subject: {subject}")


def create_rule_ews(auth_config, params, token=False):

    logging.info("Running the create_rule technique using the EWS API")

    mailbox = params['mailbox']
    forward_to =  params['forward_to']
    rule_name =  params['rule_name']
    body_contains =  params['body_contains']

    if params['ews_impersonation']:
        soap_request = create_forwarding_rule_soap_request(mailbox, forward_to, rule_name, body_contains, True)
    else:
        soap_request = create_forwarding_rule_soap_request(mailbox, forward_to, rule_name, body_contains)

    if not token:
        token =  get_ms_token(auth_config, params['auth_method'], ews_scope)

    # Send the EWS request with OAuth token
    logging.info("Calling the UpdateInboxRules operation on the EWS API")

    access_token = token['access_token']
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    response = requests.post(ews_url, headers=headers, data=soap_request)

    # Process the response
    if response.status_code == 200:
        logging.info("200 OK")
        logging.info(f"Created rule with name: {rule_name}")

        #print(response.text)

    else:
        #print(f"Failed to create rule. Status code: {response.status_code}")
        logging.error(f"UpdateInboxRules operation failed with status code {response.status_code}")
        #print(response.status_code)
        #print(response.text)


def create_rule_ews2(auth_config, params, token=False):

    logging.info("Running the create_rule technique using the EWS API")

    mailbox = params['mailbox']
    rule_name =  params['rule_name']
    body_contains =  params['body_contains']
    type = params['type']
    
    if type == 'forwarding_rule':
        
        forward_to =  params['forward_to']
    
        if params['ews_impersonation']:
            soap_request = create_forwarding_rule_soap_request(mailbox, forward_to, rule_name, body_contains, True)
        else:
            soap_request = create_forwarding_rule_soap_request(mailbox, forward_to, rule_name, body_contains)

        if not token:
            token =  get_ms_token(auth_config, params['auth_method'], ews_scope)

        # Send the EWS request with OAuth token
        logging.info("Calling the UpdateInboxRules operation on the EWS API")

        access_token = token['access_token']
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/xml; charset=utf-8"
        }

        response = requests.post(ews_url, headers=headers, data=soap_request)

        # Process the response
        if response.status_code == 200:
            logging.info("200 OK")
            logging.info(f"Created rule with name: {rule_name}")

            #print(response.text)

        else:
            #print(f"Failed to create rule. Status code: {response.status_code}")
            logging.error(f"UpdateInboxRules operation failed with status code {response.status_code}")
            print(response.status_code)
            print(response.text)
            
    elif type == 'moving_rule':
        
        destination_folder = params['destination_folder']    
     
        if params['ews_impersonation']:
            soap_request = create_moving_rule_soap_request(mailbox, destination_folder, rule_name, body_contains, True)
        else:
            soap_request = create_moving_rule_soap_request(mailbox, destination_folder, rule_name, body_contains)

        if not token:
            token =  get_ms_token(auth_config, params['auth_method'], ews_scope)

        # Send the EWS request with OAuth token
        logging.info("Calling the UpdateInboxRules operation on the EWS API")

        access_token = token['access_token']
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/xml; charset=utf-8"
        }

        response = requests.post(ews_url, headers=headers, data=soap_request)

        # Process the response
        if response.status_code == 200:
            logging.info("200 OK")
            logging.info(f"Created rule with name: {rule_name}")

            #print(response.text)

        else:
            #print(f"Failed to create rule. Status code: {response.status_code}")
            logging.error(f"UpdateInboxRules operation failed with status code {response.status_code}")
            print(response.status_code)
            print(response.text)




"""
def enable_email_forwarding_ews(params, token):
    
    logging.info("Running the enable_email_forwarding technique using the EWS API")

    user = params['user']
    forward_to =  params['forward_to']

    soap_request = enable_email_forwarding_soap_request(user, forward_to)

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
"""    

def modify_folder_permission_ews(auth_config, params, token=False):

    logging.info("Running the add_folder_permissions technique using the EWS API")

    if params['ews_impersonation']:

        find_item_body = create_find_folder_soap_request(params['mailbox'], params['folder'], True)

    else:
        find_item_body = create_find_folder_soap_request(params['mailbox'], params['folder'])

    if not token:
        token = get_ms_token(auth_config, params['auth_method'], ews_scope)

    access_token = token['access_token']

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/xml; charset=utf-8"
    }

    # Step 1: Find the folder id
    logging.info("Calling the GetFolder operation on the EWS API")
    response = requests.post(ews_url, headers = headers, data=find_item_body)
    if response.status_code == 200:
        logging.info("200 - OK")
        root = ET.fromstring(response.text)
        
        namespaces = {
            's': 'http://schemas.xmlsoap.org/soap/envelope/',
            'm': 'http://schemas.microsoft.com/exchange/services/2006/messages',
            't': 'http://schemas.microsoft.com/exchange/services/2006/types'
        }

        folder_id_element = root.find('.//t:FolderId', namespaces)
        
        if folder_id_element is not None:
            folder_id = folder_id_element.attrib.get('Id')
        else:
            logging.error("Folder ID not found in the response.")

    else:
        logging.error(f"GetFolder operation failed with status code {response.status_code }")
        print(response.text)


    # Step 2: Update foler permission
        
    update_folder_body = modify_folder_permissions_soap_request(params['mailbox'], folder_id, params['grantee'], params['access_rights'])
    logging.info("Calling the UpdateFolder operation on the EWS API")
    response = requests.post(ews_url, headers = headers, data=update_folder_body)

    grantee =  params['grantee']
    # Process the response
    if response.status_code == 200:
        logging.info("200 - OK")
        logging.info(f"Assigned read inbox permissions to {grantee}")
        #print(response.text)

    else:
        logging.error(f"UpdateFolder operation failed with status code {response.status_code }")
        print(response.text)