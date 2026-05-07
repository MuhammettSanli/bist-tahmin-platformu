# zamanlayici_kur.ps1 — Windows Gorev Zamanlayicisi'na pipeline ekler
# Yonetici olarak calistir: PowerShell -> Sag tik -> "Yonetici olarak calistir"
# Komut: .\zamanlayici_kur.ps1

$GorevAdi    = "BIST_Pipeline_Gunluk"
$PythonYolu  = (Get-Command python).Source
$ScriptYolu  = "$PSScriptRoot\pipeline.py"
$LogYolu     = "$PSScriptRoot\pipeline_log.txt"
$SaatDakika  = "07:00"   # Her sabah 07:00'de calistir

# Mevcut gorevi sil (varsa)
Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false -ErrorAction SilentlyContinue

# Eylem: python pipeline.py
$Eylem = New-ScheduledTaskAction `
    -Execute $PythonYolu `
    -Argument $ScriptYolu `
    -WorkingDirectory $PSScriptRoot

# Tetikleyici: Her gun saat 07:00
$Tetikleyici = New-ScheduledTaskTrigger -Daily -At $SaatDakika

# Ayarlar: Bilgisayar pistte olsa bile calistir, batarya durumunu gozet
$Ayarlar = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable

# Gorevi kaydet (mevcut kullanici)
Register-ScheduledTask `
    -TaskName $GorevAdi `
    -Action $Eylem `
    -Trigger $Tetikleyici `
    -Settings $Ayarlar `
    -Description "BIST hisse verileri, haberler ve modelleri gunluk gunceller" `
    -RunLevel Highest `
    -Force | Out-Null

Write-Host ""
Write-Host "Gorev olusturuldu: $GorevAdi" -ForegroundColor Green
Write-Host "Calisma saati   : Her gun $SaatDakika" -ForegroundColor Cyan
Write-Host "Python          : $PythonYolu" -ForegroundColor Cyan
Write-Host "Script          : $ScriptYolu" -ForegroundColor Cyan
Write-Host "Log dosyasi     : $LogYolu" -ForegroundColor Cyan
Write-Host ""
Write-Host "Hemen test etmek icin:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$GorevAdi'" -ForegroundColor Yellow
Write-Host "  veya: python pipeline.py" -ForegroundColor Yellow
