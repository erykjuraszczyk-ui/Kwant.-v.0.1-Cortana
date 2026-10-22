# PKK 0.1 — architektura

## Przepływ danych

```text
Klient
  │ POST /perception/image
  ▼
FastAPI: walidacja rozmiaru uploadu
  ▼
Image Analyzer: Pillow → wymiary/format/RGB/jasność
  ▼
PerceptionEvent: identyfikator + czas UTC + metoda + cechy
  ▼
JSON do klienta
```

## Granice odpowiedzialności

- `app/main.py`: HTTP, walidacja uploadu, statusy błędów.
- `app/perception/image_analyzer.py`: interpretacja niskopoziomowych pikseli.
- `app/schemas.py`: stabilny format zdarzenia percepcyjnego.
- `tests/`: testy zachowania API i analizatora.

## Planowana architektura docelowa

```text
Sensory / pliki / strumienie
        ↓
Adapters → Normalizacja obserwacji
        ↓
Percepcja AI → Wyniki + pewność + wersja modelu
        ↓
Fuzja obserwacji → Model świata
        ↓
Planowanie / polityki bezpieczeństwa
        ↓
Zatwierdzone działania

Eksperymentalny QML (opcjonalnie)
  └─ porównywany z baseline'em klasycznym; nie jest krytyczną ścieżką API
```

Każda obserwacja w przyszłych wersjach powinna zawierać źródło, znacznik czasu, metodę, wersję modelu i miarę niepewności, jeśli dana metoda ją udostępnia. Wynik estymacji nie powinien być przedstawiany jako pewny fakt.
