# PKK 0.8 — Objaśnialny moduł decyzyjny

PKK 0.8 dodaje centralny moduł, który zbiera sygnały z modelu świata i pamięci kontekstowej, a następnie tworzy ograniczoną rekomendację z uzasadnieniem, dowodami i niepewnością.

**Nie wykonuje działań zewnętrznych.** To celowa granica bezpieczeństwa dla prototypu.

## Co nowego
- `POST /decision/evaluate` — ocena aktualnej sytuacji i rekomendacja `report`, `observe_more` albo `no_action`.
- `GET /decision/policy` — jawne ograniczenia modułu decyzyjnego.
- Wykorzystanie aktywnych/nieobserwowanych obiektów i świeżych zdarzeń kontekstowych.
- Każdy wynik zawiera przesłanki, ograniczenia oraz informację `execution: none`.
- Zachowane funkcje PKK 0.7: fuzja, historia SQLite, model świata i predykcja ruchu.

## Uruchomienie — Windows PowerShell
```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Albo: `scripts\\run-windows.ps1`.

## Uruchomienie — Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Albo: `bash scripts/run-linux.sh`.

API: http://127.0.0.1:8000/docs

## Pierwszy test
W Swaggerze wywołaj `POST /decision/evaluate`:
```json
{
  "goal": "summarize_current_scene",
  "horizon_seconds": 10,
  "include_context": true
}
```
Otrzymasz rekomendację, listę przesłanek, niepewności i politykę wykonania. Jeśli brak świeżych danych, rekomendacja będzie zachęcała do dalszej obserwacji, a nie do zgadywania.

## Endpointy PKK 0.8
| Endpoint | Funkcja |
|---|---|
| `POST /decision/evaluate` | ocena sytuacji i rekomendacja |
| `GET /decision/policy` | aktywne ograniczenia |
| `GET /fusion/state` | fuzja sygnałów w oknie czasowym |
| `GET /fusion/timeline` | wspólna oś czasu |
| `POST /context/events` | zapis pochodnego zdarzenia |
| `GET /world/state` | aktualny model świata |
| `GET /memory/timeline` | historia obserwacji |
| `GET /inference/predict/{track_id}` | szacowanie ruchu |
| `GET /memory/stats` | statystyki pamięci |
| `POST /memory/reset` | czyszczenie pamięci i kontekstu |

## Zasady i ograniczenia
- To klasyczny prototyp AI; nie używa komputera kwantowego.
- Nie aktywuje samodzielnie kamery ani mikrofonu.
- Nie wykonuje poleceń systemowych, nie steruje urządzeniami i nie wysyła wiadomości.
- Nie ma jeszcze uczenia polityki ani rozumowania semantycznego. Wynik jest zbiorem prostych reguł i opisem danych.
- W przyszłej wersji każda integracja z działaniami zewnętrznymi powinna mieć listę dozwolonych operacji, dziennik audytowy, kontrolę uprawnień i jawne zatwierdzenie człowieka.
