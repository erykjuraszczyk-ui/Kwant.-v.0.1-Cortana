# PKK 0.3 — architektura

```text
Przeglądarka
  ├── getUserMedia (kamera po zgodzie użytkownika)
  ├── video → canvas (zmniejszenie klatki do 960 px)
  ├── JPEG + POST /perception/objects
  └── overlay SVG-like canvas + telemetria detekcji
                 │
                 ▼
FastAPI
  ├── kontrola rozmiaru uploadu i walidacja obrazu
  ├── PIL: dekodowanie do RGB i korekta EXIF
  ├── adapter ObjectDetector
  │    └── Ultralytics YOLO (lazy load, domyślnie CPU)
  └── JSON: klasy, confidence, bbox, processing_ms
```

Kamera nie jest dostępna dla backendu bezpośrednio. Przeglądarka klienta otwiera ją po przycisku i zgodzie, a następnie przesyła pojedyncze klatki do API. Frontend czeka na odpowiedź przed planowaniem kolejnej analizy; ogranicza to kolejkę po stronie przeglądarki. Backend serializuje inferencje współdzielonego modelu przez istniejący lock w adapterze.

`processing_ms` obejmuje czas wywołania adaptera `detect`, łącznie z ładowaniem modelu przy pierwszym wywołaniu. Nie jest to wyłącznie czysty czas wykonania sieci. `scripts/benchmark.py` mierzy również całkowity czas żądania HTTP.

Obrazy nie są zapisywane na dysku przez aplikację i nie ma magazynu klatek. To nie usuwa ryzyka transmisji: klatki trafiają do instancji API, do której skierowana jest przeglądarka. Wdrożenie sieciowe wymaga autoryzacji, HTTPS i limitowania ruchu.

Wszystkie obliczenia detekcji w tej wersji są klasyczne; brak modułu obliczeń kwantowych.
