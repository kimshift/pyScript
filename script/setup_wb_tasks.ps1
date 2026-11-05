# 重建 workbuddy 积分任务的 Windows 计划任务
# 用法：powershell -ExecutionPolicy Bypass -File script\setup_wb_tasks.ps1
# 说明：任务指向项目 .venv 的 pythonw.exe（无控制台窗口），工作目录为仓库根，
#       不再依赖 WorkBuddy 内置 Python（那个版本号目录会随客户端升级变化）。

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot  # script/ 的上一级 = 仓库根，换机器/换盘符都不用改
$pyw  = Join-Path $repo ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pyw)) {
    throw "找不到 $pyw，请先执行 mise run setup"
}

$prefix = "WB"

# 名称, 时间(HH:mm), runner 参数
$jobs = @(
    @("Health_0745",  "07:45", "health"),
    @("Checkin_0900", "09:00", "checkin"),
    @("Checkin_1300", "13:00", "checkin"),
    @("Checkin_2000", "20:00", "checkin"),
    @("Travel_0815",  "08:15", "travel"),
    @("Travel_1230",  "12:30", "travel"),
    @("Travel_1645",  "16:45", "travel"),
    @("Travel_2100",  "21:00", "travel"),
    @("Growth_1000",  "10:00", "growth auto"),
    @("Growth_1930",  "19:30", "growth auto")
)

foreach ($j in $jobs) {
    $name = "$prefix $($j[0])"
    $at   = [datetime]::Today.Add([timespan]::Parse($j[1]))

    $action    = New-ScheduledTaskAction -Execute $pyw -Argument "-m tools.wb_reward $($j[2])" -WorkingDirectory $repo
    $trigger   = New-ScheduledTaskTrigger -Daily -At $at
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    $settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                                             -DontStopIfGoingOnBatteries `
                                             -AllowStartIfOnBatteries `
                                             -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
                                             -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description "WorkBuddy reward task - $($j[2])" -Force | Out-Null
    Write-Host ("OK  {0,-18} {1}  -> {2}" -f $name, $j[1], $j[2])
}

Write-Host ""
Write-Host "已创建/更新 $($jobs.Count) 个计划任务（指向 $pyw）"
