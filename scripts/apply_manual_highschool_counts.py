from __future__ import annotations

import csv
import glob
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANUAL = DATA / "manual-student-counts-lise-2026-10-03.json"
OVERRIDES = DATA / "student-overrides.json"
SUMMARY = DATA / "manual-highschool-summary.json"
INDEX = ROOT / "index.html"
MISSING = ROOT / "eksik-veriler.html"


def load_rows():
    rows = []
    for path in sorted(glob.glob(str(DATA / "chunk-*.csv"))):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f))
    return rows


def embedded_missing_records(html: str):
    decoded = html.replace('\\"', '"')
    pattern = re.compile(
        r'\{"kurum_kodu":"(?P<code>\d+)",'
        r'"okul_adi":"(?P<school>.*?)",'
        r'"il":"(?P<province>.*?)",'
        r'"ilce":"(?P<district>.*?)",'
        r'"kademe":"(?P<level>.*?)",'
        r'"okul_turu":"(?P<school_type>.*?)",'
        r'"neden":"(?P<reason>.*?)"'
    )
    out = []
    seen = set()
    for m in pattern.finditer(decoded):
        d = m.groupdict()
        if d["code"] in seen:
            continue
        seen.add(d["code"])
        out.append(d)
    return out


def patch_missing_page(exact_codes: set[str]) -> tuple[int, int, int]:
    text = MISSING.read_text(encoding="utf-8")
    patterns = [
        r'\{\\"kurum_kodu\\":\\"(?P<code>\d+)\\".*?\}',
        r'\{\\\\\"kurum_kodu\\\\\":\\\\\"(?P<code>\d+)\\\\\".*?\}',
        r'\{"kurum_kodu":"(?P<code>\d+)".*?\}',
    ]
    matches = []
    for pattern in patterns:
        candidate = list(re.finditer(pattern, text, re.DOTALL))
        if candidate:
            matches = candidate
            break
    if not matches:
        raise RuntimeError("Could not match embedded missing record objects")

    old_total = len(matches)
    remove_codes = {m.group("code") for m in matches} & exact_codes
    if remove_codes:
        parts = []
        cursor = 0
        removed = 0
        for m in matches:
            if m.group("code") not in remove_codes:
                continue
            start, end = m.span()
            if end < len(text) and text[end] == ',':
                end += 1
            elif start > 0 and text[start - 1] == ',':
                start -= 1
            parts.append(text[cursor:start])
            cursor = end
            removed += 1
        parts.append(text[cursor:])
        text = ''.join(parts)
        new_total = old_total - removed
        old_tr = f"{old_total:,}".replace(",", ".")
        new_tr = f"{new_total:,}".replace(",", ".")
        text = text.replace(old_tr, new_tr)
        text = re.sub(rf'(?<!\d){old_total}(?!\d)', str(new_total), text)
        MISSING.write_text(text, encoding="utf-8")
        return old_total, removed, new_total
    return old_total, 0, old_total


def patch_index(missing_total: int):
    text = INDEX.read_text(encoding="utf-8")

    old = 'if(o?.student_count_status==="under_100_manual_review"){return {value:null,verified:true,under100:true,label:o.student_count_label||"100 öğrenci altında",note:o.note||"Manuel kontrolde 100 öğrenci altında.",source:"override"};}if(!vals.length){return {value:null,verified:false,under100:false,label:null,note:o?.note||"Öğrenci sayısı verisi eksik.",source:o?"override":"csv"};}'
    new = 'if(o?.student_count_status==="under_100_manual_review"){return {value:null,verified:true,under100:true,label:o.student_count_label||"100 öğrenci altında",note:o.note||"Manuel kontrolde 100 öğrenci altında.",source:"override"};}if(o?.student_count_status==="data_unavailable_moved_or_renamed"){return {value:null,verified:true,under100:false,movedOrRenamed:true,label:o.student_count_label||"Veri yok",note:o.note||"Okul taşınmış veya isim değiştirmiş olabilir.",source:"override"};}if(!vals.length){return {value:null,verified:false,under100:false,movedOrRenamed:false,label:null,note:o?.note||"Öğrenci sayısı verisi eksik.",source:o?"override":"csv"};}'
    if new not in text:
        if old not in text:
            raise RuntimeError("studentInfo patch anchor not found")
        text = text.replace(old, new, 1)

    old = 'const policy=institutionPolicy(r);if(policy==="outside")return {norm:null,status:"Analiz kapsamı dışı",reason:"Bu kayıt okul öğrenci-norm analizinin dışında tutulur. Bu sınıflandırma rehber öğretmen atanamayacağı anlamına gelmez."};if(policy==="ministerial")return {norm:null,status:"Bakanlıkça belirlenir",reason:"Madde 23 kapsamında norm kadro Bakanlıkça ayrıca belirlenir; öğrenci sayısına dayalı Madde 21 formülü uygulanmaz."};const boarding='
    new = 'const policy=institutionPolicy(r);if(policy==="outside")return {norm:null,status:"Analiz kapsamı dışı",reason:"Bu kayıt okul öğrenci-norm analizinin dışında tutulur. Bu sınıflandırma rehber öğretmen atanamayacağı anlamına gelmez."};if(policy==="ministerial")return {norm:null,status:"Bakanlıkça belirlenir",reason:"Madde 23 kapsamında norm kadro Bakanlıkça ayrıca belirlenir; öğrenci sayısına dayalı Madde 21 formülü uygulanmaz."};if(si.movedOrRenamed)return {norm:null,status:"Taşınmış / isim değişmiş",reason:"Öğrenci sayısı verisi yok. Okul taşınmış, kapanmış veya isim değiştirmiş olabilir; güncel kurum eşleştirmesi gerekli."};const boarding='
    if new not in text:
        if old not in text:
            raise RuntimeError("normFor patch anchor not found")
        text = text.replace(old, new, 1)

    old = 'return {...r,ogrenci_sayisi_etkin:si.value,ogrenci_sayisi_alt_100:!!si.under100,ogrenci_sayisi_gosterim:si.label||(si.value===null?"—":fmt(si.value)),ogrenci_dogrulama:si.note,kademe:schoolLevel(r),...normFor(r)}});'
    new = 'return {...r,ogrenci_sayisi_etkin:si.value,ogrenci_sayisi_alt_100:!!si.under100,ogrenci_veri_yok:!!si.movedOrRenamed,ogrenci_sayisi_gosterim:si.label||(si.value===null?"—":fmt(si.value)),ogrenci_dogrulama:si.note,kademe:schoolLevel(r),...normFor(r)}});'
    if new not in text:
        if old not in text:
            raise RuntimeError("row metadata patch anchor not found")
        text = text.replace(old, new, 1)

    formatted = f"{missing_total:,}".replace(",", ".")
    text = re.sub(r'Eksik Veriler · [\d.]+', f'Eksik Veriler · {formatted}', text, count=1)
    INDEX.write_text(text, encoding="utf-8")


def main():
    rows = load_rows()
    by_code = {str(r.get("kurum_kodu") or "").strip(): r for r in rows}
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    schools = payload.setdefault("schools", {})
    missing_records = embedded_missing_records(MISSING.read_text(encoding="utf-8"))
    if not missing_records:
        raise RuntimeError("Could not parse embedded missing-data records")

    lise_targets = {r["code"]: r for r in missing_records if r["level"] == "Lise"}
    manual_codes = {str(x.get("kurum_kodu") or "").strip() for x in manual}
    now = datetime.now(timezone.utc).isoformat()

    exact_applied = 0
    not_in_missing = []
    for item in manual:
        code = str(item.get("kurum_kodu") or "").strip()
        value = int(item.get("ogrenci_sayisi") or 0)
        if not code or value <= 0:
            raise RuntimeError(f"Invalid manual high-school record: {item}")
        if code not in lise_targets:
            not_in_missing.append(code)
        row = by_code.get(code, {})
        rec = lise_targets.get(code, {})
        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        previous_value = previous.get("value")
        canonical = max(value, int(previous_value)) if isinstance(previous_value, (int, float)) and previous_value > 0 else value
        observed = {int(v) for v in (previous.get("observed_values") or []) if isinstance(v, (int, float))}
        observed.add(value)
        schools[code] = {
            **previous,
            "value": canonical,
            "verified": True,
            "school": row.get("okul_adi") or rec.get("school") or previous.get("school") or "",
            "province": row.get("il") or rec.get("province") or previous.get("province") or "",
            "district": row.get("ilce") or rec.get("district") or previous.get("district") or "",
            "school_type": row.get("okul_turu") or rec.get("school_type") or previous.get("school_type") or "Lise",
            "observed_values": sorted(observed),
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "student_count_status": "exact_manual_review",
            "student_count_label": str(canonical),
            "updated_at": now,
            "note": "Kullanıcı tarafından okul sayfası tek tek kontrol edilerek doğrulanan lise öğrenci sayısı.",
        }
        exact_applied += 1

    moved_codes = sorted(set(lise_targets) - manual_codes)
    moved_labeled = 0
    preserved_positive = 0
    for code in moved_codes:
        rec = lise_targets[code]
        previous = schools.get(code) if isinstance(schools.get(code), dict) else {}
        if isinstance(previous.get("value"), (int, float)) and previous.get("value", 0) > 0:
            preserved_positive += 1
            continue
        schools[code] = {
            **previous,
            "value": None,
            "verified": True,
            "school": rec["school"],
            "province": rec["province"],
            "district": rec["district"],
            "school_type": rec["school_type"] or "Lise",
            "manual_reviewed": True,
            "manual_reviewed_at": "2026-10-03",
            "student_count_status": "data_unavailable_moved_or_renamed",
            "student_count_label": "Veri yok",
            "institution_status_label": "Taşınmış / isim değişmiş",
            "updated_at": now,
            "note": "Manuel lise kontrolünde güncel öğrenci sayısı bulunamadı; okul taşınmış, kapanmış veya isim değiştirmiş olabilir. Kesin öğrenci sayısı uydurulmadı.",
        }
        moved_labeled += 1

    payload["meta"] = {
        **(payload.get("meta") or {}),
        "manual_highschool_update_at": now,
        "manual_highschool_source": "manual-student-counts-lise-2026-10-03.json",
        "manual_highschool_rule": "Supplied exact values are applied; remaining unresolved high-school records are labeled Veri yok / Taşınmış / isim değişmiş without inventing a count.",
    }
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    before, removed, after = patch_missing_page(manual_codes)
    patch_index(after)

    summary = {
        "updated_at": now,
        "lise_targets_before": len(lise_targets),
        "manual_lise_exact": len(manual),
        "exact_counts_applied": exact_applied,
        "moved_or_renamed_targets": len(moved_codes),
        "moved_or_renamed_labeled": moved_labeled,
        "moved_or_renamed_preserved_positive": preserved_positive,
        "manual_codes_not_in_current_missing_page": sorted(not_in_missing),
        "missing_page_before": before,
        "exact_records_removed_from_missing_page": removed,
        "missing_page_after": after,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
