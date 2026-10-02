from __future__ import annotations

import glob
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OVERRIDES = DATA_DIR / "student-overrides.json"
SUMMARY = DATA_DIR / "student-scan-summary.json"


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    payload = load_json(OVERRIDES, {"meta": {}, "schools": {}})
    schools = payload.setdefault("schools", {})
    before = len(schools)

    shard_paths = sorted(glob.glob("shards/**/student-scan-shard-*.json", recursive=True))
    if not shard_paths:
        raise SystemExit("No shard result files found")

    scanned = 0
    unresolved = {}
    recovered_by_type = Counter()
    unresolved_by_type = Counter()
    unresolved_by_reason = Counter()

    for path in shard_paths:
        shard = load_json(path, {})
        meta = shard.get("meta") or {}
        scanned += int(meta.get("targets_scanned") or 0)

        for code, result in (shard.get("schools") or {}).items():
            prev = schools.get(code)
            if prev and isinstance(prev.get("value"), (int, float)):
                result["value"] = max(int(prev["value"]), int(result["value"]))
            schools[code] = result

        unresolved.update(shard.get("unresolved") or {})
        recovered_by_type.update(shard.get("recovered_by_school_type") or {})
        unresolved_by_type.update(shard.get("unresolved_by_school_type") or {})
        unresolved_by_reason.update(shard.get("unresolved_by_reason") or {})

    stamp = datetime.now(timezone.utc).isoformat()
    payload["meta"] = {
        "updated_at": stamp,
        "source": "MEB school websites",
        "rule": "When conflicting counts exist, the highest verifiable count is used.",
        "scan_mode": "parallel_deep_second_pass",
        "shards": len(shard_paths),
        "targets_scanned": scanned,
        "verified_records": len(schools),
        "new_verified_records": len(schools) - before,
        "remaining_unresolved_normal_schools": len(unresolved),
        "unresolved_reason_counts": dict(sorted(unresolved_by_reason.items())),
    }
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "updated_at": stamp,
        "scan_mode": "parallel_deep_second_pass",
        "shards": len(shard_paths),
        "targets_scanned": scanned,
        "recovered": len(schools) - before,
        "remaining_unresolved": len(unresolved),
        "recovered_by_school_type": dict(sorted(recovered_by_type.items())),
        "unresolved_by_school_type": dict(sorted(unresolved_by_type.items())),
        "unresolved_by_reason": dict(sorted(unresolved_by_reason.items())),
        "reason_legend": {
            "published_zero_or_dash": "MEB sayfasında öğrenci alanı var ancak 0 veya '-' yayınlanmış.",
            "student_field_not_found": "Site açılıyor ancak taranan/keşfedilen sayfalarda öğrenci sayısı alanı bulunamadı.",
            "site_unreachable": "Okul sitesi tarama sırasında erişilebilir yanıt vermedi.",
            "http_403": "Okul sitesi HTTP 403 ile isteği engelledi.",
            "http_429": "Okul sitesi HTTP 429 ile hız sınırı uyguladı.",
            "http_404_only": "Denenen sayfaların tamamı 404 döndürdü.",
            "no_usable_url": "Kullanılabilir MEB okul URL'si bulunamadı.",
        },
        "sample_unresolved": list(unresolved.values())[:100],
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
