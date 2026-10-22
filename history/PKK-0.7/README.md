# PKK 0.7 — Fuzja percepcji i kontekstu

PKK 0.7 rozwija 0.6 o prostą, objaśnialną fuzję kilku typów sygnałów: obserwacji wzrokowych w modelu świata oraz pochodnych zdarzeń audio, tekstowych i środowiskowych.

> **Uczciwe ograniczenie:** to klasyczny prototyp AI. Nie wykonuje obliczeń kwantowych, nie przechwytuje automatycznie mikrofonu i nie wnioskuje, że dany obiekt jest źródłem dźwięku. Dopasowanie opiera się na zbieżności w czasie.

## Nowe funkcje
- `POST /context/events` — zapis gotowego zdarzenia, np. `speech_detected` z lokalnego modułu rozpoznawania mowy.
- `GET /context/events` — historia zdarzeń kontekstowych; można filtrować po modalności.
- `GET /fusion/state?window_seconds=10` — podsumowanie sygnałów w wybranym oknie czasu, reguły i ostrożnie opisane korelacje czasowe.
- `GET /fusion/timeline` — jedna oś czasu dla obserwacji wzrokowych i kontekstu.
- Rozszerzona baza SQLite z migracją schematu do wersji 2.
- Wspólny reset pamięci i historii kontekstowej.
- Zachowane endpointy pamięci, modelu świata oraz predykcji ruchu z PKK 0.6.

## Wymagania
- Python 3.11+
- Zależności w `requirements.txt`

## Uruchomienie — Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Alternatywnie: `scripts\\run-windows.ps1`

## Uruchomienie — Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Alternatywnie: `bash scripts/run-linux.sh`

API: http://127.0.0.1:8000/docs

## Szybki eksperyment

1. Wyślij obserwację do `POST /perception/observations`.
2. Wyślij pochodne zdarzenie audio do `POST /context/events`.
3. Otwórz `GET /fusion/state?window_seconds=30`.

Obserwacja wzrokowa — `POST /perception/observations`:
```json
{
  "source": "camera-1",
  "observed_at": "2026-10-22T12:00:00Z",
  "observations": [
    {"track_id": "person-1", "label": "person", "confidence": 0.94,
     "bbox": [0.10, 0.10, 0.30, 0.70]}
  ]
}
```

Kontekst audio — `POST /context/events`:
```json
{
  "modality": "audio",
  "event_type": "speech_detected",
  "source": "local-whisper",
  "observed_at": "2026-10-22T12:00:01Z",
  "confidence": 0.82,
  "summary": "Wykryto mowę; transkrypcja wyłączona.",
  "entities": []
}
```
W przykładzie użyto daty demonstracyjnej. Dla testu aktywnego okna użyj aktualnego czasu UTC lub ustaw parametr okna adekwatnie.

## Endpointy
| Endpoint | Przeznaczenie |
|---|---|
| `POST /perception/observations` | zapis obserwacji wzrokowych |
| `POST /perception/detections` | adapter danych detektora |
| `GET /world/state` | model świata |
| `GET /memory/timeline` | historia obserwacji wzrokowych |
| `GET /memory/events` | zdarzenia modelu świata |
| `GET /memory/stats` | statystyki i wersja schematu |
| `GET /inference/predict/{track_id}` | estymacja ruchu z historii |
| `GET /inference/summary` | regułowe podsumowanie aktywności |
| `POST /context/events` | zapis zdarzenia audio/tekstu/środowiska |
| `GET /context/events` | odczyt zdarzeń kontekstowych |
| `GET /fusion/state` | regułowe podsumowanie wielu modalności |
| `GET /fusion/timeline` | wspólna oś czasu |
| `POST /memory/reset` | wyczyszczenie pamięci PKK |
| `POST /context/reset` | wyczyszczenie tylko zdarzeń kontekstowych |

## Prywatność i interpretacja
- Program nie ma funkcji nagrywania mikrofonu ani zapisywania surowych klatek wideo. Przyjmuje już przetworzone metadane.
- Pole `summary` może zawierać transkrypcję lub inny tekst. Wysyłaj tylko niezbędne dane, unikaj sekretów i włącz kontrolę dostępu przed wystawieniem API poza `localhost`.
- Domyślna baza `data/pkk.sqlite3` jest lokalna. W Dockerze plik bazy powinien być zachowany w lokalnym wolumenie/katalogu, jeżeli dane mają przetrwać odtworzenie kontenera.
- Zbieżność czasowa nie dowodzi, że widoczna osoba mówiła, że dźwięk pochodził od widocznego obiektu ani że zdarzenia mają związek przyczynowy.
- Pole `confidence` jest oceną wejściowego modułu, a nie skalibrowanym prawdopodobieństwem prawdziwości całej fuzji.

## Co oznacza „fuzja” w 0.7?
To pierwszy etap: synchronizacja metadanych, podsumowanie aktywnych modalności, proste reguły i korelacje czasowe. Nie jest to jeszcze uczenie multimodalne ani pełne rozumienie sceny. Kolejne kroki mogą dodać lokalną transkrypcję mowy, tracker obiektów, konfigurowalne reguły i metryki oceny.
