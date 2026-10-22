# PKK 0.3 — plan testów percepcji

## 1. Test funkcjonalny kamery

1. Uruchom API lokalnie i otwórz `http://127.0.0.1:8000/camera`.
2. Naciśnij **Start kamery** i jawnie przyznaj zgodę w przeglądarce.
3. Sprawdź, czy pojawia się obraz, ramki detekcji, etykiety, liczba detekcji i czas przetwarzania.
4. Wybierz wyższy próg confidence; sprawdź, czy liczba detekcji nie zwiększa się systematycznie (nie musi zmieniać się dla każdej klatki).
5. Zmień odstęp między analizami i obserwuj obciążenie CPU oraz responsywność.
6. Naciśnij **Zatrzymaj**. Obraz ma zniknąć, dioda statusu się wyłączyć, a aplikacja nie powinna zlecać nowych klatek.
7. Odmów dostępu do kamery i sprawdź czytelny komunikat błędu.

## 2. Pomiar czasu

Uruchom API, przygotuj folder `sample-images/` z obrazami, które masz prawo przetwarzać, a następnie uruchom:

```bash
python scripts/benchmark.py sample-images --output reports/pkk-benchmark.csv
```

Skrypt zapisuje nazwę pliku, liczbę etykiet, czas całego żądania i czas podany przez detektor. Pierwsze żądanie może obejmować pobranie/ładowanie wag, dlatego odrębnie raportuj pierwszy przebieg i kolejne rozgrzane przebiegi. Zapis CSV nie zawiera samych obrazów.

## 3. Ocena trafności

Benchmark czasu **nie** oblicza trafności modelu. Do precision, recall i mAP potrzebny jest zbiór ze wzorcowymi ramkami (`ground truth`) i zdefiniowanymi klasami. Dla małego ręcznego pilotażu oznacz co najmniej 50–100 klatek różniących się oświetleniem, odległością, wielkością obiektów i tłem; zapisuj fałszywe alarmy oraz obiekty pominięte. Nie nazywaj `confidence` skalibrowanym prawdopodobieństwem.

## 4. Kryteria akceptacji prototypu

- `GET /health` zwraca HTTP 200.
- Strona `/camera` nie otwiera kamery samoistnie; trzeba kliknąć przycisk i przyznać dostęp.
- W danym momencie przeglądarka ma najwyżej jedno żądanie analizy klatki w toku.
- Stop zwalnia ścieżki mediów przeglądarki i przerywa zlecanie kolejnych klatek.
- Nie ma archiwizacji klatek ani historii video w aplikacji.
- Testy jednostkowe nie wymagają sieci ani prawdziwych wag modelu.
- Wyników czasowych nie przedstawia się jako miary jakości klasyfikacji.

## 5. Ograniczenia i bezpieczeństwo

Kamera działa w przeglądarce klienta, a klatki JPEG są przesyłane do skonfigurowanego API. Przykład jest przeznaczony do lokalnego prototypu. Nie wystawiaj go bezpośrednio do internetu bez uwierzytelniania, HTTPS, limitów żądań i oceny prywatności. Uprawnienie kamery w przeglądarce wymaga bezpiecznego kontekstu (zwykle `localhost` lub HTTPS). W Dockerze kamera pozostaje po stronie przeglądarki — kontener nie potrzebuje dostępu do urządzenia kamery.
