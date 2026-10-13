param([string]$Delivery,[string]$Evidence,[string]$Tools,[string]$ConsoleCheck)
$ErrorActionPreference='Stop'
# Start-Process -Credential inherits the administrator's TEMP; use this
# account's actual profile, as an interactive logon would.
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$profile=Get-ItemPropertyValue -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$sid) -Name ProfileImagePath
$env:USERPROFILE=[Environment]::ExpandEnvironmentVariables($profile)
$env:TEMP=Join-Path $env:USERPROFILE 'AppData\Local\Temp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$env:PATH="$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
$record=@{kind='NEW_STANDARD_WINDOWS_USER_VIEW_ONLY';account_is_new=$true;python_in_path=@(Get-Command python.exe -CommandType Application -All -ErrorAction SilentlyContinue | Where-Object Source -notmatch '\\WindowsApps\\').Count;user_python_registry=Test-Path HKCU:\SOFTWARE\Python\PythonCore;machine_python_registry=Test-Path HKLM:\SOFTWARE\Python\PythonCore;new_model_calls=0;candidate_execution=0;wsl_probe=0;has_chinese_and_space=($Delivery -match '[^\x00-\x7F]' -and $Delivery.Contains(' '));has_repository_venv=Test-Path (Join-Path $Delivery '.venv')}
$listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,8765)
try {$listener.Start(); $record.port_8765_reserved_by_test=$true} catch {$record.port_8765_already_occupied=$true}
try {
 $start=Start-Process "$env:SystemRoot\System32\cmd.exe" -WorkingDirectory $Delivery -ArgumentList @('/d','/c','start-credproof.cmd') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Evidence 'startup.raw.txt') -RedirectStandardError (Join-Path $Evidence 'startup.stderr.raw.txt')
 $base=$null
 for($i=0;$i -lt 100;$i++) {
  Start-Sleep -Milliseconds 300
  $log=Get-Content (Join-Path $Evidence 'startup.raw.txt') -Raw -ErrorAction SilentlyContinue
  if($log -match 'CredProof: (http://127\.0\.0\.1:(\d+))') { $base=$Matches[1];$record.actual_port=[int]$Matches[2];break }
  if($start.HasExited) {throw 'Default CMD exited before server became ready'}
 }
 if(-not $base){throw 'Default CMD did not provide a ready loopback address'}
 $record.port_fallback_worked=$record.actual_port -ne 8765
 $bootstrap=Invoke-RestMethod "$base/api/agent/bootstrap"
 $review=Invoke-RestMethod "$base/api/review/$($bootstrap.reviews[0].id)"
 $record.reviews=@($bootstrap.reviews).Count
 $record.review_state=@($review.technical_verdict,$review.decision,$review.application_to_original)
 Push-Location $Delivery
 $origin=& (Join-Path $Delivery 'runtime/python/python.exe') -S -c "import sys,json,pathlib,agent_pilot.web,credproof_safety.human_review; root=pathlib.Path.cwd();print(json.dumps({'version':sys.version.split()[0],'no_site':sys.flags.no_site,'isolated':sys.flags.isolated,'web':str(pathlib.Path(agent_pilot.web.__file__).relative_to(root)),'review':str(pathlib.Path(credproof_safety.human_review.__file__).relative_to(root))}))"
 $record.origin=$origin | ConvertFrom-Json
 Pop-Location
 Push-Location $Tools
 $ErrorActionPreference='Continue'
 & (Join-Path $Tools 'node.exe') $ConsoleCheck --base $base --out (Join-Path $Evidence 'console') > (Join-Path $Evidence 'console.stdout.txt') 2> (Join-Path $Evidence 'console.stderr.txt')
 $record.console_exit_code=$LASTEXITCODE
 $ErrorActionPreference='Stop'
 Pop-Location
 $record.browser_open_requested=($log -notmatch 'Browser did not open')
 # Send actual Ctrl+C to this test-owned console, not to other workloads.
 Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class CPConsole { [DllImport("kernel32.dll")] public static extern bool FreeConsole(); [DllImport("kernel32.dll")] public static extern bool AttachConsole(uint id); [DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(IntPtr h,bool add); [DllImport("kernel32.dll")] public static extern bool GenerateConsoleCtrlEvent(uint e,uint g); }'
 [CPConsole]::FreeConsole() | Out-Null
 $attached=[CPConsole]::AttachConsole([uint32]$start.Id)
 [CPConsole]::SetConsoleCtrlHandler([IntPtr]::Zero,$true) | Out-Null
 $record.ctrl_c_sent=$attached -and [CPConsole]::GenerateConsoleCtrlEvent(0,0)
 Start-Sleep -Seconds 3
 [CPConsole]::FreeConsole() | Out-Null
 $record.demo_temporary_remaining=@(Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'credproof-demo-review-*' -ErrorAction SilentlyContinue).Count
 $record.strict_no_preinstalled_python = -not $record.machine_python_registry -and -not $record.user_python_registry -and $record.python_in_path -eq 0
 $record.pass=($record.console_exit_code -eq 0 -and $record.reviews -ge 1 -and ($record.review_state -join '/') -eq 'PASS/PENDING/NOT_APPLIED' -and $record.origin.version -eq '3.12.10' -and $record.origin.no_site -eq 1 -and $record.port_fallback_worked -and $record.python_in_path -eq 0 -and -not $record.user_python_registry)
} catch { $record.pass=$false;$record.error_type=$_.Exception.GetType().Name;$record.error=$_.Exception.Message } finally {
 try {$listener.Stop()} catch {}
 if($start -and -not $start.HasExited) { & "$env:SystemRoot\System32\taskkill.exe" /PID $start.Id /T /F >$null 2>&1 }
 $record | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $Evidence 'new-user.json') -Encoding UTF8
}
if($record.pass){exit 0}else{exit 1}
