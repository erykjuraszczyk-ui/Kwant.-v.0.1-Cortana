#!/usr/bin/env python3
"""Benchmark API PKK na lokalnym zestawie obrazów; nie oblicza mAP bez etykiet wzorcowych."""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import httpx

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", type=Path, help="Ścieżka do obrazu albo folderu z obrazami")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Adres lokalnego API")
    parser.add_argument("--confidence", type=float, default=0.25, help="Próg confidence 0–1")
    parser.add_argument("--output", type=Path, default=Path("pkk-benchmark.csv"), help="Plik wynikowy CSV")
    parser.add_argument("--timeout", type=float, default=120.0, help="Timeout żądania w sekundach")
    args = parser.parse_args()

    if not 0.0 <= args.confidence <= 1.0:
        parser.error("--confidence musi być z przedziału 0–1")
    if not args.images.exists():
        parser.error(f"Nie znaleziono ścieżki: {args.images}")
    if args.images.is_file():
        files = [args.images] if args.images.suffix.lower() in SUPPORTED else []
    else:
        files = sorted(path for path in args.images.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED)
    if not files:
        parser.error("Nie znaleziono plików JPEG, PNG ani WEBP.")

    rows: list[dict[str, object]] = []
    wall_times: list[float] = []
    server_times: list[float] = []
    successes = 0
    with httpx.Client(timeout=args.timeout) as client:
        for index, path in enumerate(files, start=1):
            started = time.perf_counter()
            try:
                with path.open("rb") as image_file:
                    response = client.post(
                        f"{args.url.rstrip('/')}/perception/objects",
                        params={"confidence": args.confidence},
                        files={"file": (path.name, image_file, "application/octet-stream")},
                    )
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                if not response.is_success:
                    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error = str(payload.get("error") or payload.get("detail") or f"HTTP {response.status_code}")
                    rows.append({"file": path.name, "status": "error", "wall_ms": elapsed_ms, "processing_ms": "", "count": "", "labels": "", "error": error})
                    print(f"[{index}/{len(files)}] {path.name}: ERROR — {error}")
                    continue
                data = response.json()
                labels = [item.get("label", "?") for item in data.get("detections", [])]
                proc = float(data.get("processing_ms", 0.0))
                wall_times.append(elapsed_ms)
                server_times.append(proc)
                successes += 1
                rows.append({"file": path.name, "status": "ok", "wall_ms": elapsed_ms, "processing_ms": proc, "count": data.get("count", 0), "labels": ";".join(labels), "error": ""})
                print(f"[{index}/{len(files)}] {path.name}: {data.get('count', 0)} obiektów, API {proc:.1f} ms, całość {elapsed_ms:.1f} ms")
            except (OSError, httpx.HTTPError, ValueError) as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                rows.append({"file": path.name, "status": "error", "wall_ms": elapsed_ms, "processing_ms": "", "count": "", "labels": "", "error": str(exc)})
                print(f"[{index}/{len(files)}] {path.name}: ERROR — {exc}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["file", "status", "wall_ms", "processing_ms", "count", "labels", "error"])
        writer.writeheader()
        writer.writerows(rows)

    print("\n--- PODSUMOWANIE PKK ---")
    print(f"Plików: {len(files)} | udane: {successes} | błędy: {len(files) - successes}")
    if wall_times:
        print(f"Czas całego żądania: mediana {statistics.median(wall_times):.1f} ms | p95 {percentile(wall_times, .95):.1f} ms")
        print(f"Czas detektora z API: mediana {statistics.median(server_times):.1f} ms | p95 {percentile(server_times, .95):.1f} ms")
    print(f"CSV: {args.output.resolve()}")
    print("Uwaga: pomiar czasu/liczby detekcji nie mierzy trafności. Do precision/recall/mAP potrzebne są oznaczenia wzorcowe.")
    return 0 if successes == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
