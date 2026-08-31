$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env from .env.example."
    Write-Host "Add your PostgreSQL password and GEMINI_API_KEY."
    Write-Host "Then run: python -m scripts.bootstrap --reset --embed"
    exit 0
}

Write-Host ""
Write-Host "Dependencies installed."
Write-Host "Next: python -m scripts.bootstrap --reset --embed"
