import requests
from xml.etree import ElementTree as ET

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
def create_find_item_soap_request2(mailbox, impersonation=False):
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

def create_get_item_soap_request2(item_id, mailbox, impersonation=False):
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

def read_email_ews(params, token):

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
    find_item_request = create_find_item_soap_request2(user_email)
    find_item_response = requests.post(ews_url, headers=headers, data=find_item_request)
    #print(find_item_response.status_code)
    #print(find_item_response.text)
    find_item_root = ET.fromstring(find_item_response.content)

    # Extract ItemIds from FindItem response (update based on actual XML structure)
    item_ids = []
    for elem in find_item_root.findall('.//{http://schemas.microsoft.com/exchange/services/2006/types}ItemId'):
        item_ids.append(elem.attrib['Id'])

    # Step 2: GetItem requests to read emails
    for item_id in item_ids:
        get_item_request = create_get_item_soap_request2(item_id, user_email)
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

def create_forwarding_rule_xml2(user, forward_to, rule_name, body_contains, impersonation=False):
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
                <t:PrimarySmtpAddress>{user}</t:PrimarySmtpAddress>
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

def create_rule_ews(params, token):

    print ("Starting create rule with ews")
    # EWS URL
    ews_url = "https://outlook.office365.com/EWS/Exchange.asmx"

    user = params['user']
    forward_to =  params['forward_to']
    rule_name =  params['rule_name']
    body_contains =  params['body_contains']

    soap_request = create_forwarding_rule_xml2(user, forward_to, rule_name, body_contains)

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

def enable_email_forwarding_xml(mailbox, forwarding_address):

    return f'''<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
      <soap:Header>
        <t:RequestServerVersion Version="Exchange2016" />
        <t:ExchangeImpersonation>
          <t:ConnectingSID>
            <t:PrimarySmtpAddress>{mailbox}</t:PrimarySmtpAddress>
          </t:ConnectingSID>
        </t:ExchangeImpersonation>
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

def enable_email_forwarding_ews(params, token):
    
    # EWS URL
    ews_url = "https://outlook.office365.com/EWS/Exchange.asmx"

    print ("Starting email forwarding enable with ews")
    user = params['user']
    forward_to =  params['forward_to']

    soap_request = enable_email_forwarding_xml(user, forward_to)

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