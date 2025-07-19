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
    Enhanced: Access and print details for all items in the Key Vault (secrets, keys, certificates).
    If item_name is provided, access that specific item. If not, enumerate and print all items of each type.
    """
    logging.info("Running the access_key_vault_item technique (enhanced)")

    keyvault_name = params.get('keyvault_name', "")
    item_type = params.get('item_type', "").lower()  # 'secret', 'key', 'certificate', or empty
    item_name = params.get('item_name', "")
    version = params.get('version', None)  # Optional version of the item

    if not keyvault_name:
        logging.error("Key Vault name is required.")
        return

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Map singular to plural for endpoint construction
    type_map = {
        "secret": "secrets",
        "key": "keys",
        "certificate": "certificates"
    }

    # If no item_type, try all; else, just the specified one
    types_to_try = list(type_map.keys()) if not item_type else [item_type]

    found_any = False

    for current_type in types_to_try:
        if current_type not in type_map:
            logging.error(f"Invalid item_type: {current_type}. Must be 'secret', 'key', or 'certificate'.")
            continue

        plural_type = type_map[current_type]

        # If item_name is provided, access that specific item
        if item_name:
            endpoint = f"https://{keyvault_name}.vault.azure.net/{plural_type}/{item_name}"
            if version:
                endpoint += f"/{version}"
            query_params = {"api-version": "7.3"}
            logging.info(f"Submitting GET request to {endpoint}")
            response = requests.get(endpoint, headers=headers, params=query_params)
            if response.status_code == 200:
                found_any = True
                response_json = response.json()
                # Print the value of the secret/certificate/key if present
                display_name = response_json.get("name") or response_json.get("kid", "").split("/")[-1] or response_json.get("id", "").split("/")[-1] or item_name
                logging.info(f"200 OK - Successfully accessed Key Vault {current_type}: {display_name}")
                if "value" in response_json:
                    print(f"Value for {display_name}: {response_json['value']}")
                elif "key" in response_json:
                    print(f"Key material for {display_name}: {response_json['key']}")
                elif "cer" in response_json:
                    print(f"Certificate for {display_name}: {response_json['cer']}")
                else:
                    print(f"No value found for {display_name}")
            else:
                logging.error(f"Failed to access Key Vault {current_type} '{item_name}' with status code: {response.status_code}")
                try:
                    logging.error(response.json())
                except Exception:
                    logging.error(response.text)
            logging.info(f"Access Key Vault {current_type.capitalize()} operation finished")
        else:
            # No item_name: enumerate all items of this type and print their details
            list_endpoint = f"https://{keyvault_name}.vault.azure.net/{plural_type}"
            query_params = {"api-version": "7.3"}
            logging.info(f"Enumerating all {plural_type} at {list_endpoint}")
            response = requests.get(list_endpoint, headers=headers, params=query_params)
            if response.status_code == 200:
                items = response.json().get("value", [])
                # Exclude managed items for secrets and keys
                if current_type in ["secret", "key"]:
                    items = [item for item in items if not item.get("managed", False)]
                logging.info(f"Found {len(items)} {plural_type}.")
                for entry in items:
                    # Get the item name from the id
                    item_id = entry.get("id") or entry.get("kid")
                    if not item_id:
                        continue
                    item_name_extracted = item_id.split("/")[-1]
                    # Now fetch the actual item details
                    item_endpoint = f"https://{keyvault_name}.vault.azure.net/{plural_type}/{item_name_extracted}"
                    item_query_params = {"api-version": "7.3"}
                    item_response = requests.get(item_endpoint, headers=headers, params=item_query_params)
                    if item_response.status_code == 200:
                        found_any = True
                        item_json = item_response.json()
                        display_name = item_json.get("name") or item_json.get("kid", "").split("/")[-1] or item_json.get("id", "").split("/")[-1] or item_name_extracted
                        logging.info(f"200 OK - {current_type.capitalize()}: {display_name}")
                        if "value" in item_json:
                            print(f"Value for {display_name}: {item_json['value']}")
                        elif "key" in item_json:
                            print(f"Key material for {display_name}: {item_json['key']}")
                        elif "cer" in item_json:
                            print(f"Certificate for {display_name}: {item_json['cer']}")
                        else:
                            print(f"No value found for {display_name}")
                    else:
                        logging.error(f"Failed to get details for {current_type} '{item_name_extracted}': {item_response.status_code}")
                        try:
                            logging.error(item_response.json())
                        except Exception:
                            logging.error(item_response.text)
            else:
                logging.error(f"Failed to list Key Vault {plural_type} with status code: {response.status_code}")
                try:
                    logging.error(response.json())
                except Exception:
                    logging.error(response.text)
            logging.info(f"Enumeration for {plural_type} finished.")

    if not found_any:
        logging.error("Could not access any items as secret, key, or certificate.")

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
