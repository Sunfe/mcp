#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.:-]*$')]
    [string]$ServerAddress = '66.245.192.250',
    [ValidatePattern('^[A-Za-z0-9_][A-Za-z0-9_.-]*$')]
    [string]$UserName = 'liaozhic',
    [ValidateRange(1, 65535)]
    [int]$Port = 22,
    [ValidatePattern('^/[A-Za-z0-9_./-]+$')]
    [string]$RemoteProject = '/home/liaozhic/data/mcp',
    [string]$IdentityFile,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$sshCommand = (Get-Command ssh.exe -CommandType Application -ErrorAction Stop).Source
# Prefer the npm .cmd launcher so Windows PowerShell need not execute codex.ps1.
$codexCommand = $null
foreach ($candidate in @('codex.cmd', 'codex.exe', 'codex')) {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($found) {
        $codexCommand = $found.Source
        break
    }
}
if (-not $codexCommand) {
    throw 'Codex CLI was not found. Install it and run codex login first.'
}

$sshArguments = @(
    '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
    '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
    '-p', "$Port"
)
if ($IdentityFile) {
    $sshArguments += @('-i', (Resolve-Path -LiteralPath $IdentityFile).Path)
}
$sshArguments += "${UserName}@${ServerAddress}"

Write-Host '[1/4] Checking non-interactive SSH login...'
& $sshCommand @sshArguments 'true'
if ($LASTEXITCODE -ne 0) {
    throw 'SSH failed. First use an interactive SSH login to verify the host key and configure your key/SSH agent.'
}

Write-Host '[2/4] Checking the remote MCP protocol and API...'
$remoteCheck = "$RemoteProject/.venv/bin/python $RemoteProject/scripts/check_mcp.py --query P5-35"
& $sshCommand @sshArguments $remoteCheck
if ($LASTEXITCODE -ne 0) {
    throw 'The remote MCP check failed. Check the server API on port 8016 before changing Codex config.'
}

$mcpArguments = $sshArguments + "bash $RemoteProject/scripts/mcp_stdio.sh"
# JSON strings/arrays are also valid TOML strings/arrays here, including escaped Windows paths.
$commandToml = ConvertTo-Json -InputObject $sshCommand -Compress
$argumentsToml = ConvertTo-Json -InputObject @($mcpArguments) -Compress
$snippet = @"
# BEGIN knowledge-base SSH configuration
[mcp_servers.knowledge-base]
command = $commandToml
args = $argumentsToml
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled_tools = ["list_documents", "search_documents", "get_document"]

[mcp_servers.knowledge-base.tools.list_documents]
approval_mode = "approve"

[mcp_servers.knowledge-base.tools.search_documents]
approval_mode = "approve"

[mcp_servers.knowledge-base.tools.get_document]
approval_mode = "approve"
# END knowledge-base SSH configuration
"@

$configDirectory = if ($env:CODEX_HOME) {
    $env:CODEX_HOME
} else {
    Join-Path $env:USERPROFILE '.codex'
}
$configPath = Join-Path $configDirectory 'config.toml'
$original = if (Test-Path -LiteralPath $configPath) {
    [IO.File]::ReadAllText($configPath)
} else {
    ''
}

# Let Codex parse existing TOML instead of trying to parse TOML with regular expressions.
$catalogText = & $codexCommand mcp list --json
if ($LASTEXITCODE -ne 0) {
    throw 'Codex cannot read its current configuration. No configuration has been changed.'
}
$catalog = ConvertFrom-Json -InputObject ($catalogText -join "`n")
$existing = @($catalog | Where-Object { $_.name -eq 'knowledge-base' })
$managedPattern = '(?ms)^# BEGIN knowledge-base SSH configuration\r?\n.*?^# END knowledge-base SSH configuration\r?$'
$managedBlocks = [regex]::Matches($original, $managedPattern)
if ($existing.Count -gt 0 -and $managedBlocks.Count -ne 1) {
    $candidatePath = Join-Path $env:TEMP 'codex-knowledge-base-ssh.toml'
    [IO.File]::WriteAllText($candidatePath, $snippet + "`n", $utf8)
    throw "knowledge-base already exists and is not managed by this script. Merge $candidatePath into $configPath, replacing the existing knowledge-base tables. Other settings were not changed."
}
if ($managedBlocks.Count -gt 1) {
    throw 'Multiple managed knowledge-base blocks exist. Resolve the duplicate blocks before retrying.'
}
$merged = if ($managedBlocks.Count -eq 1) {
    $match = $managedBlocks[0]
    $original.Substring(0, $match.Index) + $snippet + $original.Substring($match.Index + $match.Length)
} else {
    $original + "`n`n" + $snippet + "`n"
}

Write-Host '[3/4] Registering knowledge-base in Codex...'
$hadConfig = Test-Path -LiteralPath $configPath
$backupPath = $null
if ($merged -ne $original) {
    [IO.Directory]::CreateDirectory($configDirectory) | Out-Null
    if ($hadConfig) {
        $backupPath = $configPath + '.before-knowledge-base-' + (Get-Date -Format 'yyyyMMdd-HHmmssfff')
        Copy-Item -LiteralPath $configPath -Destination $backupPath
        Write-Host "Backup: $backupPath"
    }
    try {
        [IO.File]::WriteAllText($configPath, $merged, $utf8)
        $registeredText = & $codexCommand mcp get knowledge-base --json
        if ($LASTEXITCODE -ne 0) {
            throw 'Codex rejected the updated configuration.'
        }
        $registered = ConvertFrom-Json -InputObject ($registeredText -join "`n")
        if ($registered.transport.command -ne $sshCommand -or
            (Compare-Object @($registered.transport.args) @($mcpArguments))) {
            throw 'The effective Codex SSH command does not match the requested configuration.'
        }
    } catch {
        if ($hadConfig) {
            Copy-Item -LiteralPath $backupPath -Destination $configPath -Force
        } elseif (Test-Path -LiteralPath $configPath) {
            Remove-Item -LiteralPath $configPath
        }
        throw
    }
}
Write-Host "Registered: $configPath"
Write-Host '[4/4] Registration complete. Start a NEW Codex session to load this MCP.'

if ($Verify) {
    Write-Host 'Running a real Codex CLI query with your existing model/login...'
    $prompt = 'Verify knowledge-base MCP by calling list_documents, then search_documents with query P5-35 and limit 2. Use only these MCP tools; do not run shell commands or modify files. Report the actual tool results, document count, document_id, chunk_id, and a short quote. If a tool fails, report the failure clearly.'
    & $codexCommand exec --ephemeral --sandbox read-only -c 'mcp_servers.knowledge-base.required=true' $prompt
    if ($LASTEXITCODE -ne 0) {
        throw 'Codex verification failed. The MCP configuration is saved; check the CLI output for the cause.'
    }
    Write-Host 'Inspect the response above: both MCP tool calls must succeed to confirm end-to-end access.'
} else {
    Write-Host 'In Codex, ask: Use knowledge-base to search P5-35 and cite document_id and chunk_id.'
}
