from __future__ import annotations

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from refresh_student_counts import (
    MAX_WORKERS,
    NORMAL_TARGET_TYPES,
    current_count,
    extract_numbers,
    load_existing,
    load_rows,
    scan,
    seed_urls,
)

SHARD_INDEX = int(os.environ["SHARD_INDEX"])
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "4"))
TARGET_GROUP = os.environ.get("TARGET_GROUP", "all").strip().lower()
OUT_DIR = Path(os.environ.get("SHARD_OUT_DIR", "shard-output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

HIGH_SCHOOL_TYPES = {
    "Anadolu Lisesi",
    "Mesleki ve Teknik Anadolu Lisesi",
    "Anadolu İmam Hatip Lisesi",
    "Çok Programlı Anadolu Lisesi",
    "Fen Lisesi",
    "Lise",
    "Spor Lisesi",
    "Güzel Sanatlar Lisesi",
    "Sosyal Bilimler Lisesi",
    "Açık/Akşam Lisesi",
}
MIDDLE_SCHOOL_TYPES = {"Ortaokul", "İmam Hatip Ortaokulu", "Yatılı Bölge Ortaokulu"}


def in_target_group(school_type):
    if TARGET_GROUP == "highschool":
        return school_type in HIGH_SCHOOL_TYPES
    if TARGET_GROUP == "middle":
        return school_type in MIDDLE_SCHOOL_TYPES
    if TARGET_GROUP == "primary":
        return school_type == "İlkokul"
    return school_type in NORMAL_TARGET_TYPES


def needs_rescan(row, verified_codes):
    school_type = (row.get("okul_turu") or "").strip()
    code = str(row.get("kurum_kodu") or "").strip()
    if not in_target_group(school_type):
        return False
    if not code:
        return False
    primary = extract_numbers(row.get("ogrenci_sayisi"))
    primary_zero = bool(primary) and max(primary) == 0
    missing = current_count(row) is None
    if TARGET_GROUP == "highschool":
        return (primary_zero or missing) and bool(seed_urls(row))
    if code in verified_codes:
        return False
    return (primary_zero or missing) and bool(seed_urls(row))


def main():
    rows = load_rows()
    existing = load_existing()
    verified_codes = set((existing.get("schools") or {}).keys())

    targets = [row for row in rows if needs_rescan(row, verified_codes)]
    targets.sort(key=lambda row: str(row.get("kurum_kodu") or ""))
    if TARGET_GROUP == "highschool" and len(targets) != 532:
        raise RuntimeError(f"Safety check failed: expected exactly 532 high-school targets, got {len(targets)}")
    if TARGET_GROUP == "middle" and len(targets) != 978:
        raise RuntimeError(f"Safety check failed: expected exactly 978 middle-school targets, got {len(targets)}")
    shard_targets = [
        row for i, row in enumerate(targets)
        if i % SHARD_COUNT == SHARD_INDEX
    ]

    recovered = {}
    unresolved = {}
    recovered_by_type = Counter()
    unresolved_by_reason = Counter()
    unresolved_by_type = Counter()

    print(
        f"Shard {SHARD_INDEX + 1}/{SHARD_COUNT}: "
        f"{len(shard_targets)} of {len(targets)} unresolved {TARGET_GROUP} schools"
    )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scan, row) for row in shard_targets]
        for index, future in enumerate(as_completed(futures), 1):
            code, result, diagnostic = future.result()
            if result:
                recovered[code] = result
                recovered_by_type[result.get("school_type") or "Bilinmiyor"] += 1
            elif diagnostic:
                unresolved[code] = diagnostic
                unresolved_by_reason[diagnostic["reason"]] += 1
                unresolved_by_type[diagnostic.get("school_type") or "Bilinmiyor"] += 1

            if index % 25 == 0 or index == len(shard_targets):
                print(
                    f"Shard {SHARD_INDEX + 1}: {index}/{len(shard_targets)} | "
                    f"recovered={len(recovered)}"
                )

    stamp = datetime.now(timezone.utc).isoformat()
    result = {
        "meta": {
            "updated_at": stamp,
            "target_group": TARGET_GROUP,
            "shard_index": SHARD_INDEX,
            "shard_count": SHARD_COUNT,
            "targets_scanned": len(shard_targets),
            "recovered": len(recovered),
            "remaining_unresolved": len(unresolved),
        },
        "schools": recovered,
        "unresolved": unresolved,
        "recovered_by_school_type": dict(sorted(recovered_by_type.items())),
        "unresolved_by_school_type": dict(sorted(unresolved_by_type.items())),
        "unresolved_by_reason": dict(sorted(unresolved_by_reason.items())),
    }

    out = OUT_DIR / f"student-scan-shard-{SHARD_INDEX}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
