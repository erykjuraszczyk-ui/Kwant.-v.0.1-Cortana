$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
Write-Host "Startuję PKK 0.2. Pierwsze wykrywanie obiektu może pobrać model yolo26n.pt."
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
