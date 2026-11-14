import csv
import glob
import json
from collections import Counter
from pathlib import Path

FIELDS = [
    "code","il","ilce","okul","okul_turu","eski_ogrenci","aday_ogrenci",
    "ogrenci_farki","ogrenci_farki_yuzde","eski_norm","aday_norm",
    "ogrenci_durumu","ogrenci_kaynaklari","ogrenci_kanit",
    "eski_rehber_sayisi","aday_rehber_sayisi","rehber_farki","rehber_durumu",
    "rehber_kaynak","rehber_liste_durumu","manual_reviewed_at",
    "generated_for_personal_use","checked_at","tarama_hatalari",
]

def cell(row, key):
    value = row.get(key)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else value

def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: cell(row, k) for k in FIELDS})

def main():
    paths = sorted(glob.glob("shards/**/school-review-*.json", recursive=True))
    if len(paths) != 32:
        raise SystemExit(f"Expected 32 shard reports, found {len(paths)}")
    rows = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rows.extend(data)
    rows.sort(key=lambda r: (str(r.get("il","")), str(r.get("ilce","")), str(r.get("okul","")), str(r.get("code",""))))
    changed_statuses = {"update_candidate","new_candidate","manual_record_conflict","conflicting_page_counts"}
    changed = [r for r in rows if r.get("ogrenci_durumu") in changed_statuses or r.get("rehber_durumu") in {"update_candidate","new_candidate"}]
    write_csv("report/school-data-review.csv", rows)
    write_csv("report/school-data-review-changes.csv", changed)
    summary = {
        "schools_in_report": len(rows),
        "student_statuses": dict(Counter(r.get("ogrenci_durumu","") for r in rows)),
        "staff_statuses": dict(Counter(r.get("rehber_durumu","") for r in rows)),
        "student_candidates_any_difference": sum(r.get("ogrenci_durumu") in {"update_candidate","new_candidate"} for r in rows),
        "student_manual_conflicts": sum(r.get("ogrenci_durumu") == "manual_record_conflict" for r in rows),
        "student_source_conflicts": sum(r.get("ogrenci_durumu") == "conflicting_page_counts" for r in rows),
        "staff_candidates_any_difference": sum(r.get("rehber_durumu") in {"update_candidate","new_candidate"} for r in rows),
        "schools_with_any_change_or_review": len(changed),
        "policy": "No difference threshold: every distinct, explicit candidate count is reported. Missing/blocked/error sources preserve the old value. Multiple page values and manually reviewed conflicts require review. No source dataset was modified by the scan.",
    }
    Path("report/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
