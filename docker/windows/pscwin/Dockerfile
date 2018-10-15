FROM microsoft/windowsservercore:1803
#FROM microsoft/dotnet-framework:4.7.1


#RUN @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"; SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"

# wait for vs_installer.exe, vs_installerservice.exe
# or vs_installershell.exe because choco doesn't
RUN ["powershell", "Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"]
RUN choco install python --version 3.5.4 -y
RUN choco install git -y
RUN choco install 7zip -y
WORKDIR /dist

#RUN forfiles /c "cmd /c pip install @file"
RUN pip install pip --upgrade
COPY install-ps-cli.ps1 .
RUN powershell.exe .\install-ps-cli.ps1

CMD microengine.exe
