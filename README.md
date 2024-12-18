# msInvader
[![Open_Threat_Research Community](https://img.shields.io/badge/Open_Threat_Research-Community-brightgreen.svg)](https://twitter.com/OTR_Community)

<div align="center">
    <img src="img/msInvader.png" alt="msInvader logo" style="width: 30%; height: 35%;">
</div>
<br>
msInvader is an adversary simulation tool designed for blue teams to simulate real-world attack techniques within M365 and Azure environments. By generating realistic attack telemetry, msInvader empowers detection engineers, SOC analysts, and threat hunters to assess, enhance, and strengthen their detection and response capabilities.<br><br>

msInvader supports simulating techniques in two common attack scenarios: a compromised user account or a compromised service principal. These scenarios are critical for understanding how adversaries operate after obtaining initial access, allowing teams to simulate post-compromise behaviors and validate their detection and response mechanisms. For user account scenarios, msInvader uses the [resource owner password](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth-ropc) and [device authorization](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) OAuth flows to obtain tokens, simulating attacks such as credential compromise (e.g., phishing or password spraying attacks) or MFA bypass (e.g., adversary-in-the-middle (AiTM) or token theft attacks). For compromised service principals, it leverages the [client credentials](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow) OAuth flow to replicate unauthorized application access.

Once authenticated, msInvader interacts with Exchange Online using three methods: the Graph API, Exchange Web Services (EWS), and the REST API used by the Exchange Online PowerShell module. This flexibility allows blue teams to simulate a wide range of attack techniques across multiple scenarios.

## Documentation

Visit the [Wiki](https://github.com/mvelazc0/msInvader/wiki/) for documentation.

## Demo

[![msInvader](https://img.youtube.com/vi/a6iUrufyXRE/0.jpg)](https://www.youtube.com/watch?v=a6iUrufyXRE)


## Supported Techniques

<div align="center">

| Technique                | Graph | EWS | REST |
|--------------------------|:-----:|:---:|:----:|
| read_email               | X     | X   |      |
| search_mailbox           | X     |     |      |
| search_onedrive          | X     |     |      |
| create_rule              | X     | X   | X    |
| enable_email_forwarding  |       |     | X    |
| add_folder_permission    |       | X   | X    |
| add_mailbox_delegation   |       |     | X    |
| run_compliance_search    |       |     | X     |
| create_mailflow          |       |     | X    |

</div>


For a full list of available techniques, visit [Supported Techniques](https://github.com/mvelazc0/msInvader/wiki/Supported-Techniques) on the Wiki.

## Detections

This section will compile public detection strategies tailored to the techniques simulated by msInvader.

- [Office 365 Collection Techniques](https://research.splunk.com/stories/office_365_collection_techniques/) by the Splunk Threat Research Team

## Quick Start Guide

### Step 1 : Clone repository 

````
git clone https://github.com/mvelazc0/msInvader.git
````

### Step 2: Customize configuration file

1. Open the `config.yaml` file located in the msInvader directory.
2. Customize the configuration file to meet your needs. Refer to the [msInvader Configuration file](https://github.com/mvelazc0/msInvader/wiki/msInvader-Configuration-File) guide for details.
3. Enable and configure the desired techniques in the `playbooks` section. Each technique requires specific parameters, which are detailed in the [Supported Techniques](https://github.com/mvelazc0/msInvader/wiki/Supported-Techniques) documentation.

### Step 3: Run msInvader

To run msInvader with your configuration file:

````
python msInvader.py -c config.yaml
````

## Author

* **Mauricio Velazco** - [@mvelazco](https://twitter.com/mvelazco)

## References

* [ROADtools](https://github.com/dirkjanm/ROADtools) by [Dirk-jan Molleme](https://twitter.com/_dirkjan)
* [GraphRunner](https://github.com/dafthack/GraphRunner) by [Beau Bullock](https://twitter.com/dafthack)

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details
