# Architektura PKK 0.2

## Przepływ obrazu

1. API przyjmuje pojedynczy plik JPEG, PNG lub WEBP (limit 10 MiB).
2. Walidator sprawdza rzeczywisty format i wymiary, odrzuca uszkodzone wejście i tworzy kopię RGB w pamięci.
3. `POST /perception/image` wylicza bazowe statystyki pikseli.
4. `POST /perception/objects` przekazuje obraz do adaptera `ObjectDetector`.
5. Adapter leniwie inicjalizuje `ultralytics.YOLO`, domyślnie `yolo26n.pt`, i wykonuje inferencję na CPU.
6. Wynik jest normalizowany do klas, ocen confidence oraz prostokątów `x1/y1/x2/y2` w pikselach obrazu.
7. API oddaje JSON. Obraz nie jest zapisywany przez aplikację na dysku.

## Moduły

- `app/main.py` — REST API, walidacja przesłanych plików, mapowanie błędów.
- `app/perception/image_analyzer.py` — dekodowanie obrazu i cechy bazowe.
- `app/perception/object_detector.py` — odseparowany adapter inferencji modelu.
- `app/schemas.py` — kontrakty odpowiedzi.
- `tests/` — testy API i adaptera z modelem zastępczym; nie pobierają prawdziwych wag.

## Konfiguracja

- `PKK_MODEL`: nazwa modelu lub ścieżka do lokalnego pliku wag; domyślnie `yolo26n.pt`.
- `PKK_DEVICE`: `cpu` domyślnie; dla odpowiednio skonfigurowanego środowiska można wybrać `0`.
- `PKK_CONFIDENCE`: próg od `0` do `1`, domyślnie `0.25`.
- `PKK_MAX_DETECTIONS`: liczba detekcji na obraz w zakresie `1–300`.

Model ładowany jest przy pierwszym wywołaniu `/perception/objects`, nie przy starcie procesu. Pobranie wag wymaga internetu; kolejne inferencje mogą działać lokalnie z pamięci podręcznej. W Dockerze wolumen `/models` służy do utrzymania katalogu konfiguracji/cache między uruchomieniami.

## Ograniczenia

- Detektor wykrywa kategorie znane z danych treningowych i może nie rozpoznać nowych klas ani obiektów nietypowych.
- `confidence` jest wynikiem modelu, a nie gwarancją prawdziwości.
- Brak kamery ciągłej, śledzenia wideo, pamięci długotrwałej, planowania działań, rozpoznawania emocji i połączenia z fizycznym QPU.
- Endpoint `/health` sprawdza, czy działa API; nie gwarantuje, że model można pobrać ani załadować.

## Licencja komponentu zewnętrznego

PKK 0.2 używa pakietu i domyślnego modelu Ultralytics YOLO. Sprawdź aktualne warunki licencji Ultralytics przed dystrybucją, wdrożeniem prywatnym lub użyciem komercyjnym. Opublikowanie repozytorium na GitHub nie zastępuje analizy obowiązków licencyjnych.
