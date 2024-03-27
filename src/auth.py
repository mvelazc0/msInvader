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