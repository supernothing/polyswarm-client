# escape=`
# Tag version?
FROM mcr.microsoft.com/windows/servercore:1809
LABEL description="Base image for Polyswarm Windows Microengines"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoProfile", "-command"]

## -- Install Choco -----------------------
RUN iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

## -- Microengine Dependencies ------------
## Needed to build native extensions
RUN choco install -y git `
                     vcbuildtools

## Install basic polyswarm python pkgs
RUN choco install -y python --version 3.6.7
RUN pip install git+https://github.com/polyswarm/ethash.git#egg=pyethash
RUN pip install --no-warn-script-location polyswarm-client

## -- Utilities ---------------------------
RUN choco install -y 7zip `
                     checksum `
                     nmap `
                     sysinternals `
                     vim

## -- NSSM -------------------------------
RUN choco install -y nssm

## -- Polyswarm Powershell Utilities -----
ADD polyswarm-profile.ps1 C:/polyswarm/polyswarm-profile.ps1
RUN Get-Content C:/polyswarm/polyswarm-profile.ps1 `
  | Set-Content $profile.AllUsersAllHosts

## ---------------------------------------

CMD powershell
