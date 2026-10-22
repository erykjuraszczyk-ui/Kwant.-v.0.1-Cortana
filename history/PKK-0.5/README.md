# PKK 0.5 — Trwała pamięć i model świata

**PKK (Percepcyjny Komputer Kwantowy)** to nazwa projektu. Wersja 0.5 działa na klasycznym CPU i nie wykonuje obliczeń kwantowych.

PKK 0.5 rozwija wersję 0.4 o lokalną bazę SQLite, historię obserwacji, prostą detekcję zmian i adapter wejściowy dla wyników detektora.

## Funkcje

- Trwała pamięć SQLite (`data/pkk.sqlite3` domyślnie).
- Migrowalny schemat bazy danych (tabela `schema_migrations`).
- Bieżący model świata z klasą, pewnością, bounding boxem, czasami i licznikiem obserwacji.
- Historia obserwacji i zdarzeń: pojawienie się, ruch, zmiana klasy, ponowne pojawienie i brak ostatnich obserwacji.
- Endpoint `/perception/detections` jako adapter dla wyników detektora. Stabilny `track_id` należy przekazać z modułu śledzącego; bez niego identyfikator jest lokalny dla jednej klatki, żeby nie scalać przypadkowych obiektów.
- Limity rozmiaru pamięci, walidacja wejścia, testy oraz konfiguracja ścieżki bazy przez `PKK_DB_PATH`.
- Docker Compose z katalogiem `data/` podpiętym jako wolumen lokalny.

## Wymagania

Python 3.11+ (zalecany 3.12). Zależności są w `requirements.txt`.

## Uruchomienie — Windows 10/11

W PowerShell, w folderze projektu:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-windows.ps1
```

Skrypt tworzy `.venv`, instaluje zależności i uruchamia API na `127.0.0.1:8000`.

## Uruchomienie — Linux

```bash
chmod +x scripts/run-linux.sh
./scripts/run-linux.sh
```

## Docker

```bash
docker compose up --build
```

Baza danych pozostaje w lokalnym folderze `data/`. Domyślne mapowanie portu jest ograniczone do `127.0.0.1`.

## Dokumentacja API

Po uruchomieniu otwórz:

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Model świata: http://127.0.0.1:8000/world/state
- Statystyki pamięci: http://127.0.0.1:8000/memory/stats

## Szybki test: POST `/perception/observations`

```json
{
  "source": "camera-1",
  "observed_at": "2026-10-22T12:00:00Z",
  "observations": [
    {
      "track_id": "person-7",
      "label": "person",
      "confidence": 0.94,
      "bbox": [0.1, 0.12, 0.4, 0.9]
    }
  ]
}
```

Współrzędne `bbox` są znormalizowane 0–1 w kolejności `[x1, y1, x2, y2]`.

## Adapter: POST `/perception/detections`

```json
{
  "source": "pkk-vision",
  "frame_id": "frame-00042",
  "observed_at": "2026-10-22T12:00:00Z",
  "detections": [
    {
      "track_id": "person-7",
      "label": "person",
      "confidence": 0.94,
      "bbox": [0.1, 0.12, 0.4, 0.9]
    }
  ]
}
```

Jeżeli `track_id` jest pominięty, PKK utworzy identyfikator z `frame_id` i numeru detekcji. Taki identyfikator nie śledzi obiektu między klatkami. Do tego potrzebny jest prawdziwy tracker obiektów (np. ByteTrack) połączony z detektorem.

## Najważniejsze endpointy

| Metoda | Endpoint | Działanie |
|---|---|---|
| `GET` | `/health` | Stan aplikacji |
| `GET` | `/version` | Wersja i etap projektu |
| `POST` | `/perception/observations` | Przyjęcie obserwacji z track ID |
| `POST` | `/perception/detections` | Adapter dla wyniku detektora |
| `GET` | `/world/state` | Aktualny stan obiektów |
| `GET` | `/memory/events` | Historia zdarzeń |
| `GET` | `/memory/timeline` | Oś czasu obserwacji |
| `GET` | `/memory/stats` | Statystyki bazy |
| `POST` | `/memory/reset` | Usunięcie zapamiętanych danych |

## Ustawienia środowiskowe

- `PKK_DB_PATH` — ścieżka do bazy SQLite; domyślnie `data/pkk.sqlite3`.
- `PKK_STALE_AFTER_SECONDS` — po ilu sekundach bez obserwacji obiekt jest oznaczany jako `stale`; domyślnie `5`.
- `PKK_MOVEMENT_THRESHOLD` — minimalne przesunięcie środka bounding boxa (w znormalizowanych współrzędnych); domyślnie `0.03`.
- `PKK_MAX_OBJECTS` — maksymalna liczba obiektów w bieżącym modelu; domyślnie `2000`.
- `PKK_MAX_OBSERVATIONS` — limit zachowanych obserwacji; domyślnie `100000`.
- `PKK_MAX_EVENTS` — limit zachowanych zdarzeń; domyślnie `20000`.

## Prywatność i ograniczenia

Dane są przechowywane lokalnie w SQLite. `POST /memory/reset` usuwa obiekty, obserwacje i historię zdarzeń. Nie ma automatycznej wysyłki danych na zewnątrz.

PKK 0.5 **nie pobiera samodzielnie obrazu z kamery ani nie uruchamia detektora** — przyjmuje wyniki detekcji z PKK 0.2/0.3 lub innego źródła. Ocena `confidence` jest wartością dostarczoną przez detektor, a nie gwarancją prawdziwości. Model świata jest uporządkowanym stanem programu, nie twierdzeniem o świadomości ani pełnym rozumieniu otoczenia.
