[CmdletBinding()]
param(
    [string] $InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexInteractivePet\app-26.721.41059'),
    [switch] $IsolatedProfile,
    [switch] $EnableLogging,
    [ValidateRange(1024, 65535)]
    [int] $RemoteDebuggingPort
)

$ErrorActionPreference = 'Stop'
$resolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$executable = Join-Path $resolvedInstallRoot 'ChatGPT.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Interactive Codex is not installed: $executable"
}

$nativeArgs = [System.Collections.Generic.List[string]]::new()
if ($IsolatedProfile) {
    $profileRoot = Join-Path $env:LOCALAPPDATA 'CodexInteractivePet\profile'
    New-Item -ItemType Directory -Path $profileRoot -Force | Out-Null
    $nativeArgs.Add("--user-data-dir=$profileRoot")
}
if ($EnableLogging) {
    $logRoot = Join-Path $env:LOCALAPPDATA 'CodexInteractivePet\logs'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $nativeArgs.Add('--enable-logging')
    $nativeArgs.Add("--log-file=$(Join-Path $logRoot 'electron.log')")
}
if ($RemoteDebuggingPort -gt 0) {
    $nativeArgs.Add("--remote-debugging-port=$RemoteDebuggingPort")
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $executable
$startInfo.UseShellExecute = $false
foreach ($nativeArg in $nativeArgs) {
    $startInfo.ArgumentList.Add($nativeArg)
}
$process = [System.Diagnostics.Process]::Start($startInfo)

[pscustomobject]@{
    ProcessId = $process.Id
    Executable = $executable
    IsolatedProfile = [bool]$IsolatedProfile
    RemoteDebuggingPort = if ($RemoteDebuggingPort -gt 0) { $RemoteDebuggingPort } else { $null }
}
