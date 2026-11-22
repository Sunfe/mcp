#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status', 'InstallAutostart', 'RemoveAutostart')]
    [string]$Action = 'Start'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$logDirectory = Join-Path $projectRoot 'logs'
$startupDirectory = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupDirectory 'MCP Knowledge Server.lnk'

if ($Action -in @('InstallAutostart', 'RemoveAutostart')) {
    if ($Action -eq 'RemoveAutostart') {
        if (Test-Path -LiteralPath $shortcutPath) {
            Remove-Item -LiteralPath $shortcutPath
        }
        Write-Host 'Login autostart removed. The running API is unaffected.'
        exit 0
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $PSCommandPath + '"'
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Start the local MCP knowledge API at Windows login'
    $shortcut.Save()
    Write-Host "Login autostart installed: $shortcutPath"
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python is missing: $python. Follow docs/codex-windows-local.md first."
}

# Only manage this project's Python process, never an arbitrary port owner.
$processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $_.ExecutablePath -eq $python -and $_.CommandLine -match '-m\s+app\.main(?:\s|$)'
    })

if ($Action -eq 'Stop') {
    foreach ($process in $processes) {
        # The Windows venv launcher can own a child interpreter; stop its tree.
        & "$env:SystemRoot\System32\taskkill.exe" /PID $process.ProcessId /T /F
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the project API process tree.' }
    }
    Write-Host 'Local knowledge API stopped.'
    exit 0
}
if ($Action -eq 'Status' -or $processes.Count -gt 0) {
    if ($processes.Count -eq 0) {
        Write-Host 'Local knowledge API is not running.'
    } else {
        foreach ($process in $processes) {
            Write-Host "Local knowledge API is running, PID=$($process.ProcessId)."
            Write-Host $process.CommandLine
        }
    }
    exit 0
}

[IO.Directory]::CreateDirectory($logDirectory) | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$process = Start-Process -FilePath $python -ArgumentList @('-u', '-m', 'app.main') `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDirectory 'api.stdout.log') `
    -RedirectStandardError (Join-Path $logDirectory 'api.stderr.log')
Write-Host "Started local knowledge API, PID=$($process.Id)."
Write-Host "Logs: $logDirectory. Use scripts/check_mcp.py to check readiness."
