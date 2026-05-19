# Start Factorio headless server for FLE experiments (Windows, no Docker)
# Run from repo root. Factorio client can connect to localhost to spectate.

param(
    [string]$Scenario = "default_lab_scenario",
    [int]$RconPort = 27000,
    [string]$RconPassword = "factorio"
)

$factorio = "C:\Program Files (x86)\Steam\steamapps\common\Factorio\bin\x64\factorio.exe"
$settingsFile = "$env:APPDATA\Factorio\config\server-settings.json"

if (-not (Test-Path $factorio)) {
    Write-Error "Factorio not found at $factorio"
    exit 1
}

# Create server-settings.json if missing
if (-not (Test-Path $settingsFile)) {
    Write-Host "Creating $settingsFile"
    @'
{
  "name": "FLE Local",
  "description": "FLE research server",
  "visibility": { "public": false, "lan": false },
  "require_user_verification": false,
  "allow_commands": "admins-only"
}
'@ | Set-Content $settingsFile
}

Write-Host "Starting Factorio headless..."
Write-Host "  Scenario: $Scenario"
Write-Host "  RCON: localhost:$RconPort (password: $RconPassword)"
Write-Host "  Game port: 34197 (connect Factorio client to localhost to spectate)"
Write-Host ""

& $factorio `
    --start-server-load-scenario $Scenario `
    --rcon-port $RconPort `
    --rcon-password $RconPassword `
    --server-settings $settingsFile
