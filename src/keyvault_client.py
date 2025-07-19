import requests
import time
import logging
import random


arm_scope = "https://management.azure.com/.default"
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
    item_type = params.get('item_type', "").lower()  # 'secrets', 'keys', 'certificates', or empty
    max_results = params.get('max_results', None)

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # If no specific item_type is provided, iterate through all types
    types_to_query = ['secrets', 'keys', 'certificates'] if not item_type else [item_type]

    for current_type in types_to_query:
        if current_type not in ['secrets', 'keys', 'certificates']:
            logging.error(f"Invalid item_type: {current_type}. Must be 'secrets', 'keys', or 'certificates'.")
            continue

        base_url = f"{keyvault_url}/{current_type}"
        query_params = {"api-version": "7.3"}
        if max_results:
            query_params["maxresults"] = max_results

        logging.info(f"Submitting GET request to {base_url}")

        response = requests.get(base_url, headers=headers, params=query_params)

        if response.status_code == 200:
            logging.info(f"200 OK - Successfully listed Key Vault {current_type}.")
            response_json = response.json()
            #print(response_json)
            items = response_json.get("value", [])
            # Exclude managed secrets if listing secrets or keys
            if current_type in ["secrets", "keys"]:
                items = [item for item in items if not item.get("managed", False)]
            total_items = len(items)
            logging.info(f"Total {current_type.capitalize()} Identified: {total_items}")
        else:
            logging.error(f"Failed to list Key Vault {current_type} with status code: {response.status_code}")
            logging.error(response.json())

    logging.info("List Key Vault Items operation finished")

def access_key_vault_item(auth_config, params, token=False):
    """
    Access a specific item in the Key Vault. If item_type is not provided,
    attempt to access the item as a secret, key, and certificate, and print/log all results.
    """
    logging.info("Running the access_key_vault_item technique")

    keyvault_name = params.get('keyvault_name', "")
    item_type = params.get('item_type', "").lower()  # 'secret', 'key', 'certificate', or empty
    item_name = params.get('item_name', "")
    version = params.get('version', None)  # Optional version of the item

    if not keyvault_name:
        logging.error("Key Vault URL and item_name are required.")
        return

    types_to_try = ['secret', 'key', 'certificate'] if not item_type else [item_type]

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    found_any = False
    for current_type in types_to_try:
        if current_type not in ['secret', 'key', 'certificate']:
            logging.error(f"Invalid item_type: {current_type}. Must be 'secret', 'key', or 'certificate'.")
            continue

        # Construct the base URL for the item
        #"https://kvtest123.vault.azure.net"
        endpoint = f"https://{keyvault_name}.vault.azure.net/{current_type}s/{item_name}"
        if version:
            endpoint += f"/{version}"
        query_params = {"api-version": "7.3"}

        logging.info(f"Submitting GET request to {endpoint}")

        response = requests.get(endpoint, headers=headers, params=query_params)

        if response.status_code == 200:
            found_any = True
            response_json = response.json()
            print(response_json)
            # If listing, print all item names
            if "value" in response_json and isinstance(response_json["value"], list):
                item_names = []
                for entry in response_json["value"]:
                    # Skip managed items
                    if entry.get("managed", False):
                        continue
                    # Prefer 'id' for secrets/certs, 'kid' for keys
                    if "id" in entry:
                        name = entry["id"].split("/")[-1]
                    elif "kid" in entry:
                        name = entry["kid"].split("/")[-1]
                    else:
                        name = entry.get("name", "")
                    item_names.append(name)
                logging.info(f"200 OK - Successfully accessed Key Vault {current_type}")
                for name in item_names:
                    logging.info(name)
            else:
                # Single item access, print the name and value if present
                if "name" in response_json:
                    item_display_name = response_json["name"]
                elif "kid" in response_json:
                    item_display_name = response_json["kid"].split("/")[-1]
                elif "id" in response_json:
                    item_display_name = response_json["id"].split("/")[-1]
                else:
                    item_display_name = item_name
                logging.info(f"200 OK - Successfully accessed Key Vault {current_type}")
                logging.info(f"{item_display_name}")
                # Print the value of the secret/certificate/key if present
                if "value" in response_json:
                    print(f"Value for {item_display_name}: {response_json['value']}")
                elif "key" in response_json:
                    print(f"Key material for {item_display_name}: {response_json['key']}")
                elif "cer" in response_json:
                    print(f"Certificate for {item_display_name}: {response_json['cer']}")
        else:
            logging.error(f"Failed to access Key Vault {current_type} with status code: {response.status_code}")
            try:
                logging.error(response.json())
            except Exception:
                logging.error(response.text)

        logging.info(f"Access Key Vault {current_type.capitalize()} operation finished")

    if not found_any:
        logging.error("Could not access the item as any supported type (secret, key, certificate).")

def add_keyvault_access_policy(auth_config, params, token=False):
    logging.info("Running the keyvault_add_access_policy technique")

    subscription_id = params.get("subscription_id", "")
    resource_group = params.get("resource_group", "")
    keyvault_name = params.get("keyvault_name", "")
    user_principal_object_id = params.get("user_principal_object_id", "")
    tenant_id = params.get("tenant_id", "")

    if not subscription_id or not resource_group or not keyvault_name or not user_principal_object_id or not tenant_id:
        logging.error("Missing required parameters. Ensure all fields are provided.")
        return

    endpoint = (
        f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/"
        f"providers/Microsoft.KeyVault/vaults/{keyvault_name}/accessPolicies/add?api-version=2022-07-01"
    )

    payload = {
        "properties": {
            "accessPolicies": [
                {
                    "tenantId": tenant_id,
                    "objectId": user_principal_object_id,
                    "permissions": {
                        "secrets": ["get", "list"],
                        "keys": ["get", "list"],
                        "certificates": ["get", "list"]
                    }
                }
            ]
        }
    }

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting PUT request to {endpoint}")
    response = requests.put(endpoint, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        logging.info("Access policy successfully added to the Key Vault.")
    else:
        try:
            error_message = response.json().get("error", {}).get("message", "Unknown error.")
        except ValueError:
            error_message = response.text
        logging.error(f"Failed to add access policy: {error_message}")

    logging.info("Key Vault Access Policy Addition: Finished")


def list_keyvault_access_policies(auth_config, params, token=False):
    
    logging.info("Running the keyvault_list_access_policies technique")

    subscription_id = params.get("subscription_id", "")
    resource_group = params.get("resource_group", "")
    keyvault_name = params.get("keyvault_name", "")

    if not subscription_id or not resource_group or not keyvault_name:
        logging.error("Missing required parameters. Ensure subscription_id, resource_group, and keyvault_name are provided.")
        return

    endpoint = (
        f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/"
        f"providers/Microsoft.KeyVault/vaults/{keyvault_name}?api-version=2022-07-01"
    )

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting GET request to {endpoint}")
    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        logging.info("Successfully retrieved Key Vault access policies.")
        keyvault_properties = response.json().get("properties", {})
        access_policies = keyvault_properties.get("accessPolicies", [])
        for policy in access_policies:
            logging.info(f"Access Policy:")
            #logging.info(f"  Tenant ID: {policy.get('tenantId')}")
            logging.info(f"  Object ID: {policy.get('objectId')}")
            #permissions = policy.get("permissions", {})
            #logging.info(f"  Permissions:")
            #logging.info(f"    Secrets: {permissions.get('secrets', [])}")
            #logging.info(f"    Keys: {permissions.get('keys', [])}")
            #logging.info(f"    Certificates: {permissions.get('certificates', [])}")
    else:
        try:
            error_message = response.json().get("error", {}).get("message", "Unknown error.")
        except ValueError:
            error_message = response.text
        logging.error(f"Failed to retrieve Key Vault access policies: {error_message}")

    logging.info("Key Vault Access Policies Listing: Finished")
