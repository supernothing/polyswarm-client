# PolySwarm Client Library

[![pipeline status](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/pipeline.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![coverage report](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/coverage.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![Read the Docs Build Status](https://readthedocs.org/projects/polyswarm-client/badge/?version=latest)](https://polyswarm-client.readthedocs.io/en/latest/)

Client library to simplify interacting with a polyswarmd instance from Python

## Important Changes

### The update from 0.1.2 to 0.2.0 is a breaking change for Microengines. 

Microgengine implementations using polyswarmclient <= 0.1.2 used this pattern:

```
from polyswarmclient.microengine import Microengine

class CustomMicroengine(Microengine):
    # Microengine implementation here
```

For polyswarmclient >= 0.2.0, Microengine implementations should use the following pattern:
```
from polyswarmclient.abstractmicroengine import AbstractMicroengine

class Microengine(AbstractMicroengine):
    # Microengine implementation here
```

This implies that custom microengines now only need to provide their python module name to the `--backend` argument
instead of `module_name:CustomMicroengine`.

Additionally, as of polyswarmclient 0.2.0, AbstractMicroengine.scan() will now raise an exception if it 
has not been overridden by a sub-class and the subclass did not provide a scanner to the constructor.


## Configuring Development Environment

### Windows

In this section we define the minimum set of tools and libraries that is required to have a working Windows development environment.

These instructions assume you are using a Windows 10 host.

#### Configure Environment

We'll use an elevated PowerShell terminal to configure our environment.

1. Open an "elevated" PowerShell terminal: search "PowerShell" in the desktop search bar, right click on "Windows PowerShell" and select "Run as administrator". The following commands are to be run in this terminal.

2. Permit script execution:
```
Set-ExecutionPolicy Bypass -Scope Process -Force
```

3. Force PowerShell to use TLSv2 (this is actually required for some dependancies):
```
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
```

4. Create & change to a local directory for housing installation files:
```
mkdir ~/installers
pushd ~/installers
```

#### Install Chocolatey & Prerequisities

We will use Chocolatey to install several tools, so let's get Chocolatey installed first.

Run the following command in the privileged PowerShell:

```
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
```

Next, use Chocolatey to install those tools.

```
choco install python --version 3.5.4 -y
choco install git -y
choco install 7zip -y
choco install visualcpp-build-tools --version 14.0.25420.1 -y
choco install vim -y
```

#### Disable Windows Defender

We will disable Windows Defender to prevent it from trying to scan and quarantine your EICAR and other scanner testing files.

1. Run the following command in the privileged PowerShell:
```
Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender' DisableAntiSpyware 1
```

2. Reboot Windows.

*If you'd prefer to keep Windows Defender or a 3rd party AV installed, whitelist the directory containing PolySwarm related code, including this repository and any scan testing files (e.g. EICAR).*

#### Clone polyswarm-client

Now we meet the basic requirements where we can clone the `polyswarm-clients` repo.

For this step, you do not need the privileged PowerShell, so just open a new regular PowerShell.

Run the following command in the regular PowerShell:

```
git clone https://github.com/polyswarm/polyswarm-client.git
```

#### Create Python Virtual Environment

We will create a Python virtual environment (virtualenv), so we avoid dirtying system-wide Python packages.

1. Start a regular (not elevated) PowerShell.

2. Permit script execution:
```
Set-ExecutionPolicy Bypass -Scope Process -Force
```

3. Create & use the virtualenv:
```
cd ~
python -m venv polyswarmvenv
./polyswarmvenv/Scripts/Activate.ps1
```

We will now use this activated PowerShell to run our python commands.

#### Install Python Packages (in the Virtual Environment)

1. Ensure you're in your PolySwarm virtualenv (from previous step).

2. Install prerequisites:
```
cd polyswarm-client
pip install --upgrade awscli
pip install -r requirements.txt
pip install .
```

The last pip command above will install the polyswarm-client python package into your virtual environment.
Notice the '.' after the word install.

#### Development IDE

If you have your own IDE for development, feel free to use it, but if not, we recommend that you install PyCharm Community Edition.

You will need to use your web browser for this step.

Browse to: https://www.jetbrains.com/pycharm/download/#section=windows and click the `Download` button under Community.
Once you've downloaded the installer, run it to install PyCharm.

## Running Tests

Use tox, or install dependencies in a virtual environment and run `pytest`
