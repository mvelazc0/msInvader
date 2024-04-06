import requests
import time
import logging

def get_ms_token_client(tenant_id, client_id, client_secret, scope):

    logging.info("Using client credential OAuth flow to obtain a token")

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

    # https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth-ropc

    logging.info("Using resource owner password OAuth flow to obtain a token")

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    token_data = {

        #'client_id': '1950a258-227b-4e31-a9cf-717495945fc2', # Microsoft Azure PowerShell
        #'client_id': '00b41c95-dab0-4487-9791-b9d2c32c80f2',  # Office 365 Management. Works to read emails Graph and EWS.
        'client_id': 'd3590ed6-52b3-4102-aeff-aad2292ab01c',  # Microsoft Office. Also works to read emails Graph and EWS.
        #'client_id': '00000002-0000-0ff1-ce00-000000000000', # Office 365 Exchange Online
        #'client_id': '00000006-0000-0ff1-ce00-000000000000', # Microsoft Office 365 Portal
        #'client_id': 'fb78d390-0c51-40cd-8e17-fdbfab77341b', # Microsoft Exchange REST API Based Powershell
        # 'client_id': '00000003-0000-0000-c000-000000000000', # Microsoft Graph
        #'client_id': 'de8bc8b5-d9f9-48b1-a8ad-b748da725064', # Graph Explorer
        #'client_id': '14d82eec-204b-4c2f-b7e8-296a70dab67e', # Microsoft Graph Command Line Tools	

        'grant_type': 'password',
        'username': username,
        'password': password,
        'scope': scope
    }

    response = requests.post(token_url, data=token_data)
    token = response.json().get('access_token')
    if token:
        return token
    else:
        logging.error (f'Error obtaining token. Http response: {response.status_code}')
        #print (response.text)


def get_device_code(tenant_id, client_id, scope):

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/devicecode"
    data = {
        "client_id": client_id,
        "scope": scope
    }
    response = requests.post(url, data=data).json()
    return response

def get_ms_token_device_code(tenant_id, scope):

    logging.info("Using device code OAuth flow to obtain a token")

    client_id = '00b41c95-dab0-4487-9791-b9d2c32c80f2' # Office 365 Management. Works to read emails Graph and EWS.

    device_code_response = get_device_code(tenant_id, client_id, scope)


    user_code = device_code_response.get("user_code")
    device_code = device_code_response.get("device_code")

    #print (user_code)
    #print (device_code)

    print("Code:", user_code)    
    print("Submit the code on the following URL as the simulation user:", "https://microsoft.com/devicelogin")

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    token_data = {
        "grant_type": "device_code",
        "device_code": device_code,
        "client_id": client_id
    }

    while True:

        time.sleep(5)  
        token_response = requests.post(token_url, data=token_data).json()

        if "error" in token_response:
            if token_response["error"] == "authorization_pending":
                print("Authorization pending. Please complete the user authentication.")
            elif token_response["error"] == "slow_down":
                time.sleep(5)  
            else:
                print("Error:", token_response["error_description"])
                break
        else:
            return token_response.get('access_token')
    


def get_ms_token(auth_config, auth_type, scope):
    
    if auth_type == 1:
        return get_ms_token_username_pass(auth_config['tenant_id'], auth_config['username'], auth_config['password'], scope)
    elif auth_type == 2:
        return get_ms_token_device_code(auth_config['tenant_id'], scope)
    elif auth_type == 3:
        return get_ms_token_client(auth_config['tenant_id'], auth_config['application_id'], auth_config['client_secret'], scope)