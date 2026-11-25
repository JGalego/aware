# Installs aware on Windows. aware is a bash tool (it drives tmux), so this runs install.sh inside WSL.
# Usage: irm https://raw.githubusercontent.com/JGalego/aware/main/install.ps1 | iex
# Needs WSL with a Linux distro that has jq, tmux, python3, git and Claude Code. Setup: wsl --install
$ErrorActionPreference = 'Stop'

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Host 'aware runs inside WSL. Install it first (wsl --install), reboot, then run this again.'
    return
}

wsl.exe -e bash -lc 'curl -fsSL https://raw.githubusercontent.com/JGalego/aware/main/install.sh | bash'
if ($LASTEXITCODE -ne 0) {
    Write-Host 'aware: the install failed inside WSL. Is a distro installed (wsl --install -d Ubuntu) and are jq, tmux and claude on its PATH?'
    return
}
Write-Host 'Done. Open WSL and run: aware launch --watch'
