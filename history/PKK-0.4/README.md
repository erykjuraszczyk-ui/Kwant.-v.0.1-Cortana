# PKK 0.4 — Pamięć percepcyjna i model świata

PKK 0.4 rozszerza prototyp percepcji o **śledzenie obserwowanych obiektów**, krótkotrwałą pamięć zdarzeń i prosty model świata. To nadal klasyczny system AI — nie wykonuje obliczeń kwantowych.

## Funkcje
- `POST /perception/observations` — przyjmuje obserwacje z detektora lub symulatora.
- `GET /world/state` — zwraca aktualny model świata.
- `GET /memory/events` — zwraca ostatnie zdarzenia pamięci.
- `POST /memory/reset` — czyści pamięć procesu.
- Łączenie obserwacji z obiektami po `track_id`.
- Automatyczne oznaczanie obiektów jako `stale`, gdy nie były widziane przez określony czas.
- Ograniczona pamięć pierścieniowa oraz walidacja danych.
- Testy automatyczne.

## Wymagania
- Python 3.11+
- FastAPI, Uvicorn, Pydantic, pytest

## Uruchomienie — Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Uruchomienie — Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Otwórz http://127.0.0.1:8000/docs

## Szybki test
W Swaggerze wyślij `POST /perception/observations`:
```json
{
  "source": "camera-1",
  "observed_at": "2026-10-22T12:00:00Z",
  "observations": [
    {"track_id": "object-1", "label": "person", "confidence": 0.94,
     "bbox": [0.1, 0.12, 0.4, 0.9]}
  ]
}
```
Współrzędne `bbox` są znormalizowane do zakresu 0–1 w kolejności `[x1, y1, x2, y2]`.

## Ważne ograniczenia
- PKK 0.4 nie wykonuje samodzielnie detekcji z kamery; przyjmuje wyniki z detektora PKK 0.2/0.3 albo symulatora.
- Identyfikacja obiektów zależy od stabilności `track_id` dostarczanego przez źródło. Bez tracker-a nie należy zakładać, że `object-1` w dwóch klatkach to ta sama fizyczna rzecz.
- Pamięć jest tylko w RAM i znika po restarcie. To celowy, bezpieczniejszy etap prototypu.
- Model świata to stan operacyjny, a nie dowód na rozumienie świadomości czy prawdziwego świata.
