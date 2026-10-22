# PKK — Percepcyjny Komputer Kwantowy
## Zbiorczy pakiet wersji 0.1–1.0

To archiwum łączy wszystkie przesłane wersje projektu **PKK 0.1–PKK 1.0**. Główny katalog zawiera kod **PKK 1.0**, a katalog `history/` zachowuje wcześniejsze migawki źródłowe.

> **Ważne technicznie:** nazwa projektu jest koncepcją. PKK 1.0 to klasyczny prototyp AI z API, pamięcią, regułami, fuzją i warstwą dialogową. Nie wykonuje jeszcze obliczeń na fizycznym komputerze kwantowym.

## Zawartość archiwum

| Wersja | Główna zmiana |
|---|---|
| `0.1` | Podstawowe API oraz statystyki pikseli obrazu |
| `0.2` | Detekcja obiektów przez klasyczny model AI |
| `0.3` | Analiza klatek z kamery w przeglądarce i benchmark |
| `0.4` | Pamięć percepcyjna i podstawowy model świata |
| `0.5` | Trwała pamięć SQLite i historia obserwacji |
| `0.6` | Wnioskowanie regułowe i estymacja krótkoterminowego ruchu |
| `0.7` | Fuzja obserwacji wzrokowych z metadanymi innych modalności |
| `0.8` | Objaśnialne rekomendacje i ograniczenia działań |
| `0.9` | Warstwa dialogowa Cortany i adaptery modeli językowych |
| `1.0` | Zintegrowany prototyp i panel Cortany z opcjonalnym głosem |

W `history/PKK-X/` zachowano pliki źródłowe każdej wcześniejszej wersji. Główny katalog jest punktem startowym do rozwijania projektu dalej od wersji 1.0.

## Uruchomienie PKK 1.0 na Windows 10/11

Wymagany Python 3.12 (Python 3.11+ może działać, ale skrypt automatyczny wskazuje 3.12).

1. Rozpakuj archiwum.
2. Otwórz PowerShell w głównym katalogu — tam, gdzie znajdują się `README.md`, `app/` i `scripts/`.
3. Uruchom:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\run-windows.ps1
```

Po starcie otwórz:

- Panel Cortany: http://127.0.0.1:8000/cortana
- Dokumentacja API: http://127.0.0.1:8000/docs
- Status całości: http://127.0.0.1:8000/system/status

## Uruchomienie w Linux / Ubuntu

```bash
bash scripts/run-linux.sh
```

Albo utwórz wirtualne środowisko, zainstaluj `requirements.txt` i uruchom:

```bash
python -m uvicorn app.main:app --reload
```

## Model językowy

Domyślnie panel działa w trybie lokalnych reguł i nie potrzebuje klucza API. Aby włączyć model językowy, skonfiguruj zmienne `PKK_CHAT_PROVIDER`, `PKK_CHAT_BASE_URL`, `PKK_CHAT_MODEL` i opcjonalnie `PKK_CHAT_API_KEY` w backendzie. Instrukcje i uwagi prywatności są w dalszej części `README.md` w sekcji PKK 1.0 (informacje warstwy dialogowej).

Nie umieszczaj sekretów ani pliku `.env` w publicznym repozytorium.

## Testy

W katalogu głównym:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Testy weryfikują API i wybrane zachowania modułów. Nie są dowodem, że w danym środowisku zadziała mikrofon, fizyczna kamera, zewnętrzne API lub wagi modelu detekcji.

## Układ

```text
PKK-Kompletny-0.1-1.0/
├── app/                 # kod PKK 1.0 (punkt startowy)
├── tests/               # testy wersji 1.0
├── scripts/             # skrypty uruchomieniowe
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── SHA256SUMS-INPUTS.txt
└── history/
    ├── PKK-0.1/
    ├── PKK-0.2/
    ├── ...
    └── PKK-0.9/
```

## Prywatność i dane

W archiwum zbiorczym usunięto runtime-owe pliki bazy SQLite, cache Pythona i lokalne środowiska wirtualne. Aplikacja utworzy nową bazę danych przy uruchomieniu. Dla zachowania danych uruchomionej aplikacji katalog bazy powinien być utrzymywany i nie kasowany.

Gdy aktywujesz zewnętrzny model językowy, wiadomość oraz wybrane metadane PKK mogą opuścić komputer. Rozpoznawanie mowy Web Speech API i synteza głosu zależą od przeglądarki; nie należy zakładać, że każde rozpoznawanie odbywa się całkowicie lokalnie.

## Kierunek dalszego rozwoju

Następny etap powinien skupić się na integracyjnym teście end-to-end, stabilnym trackerze obiektów, lokalnym rozpoznawaniu mowy i mierzalnych metrykach. Eksperymentalny moduł QML należy dołączyć osobno i oceniać na konkretnym zadaniu względem klasycznej metody bazowej.
