# Build GoldTracker into a self-contained single-file EXE
# Usage: .\build_exe.ps1
# Requirements: pip install pyinstaller

$python  = "D:\Crypto\Software\python.exe"
$script  = "$PSScriptRoot\gold_tracker.py"
$dist    = "$PSScriptRoot\dist"
$work    = "$PSScriptRoot\build_tmp"

# ── Locate conda TCL/TK assets (non-standard in conda environments) ──────────
$condaBase = "D:\Crypto\Software"
$tclDir    = "$condaBase\Library\lib\tcl8.6"
$tkDir     = "$condaBase\Library\lib\tk8.6"
$tcl8Dir   = "$condaBase\Library\lib\tcl8"
$tclDll    = "$condaBase\Library\bin\tcl86t.dll"
$tkDll     = "$condaBase\Library\bin\tk86t.dll"
$tkinterPyd = "$condaBase\DLLs\_tkinter.pyd"

foreach ($p in @($tclDir,$tkDir,$tclDll,$tkDll,$tkinterPyd)) {
    if (-not (Test-Path $p)) {
        Write-Host "ERROR: Not found: $p" -ForegroundColor Red
        exit 1
    }
}

Write-Host "==> Installing / upgrading PyInstaller..." -ForegroundColor Cyan
& $python -m pip install --quiet --upgrade pyinstaller

Write-Host "==> Building GoldTracker.exe (with TCL/TK assets)..." -ForegroundColor Cyan

& $python -m PyInstaller `
    --onefile `
    --noconsole `
    --name GoldTracker `
    --distpath $dist `
    --workpath $work `
    --specpath $work `
    --hidden-import tkinter `
    --hidden-import tkinter.ttk `
    --hidden-import tkinter.messagebox `
    --collect-all tkinter `
    --add-data "${tclDir};tcl8.6" `
    --add-data "${tkDir};tk8.6" `
    --add-data "${tcl8Dir};tcl8" `
    --add-binary "${tclDll};." `
    --add-binary "${tkDll};." `
    --add-binary "${tkinterPyd};." `
    $script

if ($LASTEXITCODE -eq 0) {
    $size = "{0:F1}" -f ((Get-Item "$dist\GoldTracker.exe").Length / 1MB)
    Write-Host ""
    Write-Host "==> Build succeeded!  $size MB" -ForegroundColor Green
    Write-Host "    Output: $dist\GoldTracker.exe" -ForegroundColor Green
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
} else {
    Write-Host "==> Build FAILED (exit code $LASTEXITCODE)" -ForegroundColor Red
}
