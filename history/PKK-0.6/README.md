# PKK 0.6 — Silnik wnioskowania i krótkoterminowego przewidywania

PKK 0.6 rozwija wersję 0.5 o **objaśnialne reguły aktywności** i **krótkoterminową estymację położenia obiektów** na podstawie historii obserwacji. Pamięć SQLite z wersji 0.5 została zachowana.

> Uczciwe ograniczenie: jest to klasyczny prototyp AI, nie komputer kwantowy. Estymacja ruchu zakłada lokalnie liniowy ruch obiektu w obrazie. Wynik nie gwarantuje przyszłej pozycji i nie jest prawdopodobieństwem. Etykiety klas pochodzą z detektora wejściowego.

## Nowe możliwości
- `GET /inference/predict/{track_id}` — dopasowanie linii do historycznych środków ramek i prognoza na krótki horyzont 0.1–10 s.
- `GET /inference/summary` — jawne reguły podsumowujące ruch, nowe obiekty, brak obserwacji, zmianę klasy i ponowne pojawienie się.
- Zwraca wektor prędkości w znormalizowanych współrzędnych obrazu, przewidywaną ramkę, błąd dopasowania, liczbę próbek i opis jakości estymacji.
- Zachowuje SQLite, historię zdarzeń, oś czasu, adapter detektora i endpointy z wersji 0.5.

## Wymagania
- Python 3.11+
- Zależności z `requirements.txt`

## Uruchomienie — Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Alternatywnie: `\.\scripts\run-windows.ps1`

## Uruchomienie — Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Alternatywnie: `bash scripts/run-linux.sh`

Dokumentacja API: http://127.0.0.1:8000/docs

## Szybki eksperyment
Wyślij kilka różnych obserwacji z tym samym `track_id` i różnymi czasami `observed_at`. Współrzędne ramki `bbox` muszą być znormalizowane do 0–1 w kolejności `[x1, y1, x2, y2]`.

Przykładowe pierwsze żądanie do `POST /perception/observations`:
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
Zmień czas i przesuwaj ramkę w kolejnych żądaniach, np. do `[0.15, 0.10, 0.35, 0.70]`, a następnie wywołaj:
`GET /inference/predict/person-1?horizon_seconds=1.0`

## Główne endpointy
| Endpoint | Funkcja |
|---|---|
| `POST /perception/observations` | Zapis obserwacji |
| `POST /perception/detections` | Adapter danych detektora |
| `GET /world/state` | Aktualny model świata |
| `GET /memory/timeline` | Oś czasu obserwacji |
| `GET /memory/events` | Zapis zdarzeń |
| `GET /memory/stats` | Statystyki bazy |
| `GET /inference/predict/{track_id}` | Krótkoterminowa estymacja ruchu |
| `GET /inference/summary` | Regułowe podsumowanie aktywności |
| `POST /memory/reset` | Wyczyszczenie danych pamięci |

## Jak interpretować wynik przewidywania
- `velocity_normalized_per_second`: zmiana środka ramki na sekundę w skali obrazu 0–1.
- `predicted_bbox`: przewidywana ramka; przy krawędzi obrazu położenie jest ograniczane do granic obrazu.
- `fit_rmse`: błąd dopasowania linii do historycznych środków ramek; niższa wartość zwykle oznacza prostszy przebieg w badanym oknie.
- `estimate_quality`: wskaźnik jakości oparty na liczbie próbek, długości historii i błędzie dopasowania, **nie prawdopodobieństwo**.
- Prognoza staje się mniej wiarygodna przy skrętach, zasłonięciu, błędach detekcji lub nagłych zmianach ruchu.

## Prywatność i ograniczenia
- Dane pozostają lokalnie w pliku SQLite; aplikacja nie wysyła ich z własnej inicjatywy do zewnętrznych usług.
- Używaj stabilnego `track_id` z trackera. Adapter bez `track_id` tworzy identyfikator ograniczony do jednej klatki, więc nie pozwala wiarygodnie przewidywać ruchu między klatkami.
- Predykcja działa na współrzędnych obrazu, nie na metrach w świecie rzeczywistym.
- „Wnioskowanie” to zestaw jawnych reguł i regresja liniowa, a nie ogólne rozumienie sytuacji.
