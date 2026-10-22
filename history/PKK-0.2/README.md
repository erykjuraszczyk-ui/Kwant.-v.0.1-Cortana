# PKK 0.2 — Percepcyjny Komputer Kwantowy

**Wersja:** `0.2.0` · **Platformy:** Windows 10/11 i Linux · **API:** FastAPI · **Model:** YOLO26n (CPU jako domyślne urządzenie)

PKK 0.2 rozwija bazowe API z wersji 0.1 o **rzeczywistą detekcję obiektów na obrazach**. Model jest ładowany lokalnie, a obraz przesłany do API jest przetwarzany w pamięci i nie jest zapisywany przez aplikację na dysku.

> **Ważne, bez marketingowej magii:** to klasyczna sieć neuronowa uruchamiana na zwykłym CPU/GPU. PKK 0.2 nie korzysta z fizycznego komputera kwantowego i nie demonstruje przewagi kwantowej. W tym etapie budujemy rzetelny baseline percepcji.

## Funkcje

- `GET /health` — sprawdzenie, czy API odpowiada.
- `GET /version` — wersja usługi.
- `GET /perception/model` — konfiguracja modelu, urządzenie i informacja, czy model jest załadowany.
- `POST /perception/image` — kompatybilna z 0.1 analiza bazowych statystyk pikseli.
- `POST /perception/objects` — wykrywanie obiektów; odpowiedź zawiera etykietę, `class_id`, ocenę `confidence` i ramkę ograniczającą.
- Dokumentacja interaktywna Swagger pod `/docs`.
- Testy automatyczne nie wymagają pobierania prawdziwych wag modelu.

## Wymagania

- Python 3.11 lub 3.12 (zalecany 3.12).
- Połączenie z internetem przy instalacji zależności oraz pierwszym pobraniu modelu.
- Zapas miejsca i RAM na PyTorch oraz model. Instalacja zależności może zajmować dużo miejsca (pakiety ML są duże). CPU wystarczy do testów; czas analizy zależy od komputera i rozdzielczości obrazu.
- Docker jest opcjonalny.

## Uruchomienie — Windows 10/11

1. Pobierz i rozpakuj `PKK-0.2.zip`.
2. Otwórz PowerShell w folderze `pkk-0.2`.
3. Uruchom skrypt:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-windows.ps1
```

Jeśli wolisz komendy ręczne:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Przy pierwszym zapytaniu do `/perception/objects` model `yolo26n.pt` może zostać pobrany automatycznie. To może potrwać i wymaga działającego internetu. Gdy wagi są już w pamięci podręcznej, inferencja jest wykonywana lokalnie.

## Uruchomienie — Linux / Ubuntu

```bash
chmod +x scripts/run-linux.sh
./scripts/run-linux.sh
```

Jeśli nie masz modułu `venv`, zainstaluj pakiet `python3-venv` dla swojej dystrybucji. Nie instaluj zależności pip globalnie do zarządzanego środowiska systemowego.

## Uruchomienie przez Docker

W katalogu projektu:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f pkk-api
```

Zatrzymanie:

```bash
docker compose down
```

Port jest domyślnie wystawiony tylko na `127.0.0.1`, aby nie udostępniać prototypu całej sieci. Pierwsze żądanie detekcji wymaga dostępu do pobrania modelu. Wagi pobrane wewnątrz kontenera nie są dołączone do archiwum źródłowego; po usunięciu i odtworzeniu kontenera pobranie może być wymagane ponownie.

## Sprawdzenie API

Po uruchomieniu otwórz:

- <http://127.0.0.1:8000/docs> — Swagger / testowanie endpointów.
- <http://127.0.0.1:8000/health> — stan API.
- <http://127.0.0.1:8000/version> — wersja.
- <http://127.0.0.1:8000/perception/model> — status konfiguracji modelu.

### Jak wykryć obiekty

1. Otwórz `/docs`.
2. Rozwiń `POST /perception/objects`.
3. Kliknij **Try it out**.
4. Wybierz obraz JPEG, PNG lub WEBP.
5. Opcjonalnie podaj `confidence` z zakresu `0–1` (np. `0.25`).
6. Kliknij **Execute**.

Alternatywnie, w PowerShell (podmień ścieżkę na swój plik):

```powershell
curl.exe -X POST "http://127.0.0.1:8000/perception/objects" -F "file=@C:\sciezka\zdjecie.jpg"
```

Przykładowy kształt odpowiedzi:

```json
{
  "event_id": "<unikalne-id>",
  "timestamp": "2026-10-22T12:00:00Z",
  "modality": "image",
  "status": "processed",
  "method": "ultralytics_yolo_object_detection",
  "model": "yolo26n.pt",
  "device": "cpu",
  "confidence_threshold": 0.25,
  "image": {"width": 1280, "height": 720, "format": "JPEG", "source_mode": "RGB"},
  "count": 1,
  "detections": [
    {
      "class_id": 0,
      "label": "person",
      "confidence": 0.91,
      "bbox": {"x1": 100.0, "y1": 45.0, "x2": 260.0, "y2": 640.0}
    }
  ],
  "note": "To predykcje modelu detekcji..."
}
```

To przykład formatu, a nie wynik rzeczywistego pomiaru. Etykiety i wyniki zależą od obrazu i modelu. Ocena `confidence` nie jest gwarancją poprawności ani skalibrowanym prawdopodobieństwem.

## Konfiguracja modelu

Skopiuj `.env.example` do `.env` jako ściągę ustawień. Proste skrypty uruchomieniowe nie wczytują automatycznie pliku `.env`; ustaw zmienne w terminalu albo w konfiguracji Docker Compose.

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `PKK_MODEL` | `yolo26n.pt` | Nazwa modelu albo ścieżka do lokalnych wag |
| `PKK_DEVICE` | `cpu` | Urządzenie inferencji; zacznij od CPU |
| `PKK_CONFIDENCE` | `0.25` | Próg wyniku modelu (0–1) |
| `PKK_MAX_DETECTIONS` | `100` | Limit wykryć na obraz (1–300) |
| `PKK_LOG_LEVEL` | `INFO` | Poziom logowania |

Dla pojedynczego testu możesz podać `confidence` w query string endpointu. Nie wpisuj żadnych sekretów do kodu ani do repozytorium.

## Testy automatyczne

W aktywnym środowisku wirtualnym:

```bash
python -m pytest -q
```

Testy używają modelu zastępczego, aby były szybkie i nie pobierały wag. Nie mierzą skuteczności prawdziwego modelu na Twoim zbiorze danych. Rzetelna ocena jakości wymaga oznaczonego zestawu testowego i policzenia m.in. precision, recall oraz mAP.

## Bezpieczeństwo i prywatność

- Limit uploadu: 10 MiB; dozwolone formaty: JPEG, PNG, WEBP; limit wymiarów: 20 mln pikseli.
- Walidowany jest rzeczywisty format pliku, a nie wyłącznie nagłówek `Content-Type`.
- Przesłane obrazy nie są zapisywane przez kod aplikacji na dysku, ale nie wysyłaj danych poufnych do niezaufanego środowiska.
- API w przykładach działa lokalnie. Przed udostępnieniem w sieci potrzebne są m.in. uwierzytelnianie, ograniczenia ruchu, HTTPS i przegląd bezpieczeństwa.
- Endpoint `/health` sprawdza API, nie dostępność modelu.

## Licencja modelu — przeczytaj przed publikacją lub komercyjnym użyciem

PKK 0.2 korzysta z pakietu i domyślnych wag Ultralytics YOLO. Warunki Ultralytics rozróżniają licencję AGPL-3.0 i licencję Enterprise. Przed publikacją zmodyfikowanego rozwiązania, użyciem prywatnym lub komercyjnym sprawdź aktualne zasady na stronie <https://www.ultralytics.com/license> i dopasuj licencję całego projektu do sposobu wykorzystania. To nie jest porada prawna.

## Struktura repozytorium

```text
pkk-0.2/
├── app/
│   ├── main.py
│   ├── schemas.py
│   └── perception/
│       ├── image_analyzer.py
│       └── object_detector.py
├── tests/
├── docs/ARCHITECTURE.md
├── scripts/run-linux.sh
├── scripts/run-windows.ps1
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Następny etap: PKK 0.3

- Dodać obsługę kamery lub klatek wideo w kontrolowanym trybie.
- Zbudować jawny zestaw próbny i raport precision/recall/mAP.
- Dodać łączenie wyników wizji z czasem i kontekstem, z kontrolą retencji danych.
- Dopiero po zbudowaniu klasycznego punktu odniesienia rozpocząć eksperymenty QML i porównywać jakość, czas oraz koszt.

## GitHub

Wgraj **zawartość** folderu `pkk-0.2` do repozytorium, tak aby `README.md` i `app/` znajdowały się w głównym katalogu. Nie wgrywaj `.venv`, plików modelu, prywatnych zdjęć ani tokenów.
