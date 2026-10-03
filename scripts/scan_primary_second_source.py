from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path("data")
OVERRIDES = DATA_DIR / "student-overrides.json"
MEB_SUMMARY = DATA_DIR / "student-scan-summary.json"
SUMMARY = DATA_DIR / "primary-second-source-summary.json"
BASE = "https://ilkokullar.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/4.1; +https://norm.pdrkampus.com)"}
TIMEOUT = 10


def ascii_slug(s: str) -> str:
    s = (s or "").strip().lower().replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def norm(s: str) -> str:
    s = (s or "").strip().lower().replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_rows():
    rows = []
    for p in sorted(DATA_DIR.glob("chunk-*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_overrides():
    return load_json(OVERRIDES, {"schools": {}})


def parse_num(v):
    if v is None:
        return None
    m = re.findall(r"\d+", str(v).replace(".", ""))
    if not m:
        return None
    vals = [int(x) for x in m]
    return max(vals) if vals else None


def fetch_candidate(row):
    province = ascii_slug(row.get("il") or "")
    district = ascii_slug(row.get("ilce") or "")
    school = ascii_slug(row.get("okul_adi") or "")
    if not (province and district and school):
        return None, "bad_slug"
    url = f"{BASE}/{province}/{district}/{school}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except Exception:
        return None, "request_failed"
    if r.status_code != 200:
        return None, f"http_{r.status_code}"
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    nt = norm(text)
    if norm(row.get("okul_adi") or "") not in nt:
        return None, "school_mismatch"
    if norm(row.get("il") or "") not in nt or norm(row.get("ilce") or "") not in nt:
        return None, "location_mismatch"
    vals = [int(x) for x in re.findall(r"Öğrenci\s+Sayısı\s*:\s*(\d{1,5})", text, re.I)]
    vals += [int(x) for x in re.findall(r"(\d{1,5})\s+öğrenci\s+ile\s+eğitim", text, re.I)]
    vals = [x for x in vals if 0 < x <= 10000]
    if not vals:
        return None, "count_not_found"
    return {"count": max(vals), "url": url}, "ok"


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    payload = load_overrides()
    schools = payload.setdefault("schools", {})
    meb_summary = load_json(MEB_SUMMARY, {})
    unresolved = meb_summary.get("unresolved") or {}

    targets = []
    for code, info in unresolved.items():
        row = by_code.get(str(code).strip())
        if not row:
            continue
        if (row.get("okul_turu") or "").strip() != "İlkokul":
            continue
        targets.append(row)

    found = {}
    reasons = {}
    for i, row in enumerate(targets, 1):
        item, reason = fetch_candidate(row)
        reasons[reason] = reasons.get(reason, 0) + 1
        if item:
            code = str(row.get("kurum_kodu") or "").strip()
            old = schools.get(code) or {}
            observed = []
            for v in old.get("observed_values") or []:
                n = parse_num(v)
                if n:
                    observed.append(n)
            for k in ("value", "student_count"):
                n = parse_num(old.get(k))
                if n:
                    observed.append(n)
            observed.append(item["count"])
            value = max(observed)
            schools[code] = {
                **old,
                "value": value,
                "verified": True,
                "observed_values": sorted(set(observed)),
                "source": "ilkokullar.com",
                "source_url": item["url"],
                "note": f"ilkokullar.com üzerinde il/ilçe/okul adı eşleşmesiyle {item['count']} öğrenci görüldü; mevcut doğrulanmış değerlerle karşılaştırılıp en yüksek {value} kullanıldı."
            }
            found[code] = {"school": row.get("okul_adi"), "province": row.get("il"), "district": row.get("ilce"), "value": value, "source_url": item["url"]}
        if i % 100 == 0:
            print("scanned", i, "/", len(targets), "found", len(found), flush=True)

    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "targets": len(targets),
        "recovered": len(found),
        "remaining": len(targets) - len(found),
        "reasons": reasons,
        "schools": found,
    }
    SUMMARY.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("targets", "recovered", "remaining")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
