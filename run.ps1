param([Parameter(ValueFromRemainingArguments=$true)][string[]]$LeadArguments)
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = 'C:\Users\CJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = 'python' }
& $taskPython (Join-Path $PSScriptRoot 'src\process_leads.py') @LeadArguments
exit $LASTEXITCODE
