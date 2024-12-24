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

            if status_response.status_code == 200:
                operation_status = status_response.json().get("status", "").lower()

                if operation_status == "succeeded":
                    logging.info("Command executed successfully.")
                    logging.info("VM Command Execution: Finished with SUCCESS")
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