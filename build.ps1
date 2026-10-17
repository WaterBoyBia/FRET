$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path version/build, version/temp, output | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousCache = $env:PYINSTALLER_CONFIG_DIR
$previousMpl = $env:MPLCONFIGDIR
try {
    $env:TEMP = Join-Path $PSScriptRoot 'version/temp'
    $env:TMP = $env:TEMP
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'version/build/cache'
    $env:MPLCONFIGDIR = Join-Path $PSScriptRoot 'version/build/matplotlib'
    conda run --no-capture-output -n donna python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    conda run --no-capture-output -n donna python -m PyInstaller --noconfirm --onedir --windowed --name FRET --paths src --distpath version --workpath version/build --specpath version/build --hidden-import matplotlib.backends.backend_svg --hidden-import matplotlib.backends.backend_pdf --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 src/main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    conda run --no-capture-output -n donna python tests/verify_package.py --exe version/FRET/FRET.exe --input data/example.csv --output output/packaged-check
    if ($LASTEXITCODE -ne 0) { throw 'Packaged application validation failed.' }
    Write-Output 'Complete application folder: version/FRET. Copy the entire folder to distribute.'
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
    $env:MPLCONFIGDIR = $previousMpl
}
