param([Parameter(ValueFromRemainingArguments=$true)][string[]]$LeadArguments)
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = 'C:\Users\CJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = 'python' }
& $taskPython -B (Join-Path $PSScriptRoot 'src\check_hubspot.py') @LeadArguments
exit $LASTEXITCODE
