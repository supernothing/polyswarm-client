# This file contains utilities which are added to all users (and all hosts)
# $profile, Powershell's rcfile analogue. Like an RC file, this will
# be run every time powershell (or core) runs, please remember to
# keep this file LEAN! - zv

function Install-Service {
    <#
    .SYNOPSIS
    Installs a new service from the path of an executable

    .DESCRIPTION
    Install-Service converts an ordinary executable into a Windows service with
    NSSM. By default, Install-Service will use Polyswarm-recommended service
    defaults for important NSSM parameters, however, you can override any of
    these and provide an 'nssm set' option you would like (even those not
    parameterized by this script) by passing it with a dash prefixed (e.g
    -AppPriority 20)

    .PARAMETER Path
    Specifies the executable path

    .PARAMETER Name
    Specifies the service name

    .PARAMETER Callback
    Specifies the service name

    .INPUTS
    None. You cannot pipe objects to Add-Extension.

    .OUTPUTS
    System.String. Add-Extension returns a string with the extension
    or file name.

    .EXAMPLE
    PS> Install-Service -Name tachyon_server -Path C:\microengine\tachyon_server.exe
    [NSSM] Installing tachyon_server Service
    Done!

    .EXAMPLE
    PS> Install-Service -Name microengine -Path C:\Python\Scripts\microengine.exe -AppDirectory "C:\" -AppParameters "--log DEBUG" -AppParameters "--insecure-transport" --keyfile "dummy"
    [NSSM] Installing tachyon_server Service
    Done!
    PS> Start-Service microengine
    Using account: 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    Logging Level: DEBUG

    .LINK
    https://nssm.cc/usage

    .LINK
    https://nssm.cc/commands

    .LINK
    https://gist.github.com/magnetikonline/2217fd95cf15a0324696

    #>

    Param(
        [Parameter(Mandatory = $true)]
        [String]$Name
        [Parameter(Mandatory = $true)]
        [String]$Path
        [String]$AppDirectory = "C:\$Name"
        [String]$AppExit = "Default Restart"
        [Number]$AppRestartDelay = 250
        [String]$AppStdOut = "C:\$Name"
        [String]$AppStdErr = "$AppStdOut"
        [String]$StartType = "SERVICE_AUTO_START"
    )

    Get-Command "nssm"

    echo "[NSSM] Installing $Name Service"

    iex "nssm install $Name $Path"
    iex "nssm set $Name AppDirectory $AppDirectory"
    iex "nssm set $Name AppExit $AppExit"
    iex "nssm set $Name AppRestartDelay $AppRestartDelay"
    iex "nssm set $Name AppStdOut $AppStdOut"
    iex "nssm set $Name AppStdErr $AppStdErr"
    iex "nssm set $Name Start $StartType"

    # The user is now passing other, nondefaulting, unanticipated variables to
    # `nssm set`, we read them off as standard PS parameters and raise if the
    # length is odd.
    if ($args.length -ge 1) {
        # don't clobber the real args
        $sargs = $args.Clone()
        if ($sargs.length % 2 -ne 0) {
            throw "Invalid Supplementary Arglist Length"
        }

        while ($sargs) {
            $key, $value, $sargs = $sargs
            # Now do the actual `nssm set`
            iex "nssm set $Name $key $value"
        }
    }


    echo "Done!"
}
