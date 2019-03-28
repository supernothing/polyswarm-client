#FROM microsoft/windowsservercore:ltsc2016
#FROM microsoft/dotnet-framework:4.7.1
FROM microsoft/windowsservercore:1803


#RUN @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"; SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"

# wait for vs_installer.exe, vs_installerservice.exe
# or vs_installershell.exe because choco doesn't

RUN ["powershell", "Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"]
RUN choco install python --version 3.6.7 -y
RUN choco install git -y
RUN choco install 7zip -y


RUN powershell -NoProfile -InputFormat None -Command \
    choco install visualcpp-build-tools \
#        --version 15.0.26228.20170424 -y; \
        --version 14.0.25420.1 -y;

#    Write-Host 'Waiting for Visual C++ Build Tools to finish'; \
#    Wait-Process -Name vs_installerservice


ENV PYTHON_PIP_VERSION 18.0

RUN powershell Write-Host ('Installing pip=={0} ...' -f $env:PYTHON_PIP_VERSION); \
	[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; \
	Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'; \
	python get-pip.py \
		--disable-pip-version-check \
		--no-cache-dir \
		('pip=={0}' -f $env:PYTHON_PIP_VERSION) \
	; \
	Remove-Item get-pip.py -Force; \
	\
	Write-Host 'Verifying pip install ...'; \
	pip --version; \
	\
	Write-Host 'Complete.';

WORKDIR /usr/src/app

COPY . .


#RUN powershell Write-Host "$((Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment\' -Name 'PATH').Path); $((Get-ItemProperty -Path 'HKCU:\Environment' -Name 'PATH').Path)"
#RUN RefreshEnv
#RUN "c:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86_x64 &&

#RUN powershell Get-Item Env:Path
#RUN pip install --no-cache-dir -r requirements.txt
##
##
WORKDIR /dist

#RUN pip install --no-cache-dir .
###
#RUN git clone -b fix/less-reqs-windows https://github.com/polyswarm/polyswarm-client.git
RUN pip install pip awscli --upgrade
RUN choco install vim -y
COPY docker/windows/choco/build-ps-client.ps1 build-ps-client.ps1
CMD ["powershell.exe", ".\\build-ps-client.ps1" ]


