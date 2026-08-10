#!/usr/bin/env python3
"""Genera crea_foods.js dalle Tabelle di Composizione degli Alimenti CREA.

Uso: GitHub Actions durante la pubblicazione della PWA.
La PWA attribuisce chiaramente i dati a CREA Centro di ricerca Alimenti e Nutrizione.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.alimentinutrizione.it"
INDEX = BASE + "/tabelle-nutrizionali/ricerca-per-ordine-alfabetico"
OUT = Path(__file__).resolve().parent / "crea_foods.js"
UA = "DiarioAlimentare-Luca-Daniela/1.0 (GitHub Pages build; CREA source attribution included)"

session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
})


def get(url: str, attempts: int = 4) -> str:
    last = None
    for n in range(attempts):
        try:
            r = session.get(url, timeout=35)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            last = exc
            time.sleep(1.5 + n * 2)
    raise RuntimeError(f"Impossibile scaricare {url}: {last}")


def number(text: str):
    cleaned = (text or "").replace("\xa0", " ").strip()
    # valori non disponibili / tracce testuali restano None
    m = re.search(r"-?\d+(?:[.,]\d+)?", cleaned)
    return float(m.group(0).replace(",", ".")) if m else None


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def parse_food(url: str, code: str, fallback_name: str):
    soup = BeautifulSoup(get(url), "html.parser")
    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    name = h1s[-1] if h1s else fallback_name
    if name.lower().startswith("tabelle di composizione"):
        name = fallback_name

    vals = {"kcal100": None, "protein100": None, "fat100": None, "carb100": None}

    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        if len(cells) < 3:
            continue
        label = norm(cells[0])
        key = None
        if label.startswith("energia") and "kcal" in label:
            key = "kcal100"
        elif label.startswith("proteine"):
            key = "protein100"
        elif label.startswith("lipidi"):
            key = "fat100"
        elif label.startswith("carboidrati disponibili"):
            key = "carb100"
        if key:
            val = number(cells[2])
            if val is not None:
                vals[key] = val

    # Per il diario servono tutti e quattro i macronutrienti.
    if not all(vals[k] is not None for k in vals):
        return None

    return {
        "id": code,
        "code": code,
        "name": name,
        "url": url,
        "source": "CREA",
        **vals,
    }


def main():
    soup = BeautifulSoup(get(INDEX), "html.parser")
    foods = {}
    rx = re.compile(r"/tabelle-nutrizionali/(\d+)/?$")

    for a in soup.select("a[href]"):
        href = a.get("href", "").split("?", 1)[0].split("#", 1)[0]
        m = rx.search(href)
        name = a.get_text(" ", strip=True)
        if m and name:
            code = m.group(1)
            foods[code] = (name, urljoin(BASE, href))

    if len(foods) < 700:
        raise RuntimeError(f"Indice CREA inatteso: trovati solo {len(foods)} alimenti")

    result = []
    failed = []
    total = len(foods)
    ordered = sorted(foods.items(), key=lambda item: item[1][0].lower())

    for i, (code, (name, url)) in enumerate(ordered, 1):
        try:
            item = parse_food(url, code, name)
            if item:
                result.append(item)
            else:
                failed.append((code, name, "macronutrienti incompleti"))
        except Exception as exc:
            failed.append((code, name, str(exc)))

        if i % 50 == 0 or i == total:
            print(f"CREA: {i}/{total} pagine; valide {len(result)}; scartate {len(failed)}", flush=True)
        # Carico moderato sul sito: il build avviene solo durante la pubblicazione.
        time.sleep(0.12)

    if len(result) < 650:
        raise RuntimeError(f"Estrazione CREA insufficiente: {len(result)} alimenti validi su {total}")

    header = (
        "// Dati nutrizionali CREA incorporati staticamente nella PWA.\n"
        "// Fonte: CREA Centro di ricerca Alimenti e Nutrizione - https://www.alimentinutrizione.it\n"
        "// Tabelle di Composizione degli Alimenti, aggiornamento 2019.\n"
        "// Generato automaticamente durante la pubblicazione GitHub Pages.\n"
    )
    OUT.write_text(
        header + "window.CREA_FOODS = " + json.dumps(result, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Creato {OUT.name}: {len(result)} alimenti CREA", flush=True)

    if failed:
        print("Prime voci non importate:", file=sys.stderr)
        for row in failed[:20]:
            print(" -", row, file=sys.stderr)


if __name__ == "__main__":
    main()
