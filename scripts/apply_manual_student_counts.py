from __future__ import annotations

import csv
import glob
import json
import re
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
    paths = sorted(glob.glob(str(DATA / "chunk-*.csv")))
    if not paths:
        raise RuntimeError("No chunk CSV files found")
    for i, path in enumerate(paths):
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows.extend(reader)
    return rows


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {"meta": {}, "schools": {}}
    schools = payload.setdefault("schools", {})

    preschool_unresolved = {
        code: row for code, row in by_code.items()
        if (row.get("okul_turu") or "").strip() == "Anaokulu" and raw_positive_count(row) is None
    }
    if len(preschool_unresolved) != 410:
        raise RuntimeError(f"Expected 410 raw unresolved preschool records, found {len(preschool_unresolved)}")

    manual_codes = set()
    preschool_manual_codes = set()
    applied_counts = 0
    now = datetime.now(timezone.utc).isoformat()

    for item in manual:
        code = str(item.get("kurum_kodu") or "").strip()
        if not code or code not in by_code:
            raise RuntimeError(f"Manual record not found in dataset: {code}")
        value = int(item["ogrenci_sayisi"])
        if value <= 0:
            raise RuntimeError(f"Invalid manual count for {code}: {value}")
        manual_codes.add(code)
        if (item.get("kademe") or "").strip() == "Anaokulu":
            preschool_manual_codes.add(code)

        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        previous_value = previous.get("value")
        canonical = max(value, int(previous_value)) if isinstance(previous_value, (int, float)) else value
        observed = set(previous.get("observed_values") or [])
        observed.add(value)
        sources = list(previous.get("sources") or [])
        src_url = item.get("kaynak_url") or ""
        manual_source = {"url": src_url, "values": [value], "evidence": ["Kullanıcı tarafından okul sayfası tek tek kontrol edilerek girildi."]}
        if manual_source not in sources:
            sources.append(manual_source)

        row = by_code[code]
        schools[code] = {
            **previous,
            "value": canonical,
            "verified": True,
            "school": row.get("okul_adi") or item.get("okul_adi") or "",
            "province": row.get("il") or "",
            "district": row.get("ilce") or "",
            "school_type": row.get("okul_turu") or "",
            "observed_values": sorted(int(v) for v in observed if isinstance(v, (int, float))),
            "sources": sources,
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "updated_at": now,
            "note": "Manuel okul sayfası kontrolüyle doğrulanan öğrenci sayısı işlendi; çelişkide en yüksek doğrulanabilir değer kullanıldı.",
        }
        applied_counts += 1

    unmatched_preschool_manual = sorted(preschool_manual_codes - set(preschool_unresolved))
    remaining_under_100 = 0
    skipped_existing_value = 0

    for code, row in preschool_unresolved.items():
        if code in preschool_manual_codes:
            continue
        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        if isinstance(previous.get("value"), (int, float)) and previous.get("value", 0) > 0:
            skipped_existing_value += 1
            continue
        schools[code] = {
            **previous,
            "verified": True,
            "school": row.get("okul_adi") or "",
            "province": row.get("il") or "",
            "district": row.get("ilce") or "",
            "school_type": row.get("okul_turu") or "Anaokulu",
            "student_count_status": "under_100_manual_review",
            "student_count_label": "100 öğrenci altında",
            "value_upper_bound": 99,
            "norm_eligible_by_student_count": False,
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "updated_at": now,
            "note": "Kullanıcı tarafından tek tek kontrol edildi; kesin öğrenci sayısı bulunamadı, 100 öğrencinin altında olduğu belirtildi. Sayısal öğrenci değeri uydurulmadı.",
        }
        remaining_under_100 += 1

    payload["meta"] = {
        **(payload.get("meta") or {}),
        "manual_update_at": now,
        "manual_update_source": "manual-student-counts-2026-10-03.json",
        "manual_rule": "Manual counts are stored as verified observations; unresolved preschool records are labeled under 100 without fabricating an exact count.",
    }
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "updated_at": now,
        "manual_records_total": len(manual),
        "manual_preschool_records": len(preschool_manual_codes),
        "manual_other_records": len(manual) - len(preschool_manual_codes),
        "raw_unresolved_preschool_pool": len(preschool_unresolved),
        "manual_preschool_in_unresolved_pool": len(preschool_manual_codes & set(preschool_unresolved)),
        "manual_preschool_outside_unresolved_pool": unmatched_preschool_manual,
        "exact_counts_applied": applied_counts,
        "preschool_labeled_under_100": remaining_under_100,
        "preschool_skipped_due_existing_verified_value": skipped_existing_value,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
