# Manu — one-time setup for Windows 11 (run setup.bat, or this file in PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Checking winget…"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget not found. Install 'App Installer' from the Microsoft Store, then re-run." -ForegroundColor Red
    exit 1
}

Step "Installing Python 3.11 (skipped if already installed)…"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
} else { Write-Host "    Python launcher found." }

Step "Installing ffmpeg (audio converter)…"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
} else { Write-Host "    ffmpeg found." }

Step "Installing Ollama (runs the AI model)…"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
} else { Write-Host "    Ollama found." }

# Refresh PATH so tools installed above are visible in this same session
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")

Step "Creating Python virtual environment…"
if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& .\.venv\Scripts\Activate.ps1

Step "Installing PyTorch with CUDA (this is ~2.5 GB, one time)…"
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

Step "Installing the rest of the Python packages…"
pip install -r requirements.txt

Step "Downloading the chat model (qwen3:8b, ~5 GB, one time)…"
ollama pull qwen3:8b

Step "Downloading speech + embedding models…"
python scripts\download_models.py

Write-Host "`nAll done! Double-click run.bat to start Manu." -ForegroundColor Green
