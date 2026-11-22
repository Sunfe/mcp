#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    [Console]::Error.WriteLine("Project Python is missing: $python")
    exit 1
}
Set-Location -LiteralPath $projectRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
# stdout belongs exclusively to MCP JSON-RPC.
& $python -u -m app.mcp_server
exit $LASTEXITCODE
