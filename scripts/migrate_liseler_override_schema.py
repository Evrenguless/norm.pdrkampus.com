from __future__ import annotations

import json
from pathlib import Path

path = Path("data/student-overrides.json")
payload = json.loads(path.read_text(encoding="utf-8"))
schools = payload.setdefault("schools", {})
changed = 0

for item in schools.values():
    if not isinstance(item, dict):
        continue
    if item.get("source") != "liseler.com.tr":
        continue
    count = item.get("student_count")
    if count is None:
        continue
    try:
        count = int(count)
    except (TypeError, ValueError):
        continue
    if item.get("value") != count:
        item["value"] = count
        item["verified"] = True
        item.setdefault("note", "liseler.com.tr ikinci kaynak taramasında bulunan öğrenci sayısı site hesaplamasında kullanılmak üzere aktarıldı.")
        changed += 1

path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"migrated={changed}")
