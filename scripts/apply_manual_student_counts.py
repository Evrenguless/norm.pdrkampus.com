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
MISSING_PAGE = ROOT / "eksik-veriler.html"


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
    return rows


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {"meta": {}, "schools": {}}
    schools = payload.setdefault("schools", {})
    missing_html = MISSING_PAGE.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()

    manual_codes = set()
    preschool_manual_codes = set()
    manual_preschool_status = Counter()
    codes_absent_from_chunks = []
    html_matches = 0

    for item in manual:
        code = str(item.get("kurum_kodu") or "").strip()
        value = int(item["ogrenci_sayisi"])
        if not code or value <= 0:
            raise RuntimeError(f"Invalid manual record: {item}")
        row = by_code.get(code, {})
        if not row:
            codes_absent_from_chunks.append(code)
        if code in missing_html:
            html_matches += 1
        manual_codes.add(code)
        if (item.get("kademe") or "").strip() == "Anaokulu":
            preschool_manual_codes.add(code)
            manual_preschool_status[(row.get("durum") or "ARCHIVED_NOT_IN_CHUNKS").strip()] += 1

        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        previous_value = previous.get("value")
        canonical = max(value, int(previous_value)) if isinstance(previous_value, (int, float)) and previous_value > 0 else value
        observed = {int(v) for v in (previous.get("observed_values") or []) if isinstance(v, (int, float))}
        observed.add(value)
        schools[code] = {
            **previous,
            "value": canonical,
            "verified": True,
            "school": row.get("okul_adi") or previous.get("school") or "",
            "province": row.get("il") or previous.get("province") or "",
            "district": row.get("ilce") or previous.get("district") or "",
            "school_type": row.get("okul_turu") or previous.get("school_type") or item.get("kademe") or "",
            "observed_values": sorted(observed),
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "updated_at": now,
            "note": "Kullanıcı tarafından okul sayfası tek tek kontrol edilerek doğrulanan öğrenci sayısı.",
        }

    preschools = [r for r in rows if (r.get("okul_turu") or "").strip() == "Anaokulu"]
    status_counts = Counter((r.get("durum") or "").strip() or "(bos)" for r in preschools)
    candidate_no_positive = {str(r.get("kurum_kodu") or "").strip() for r in preschools if raw_positive_count(r) is None}
    candidate_not_found = {str(r.get("kurum_kodu") or "").strip() for r in preschools if (r.get("durum") or "").strip() == "bulunamadi"}
    candidate_not_clean_found = {str(r.get("kurum_kodu") or "").strip() for r in preschools if (r.get("durum") or "").strip() != "bulundu"}

    sample_code = codes_absent_from_chunks[0] if codes_absent_from_chunks else next(iter(preschool_manual_codes), "")
    pos = missing_html.find(sample_code) if sample_code else -1
    html_sample = missing_html[max(0, pos-500):pos+700] if pos >= 0 else ""

    payload["meta"] = {**(payload.get("meta") or {}), "manual_update_at": now, "manual_update_source": "manual-student-counts-2026-10-03.json"}
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "updated_at": now,
        "manual_records_total": len(manual),
        "manual_preschool_records": len(preschool_manual_codes),
        "manual_other_records": len(manual)-len(preschool_manual_codes),
        "exact_counts_applied": len(manual),
        "manual_codes_found_in_missing_page_html": html_matches,
        "manual_codes_absent_from_current_chunks": codes_absent_from_chunks,
        "preschool_total_current_chunks": len(preschools),
        "preschool_status_counts": dict(status_counts),
        "manual_preschool_status_counts": dict(manual_preschool_status),
        "candidate_counts": {"no_positive_raw_count": len(candidate_no_positive), "durum_bulunamadi": len(candidate_not_found), "durum_not_bulundu": len(candidate_not_clean_found)},
        "manual_overlap": {"no_positive_raw_count": len(preschool_manual_codes & candidate_no_positive), "durum_bulunamadi": len(preschool_manual_codes & candidate_not_found), "durum_not_bulundu": len(preschool_manual_codes & candidate_not_clean_found)},
        "missing_page_sample_around_first_absent_code": html_sample,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
