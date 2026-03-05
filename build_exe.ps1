# Build GoldTracker into a self-contained single-file EXE
# Usage: .\build_exe.ps1
# Requirements: pip install pyinstaller

$python = "D:\Crypto\Software\python.exe"
$script = "$PSScriptRoot\gold_tracker.py"
$dist   = "$PSScriptRoot\dist"

Write-Host "==> Installing / upgrading PyInstaller..." -ForegroundColor Cyan
& $python -m pip install --quiet --upgrade pyinstaller

Write-Host "==> Building GoldTracker.exe..." -ForegroundColor Cyan
& $python -m PyInstaller `
    --onefile `
    --noconsole `
    --name GoldTracker `
    --distpath $dist `
    --workpath "$PSScriptRoot\build_tmp" `
    --specpath "$PSScriptRoot\build_tmp" `
    $script

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==> Build succeeded!" -ForegroundColor Green
    Write-Host "    Output: $dist\GoldTracker.exe" -ForegroundColor Green
    # Clean up temp artifacts
    if (Test-Path "$PSScriptRoot\build_tmp") {
        Remove-Item "$PSScriptRoot\build_tmp" -Recurse -Force
    }
} else {
    Write-Host "==> Build FAILED (exit code $LASTEXITCODE)" -ForegroundColor Red
}
