from __future__ import annotations

import csv, glob, json, re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "preschool-missing-audit.json"


def num(v):
    s = str(v or "").strip()
    if not s:
        return None
    vals = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", s)]
    return max(vals) if vals else None


def trlower(v):
    return str(v or "").replace("I", "ı").replace("İ", "i").lower()


def is_preschool(row):
    t = (row.get("okul_turu") or "").strip()
    tl = trlower(t)
    return t == "Anaokulu" or "anaokulu" in tl or "ana okulu" in tl


def student_info(row, overrides):
    code = str(row.get("kurum_kodu") or "").strip()
    o = overrides.get(code) if isinstance(overrides.get(code), dict) else None
    if o and o.get("student_count_status") == "under_100_manual_review":
        return {"missing": False, "under100": True, "value": None, "override": o}
    vals = []
    for field in ("ogrenci_sayisi", "ogrenci_sayilari"):
        n = num(row.get(field))
        if n is not None:
            vals.append(n)
    if o:
        n = num(o.get("value"))
        if n is not None:
            vals.append(n)
        for v in o.get("observed_values") or []:
            n = num(v)
            if n is not None:
                vals.append(n)
    if not vals:
        return {"missing": True, "under100": False, "value": None, "override": o}
    value = max(vals)
    if value == 0 and not (o and o.get("verified")):
        return {"missing": True, "under100": False, "value": None, "override": o}
    return {"missing": False, "under100": False, "value": value, "override": o}


def main():
    payload = json.loads((DATA / "student-overrides.json").read_text(encoding="utf-8"))
    overrides = payload.get("schools", {})
    manual = json.loads((DATA / "manual-student-counts-2026-10-03.json").read_text(encoding="utf-8"))
    manual_codes = {str(x.get("kurum_kodu") or "").strip() for x in manual.get("records", [])}

    rows = []
    for path in sorted(glob.glob(str(DATA / "chunk-*.csv"))):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f))

    preschool = [r for r in rows if is_preschool(r)]
    missing = []
    for r in preschool:
        info = student_info(r, overrides)
        if not info["missing"]:
            continue
        code = str(r.get("kurum_kodu") or "").strip()
        o = info.get("override") or {}
        missing.append({
            "kurum_kodu": code,
            "okul_adi": r.get("okul_adi"),
            "il": r.get("il"),
            "ilce": r.get("ilce"),
            "okul_turu": r.get("okul_turu"),
            "ogrenci_sayisi": r.get("ogrenci_sayisi"),
            "ogrenci_sayilari": r.get("ogrenci_sayilari"),
            "in_manual_exact_file": code in manual_codes,
            "override_status": o.get("student_count_status"),
            "override_verified": o.get("verified"),
            "override_value": o.get("value"),
            "override_note": o.get("note"),
        })

    result = {
        "preschool_rows_total": len(preschool),
        "remaining_missing_total": len(missing),
        "missing_by_okul_turu": dict(Counter((x.get("okul_turu") or "") for x in missing)),
        "remaining_missing": missing,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
