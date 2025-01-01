import requests
import time
import logging
import random


def vm_execute_command(auth_config, params, token=False):
    
    logging.info("Running the vm_execute_command technique")

    subscription_id = params.get("subscription_id", "")
    resource_group = params.get("resource_group", "")
    vm_name = params.get("vm_name", "")
    command_type = params.get("command", {}).get("type", "linux").lower()
    script = params.get("command", {}).get("script", [])
    parameters = params.get("command", {}).get("parameters", [])
    poll_interval = params.get("poll_interval", 5)
    timeout = params.get("timeout", 300)

    if not subscription_id or not resource_group or not vm_name:
        logging.error("Subscription ID, Resource Group, and VM Name are required.")
        return

    endpoint = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.Compute/"
        f"virtualMachines/{vm_name}/runCommand?api-version=2022-08-01"
    )

    payload = {
        "commandId": "RunShellScript" if command_type == "linux" else "RunPowerShellScript",
        "script": script,
        "parameters": parameters,
    }

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting POST request to {endpoint}")
    response = requests.post(endpoint, headers=headers, json=payload)

    if response.status_code == 202:
        operation_url = response.headers.get("Azure-AsyncOperation")
        if not operation_url:
            logging.error("202 Accepted but no operation URL provided for tracking.")
            logging.info("VM Command Execution: Finished with FAILURE")
            return

        logging.info("Command accepted, tracking asynchronous execution.")
        elapsed_time = 0

        while elapsed_time < timeout:
            logging.info(f"Polling operation status (Elapsed: {elapsed_time}s)...")
            status_response = requests.get(operation_url, headers=headers)
            output = status_response.json().get("properties", {}).get("output", "No output available")


            if status_response.status_code == 200:
                operation_status = status_response.json().get("status", "").lower()

                if operation_status == "succeeded":
                    logging.info("Command executed successfully.")
                    logging.info("VM Command Execution: Finished with SUCCESS")
                    logging.info(f"Command Output: {output}")
                    return
                elif operation_status == "failed":
                    logging.error("Command execution failed.")
                    logging.info("VM Command Execution: Finished with FAILURE")
                    return
                else:
                    logging.info(f"Current operation status: {operation_status}")

            else:
                logging.error(f"Error while polling status: {status_response.text}")
                logging.info("VM Command Execution: Finished with FAILURE")
                return

            time.sleep(poll_interval)
            elapsed_time += poll_interval

        logging.error("Command execution timed out.")
    elif response.status_code == 200:
        logging.info("Command executed synchronously and succeeded.")
        logging.info("VM Command Execution: Finished with SUCCESS")
    else:
        error_message = response.json().get("error", {}).get("message", "Unknown error.")
        logging.error(f"Command execution failed: {error_message}")
        logging.info("VM Command Execution: Finished with FAILURE")


def vm_list_extensions(auth_config, params, token=False):
    
    logging.info("Running the vm_list_extensions technique")

    subscription_id = params.get("subscription_id", "")
    resource_group = params.get("resource_group", "")
    vm_name = params.get("vm_name", "")

    if not subscription_id or not resource_group or not vm_name:
        logging.error("Missing required parameters. Ensure subscription_id, resource_group, and vm_name are provided.")
        return

    endpoint = (
        f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/"
        f"providers/Microsoft.Compute/virtualMachines/{vm_name}/extensions?api-version=2022-08-01"
    )

    access_token = token["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    logging.info(f"Submitting GET request to {endpoint}")
    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        logging.info("VM extensions successfully retrieved.")
        extensions = response.json().get("value", [])
        for ext in extensions:
            logging.info(f"Extension Found: {ext.get('name')} ({ext.get('type')})")
            logging.info(f"Publisher: {ext.get('properties', {}).get('publisher')}")
            logging.info(f"TypeHandlerVersion: {ext.get('properties', {}).get('typeHandlerVersion')}")
            logging.info(f"ProvisioningState: {ext.get('properties', {}).get('provisioningState')}")
    else:
        try:
            error_message = response.json().get("error", {}).get("message", "Unknown error.")
        except ValueError:
            error_message = response.text
        logging.error(f"Failed to list VM extensions: {error_message}")

    logging.info("VM Extension Listing: Finished")
        