param(
    [switch]$WithLocalModels,
    [switch]$NoDesktopShortcut
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $projectRoot ".venv"

function Test-Python312 {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $launcher) {
        return $false
    }
    # I Windows PowerShell 5.1 blir py.exe:s meddelande om en saknad version
    # ett NativeCommandError när ErrorActionPreference är Stop. Start-Process
    # låter oss läsa exitkoden utan att ett normalt "3.12 saknas" avbryter
    # installationsprogrammet innan det hinner erbjuda winget-installation.
    try {
        $process = Start-Process `
            -FilePath $launcher.Source `
            -ArgumentList @("-3.12", "-c", "pass") `
            -Wait `
            -PassThru `
            -WindowStyle Hidden
        return $process.ExitCode -eq 0
    }
    catch {
        return $false
    }
}

Write-Host "Debatt-transkriberaren: Windows-installation" -ForegroundColor Cyan

if (-not (Test-Python312)) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Error "Python 3.12 saknas. Installera det från https://www.python.org/downloads/windows/ och kör filen igen."
    }
    $answer = Read-Host "Python 3.12 saknas. Installera automatiskt med winget? [J/n]"
    if ($answer -match "^[Nn]") {
        Write-Error "Installationen avbröts eftersom Python 3.12 krävs."
    }
    & $winget.Source install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $wingetExitCode = $LASTEXITCODE
    if ($wingetExitCode -ne 0 -or -not (Test-Python312)) {
        Write-Error "Python-installationen lyckades inte. Installera Python 3.12 manuellt och försök igen."
    }
}

$ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Error "FFmpeg saknas. Installera FFmpeg och lägg ffmpeg/ffprobe i PATH."
    }
    $answer = Read-Host "FFmpeg saknas. Installera automatiskt med winget? [J/n]"
    if ($answer -match "^[Nn]") {
        Write-Error "Installationen avbröts eftersom FFmpeg krävs."
    }
    & $winget.Source install --exact --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Error "FFmpeg-installationen misslyckades."
    }
    Write-Host "FFmpeg installerades. Om GUI:t inte hittar det, logga ut/in i Windows och försök igen." -ForegroundColor Yellow
}

$launcher = (Get-Command py.exe).Source
if (-not (Test-Path (Join-Path $venvPath "Scripts\python.exe"))) {
    Write-Host "Skapar en isolerad Python-miljö..."
    & $launcher -3.12 -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Kunde inte skapa Python-miljön."
    }
}

$python = Join-Path $venvPath "Scripts\python.exe"
Write-Host "Uppdaterar installationsverktyg..."
& $python -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    Write-Error "Kunde inte uppdatera pip."
}

$extras = if ($WithLocalModels) { "vision,local" } else { "vision" }
$editableTarget = "${projectRoot}[$extras]"
Write-Host "Installerar GUI och analyskomponenter. Detta kan ta flera minuter..."
& $python -m pip install --editable $editableTarget
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python-paketen kunde inte installeras."
}

& $python -c "import tkinter; import debate_transcriber.gui"
if ($LASTEXITCODE -ne 0) {
    Write-Error "GUI-kontrollen misslyckades."
}

if (-not $NoDesktopShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Debatt-transkriberaren.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $projectRoot "run-gui.bat"
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "Skapa talaridentifierade JSON-transkript från debattvideo"
    $shortcut.Save()
    Write-Host "En genväg skapades på skrivbordet." -ForegroundColor Green
}

Write-Host "Installationen är klar." -ForegroundColor Green
if ($WithLocalModels) {
    Write-Host "Lokalläget behöver inga API-nycklar. Öppna modeller hämtas automatiskt första gången." -ForegroundColor Green
}
