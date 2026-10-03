from pathlib import Path
import json

PATH = Path("data/student-overrides.json")

TARGETS = {
    "771503": "100. Yıl Şehit Serkan Ağca Anaokulu",
    "776609": "Solaklı Anaokulu",
    "772888": "Yolağzı Anaokulu",
    "773752": "Yeşilköy Özel Eğitim Anaokulu",
    "770871": "Şükrüpaşa Anaokulu",
    "777092": "Dörtyol Özel Eğitim Anaokulu",
    "774530": "Elmaşehir Anaokulu",
    "775456": "Kocasinan Türkan Altun ve Av. Mehmet Altun Anaokulu",
    "776373": "Mithatpaşa Anaokulu",
    "767370": "Şehit Birol Mutlu Özel Eğitim Anaokulu",
    "773115": "Yenitaşkent Yusuf Bayık Anaokulu",
    "772060": "Emine Erdoğan Anaokulu",
    "776553": "Akasya Anaokulu",
    "776215": "Minik Yıldızlar Anaokulu",
    "774908": "Selçuklu Anaokulu",
    "776863": "Alaköy Anaokulu",
    "776127": "Başakşehir Mutlu Eğitim Anaokulu",
    "777262": "Esenler Şule Yüksel Şenler Anaokulu",
    "777096": "Piri Reis Anaokulu",
    "774528": "Keskin Öğretmen Birgül Kesin Anaokulu",
}

payload = json.loads(PATH.read_text(encoding="utf-8"))
schools = payload.setdefault("schools", {})

for code, school_name in TARGETS.items():
    entry = dict(schools.get(code, {}))
    entry.update(
        {
            "value": None,
            "verified": True,
            "student_count_status": "under_100_manual_review",
            "student_count_label": "100 öğrenci altında",
            "note": "Kullanıcı talebi doğrultusunda 100 öğrenci altında olarak işaretlendi.",
            "school_name": school_name,
        }
    )
    schools[code] = entry

PATH.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"{len(TARGETS)} anaokulu 100 öğrenci altında olarak işaretlendi.")
