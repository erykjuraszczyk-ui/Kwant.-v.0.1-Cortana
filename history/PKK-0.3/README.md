# PKK 0.3 — Percepcyjny Komputer Kwantowy

**Wersja:** `0.3.0` · **Systemy:** Windows 10/11 i Linux · **API:** FastAPI · **Percepcja:** YOLO + kamera przeglądarki

PKK 0.3 rozbudowuje PKK 0.2 o lokalną stronę do analizy obrazu z kamery na żywo, nakładkę z ramkami detekcji, telemetrię czasu analizy i skrypt do pomiaru wydajności na własnym zestawie obrazów.

> **Ważne:** mimo nazwy projektu ta wersja działa na klasycznym CPU/GPU i klasycznej sieci neuronowej. Nie steruje fizyczną kamerą z backendu ani nie używa komputera kwantowego. Kamera jest otwierana przez przeglądarkę dopiero po kliknięciu przycisku i przyznaniu zgody.

## Nowości w 0.3

- `GET /camera` — panel z podglądem, ramkami obiektów i etykietami.
- Klatki JPEG są wysyłane kolejno do `POST /perception/objects`; następna analiza zaczyna się dopiero po zakończeniu poprzedniej.
- Regulowany odstęp między analizami i próg `confidence`.
- `processing_ms` w odpowiedzi API — czas wywołania detektora w ms (pierwsza analiza może obejmować ładowanie modelu).
- `scripts/benchmark.py` — pomiar czasu API na folderze obrazów i eksport CSV. To pomiar wydajności, nie samodzielna metryka trafności.
- Zachowane endpointy PKK 0.1 i 0.2, w tym `/health`, `/version`, `/perception/image` i `/perception/objects`.
- Testy nie wymagają pobierania prawdziwych wag modelu.

## Wymagania

- Python 3.11 lub 3.12 (zalecany 3.12).
- Internet przy instalacji zależności i pierwszym pobraniu wag modelu, jeśli ich nie masz.
- Dostęp do kamery z poziomu przeglądarki oraz jej zgoda.
- Docker jest opcjonalny. Przy pierwszej instalacji pakiety ML mogą zająć dużo miejsca.

## Uruchomienie — Windows 10/11

1. Rozpakuj `PKK-0.3.zip`.
2. Otwórz PowerShell w katalogu `pkk-0.3`.
3. Uruchom:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-windows.ps1
```

Alternatywnie, ręcznie:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Uruchomienie — Linux / Ubuntu

```bash
chmod +x scripts/run-linux.sh scripts/benchmark.py
./scripts/run-linux.sh
```

Jeśli brakuje `venv`, zainstaluj pakiet `python3-venv` dla swojej dystrybucji. Nie instaluj zależności globalnie do zarządzanego środowiska systemowego.

## Otwórz panel kamery

Po starcie serwera otwórz lokalnie:

- **Panel percepcji na żywo:** <http://127.0.0.1:8000/camera>
- Dokumentacja API: <http://127.0.0.1:8000/docs>
- Stan API: <http://127.0.0.1:8000/health>
- Konfiguracja modelu: <http://127.0.0.1:8000/perception/model>

Na stronie naciśnij **Start kamery**, zezwól na dostęp w przeglądarce i poczekaj na pierwszą analizę. Przy pierwszym żądaniu model YOLO może pobrać wagi; pierwsza analiza może więc trwać dłużej. Użyj **Zatrzymaj**, aby zwolnić kamerę.

**Ważne wskazówki:**

- `getUserMedia` wymaga bezpiecznego kontekstu — zwykle `localhost` albo HTTPS. Nie będzie działać dla dowolnej strony HTTP w sieci lokalnej.
- Kamera pozostaje po stronie przeglądarki; Docker nie wymaga mapowania urządzenia kamery. Klatki są przesyłane do lokalnego backendu do analizy.
- Aplikacja nie zapisuje obrazów na dysku ani nie przechowuje historii wideo. Klatki istnieją w pamięci podczas przetwarzania.
- Dla słabszego CPU ustaw odstęp 2–3 s. Pętla nie wysyła równoległych żądań z tej strony.

## Docker

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f pkk-api
```

Zatrzymanie: `docker compose down`. API wystawione jest domyślnie tylko na `127.0.0.1:8000`. Wagi są przechowywane w wolumenie Dockera; nie znajdują się w ZIP.

## Benchmark wydajności

Przygotuj folder `sample-images/` z plikami, które masz prawo analizować, uruchom API, a następnie:

```bash
python scripts/benchmark.py sample-images --output reports/pkk-benchmark.csv
```

Dostępne opcje: `--url`, `--confidence`, `--timeout`, `--output`. CSV zawiera nazwę pliku, status żądania, liczbę detekcji, etykiety oraz czasy odpowiedzi i detektora. Obrazy nie są kopiowane do raportu.

**Czas to nie trafność.** Aby ocenić jakość rozpoznawania, potrzebny jest oznaczony zbiór prawdziwych ramek i klas (`ground truth`); dopiero wtedy oblicza się m.in. precision, recall i mAP. Więcej: [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md).

## Testy automatyczne

W aktywnym środowisku wirtualnym:

```bash
python -m pytest -q
```

Testy używają lekkiego modelu testowego zamiast rzeczywistych wag; nie potwierdzają wydajności ani trafności konkretnego modelu na danym komputerze.

## Konfiguracja modelu

Skopiuj `.env.example` jako ściągę ustawień. Skrypty startowe nie wczytują automatycznie `.env`; ustaw zmienne środowiskowe w terminalu lub w konfiguracji Docker Compose.

| Zmienna | Domyślna wartość | Znaczenie |
|---|---|---|
| `PKK_MODEL` | `yolo26n.pt` | Nazwa lub ścieżka do wag modelu |
| `PKK_DEVICE` | `cpu` | Urządzenie inferencji; zacznij od CPU |
| `PKK_CONFIDENCE` | `0.25` | Domyślny próg detekcji |
| `PKK_MAX_DETECTIONS` | `100` | Maksymalna liczba detekcji na klatkę |
| `PKK_LOG_LEVEL` | `INFO` | Poziom logowania |

## Prywatność i bezpieczeństwo

- Kamera jest uruchamiana tylko na żądanie użytkownika w przeglądarce.
- API akceptuje JPEG, PNG i WEBP do 10 MiB i kontroluje wymiary obrazu.
- Klatki nie są archiwizowane przez kod aplikacji. Same żądania są przetwarzane przez backend i nie powinny zawierać danych, których nie chcesz wysłać do tej instancji API.
- Przed udostępnieniem API poza komputer lokalny konieczne są co najmniej uwierzytelnianie, HTTPS, ograniczanie ruchu, kontrola dostępu i przegląd prywatności.

## Licencja modelu

Domyślny adapter wykorzystuje Ultralytics. Przed publikacją lub zastosowaniem komercyjnym sprawdź bieżące warunki licencyjne: <https://www.ultralytics.com/license>. Licencja całego wdrożenia zależy od sposobu wykorzystania.

## Struktura projektu

```text
pkk-0.3/
├── app/
│   ├── main.py
│   ├── schemas.py
│   ├── static/camera.html
│   └── perception/
│       ├── image_analyzer.py
│       └── object_detector.py
├── docs/TEST_PLAN.md
├── scripts/benchmark.py
├── scripts/run-linux.sh
├── scripts/run-windows.ps1
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## GitHub

Wgraj zawartość folderu `pkk-0.3` do głównego katalogu repozytorium tak, aby `README.md`, `app/` i `tests/` znajdowały się na najwyższym poziomie. Nie dodawaj `.venv`, wag `.pt`, zdjęć prywatnych ani sekretów.
