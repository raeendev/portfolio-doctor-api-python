# Install Dependencies for Portfolio Doctor API
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Install Dependencies for Portfolio Doctor API" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = py --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not installed!" -ForegroundColor Red
    Write-Host "Please install from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Create Virtual Environment
Write-Host "[1/3] Creating Virtual Environment..." -ForegroundColor Yellow
try {
    py -m venv venv
    Write-Host "[OK] Virtual Environment created" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create venv" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Activate Virtual Environment
Write-Host "[2/3] Activating Virtual Environment..." -ForegroundColor Yellow
try {
    & "venv\Scripts\Activate.ps1"
    Write-Host "[OK] Virtual Environment activated" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Failed to activate venv - continuing..." -ForegroundColor Yellow
}
Write-Host ""

# Install Dependencies
Write-Host "[3/3] Installing Dependencies..." -ForegroundColor Yellow
try {
    & "venv\Scripts\python.exe" -m pip install --upgrade pip
    & "venv\Scripts\python.exe" -m pip install -r requirements.txt
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Installation completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the server:" -ForegroundColor Yellow
Write-Host "  1. venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  2. python main.py" -ForegroundColor White
Write-Host ""

