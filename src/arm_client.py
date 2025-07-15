import requests
import logging

def enumerate_arm_role_assignments(auth_config, params, token=False):
    """
    Enumerate Azure role assignments using the ARM API.
    Lists all role assignments for a given subscription.
    """
    logging.info("Running the enumerate_arm_role_assignments technique")
    subscription_id = params.get("subscription_id")
    if not subscription_id:
        logging.error("subscription_id parameter is required for ARM role assignment enumeration.")
        return

    # ARM endpoint for role assignments
    url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"

    access_token = token["access_token"]
    if not access_token:
        logging.error("A valid Azure access token is required for ARM API calls.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            assignments = response.json().get("value", [])
            logging.info(f"Found {len(assignments)} role assignments in subscription {subscription_id}:")
            for assignment in assignments:
                principal_id = assignment["properties"].get("principalId")
                role_definition_id = assignment["properties"].get("roleDefinitionId")
                scope = assignment["properties"].get("scope")
                logging.info(f"Principal: {principal_id}, Role: {role_definition_id}, Scope: {scope}")
            return assignments
        else:
            logging.error(f"Failed to enumerate role assignments: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Exception during ARM role assignment enumeration: {e}")

def enumerate_arm_resources(auth_config, params, token=False):
    """
    Enumerate all Azure resources in a subscription using the ARM API.
    Provides a complete inventory of resources (VMs, storage accounts, databases, etc.).
    """
    logging.info("Running the enumerate_arm_resources technique")
    subscription_id = params.get("subscription_id")
    if not subscription_id:
        logging.error("subscription_id parameter is required for ARM resource enumeration.")
        return

    # ARM endpoint for resource discovery
    url = f"https://management.azure.com/subscriptions/{subscription_id}/resources?api-version=2022-09-01"

    access_token = token["access_token"]
    if not access_token:
        logging.error("A valid Azure access token is required for ARM API calls.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            resources = response.json().get("value", [])
            logging.info(f"Found {len(resources)} resources in subscription {subscription_id}:")
            for resource in resources:
                res_id = resource.get("id")
                res_type = resource.get("type")
                res_name = resource.get("name")
                res_location = resource.get("location")
                logging.info(f"Resource: {res_name}, Type: {res_type}, Location: {res_location}, ID: {res_id}")
            return resources
        else:
            logging.error(f"Failed to enumerate resources: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Exception during ARM resource enumeration: {e}")

def enumerate_privileged_arm_role_holders(auth_config, params, token=False):
    """
    Enumerate all identities assigned to high-privilege roles (Owner, Contributor, User Access Administrator)
    in the given subscription using the ARM API.
    """
    logging.info("Running the enumerate_privileged_role_holders technique")
    subscription_id = params.get("subscription_id")
    if not subscription_id:
        logging.error("subscription_id parameter is required for privileged role enumeration.")
        return

    # Well-known roleDefinitionIds for privileged roles
    privileged_roles = {
        "Owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
        "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
        "User Access Administrator": "e8611c31-1e3a-4b2a-9c29-54c13a989da2"
    }

    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}/providers/"
        "Microsoft.Authorization/roleAssignments?api-version=2022-04-01&$filter=atScope()"
    )

    access_token = token["access_token"]
    if not access_token:
        logging.error("A valid Azure access token is required for ARM API calls.")
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            assignments = response.json().get("value", [])
            privileged_assignments = []
            for assignment in assignments:
                role_definition_id = assignment["properties"].get("roleDefinitionId", "").lower()
                for role_name, role_id in privileged_roles.items():
                    if role_id in role_definition_id:
                        principal_id = assignment["properties"].get("principalId")
                        scope = assignment["properties"].get("scope")
                        logging.info(
                            f"Privileged Role: {role_name}, Principal: {principal_id}, "
                            f"RoleDefinitionId: {role_definition_id}, Scope: {scope}"
                        )
                        privileged_assignments.append({
                            "role": role_name,
                            "principalId": principal_id,
                            "roleDefinitionId": role_definition_id,
                            "scope": scope
                        })
            logging.info(f"Found {len(privileged_assignments)} privileged role assignments in subscription {subscription_id}.")
            return privileged_assignments
        else:
            logging.error(f"Failed to enumerate privileged role holders: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Exception during privileged role enumeration: {e}")