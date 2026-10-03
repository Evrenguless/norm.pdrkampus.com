from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
MISSING = ROOT / "eksik-veriler.html"
MANUAL = ROOT / "data" / "manual-student-counts-2026-10-03.json"
OVERRIDES = ROOT / "data" / "student-overrides.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)


def resolved_codes() -> set[str]:
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))["records"]
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    schools = payload.get("schools", {})
    codes = {str(x.get("kurum_kodu") or "").strip() for x in manual}
    codes |= {
        str(code) for code, row in schools.items()
        if isinstance(row, dict) and row.get("student_count_status") == "under_100_manual_review"
    }
    codes.discard("")
    return codes


def patch_missing_page() -> int:
    text = MISSING.read_text(encoding="utf-8")
    codes = resolved_codes()

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

    present_resolved = {m.group("code") for m in matches} & codes
    old_total = len(matches)
    if present_resolved:
        parts = []
        cursor = 0
        removed = 0
        for m in matches:
            if m.group("code") not in present_resolved:
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
        print(json.dumps({"missing_before": old_total, "resolved_removed": removed, "missing_after": new_total}, ensure_ascii=False))
        return new_total

    print(json.dumps({"missing_before": old_total, "resolved_removed": 0, "missing_after": old_total, "already_patched": True}, ensure_ascii=False))
    return old_total


def patch_index(missing_total: int) -> None:
    text = INDEX.read_text(encoding="utf-8")
    text = replace_once(text,
        'const vals=[...csvVals,...overrideVals];if(!vals.length){return {value:null,verified:false,note:o?.note||"Öğrenci sayısı verisi eksik.",source:o?"override":"csv"};}',
        'const vals=[...csvVals,...overrideVals];if(o?.student_count_status==="under_100_manual_review"){return {value:null,verified:true,under100:true,label:o.student_count_label||"100 öğrenci altında",note:o.note||"Manuel kontrolde 100 öğrenci altında.",source:"override"};}if(!vals.length){return {value:null,verified:false,under100:false,label:null,note:o?.note||"Öğrenci sayısı verisi eksik.",source:o?"override":"csv"};}',
        "studentInfo under-100 state")
    text = replace_once(text,
        'if(t==="Anaokulu"||tl.includes("anaokulu")||tl.includes("ana okulu")){if(n===null)return boarding?{norm:1,status:"Kısmi hesap",reason:"Yatılı/pansiyonlu işaretinden en az 1; öğrenci sayısı eksik."}:{norm:null,status:"Ek veri gerekli",reason:"Anaokulu için öğrenci sayısı eksik."};',
        'if(t==="Anaokulu"||tl.includes("anaokulu")||tl.includes("ana okulu")){if(si.under100)return boarding?{norm:1,status:"Hesaplandı",reason:"Manuel kontrolde 100 öğrenci altında; yatılı/pansiyonlu işaretinden 1 norm."}:{norm:0,status:"Hesaplandı",reason:"Manuel kontrolde 100 öğrenci altında; anaokulu 150 öğrenci eşiğinin altında."};if(n===null)return boarding?{norm:1,status:"Kısmi hesap",reason:"Yatılı/pansiyonlu işaretinden en az 1; öğrenci sayısı eksik."}:{norm:null,status:"Ek veri gerekli",reason:"Anaokulu için öğrenci sayısı eksik."};',
        "preschool norm branch")
    text = replace_once(text,
        'return {...r,ogrenci_sayisi_etkin:si.value,ogrenci_dogrulama:si.note,kademe:schoolLevel(r),...normFor(r)}});',
        'return {...r,ogrenci_sayisi_etkin:si.value,ogrenci_sayisi_alt_100:!!si.under100,ogrenci_sayisi_gosterim:si.label||(si.value===null?"—":fmt(si.value)),ogrenci_dogrulama:si.note,kademe:schoolLevel(r),...normFor(r)}});',
        "row display metadata")
    text = replace_once(text,
        '${r.ogrenci_sayisi_etkin===null?"—":fmt(r.ogrenci_sayisi_etkin)}',
        '${esc(r.ogrenci_sayisi_gosterim||(r.ogrenci_sayisi_etkin===null?"—":fmt(r.ogrenci_sayisi_etkin)))}',
        "student count table cell")
    text = replace_once(text,
        'function studentMatch(r,v){const n=r.ogrenci_sayisi_etkin;if(!v)return true;if(v==="missing")return n===null;if(n===null)return false;if(v==="0-149")return n<=149;',
        'function studentMatch(r,v){const n=r.ogrenci_sayisi_etkin;if(!v)return true;if(v==="missing")return n===null&&!r.ogrenci_sayisi_alt_100;if(v==="0-149")return r.ogrenci_sayisi_alt_100||(n!==null&&n<=149);if(n===null)return false;',
        "student filter behavior")

    formatted = f"{missing_total:,}".replace(",", ".")
    text = re.sub(r'Eksik Veriler · [\d.]+', f'Eksik Veriler · {formatted}', text, count=1)
    INDEX.write_text(text, encoding="utf-8")


def main() -> None:
    missing_total = patch_missing_page()
    patch_index(missing_total)


if __name__ == "__main__":
    main()
