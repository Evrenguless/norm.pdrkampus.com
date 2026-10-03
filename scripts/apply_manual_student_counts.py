from __future__ import annotations

import csv
import glob
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANUAL = DATA / "manual-student-counts-2026-10-03.json"
OVERRIDES = DATA / "student-overrides.json"
SUMMARY = DATA / "manual-student-counts-summary.json"


def numbers(value):
    if value is None:
        return []
    out = []
    for m in re.findall(r"\d+(?:[.,]\d+)?", str(value)):
        try:
            n = int(float(m.replace(",", ".")))
        except ValueError:
            continue
        if 0 <= n <= 10000:
            out.append(n)
    return out


def raw_positive_count(row):
    vals = numbers(row.get("ogrenci_sayisi")) + numbers(row.get("ogrenci_sayilari"))
    vals = [v for v in vals if v > 0]
    return max(vals) if vals else None


def load_rows():
    rows = []
    for path in sorted(glob.glob(str(DATA / "chunk-*.csv"))):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f))
    if not rows:
        raise RuntimeError("No chunk CSV files found")
    return rows


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {"meta": {}, "schools": {}}
    schools = payload.setdefault("schools", {})
    now = datetime.now(timezone.utc).isoformat()

    manual_codes = set()
    preschool_manual_codes = set()
    manual_preschool_status = Counter()
    exact_counts_applied = 0

    for item in manual:
        code = str(item.get("kurum_kodu") or "").strip()
        row = by_code.get(code)
        if not row:
            raise RuntimeError(f"Manual record not found in dataset: {code}")
        value = int(item["ogrenci_sayisi"])
        if value <= 0:
            raise RuntimeError(f"Invalid manual count for {code}: {value}")
        manual_codes.add(code)
        if (item.get("kademe") or "").strip() == "Anaokulu":
            preschool_manual_codes.add(code)
            manual_preschool_status[(row.get("durum") or "").strip() or "(bos)"] += 1

        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        previous_value = previous.get("value")
        canonical = max(value, int(previous_value)) if isinstance(previous_value, (int, float)) and previous_value > 0 else value
        observed = {int(v) for v in (previous.get("observed_values") or []) if isinstance(v, (int, float))}
        observed.add(value)
        sources = list(previous.get("sources") or [])
        manual_source = {
            "url": item.get("kaynak_url") or "",
            "values": [value],
            "evidence": ["Kullanıcı tarafından okul sayfası tek tek kontrol edilerek girildi."],
        }
        if manual_source not in sources:
            sources.append(manual_source)

        schools[code] = {
            **previous,
            "value": canonical,
            "verified": True,
            "school": row.get("okul_adi") or "",
            "province": row.get("il") or "",
            "district": row.get("ilce") or "",
            "school_type": row.get("okul_turu") or "",
            "observed_values": sorted(observed),
            "sources": sources,
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "updated_at": now,
            "note": "Manuel okul sayfası kontrolüyle doğrulanan öğrenci sayısı işlendi; çelişkide en yüksek doğrulanabilir değer kullanıldı.",
        }
        exact_counts_applied += 1

    preschools = [r for r in rows if (r.get("okul_turu") or "").strip() == "Anaokulu"]
    status_counts = Counter((r.get("durum") or "").strip() or "(bos)" for r in preschools)
    candidate_no_positive = {str(r.get("kurum_kodu") or "").strip() for r in preschools if raw_positive_count(r) is None}
    candidate_not_found = {str(r.get("kurum_kodu") or "").strip() for r in preschools if (r.get("durum") or "").strip() == "bulunamadi"}
    candidate_zero_exact = {str(r.get("kurum_kodu") or "").strip() for r in preschools if 0 in numbers(r.get("ogrenci_sayisi")) and raw_positive_count(r) is None}
    candidate_not_clean_found = {str(r.get("kurum_kodu") or "").strip() for r in preschools if (r.get("durum") or "").strip() != "bulundu"}

    payload["meta"] = {
        **(payload.get("meta") or {}),
        "manual_update_at": now,
        "manual_update_source": "manual-student-counts-2026-10-03.json",
    }
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "updated_at": now,
        "manual_records_total": len(manual),
        "manual_preschool_records": len(preschool_manual_codes),
        "manual_other_records": len(manual) - len(preschool_manual_codes),
        "exact_counts_applied": exact_counts_applied,
        "preschool_total": len(preschools),
        "preschool_status_counts": dict(status_counts),
        "manual_preschool_status_counts": dict(manual_preschool_status),
        "candidate_counts": {
            "no_positive_raw_count": len(candidate_no_positive),
            "durum_bulunamadi": len(candidate_not_found),
            "zero_with_no_positive": len(candidate_zero_exact),
            "durum_not_bulundu": len(candidate_not_clean_found),
        },
        "manual_overlap": {
            "no_positive_raw_count": len(preschool_manual_codes & candidate_no_positive),
            "durum_bulunamadi": len(preschool_manual_codes & candidate_not_found),
            "zero_with_no_positive": len(preschool_manual_codes & candidate_zero_exact),
            "durum_not_bulundu": len(preschool_manual_codes & candidate_not_clean_found),
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
