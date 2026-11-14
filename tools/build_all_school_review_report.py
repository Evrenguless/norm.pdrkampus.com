from __future__ import annotations

import csv
import glob
import json
from collections import Counter
from pathlib import Path

FIELDS = [
    "Kurum kodu", "İl", "İlçe", "Okul", "Okul türü",
    "Mevcut öğrenci sayısı", "Sitede bulunan öğrenci sayısı", "Öğrenci farkı", "Öğrenci sonucu",
    "Mevcut rehber öğretmen sayısı", "Sitede sayılabilen rehber öğretmen sayısı", "Rehber öğretmen farkı", "Rehber öğretmen sonucu",
    "Mevcut norm", "Aday norm", "Öğrenci kaynak URL'leri", "Rehber öğretmen kaynak URL'si",
    "Kanıt metni", "Elle doğrulama tarihi", "Tarama zamanı", "Tarama hataları",
]

STUDENT_STATUS = {
    "update_candidate": "DEĞİŞİKLİK ADAYI",
    "manual_record_conflict": "DEĞİŞİKLİK ADAYI (MEVCUT ELLE DOĞRULANMIŞ DEĞERDEN FARKLI)",
    "new_candidate": "YENİ DEĞER ADAYI",
    "unchanged": "DEĞİŞİKLİK YOK",
    "no_student_count_found": "BULUNAMADI / KAYNAKTA YOK — ESKİ DEĞER KORUNACAK",
    "conflicting_page_counts": "SAYFALARDA ÇELİŞKİLİ — ESKİ DEĞER KORUNACAK",
    "no_official_website": "RESMÎ OKUL SİTESİ YOK — ESKİ DEĞER KORUNACAK",
    "scan_error": "TARAMA HATASI — ESKİ DEĞER KORUNACAK",
}
STAFF_STATUS = {
    "update_candidate": "DEĞİŞİKLİK ADAYI",
    "new_candidate": "YENİ POZİTİF DEĞER ADAYI",
    "unchanged": "DEĞİŞİKLİK YOK",
    "not_listed_unknown": "0 / LİSTEDE YOK — MEVCUT DEĞER KORUNACAK",
    "scan_error": "TARAMA HATASI — MEVCUT DEĞER KORUNACAK",
    "no_official_website": "RESMÎ OKUL SİTESİ YOK — MEVCUT DEĞER KORUNACAK",
}

def compact(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value

def student_status(row):
    status = row.get("ogrenci_durumu", "")
    if status == "no_student_count_found" and row.get("tarama_hatalari"):
        return "KAYNAĞA ERİŞİLEMEDİ / SAYI BULUNAMADI — ESKİ DEĞER KORUNACAK"
    return STUDENT_STATUS.get(status, status.upper() if status else "BELİRTİLMEDİ")

def staff_status(row):
    status = row.get("rehber_durumu", "")
    return STAFF_STATUS.get(status, (status or "BELİRTİLMEDİ").upper() + " — MEVCUT DEĞER KORUNACAK")

def main():
    paths = sorted(glob.glob("shards/**/school-review-*.json", recursive=True))
    if len(paths) != 32:
        raise SystemExit(f"32 tarama parçası bekleniyordu; {len(paths)} bulundu")
    rows = []
    for path in paths:
        part = json.loads(Path(path).read_text(encoding="utf-8"))
        rows.extend(part)
    rows.sort(key=lambda r: (str(r.get("il", "")), str(r.get("ilce", "")), str(r.get("okul", "")), str(r.get("code", ""))))

    Path("report").mkdir(parents=True, exist_ok=True)
    output = Path("report/tum-okullar-karsilastirma.csv")
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            sources = row.get("ogrenci_kaynaklari") or []
            writer.writerow({
                "Kurum kodu": row.get("code", ""),
                "İl": row.get("il", ""),
                "İlçe": row.get("ilce", ""),
                "Okul": row.get("okul", ""),
                "Okul türü": row.get("okul_turu", ""),
                "Mevcut öğrenci sayısı": compact(row.get("eski_ogrenci")),
                "Sitede bulunan öğrenci sayısı": compact(row.get("aday_ogrenci")),
                "Öğrenci farkı": compact(row.get("ogrenci_farki")),
                "Öğrenci sonucu": student_status(row),
                "Mevcut rehber öğretmen sayısı": compact(row.get("eski_rehber_sayisi")),
                "Sitede sayılabilen rehber öğretmen sayısı": compact(row.get("aday_rehber_sayisi")),
                "Rehber öğretmen farkı": compact(row.get("rehber_farki")),
                "Rehber öğretmen sonucu": staff_status(row),
                "Mevcut norm": compact(row.get("eski_norm")),
                "Aday norm": compact(row.get("aday_norm")),
                "Öğrenci kaynak URL'leri": compact(sources),
                "Rehber öğretmen kaynak URL'si": row.get("rehber_kaynak", ""),
                "Kanıt metni": compact(row.get("ogrenci_kanit")),
                "Elle doğrulama tarihi": row.get("manual_reviewed_at", ""),
                "Tarama zamanı": row.get("checked_at", ""),
                "Tarama hataları": compact(row.get("tarama_hatalari")),
            })

    student_counts = Counter(student_status(r) for r in rows)
    staff_counts = Counter(staff_status(r) for r in rows)
    print(json.dumps({
        "school_rows": len(rows),
        "student_results": dict(student_counts),
        "staff_results": dict(staff_counts),
        "report_file": str(output),
        "update_policy": "Açıkça bulunan her farklı öğrenci sayısı değişiklik adayıdır. Öğrenci sayısı bulunamadığında, site yok/erişilemiyor veya sayfalar çelişkili olduğunda eski değer korunur. Rehber öğretmen için yalnızca pozitif ve mevcut değerden farklı sayı adaydır; liste yok/0/okunamıyor ise mevcut değer korunur. Kaynak veri dosyaları değiştirilmez.",
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
