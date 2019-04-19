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

    .INPUTS
    None. You cannot pipe objects to Add-Extension.

    .OUTPUTS
    System.String. Add-Extension returns a string with the extension
    or file name.

    .EXAMPLE
    PS> Install-Service -Name "tachyon_server" -Path "C:\microengine\tachyon_server.exe"
    [NSSM] Installing tachyon_server Service
    Done!

    .EXAMPLE
    PS> Install-Service -Name "tachyon_server" -Path "C:\microengine\tachyon_server.exe" -AppDirectory "C:\tachyon" -AppPriority 32
    [NSSM] Installing tachyon_server Service
    Done!

    #>

    Param(
        [Parameter(Mandatory = $true)]
        [String]$Name
        [Parameter(Mandatory = $true)]
        [ValidateDrive("C", "D")]
        [String]$Path
        [String]$AppDirectory = "C:\$Name"
        [String]$AppExit = "Default Restart"
        [Number]$AppRestartDelay = 250
        [String]$AppStdOut = "C:\$Name"
        [String]$AppStdErr = "$AppStdOut"
    )

    echo "[NSSM] Installing $Name Service"
    nssm install $Name $Path
    nssm set $Name AppDirectory "$AppDirectory"
    nssm set $Name AppExit "$AppExit"
    nssm set $Name AppRestartDelay "$AppRestartDelay"
    nssm set $Name AppStdOut "$AppStdOut"
    nssm set $Name AppStdErr "$AppStdErr"

    # The user is now passing other, unanticipated variables to `nssm set`, we
    # read them off as standard PS parameters and raise if the length is odd.
    Function ConvertTo-Hash($list) {
        if ($list.length % 2 -ne 0) { throw "Invalid Length" }

        $h = @{}

        while($list) {
            $head, $next, $list = $list
            $h.$head = $next
        }

        $h
    }

    # Now do the actual `nssm set`
    $remaining = ConvertTo-Hash($args)
    foreach ($key in $remaining.Keys) {
        $value = $remaining[$key]
        nssm set $Name $key $value
    }

    nssm set microengine Start SERVICE_AUTO_START

    echo "Done!"
}
