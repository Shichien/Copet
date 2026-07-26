$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand -or $null -eq $pythonCommand) {
    throw 'Node.js and Python are required to run the test suite.'
}

$nodeArgs = @('--test', (Join-Path $repoRoot 'runtime\test-runtime.cjs'))
& $nodeCommand.Source @nodeArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Runtime tests failed with exit code $exitCode"
}

$pipelineArgs = @(
    '-m',
    'unittest',
    'discover',
    '-s',
    (Join-Path $repoRoot 'skill\tests'),
    '-v'
)
& $pythonCommand.Source @pipelineArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Interaction pipeline tests failed with exit code $exitCode"
}

$validationArgs = @(
    (Join-Path $repoRoot 'skill\scripts\validate_interaction_pack.py'),
    '--package-dir',
    (Join-Path $repoRoot 'pet\package')
)
& $pythonCommand.Source @validationArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Pet package validation failed with exit code $exitCode"
}
