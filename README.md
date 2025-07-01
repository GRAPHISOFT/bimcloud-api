# About

This repository hosts the BIMcloud API specification, a small library, and an example application in Python. Please note that this is the first released version; upcoming releases will extend or alter the functionalities based on user workflows, performance, and security considerations.

# Specification

Please refer to [openapi/2023.2.yaml](https://raw.githubusercontent.com/GRAPHISOFT/bimcloud-api/master/openapi/2023.2.yaml) for the specification. It is in standard OpenAPI 3.0 (Swagger) format, which can be viewed using any compatible viewer (such as VS Code, or by pasting the GitHub raw URL into [the online Swagger viewer](https://petstore.swagger.io/)).

# Demo

The demo application (`demo.py`) demonstrates a simple workflow that covers all operations required to upload, download, and delete a file at an arbitrary path on a BIMcloud server.

Please refer to the [lib/workflow.py](https://github.com/GRAPHISOFT/bimcloud-api/blob/master/lib/workflow.py) source code and its comments for detailed information.

*Notice: Since authentication APIs send passwords in clear text, it is advised to configure BIMcloud to be accessible using HTTPS endpoints from the Internet.*

## Installation

The demo console application requires Python 3.7+ with the [requests](https://2.python-requests.org/) library installed.

Virtual environment setup:

```bash
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
```

## Run

The demo is a basic command-line application. Entering:

```bash
python ./demo.py --help
```

will display:

```
usage: demo.py [-h] -m MANAGER -c CLIENTID [-d] [-u USER] [-p PASSWORD] [-t TEMPDIR]

options:
  -h, --help            show this help message and exit
  -m, --manager MANAGER
                        URL of BIMcloud Manager.
  -c, --clientid CLIENTID
                        3rd party client ID (an arbitrary unique string, e.g., your domain).
  -d, --debug           Debug exceptions.
  -u, --user USER       Username for simple authentication if BIMcloud supports it.
  -p, --password PASSWORD
                        Password for simple authentication if BIMcloud supports it.
  -t, --tempdir TEMPDIR
                        Temporary directory to store downloaded files. Default is the system temporary directory.
```

This should be self-explanatory. For example, to get the demo running, enter:

```bash
python ./demo.py -m=<manager-url> -u=<username> -p=<password> -clientid=<your-domain>
```

Note: Username and password authentication is only allowed if BIMcloud legacy authentication is enabled. If you omit the -u and -p parameters, SSO authentication will be used.