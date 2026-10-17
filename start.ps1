$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
conda run --no-capture-output -n donna python src/main.py @args
exit $LASTEXITCODE
