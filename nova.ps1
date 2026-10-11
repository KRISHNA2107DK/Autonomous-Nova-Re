<#
  AutoHeal launcher for Windows (PowerShell).

    .\nova.ps1 demo        everything end-to-end (first run ~15 min, then ~1 min to be ready)
    .\nova.ps1 serve       dashboard + API on http://127.0.0.1:8000
    .\nova.ps1 campaign    run the 5-round chaos campaign
    .\nova.ps1 help        all commands

  On first use it creates a Python virtual environment OUTSIDE the repository
  (%LOCALAPPDATA%\AutoHeal\venv) so a OneDrive-synced folder never has to
  sync ~1 GB of dependencies, and installs requirements.txt into it.
#>
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$HomeDir = if ($env:NOVASURGE_HOME) { $env:NOVASURGE_HOME } else { Join-Path $env:LOCALAPPDATA "AutoHeal" }
$Venv = Join-Path $HomeDir "venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$Stamp = Join-Path $HomeDir "requirements.sha256"

function Find-Python {
    foreach ($cand in @("py -3.13", "py -3.12", "py -3.11", "python")) {
        $parts = $cand.Split(" ")
        try {
            $v = & $parts[0] $parts[1..($parts.Length - 1)] -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]"3.11") { return $parts }
        } catch { }
    }
    throw "Python 3.11+ not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')."
}

New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
if (-not (Test-Path $Py)) {
    $base = Find-Python
    Write-Host "[novasurge] creating virtual environment in $Venv"
    & $base[0] $base[1..($base.Length - 1)] -m venv $Venv
}
$req = Join-Path $Repo "requirements.txt"
$hash = (Get-FileHash $req -Algorithm SHA256).Hash
if (-not (Test-Path $Stamp) -or (Get-Content $Stamp) -ne $hash) {
    Write-Host "[novasurge] installing Python dependencies (first run downloads ~250 MB)"
    # pip missing or broken: restore it (native stderr must not trip $ErrorActionPreference = "Stop")
    $ErrorActionPreference = "Continue"
    & $Py -m pip --version 2>$null | Out-Null
    $pipOk = ($LASTEXITCODE -eq 0)
    if (-not $pipOk) { & $Py -m ensurepip --upgrade 2>$null | Out-Null }
    $ErrorActionPreference = "Stop"
    & $Py -m pip install --disable-pip-version-check -q --upgrade "pip<26.2"
    & $Py -m pip install --disable-pip-version-check -q -r $req
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Set-Content -Path $Stamp -Value $hash
}

Push-Location $Repo
try {
    if ($args.Count -eq 0 -or $args[0] -in @("help", "-h", "--help")) {
        & $Py -m novasurge --help
    } else {
        & $Py -m novasurge @args
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
