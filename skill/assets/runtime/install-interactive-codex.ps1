[CmdletBinding()]
param(
    [string] $InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexInteractivePet\app-26.721.41059'),
    [string] $PetPackagePath = (Join-Path $PSScriptRoot '..\pet\package'),
    [switch] $PetPackageOnly,
    [switch] $UpgradePetPackage
)

$ErrorActionPreference = 'Stop'
$expectedAppVersion = '26.721.41059'
$expectedStoreVersion = [Version] '26.721.4979.0'
$expectedSourceAsarSha256 = '44884F86D619A12C3C0AF1B8C65945005BDA4379775B03270674C666226FF4B7'
$patchedAsar = Join-Path $PSScriptRoot 'app.asar'

$resolvedInstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$resolvedLocalAppData = [System.IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\')
if (-not $resolvedInstallRoot.StartsWith("$resolvedLocalAppData\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallRoot must stay inside LOCALAPPDATA: $resolvedLocalAppData"
}
$targetAsar = Join-Path $resolvedInstallRoot 'resources\app.asar'
$markerPath = Join-Path $resolvedInstallRoot 'interactive-pet-install.json'
$storePackageVersion = $null
$installedPetId = $null

if ($PetPackageOnly) {
    if (-not (Test-Path -LiteralPath $targetAsar -PathType Leaf)) {
        throw "Existing interactive Codex app.asar is missing: $targetAsar"
    }
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        throw "Existing interactive Codex install marker is missing: $markerPath"
    }
    $existingMarker = Get-Content -Raw -LiteralPath $markerPath | ConvertFrom-Json
    if ($existingMarker.appVersion -ne $expectedAppVersion) {
        throw "Existing interactive Codex version $($existingMarker.appVersion) does not match $expectedAppVersion"
    }
    $installedAsarHash = (Get-FileHash -LiteralPath $targetAsar -Algorithm SHA256).Hash
    if ($existingMarker.appAsarSha256 -ne $installedAsarHash) {
        throw 'Existing interactive Codex app.asar does not match its install marker.'
    }
    $storePackageVersion = $existingMarker.storePackageVersion
}
else {
    if (-not (Test-Path -LiteralPath $patchedAsar -PathType Leaf)) {
        throw "Patched app.asar is missing: $patchedAsar. Run build-interactive-codex.ps1 first."
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

    $sourceRoot = Join-Path $package.InstallLocation 'app'
    $sourcePackageJson = Join-Path $sourceRoot 'resources\app.asar'
    if (-not (Test-Path -LiteralPath $sourcePackageJson -PathType Leaf)) {
        throw "Codex app.asar is missing: $sourcePackageJson"
    }
    $sourceAsarSha256 = (Get-FileHash -LiteralPath $sourcePackageJson -Algorithm SHA256).Hash
    if ($sourceAsarSha256 -ne $expectedSourceAsarSha256) {
        throw 'The installed Codex app.asar does not match the build this patch targets.'
    }

    New-Item -ItemType Directory -Path $resolvedInstallRoot -Force | Out-Null
    $entries = Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force
    foreach ($entry in $entries) {
        $relativePath = [System.IO.Path]::GetRelativePath($sourceRoot, $entry.FullName)
        if ($relativePath -eq 'resources\app.asar') {
            continue
        }
        $targetPath = Join-Path $resolvedInstallRoot $relativePath
        if ($entry.PSIsContainer) {
            New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
            continue
        }
        if (Test-Path -LiteralPath $targetPath -PathType Leaf) {
            continue
        }
        $targetDirectory = Split-Path -Parent $targetPath
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        $copyParams = @{
            LiteralPath = $entry.FullName
            Destination = $targetPath
        }
        Copy-Item @copyParams
    }

    $copyAsarParams = @{
        LiteralPath = $patchedAsar
        Destination = $targetAsar
        Force = $true
    }
    Copy-Item @copyAsarParams
    $storePackageVersion = $package.Version.ToString()
}

if (-not (Test-Path -LiteralPath $PetPackagePath -PathType Container)) {
    throw "Pet package directory is missing: $PetPackagePath"
}

$petManifestPath = Join-Path $PetPackagePath 'pet.json'
$interactionManifestPath = Join-Path $PetPackagePath 'interaction.json'
foreach ($requiredPath in @($petManifestPath, $interactionManifestPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Pet package file is missing: $requiredPath"
    }
}
$petManifest = Get-Content -LiteralPath $petManifestPath -Raw | ConvertFrom-Json
$interactionManifest = Get-Content -LiteralPath $interactionManifestPath -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($petManifest.id) -or $petManifest.id -notmatch '^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$') {
    throw 'The pet id must be a safe lowercase pet folder name.'
}
$officialAtlasName = [string] $petManifest.spritesheetPath
$interactionAtlasName = [string] $interactionManifest.atlases.interaction.path
foreach ($atlasName in @($officialAtlasName, $interactionAtlasName)) {
    if (
        [string]::IsNullOrWhiteSpace($atlasName) -or
        [System.IO.Path]::GetFileName($atlasName) -ne $atlasName
    ) {
        throw 'Pet atlas paths must be plain file names inside the package.'
    }
}
$officialAtlasPath = Join-Path $PetPackagePath $officialAtlasName
$interactionAtlasPath = Join-Path $PetPackagePath $interactionAtlasName
foreach ($requiredPath in @($officialAtlasPath, $interactionAtlasPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Pet package file is missing: $requiredPath"
    }
}
if ($interactionManifest.schemaVersion -ne 1) {
    throw 'The interaction package schemaVersion must be 1.'
}
if ($interactionManifest.petId -ne $petManifest.id) {
    throw 'The interaction package petId does not match pet.json.'
}
if ($interactionManifest.compatibility.officialWakeCommand -ne '/pet') {
    throw 'The interaction package must preserve the /pet wake command.'
}
$userProfile = [Environment]::GetFolderPath('UserProfile')
$codexRoot = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    Join-Path $userProfile '.codex'
}
else {
    [System.IO.Path]::GetFullPath($env:CODEX_HOME)
}
$petsRoot = [System.IO.Path]::GetFullPath((Join-Path $codexRoot 'pets'))
$petTarget = [System.IO.Path]::GetFullPath((Join-Path $petsRoot $petManifest.id))
if (-not $petTarget.StartsWith("$($petsRoot.TrimEnd('\'))\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'The resolved pet target is outside the Codex pets directory.'
}
New-Item -ItemType Directory -Path $petTarget -Force | Out-Null
$petSourceFiles = @(
    $petManifestPath,
    $officialAtlasPath,
    $interactionManifestPath,
    $interactionAtlasPath
)
$conflictingFiles = @()
foreach ($sourceFile in $petSourceFiles) {
    $targetFile = Join-Path $petTarget (Split-Path -Leaf $sourceFile)
    if (Test-Path -LiteralPath $targetFile -PathType Leaf) {
        $sourceHash = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash
        if ($sourceHash -ne $targetHash) {
            $conflictingFiles += $targetFile
        }
    }
}
if ($conflictingFiles.Count -gt 0 -and -not $UpgradePetPackage) {
    $renderedConflicts = $conflictingFiles -join ', '
    throw "Different pet package files are already installed: $renderedConflicts. Use -UpgradePetPackage to replace the complete package."
}

$stagedFiles = @()
try {
    foreach ($sourceFile in $petSourceFiles) {
        $targetFile = Join-Path $petTarget (Split-Path -Leaf $sourceFile)
        $sourceHash = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash
        if (Test-Path -LiteralPath $targetFile -PathType Leaf) {
            $targetHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash
            if ($sourceHash -eq $targetHash) {
                continue
            }
        }
        $temporaryName = ".$(Split-Path -Leaf $targetFile).$([Guid]::NewGuid().ToString('N')).tmp"
        $temporaryPath = Join-Path $petTarget $temporaryName
        Copy-Item -LiteralPath $sourceFile -Destination $temporaryPath
        $stagedHash = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash
        if ($stagedHash -ne $sourceHash) {
            throw "Staged pet file failed hash verification: $temporaryPath"
        }
        $stagedFiles += [pscustomobject]@{
            TemporaryPath = $temporaryPath
            TargetPath = $targetFile
        }
    }
    foreach ($stagedFile in $stagedFiles) {
        Move-Item -LiteralPath $stagedFile.TemporaryPath -Destination $stagedFile.TargetPath -Force
    }
}
finally {
    foreach ($stagedFile in $stagedFiles) {
        if (Test-Path -LiteralPath $stagedFile.TemporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $stagedFile.TemporaryPath -Force
        }
    }
}
$installedPetId = $petManifest.id

if (-not $PetPackageOnly) {
    $marker = [ordered]@{
        appVersion = $expectedAppVersion
        storePackageVersion = $storePackageVersion
        installedAt = [DateTimeOffset]::Now.ToString('o')
        appAsarSha256 = (Get-FileHash -LiteralPath $targetAsar -Algorithm SHA256).Hash
    }
    $marker | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding utf8
}

[pscustomobject]@{
    InstallRoot = $resolvedInstallRoot
    Executable = (Join-Path $resolvedInstallRoot 'ChatGPT.exe')
    AppAsar = $targetAsar
    PetPackageOnly = [bool] $PetPackageOnly
    PetPackageInstalled = (Test-Path -LiteralPath $PetPackagePath -PathType Container)
    PetPackageUpgrade = [bool] $UpgradePetPackage
    PetId = $installedPetId
}
