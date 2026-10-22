# PKK 0.1 — Percepcyjny Komputer Kwantowy

**Status:** prototyp bazowy (MVP) • **Wersja:** `0.1.0`

PKK 0.1 to szkielet systemu percepcji z REST API. Przyjmuje obraz, sprawdza jego format i podstawowe bezpieczeństwo, a następnie wylicza statystyki pikseli. To fundament architektury, a nie gotowy system rozpoznawania scen.

> **Uczciwe ograniczenie:** wersja 0.1 nie korzysta z komputera kwantowego ani modelu AI do rozpoznawania obiektów. Przygotowuje testowalną bazę pod późniejsze moduły AI i eksperymentalny plugin QML.

## 1. Co działa

- `GET /health` — kontrola stanu API.
- `GET /version` — wersja usługi.
- `POST /perception/image` — analiza pliku JPEG, PNG lub WEBP.
- Statystyki obrazu: wymiary, format, tryb, średnie kanały RGB, przybliżona jasność i proporcje.
- Limit uploadu 10 MiB i limit wymiarów obrazu.
- Przetwarzanie obrazu w pamięci; aplikacja nie zapisuje przesłanych plików na dysku.
- Testy automatyczne oraz obsługa Docker Compose.

## 2. Wymagania

- Python 3.11 lub nowszy (zalecany Python 3.12).
- Windows 10/11 albo Linux.
- Docker z wtyczką Compose jest opcjonalny.

## 3. Uruchomienie na Windows 10/11

Otwórz PowerShell w katalogu projektu. Możesz wykonać skrypt:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-windows.ps1
```

Albo ręcznie:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Jeżeli PowerShell blokuje aktywację środowiska, można uruchamiać interpreter bez aktywacji: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`, a potem `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`.

## 4. Uruchomienie na Linux / Ubuntu

```bash
chmod +x scripts/run-linux.sh
./scripts/run-linux.sh
```

Jeśli moduł `venv` nie jest zainstalowany w systemie, doinstaluj odpowiedni pakiet dla swojej dystrybucji (na Ubuntu zwykle `python3-venv`). Nie instaluj zależności pip globalnie do zarządzanego środowiska systemowego.

## 5. Uruchomienie przez Docker

Z katalogu projektu:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f pkk-api
```

Zatrzymanie:

```bash
docker compose down
```

## 6. Sprawdzenie działania

Po uruchomieniu otwórz w przeglądarce:

- Dokumentacja API: <http://127.0.0.1:8000/docs>
- Stan: <http://127.0.0.1:8000/health>
- Wersja: <http://127.0.0.1:8000/version>

Aby przetestować obraz, wejdź do `/docs`, rozwiń `POST /perception/image`, kliknij **Try it out**, wybierz plik PNG/JPEG/WEBP i wybierz **Execute**.

Przykład z terminala (podmień `sample.png` na istniejący plik):

```bash
curl -X POST "http://127.0.0.1:8000/perception/image" \
  -F "file=@sample.png"
```

## 7. Testy automatyczne

W aktywnym środowisku wirtualnym:

```bash
python -m pytest -q
```

Testy sprawdzają health/version, poprawne przetwarzanie PNG oraz odrzucanie niepoprawnego wejścia.

## 8. Przykładowa odpowiedź

```json
{
  "event_id": "unikalny-identyfikator",
  "timestamp": "2026-01-01T12:00:00Z",
  "modality": "image",
  "status": "processed",
  "method": "basic_pixel_statistics",
  "note": "To analiza cech pikseli, a nie rozpoznawanie znaczenia sceny.",
  "features": {
    "width": 640,
    "height": 480,
    "format": "PNG",
    "mode": "RGB",
    "mean_rgb": {"red": 100.0, "green": 120.0, "blue": 140.0},
    "brightness": 0.45,
    "aspect_ratio": 1.3333,
    "pixel_count": 307200
  }
}
```

Wartości są ilustracyjne, nie pochodzą z rzeczywistego pomiaru.

## 9. Struktura projektu

```text
pkk-0.1/
├── app/
│   ├── main.py
│   ├── schemas.py
│   └── perception/
│       └── image_analyzer.py
├── tests/
│   ├── test_api.py
│   └── test_image_analyzer.py
├── docs/
│   └── ARCHITECTURE.md
├── scripts/
│   ├── run-linux.sh
│   └── run-windows.ps1
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 10. Ograniczenia i prywatność

- Statystyki RGB nie mówią, jakie obiekty znajdują się na zdjęciu.
- API nie zapisuje obrazu, ale klient lub infrastruktura uruchomieniowa mogą prowadzić własne logi; nie przesyłaj danych poufnych do niezaufanego środowiska.
- W tej wersji serwer nasłuchuje lokalnie na `127.0.0.1` w instrukcjach uruchomienia. Nie wystawiaj go do internetu bez uwierzytelniania, limitów ruchu i konfiguracji HTTPS.
- Nie ma pamięci trwałej, kamery w czasie rzeczywistym, mikrofonu, autonomicznych działań ani QPU.

## 11. Następny etap: PKK 0.2

1. Dodanie wymiennego adaptera modelu wizji (najpierw klasycznego, lokalnego).
2. Osobna warstwa `perception/events`, żeby normalizować wyniki modeli.
3. Testy jakości na jawnie opisanym zestawie obrazów i raport metryk.
4. Dopiero później — izolowany eksperymentalny adapter QML z pomiarem czasu, jakości i kosztu względem mocnego baseline'u klasycznego.

## 12. GitHub

Rozpakuj ZIP, utwórz repozytorium GitHub i wgraj **zawartość** folderu `pkk-0.1` (tak, aby `README.md` i `app/` znajdowały się w katalogu głównym repozytorium). Nie wgrywaj folderu `.venv`, tokenów ani poufnych obrazów.
