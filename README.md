# msInvader
[![Open_Threat_Research Community](https://img.shields.io/badge/Open_Threat_Research-Community-brightgreen.svg)](https://twitter.com/OTR_Community)

<div align="center">
    <img src="img/msInvader.png" alt="msInvader logo">
</div>
<br>
msInvader is an adversary simulation tool built for blue teams, designed to simulate adversary techniques within M365 and Azure environments. Its purpose is to generate attack telemetry that aids teams in building, testing, and enhancing detection analytics. <br> <br>
To facilitate realistic simulations, msInvader implements multiple authentication mechanisms that mirror different attack scenarios. It supports two OAuth flows for simulating a compromised user scenario: the resource owner password flow and the device authorization flow. These methods allow msInvader to obtain tokens simulating the compromise of a user's credentials or an successful adversary in the middle (AiTM) attack . Additionally, msInvader can replicate conditions involving compromised service principals by supporting the client credentials OAuth flow.<br><br>

Once authenticated, msInvader is capable of interacting with Exchange Online through three distinct methods: the Graph API, Exchange Web Services (EWS), and the REST API utilized by the Exchange Online PowerShell module. This support enables msInvader to comprehensively simulate attack techniques, providing blue teams with the flexibility to simulate multiple scenarios. 

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


Visit [Supported Techniques](https://github.com/mvelazc0/msInvader/wiki/Supported-Techniques) on the Wiki for technique descriptions.


## Quick Start Guide

### Step 1 : Clone repository 

````
git clone https://github.com/mvelazc0/msInvader.git
````

### Step 2: Customize configuration file

1. Open the `config.yaml` file located in the msInvader directory.
2. Configure the `authentication` section with your Azure/M365 credentials. Refer to the [msInvader Configuration file](https://github.com/mvelazc0/msInvader/wiki/msInvader-Configuration-File) guide for details.
3. Enable and configure the desired techniques in the `techniques` section. Each technique requires specific parameters, which are detailed in the [Supported Techniques](https://github.com/mvelazc0/msInvader/wiki/Supported-Techniques) documentation.

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
