$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Entry = Join-Path $Root "pdf_unlocker.py"
$Icon = Join-Path $Root "assets\pdf_unlocker.ico"
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build\pyinstaller"
$Spec = Join-Path $Root "build\spec"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "PDFUnlocker" `
  --icon "$Icon" `
  --add-data "$Icon;." `
  --collect-data customtkinter `
  --collect-all tkinterdnd2 `
  --distpath "$Dist" `
  --workpath "$Build" `
  --specpath "$Spec" `
  "$Entry"

Write-Host "Done: $Dist\PDFUnlocker.exe"
