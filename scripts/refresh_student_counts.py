from __future__ import annotations

import csv
import glob
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT = DATA_DIR / "student-overrides.json"
MAX_WORKERS = 10
TIMEOUT = 12

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/1.0; +https://norm.pdrkampus.com)"
}

COUNT_PATTERNS = [
    re.compile(r"Öğrenci\s*Say(?:ı|i)s(?:ı|i)\s*[:\-]?\s*(\d{1,5})", re.I),
    re.compile(r"Öğrenci\s*Sayımız\s*[:\-]?\s*(\d{1,5})", re.I),
    re.compile(r"Toplam\s*Öğrenci(?:\s*Say(?:ı|i)s(?:ı|i))?\s*[:\-]?\s*(\d{1,5})", re.I),
]

def extract_numbers(value):
    if value is None:
        return []
    vals = []
    for m in re.findall(r"\d+(?:[.,]\d+)?", str(value)):
        try:
            n = int(float(m.replace(",", ".")))
        except ValueError:
            continue
        if 0 <= n <= 10000:
            vals.append(n)
    return vals

def current_count(row):
    vals = extract_numbers(row.get("ogrenci_sayisi")) + extract_numbers(row.get("ogrenci_sayilari"))
    return max(vals) if vals else None

def candidate_urls(row):
    bases = []
    for k in ("web_sitesi", "kaynak_url"):
        v = (row.get(k) or "").strip()
        if v.startswith("http") and v not in bases:
            bases.append(v.rstrip("/") + "/")
    urls = []
    for base in bases:
        for rel in ("", "tema/", "tema/okulumuz_hakkinda.php"):
            u = urljoin(base, rel)
            if u not in urls:
                urls.append(u)
    return urls

def parse_student_counts(html):
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    found = set()
    for source in (text, html):
        for pat in COUNT_PATTERNS:
            for m in pat.finditer(source):
                try:
                    n = int(m.group(1))
                except ValueError:
                    continue
                if 0 <= n <= 10000:
                    found.add(n)
    return sorted(found)

def fetch_url(session, url):
    for attempt in range(2):
        try:
            r = session.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
            if r.status_code == 200 and r.text:
                return parse_student_counts(r.text), r.url
        except requests.RequestException:
            pass
        if attempt == 0:
            time.sleep(0.5)
    return [], url

def scan(row):
    code = str(row.get("kurum_kodu") or "").strip()
    school = row.get("okul_adi") or ""
    existing = current_count(row)
    observed = set()
    sources = []
    with requests.Session() as session:
        for url in candidate_urls(row):
            vals, final_url = fetch_url(session, url)
            if vals:
                observed.update(vals)
                sources.append({"url": final_url, "values": vals})
    if not observed:
        return code, None

    # User rule: conflicting values -> always use the highest verifiable value.
    value = max(([existing] if existing is not None else []) + list(observed))
    if value <= 0:
        return code, None

    return code, {
        "value": value,
        "verified": True,
        "school": school,
        "province": row.get("il") or "",
        "district": row.get("ilce") or "",
        "observed_values": sorted(observed),
        "sources": sources,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "MEB okul sayfalarında ve mevcut veri alanlarında bulunan değerler arasından en yüksek öğrenci sayısı kullanıldı."
    }

def load_rows():
    paths = sorted(glob.glob(str(DATA_DIR / "chunk-*.csv")))
    if not paths:
        return []

    rows = []
    with open(paths[0], newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows.extend(reader)

    # chunk-002..056 continue the original CSV and intentionally have no header.
    for path in paths[1:]:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f, fieldnames=fieldnames))
    return rows

def load_existing():
    if not OUT.exists():
        return {"meta": {}, "schools": {}}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"meta": {}, "schools": {}}

def main():
    rows = load_rows()
    # Re-scan every school whose primary scraped student field is zero, plus
    # records that still have no usable count. This intentionally includes rows
    # where another CSV field already contains a non-zero number: the MEB page
    # may expose an even higher/current value, and the project rule is to keep
    # the highest verifiable value.
    def needs_rescan(r):
        primary = extract_numbers(r.get("ogrenci_sayisi"))
        primary_zero = bool(primary) and max(primary) == 0
        return (primary_zero or current_count(r) in (None, 0)) and bool(candidate_urls(r))

    targets = [r for r in rows if needs_rescan(r)]

    payload = load_existing()
    schools = payload.setdefault("schools", {})
    verified_before = len(schools)

    print(f"Loaded {len(rows)} schools; scanning {len(targets)} zero/missing records")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(scan, r) for r in targets]
        for i, fut in enumerate(as_completed(futures), 1):
            code, result = fut.result()
            if result:
                prev = schools.get(code)
                # Never lower a previously verified value.
                if prev and isinstance(prev.get("value"), (int, float)):
                    result["value"] = max(int(prev["value"]), int(result["value"]))
                schools[code] = result
            if i % 50 == 0:
                print(f"Scanned {i}/{len(targets)}")

    payload["meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "MEB school websites",
        "rule": "When conflicting counts exist, the highest verifiable count is used.",
        "targets_scanned": len(targets),
        "verified_records": len(schools),
        "new_or_retained_records": len(schools) - verified_before,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(schools)} verified overrides to {OUT}")

if __name__ == "__main__":
    main()
