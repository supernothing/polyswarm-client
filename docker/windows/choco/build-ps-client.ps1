$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['*:ErrorAction']='Stop'

pip wheel -r /usr/src/app/requirements.txt
7z a polyswarm-client.7z *.whl


aws.cmd s3 cp --acl=public-read  polyswarm-client.7z s3://polyswarm-wheel/

$native_call_success = $?
if (-not $native_call_success)
{
    throw 'failed to upload to S3 bucket'
}