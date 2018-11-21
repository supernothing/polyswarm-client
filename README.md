# PolySwarm Client Library

[![pipeline status](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/pipeline.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![coverage report](https://gitlab.polyswarm.io/externalci/polyswarm-client/badges/master/coverage.svg)](https://gitlab.polyswarm.io/externalci/polyswarm-client/commits/master)
[![Read the Docs Build Status](https://readthedocs.org/projects/polyswarm-client/badge/?version=latest)](https://polyswarm-client.readthedocs.io/en/latest/)

Client library to simplify interacting with a polyswarmd instance from Python

## Running tests

Use tox, or install dependencies in a virtual environment and run `pytest`


## Development

### Setup your Windows Development Environment

In this section we define the minimum set of tools and libraries that is required to have a working Windows development environment.
These instructions assume you are using a Windows 10 host.

#### Prepare your privileged PowerShell

We will use PowerShell to run most of the commands, so
select `Windows PowerShell` and `Run as Administrator` to get a privileged PowerShell.

Run the following commands in the PowerShell to enable some necessary features:

```
# Allow PowerShell to run scripts
Set-ExecutionPolicy Bypass -Scope Process -Force

# Make PowerShell use TLSv2 for web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Change your working directory to your home directory
cd ~/

# Make a directory to store the downloaded install files
mkdir installers
cd installers
```

#### Chocolatey

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

#### Remove Windows Defender

We will uninstall Windows Defender to prevent it from trying to scan and quarantine your EICAR and other scanner testing files.

Run the following command in the privileged PowerShell:

```
Uninstall-WindowsFeature -Name Windows-Defender
```

Note: 
1. If you'd prefer to leave Windows Defender installed, that is your choice.
In that case, you will need to configure Windows Defender to ignore the EICAR testing files in the polyswarm-client directory.
2. If you have any other anti-virus software on your host, make sure to either remove it, or configure it to ignore the EICAR test files.

#### Install python pip

We will need pip to install several python libraries, so let's install pip.
Run the following commands in the privileged PowerShell:

```
Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'
python get-pip.py
pip install --upgrade pip setuptools wheel
```

#### Clone polyswarm-client repo

Now we meet the basic requirements where we can clone the `polyswarm-clients` repo.

For this step, you do not need the privileged PowerShell, so just open a new regular PowerShell.

Run the following command in the regular PowerShell:

```
git clone https://github.com/polyswarm/polyswarm-client.git
```

#### Create python virtual environment

We will create a python virtual environment, so we do not mess with the system python packages.

Run the following command in the regular PowerShell:

```
cd ~/
python -m venv polyswarmvenv
./polyswarmvenv/Scripts/Activate.ps1
```

We will now use this activated PowerShell to run our python commands.

#### Install python packages into venv

Into our virtual environment, we want to install several python packages.
Use the activated PowerShell from the previous step to do this.

Run the following commands in the activated PowerShell:

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

