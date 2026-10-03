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
MISSING_PAGE = ROOT / "eksik-veriler.html"


def load_rows():
    rows = []
    for path in sorted(glob.glob(str(DATA / "chunk-*.csv"))):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f))
    return rows


def embedded_missing_records(html: str):
    pattern = re.compile(
        r'\{\\"kurum_kodu\\":\\"(?P<code>\d+)\\",'
        r'\\"okul_adi\\":\\"(?P<school>.*?)\\",'
        r'\\"il\\":\\"(?P<province>.*?)\\",'
        r'\\"ilce\\":\\"(?P<district>.*?)\\",'
        r'\\"kademe\\":\\"(?P<level>.*?)\\",'
        r'\\"okul_turu\\":\\"(?P<school_type>.*?)\\",'
        r'\\"neden\\":\\"(?P<reason>.*?)\\"'
    )
    out = []
    seen = set()
    for m in pattern.finditer(html):
        d = m.groupdict()
        if d["code"] in seen:
            continue
        seen.add(d["code"])
        out.append(d)
    return out


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {"meta": {}, "schools": {}}
    schools = payload.setdefault("schools", {})
    missing_records = embedded_missing_records(MISSING_PAGE.read_text(encoding="utf-8"))
    if not missing_records:
        raise RuntimeError("Could not parse embedded missing-data records")
    now = datetime.now(timezone.utc).isoformat()

    manual_preschool_codes = set()
    exact_counts_applied = 0
    manual_codes_not_in_missing_page = []
    missing_codes = {r["code"] for r in missing_records}

    for item in manual:
        code = str(item.get("kurum_kodu") or "").strip()
        value = int(item["ogrenci_sayisi"])
        if not code or value <= 0:
            raise RuntimeError(f"Invalid manual record: {item}")
        if code not in missing_codes:
            manual_codes_not_in_missing_page.append(code)
        if (item.get("kademe") or "").strip() == "Anaokulu":
            manual_preschool_codes.add(code)

        row = by_code.get(code, {})
        embedded = next((r for r in missing_records if r["code"] == code), {})
        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        previous_value = previous.get("value")
        canonical = max(value, int(previous_value)) if isinstance(previous_value, (int, float)) and previous_value > 0 else value
        observed = {int(v) for v in (previous.get("observed_values") or []) if isinstance(v, (int, float))}
        observed.add(value)
        schools[code] = {
            **previous,
            "value": canonical,
            "verified": True,
            "school": row.get("okul_adi") or embedded.get("school") or previous.get("school") or "",
            "province": row.get("il") or embedded.get("province") or previous.get("province") or "",
            "district": row.get("ilce") or embedded.get("district") or previous.get("district") or "",
            "school_type": row.get("okul_turu") or embedded.get("school_type") or previous.get("school_type") or item.get("kademe") or "",
            "observed_values": sorted(observed),
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "student_count_status": "exact_manual_review",
            "student_count_label": str(canonical),
            "updated_at": now,
            "note": "Kullanıcı tarafından okul sayfası tek tek kontrol edilerek doğrulanan öğrenci sayısı.",
        }
        exact_counts_applied += 1

    preschool_targets = {r["code"]: r for r in missing_records if r["level"] == "Anaokulu" or r["school_type"] == "Anaokulu"}
    if not manual_preschool_codes.issubset(set(preschool_targets)):
        bad = sorted(manual_preschool_codes - set(preschool_targets))
        raise RuntimeError(f"Manual preschool codes missing from source target pool: {bad}")

    remainder = sorted(set(preschool_targets) - manual_preschool_codes)
    labeled_under_100 = 0
    skipped_existing_exact = 0
    for code in remainder:
        rec = preschool_targets[code]
        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        if isinstance(previous.get("value"), (int, float)) and previous.get("value", 0) > 0:
            skipped_existing_exact += 1
            continue
        schools[code] = {
            **previous,
            "verified": True,
            "school": rec["school"],
            "province": rec["province"],
            "district": rec["district"],
            "school_type": rec["school_type"] or "Anaokulu",
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "student_count_status": "under_100_manual_review",
            "student_count_label": "100 öğrenci altında",
            "value_upper_bound": 99,
            "norm_eligible_by_student_count": False,
            "updated_at": now,
            "note": "Kullanıcı anaokulu hedef listesini tek tek kontrol etti; kesin öğrenci sayısı bulunamadı ve okulun 100 öğrencinin altında olduğu belirtildi. Kesin sayı uydurulmadı.",
        }
        labeled_under_100 += 1

    payload["meta"] = {
        **(payload.get("meta") or {}),
        "manual_update_at": now,
        "manual_update_source": "manual-student-counts-2026-10-03.json",
        "manual_preschool_rule": "Exact manual values are used where supplied; remaining reviewed preschool targets are labeled under 100 without an invented exact count. Existing positive verified values are preserved.",
    }
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "updated_at": now,
        "embedded_missing_records_total": len(missing_records),
        "embedded_preschool_targets": len(preschool_targets),
        "manual_records_total": len(manual),
        "manual_preschool_exact": len(manual_preschool_codes),
        "manual_other_exact": len(manual) - len(manual_preschool_codes),
        "exact_counts_applied": exact_counts_applied,
        "preschool_remainder_after_manual_exact": len(remainder),
        "preschool_labeled_under_100": labeled_under_100,
        "preschool_remainder_preserved_existing_exact": skipped_existing_exact,
        "manual_codes_not_in_missing_page": manual_codes_not_in_missing_page,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
