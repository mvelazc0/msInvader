import requests

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
        'client_id': '00b41c95-dab0-4487-9791-b9d2c32c80f2',  # Office 365 Management. Works to read emails Graph and EWS.
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
        print ('Error obtaining token')
        print (response.text)


def get_ms_token(auth, auth_type, scope):
    
    if auth_type == 1:
        return get_ms_token_username_pass(auth['tenant_id'] , auth['username'], auth['password'], scope)
    elif auth_type == 2:
        return get_ms_token_client()
    elif auth_type == 3:
        return get_ms_token_client()