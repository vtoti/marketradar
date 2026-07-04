<#
.SYNOPSIS
    Registra (ou remove) a coleta diária do Radar de Mercado no Agendador
    de Tarefas do Windows.

.EXAMPLE
    # Registrar para rodar todo dia às 08:00
    .\register_task.ps1

.EXAMPLE
    # Horário e limite personalizados
    .\register_task.ps1 -Time "07:30" -Limit 80

.EXAMPLE
    # Remover a tarefa
    .\register_task.ps1 -Unregister
#>
param(
    [string]$Time = "08:00",
    [int]$Limit = 60,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskName = "RadarDeMercado-ColetaDiaria"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Script = Join-Path $Root "collect_job.py"

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Tarefa '$TaskName' removida." -ForegroundColor Yellow
    } else {
        Write-Host "Tarefa '$TaskName' não existe." -ForegroundColor Yellow
    }
    return
}

if (-not (Test-Path $Python)) {
    throw "Python da venv não encontrado em $Python. Rode a instalação do README primeiro."
}

$Action = New-ScheduledTaskAction -Execute $Python `
    -Argument "`"$Script`" --limit $Limit" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "Coleta diária de anúncios (Radar de Mercado)" `
    -Force | Out-Null

Write-Host "Tarefa '$TaskName' registrada para rodar diariamente às $Time." -ForegroundColor Green
Write-Host "Comando: $Python `"$Script`" --limit $Limit" -ForegroundColor DarkGray
Write-Host "Rodar agora para testar: Start-ScheduledTask -TaskName $TaskName" -ForegroundColor DarkGray
