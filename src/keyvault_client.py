import requests
import time
import logging
import random


#keyvault_scope = "https://management.azure.com/.default"
keyvault_scope = "https://vault.azure.net/.default"


def list_key_vaults(auth_config, params, token=False):

    logging.info("Running the list_key_vaults technique")
    
    subscription_id =  params.get('subscription_id', "")

    base_url = "https://management.azure.com"
    short_endpoint = (
        f"/subscriptions/{subscription_id}"
        f"/resources?api-version=2021-04-01&$filter=resourceType eq 'Microsoft.KeyVault/vaults'"
    )
    full_endpoint = base_url + short_endpoint

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting GET request to {short_endpoint}")

    response = requests.get(full_endpoint, headers=headers)

    if response.status_code == 200:
        logging.info("200 OK - Successfully listed Key Vaults.")

        response_json = response.json()
        key_vaults = response_json.get("value", [])
        total_key_vaults = len(key_vaults)
        logging.info(f"Total Key Vaults Identified: {total_key_vaults}")        

    else:
        logging.error(f"Failed to list Key Vaults with status code: {response.status_code}")
        logging.error(response.json())

    logging.info("List Key Vaults operation finished")
    

def list_keyvault_items(auth_config, params, token=False):
    logging.info("Running the list_key_vault_items technique")

    keyvault_url = params.get('keyvault_url', "")
    item_type = params.get('item_type', "").lower()  # 'secrets', 'keys', or 'certificates'
    max_results = params.get('max_results', None)

    if item_type not in ['secrets', 'keys', 'certificates']:
        logging.error(f"Invalid item_type: {item_type}. Must be 'secrets', 'keys', or 'certificates'.")
        return

    base_url = f"{keyvault_url}/{item_type}"
    query_params = {"api-version": "7.3"}
    if max_results:
        query_params["maxresults"] = max_results

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting GET request to {base_url}")

    response = requests.get(base_url, headers=headers, params=query_params)

    if response.status_code == 200:
        logging.info(f"200 OK - Successfully listed Key Vault {item_type}.")
        
        response_json = response.json()
        items = response_json.get("value", [])
        total_items = len(items)
        logging.info(f"Total {item_type.capitalize()} Identified: {total_items}")

    else:
        logging.error(f"Failed to list Key Vault {item_type} with status code: {response.status_code}")
        logging.error(response.json())

    logging.info(f"List Key Vault {item_type.capitalize()} operation finished")
