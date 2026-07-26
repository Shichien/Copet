[CmdletBinding()]
param(
    [string] $OutputPath = (Join-Path $PSScriptRoot 'app.asar')
)

$ErrorActionPreference = 'Stop'
$expectedAppVersion = '26.715.72359'
$expectedStoreVersion = [Version] '26.715.10079.0'
$expectedSourceAsarSha256 = '719D9B2DB7EB550D7A507A61716DDE3360A9C9E4387C6EE6B23F42FD3191DFA2'

$requiredSources = @(
    'patch-client.cjs',
    'interactive-pet-loader.cjs',
    'interactive-pet-runtime.js',
    'interactive-pet-store.cjs'
)
foreach ($name in $requiredSources) {
    $path = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required patch source is missing: $path"
    }
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$npxCommand = Get-Command npx -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand -or $null -eq $npxCommand) {
    throw 'Node.js and npm are required to build the patched app.asar.'
}

$package = Get-AppxPackage -Name 'OpenAI.Codex' |
    Sort-Object Version -Descending |
    Select-Object -First 1
if ($null -eq $package) {
    throw 'The Microsoft Store Codex package is not installed.'
}
if ($package.Version -ne $expectedStoreVersion) {
    throw "Unsupported Microsoft Store Codex version $($package.Version); expected $expectedStoreVersion"
}

$sourceAsar = Join-Path $package.InstallLocation 'app\resources\app.asar'
if (-not (Test-Path -LiteralPath $sourceAsar -PathType Leaf)) {
    throw "Codex app.asar is missing: $sourceAsar"
}
$sourceHash = (Get-FileHash -LiteralPath $sourceAsar -Algorithm SHA256).Hash
if ($sourceHash -ne $expectedSourceAsarSha256) {
    throw 'The installed Codex app.asar does not match the build this patch targets.'
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$temporaryBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
$temporaryRoot = Join-Path $temporaryBase "CopetBuild-$([Guid]::NewGuid().ToString('N'))"
$unpackedRoot = Join-Path $temporaryRoot 'app'
$temporaryAsar = Join-Path $temporaryRoot 'app.asar'
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $extractArgs = @('--yes', '@electron/asar', 'extract', $sourceAsar, $unpackedRoot)
    & $npxCommand.Source @extractArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "asar extraction failed with exit code $exitCode"
    }

    $patchArgs = @((Join-Path $PSScriptRoot 'patch-client.cjs'), $unpackedRoot)
    & $nodeCommand.Source @patchArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Copet client patch failed with exit code $exitCode"
    }

    $packageJson = Get-Content -Raw -LiteralPath (Join-Path $unpackedRoot 'package.json') |
        ConvertFrom-Json
    if ($packageJson.version -ne $expectedAppVersion) {
        throw "Patched app version $($packageJson.version) does not match $expectedAppVersion"
    }

    $packArgs = @('--yes', '@electron/asar', 'pack', $unpackedRoot, $temporaryAsar)
    & $npxCommand.Source @packArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "asar packaging failed with exit code $exitCode"
    }
    if (-not (Test-Path -LiteralPath $temporaryAsar -PathType Leaf)) {
        throw 'The patched app.asar was not created.'
    }

    Copy-Item -LiteralPath $temporaryAsar -Destination $resolvedOutput -Force
    $outputHash = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash
    [pscustomobject]@{
        AppVersion = $expectedAppVersion
        Output = $resolvedOutput
        Sha256 = $outputHash
    }
}
finally {
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $isExpectedTemporaryPath =
        $resolvedTemporaryRoot.StartsWith("$temporaryBase\", [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedTemporaryRoot).StartsWith('CopetBuild-', [System.StringComparison]::Ordinal)
    if (-not $isExpectedTemporaryPath) {
        throw "Refusing to clean unexpected temporary path: $resolvedTemporaryRoot"
    }
    if (Test-Path -LiteralPath $resolvedTemporaryRoot) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
