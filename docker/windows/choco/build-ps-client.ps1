$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['*:ErrorAction']='Stop'

git clone https://github.com/polyswarm/ethash.git
cd ethash
python setup.py sdist bdist_wheel

move-item  c:\dist\ethash\dist\*.whl c:\dist\ethash\
pip wheel /usr/src/app/

7z a polyswarm-client.7z *.whl


#aws.cmd s3 cp --acl=public-read  polyswarm-client.7z s3://polyswarm-wheel/

$native_call_success = $?
if (-not $native_call_success)
{
    throw 'failed to upload to S3 bucket'
}