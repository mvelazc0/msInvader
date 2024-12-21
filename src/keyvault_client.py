import requests
import time
import logging
import random


keyvault_scope = "https://management.azure.com/.default"

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
        #print (response.json())
    else:
        logging.error(f"Failed to list Key Vaults with status code: {response.status_code}")
        logging.error(response.json())

    # Log finishing the operation
    logging.info("List Key Vaults operation finished")