# escape=`
# Tag version?
FROM mcr.microsoft.com/windows/servercore:1809
LABEL description="Base image for Polyswarm Windows Microengines"
SHELL ["powershell", "-ExecutionPolicy bypass", "-NoProfile", "-command"]

## -- Install Choco -----------------------
RUN iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

## -- Microengine Dependencies ------------
## Needed to build native extensions
RUN choco install -y git
RUN choco install -y vcbuildtools --version 2015.4

## Install basic polyswarm python pkgs
RUN choco install -y python --version 3.6.7
RUN pip install --no-warn-script-location polyswarm-client

## -- Utilities ---------------------------
RUN choco install -y vim-console

## -- NSSM -------------------------------
RUN choco install -y nssm

## -- Polyswarm Powershell Utilities -----
ADD polyswarm-profile.ps1 C:/polyswarm/polyswarm-profile.ps1
RUN Get-Content C:/polyswarm/polyswarm-profile.ps1 `
  | Set-Content $profile.AllUsersAllHosts

# Remove various caches
RUN Remove-Item -Path "$env:TMP\*","$env:LocalAppData\pip\*" -Recurse -Force

## ---------------------------------------

CMD powershell
