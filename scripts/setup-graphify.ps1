# One-time setup per machine (Windows PowerShell).
# Installs the graphify CLI and registers the /graphify skill in ~/.claude
# so it works in every project on this computer, not only this repository.
$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    winget install --id=astral-sh.uv -e
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
}

uv tool install --upgrade graphifyy
uv tool update-shell
$env:Path = "$env:USERPROFILE\.local\bin;" + $env:Path

graphify install --platform windows
graphify --version
Write-Host "Done. Restart your terminal / Claude Code, then type /graphify . in any project."
