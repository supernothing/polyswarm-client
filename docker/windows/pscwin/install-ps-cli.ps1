write-output "Starting PolySwarm Client Install"

#pip install pip --upgrade
python.exe -m pip install -U pip



Invoke-WebRequest -Uri https://s3.amazonaws.com/polyswarm-wheel/polyswarm-client.7z -OutFile .\polyswarm-client.7z
dir
7z x .\polyswarm-client.7z

&"pip" install @(Get-ChildItem -Recurse -Filter *.whl)

Invoke-WebRequest -Uri https://letsencrypt.org/certs/isrgrootx1.pem.txt -Outfile c:\ca.txt

# add lets encrypt CA in case traefik doesn't chain.
certutil -addstore Root "c:\ca.txt"


write-output "Finished Polyswarm Client Install"

