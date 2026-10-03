from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import four_pass_all_missing_v2 as base

# These institution types do not use ordinary student headcount as the norm metric.
EXCLUDE_MARKERS = [
    'rehberlik ve arastirma', 'rehberlik arastirma',
    'mesleki egitim merkezi', 'meslek egitim merkezi',
    'halk egitim merkezi', 'halk egitimi merkezi',
    'ogretmenevi', 'aksam sanat okulu',
    'milli egitim mudurlugu', 'millî egitim mudurlugu',
    'bilim ve sanat merkezi', 'olgunlasma enstitusu',
    'hizmet ici egitim enstitusu', 'bakanlik merkez',
    'yurt disi', 'yurtdisi'
]


def eligible(row):
    code = str(row.get('kurum_kodu') or '').strip()
    name = str(row.get('okul_adi') or '').strip()
    if not code or not name:
        return False
    blob = base.norm((row.get('okul_turu') or '') + ' ' + name)
    return not any(marker in blob for marker in EXCLUDE_MARKERS)


def main():
    rows = base.load_rows()
    payload = base.load_json(base.OVERRIDES, {'schools': {}})
    schools = payload.setdefault('schools', {})

    scoped = [row for row in rows if eligible(row)]
    targets = []
    for row in scoped:
        code = str(row.get('kurum_kodu') or '').strip()
        if not (base.raw_values(row) + base.override_values(code, schools)):
            targets.append(row)

    counts = {
        'all_rows': len(rows),
        'school_scope_rows': len(scoped),
        'targets': len(targets),
    }
    print(json.dumps(counts, ensure_ascii=False), flush=True)

    # Hard guards: never claim exhaustive coverage if the source/target pool is suspiciously small.
    if len(rows) < 50000:
        raise RuntimeError(f"Safety check failed: expected >50k rows, got {len(rows)}")
    if len(scoped) < 45000:
        raise RuntimeError(f"Safety check failed: expected >45k eligible institution rows, got {len(scoped)}")
    if not (1000 <= len(targets) <= 7000):
        raise RuntimeError(f"Safety check failed: expected 1000-7000 unresolved targets, got {len(targets)}")

    results = {}
    accepted = 0
    candidates = 0

    with ThreadPoolExecutor(max_workers=base.WORKERS) as executor:
        futures = {executor.submit(base.scan_one, row): row for row in targets}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            code = result['institution_code']
            results[code] = result
            hit = result.get('accepted')

            if hit:
                old = schools.get(code) or {}
                observed = []
                for value in old.get('observed_values') or []:
                    observed += base.nums(value)
                observed += base.nums(old.get('value'))
                observed.append(hit['value'])
                observed = [value for value in observed if value > 0]
                final_value = max(observed)
                schools[code] = {
                    **old,
                    'value': final_value,
                    'verified': True,
                    'observed_values': sorted(set(observed)),
                    'source': hit['source_type'],
                    'source_url': hit['source_url'],
                    'confidence': hit['confidence'],
                    'school': result['school'],
                    'province': result['province'],
                    'district': result['district'],
                    'school_type': result['school_type'],
                    'note': 'Dört adımlı eksik veri taramasında doğrulandı; doğrulanabilir değerler içinden en yüksek değer kullanıldı.'
                }
                accepted += 1

            if result['result'].endswith('aday_var'):
                candidates += 1

            if index % 100 == 0 or index == len(targets):
                print(
                    f"scanned {index}/{len(targets)} accepted={accepted} low_conf_candidates={candidates}",
                    flush=True,
                )

    unresolved = sum(
        1 for result in results.values()
        if result['result'].startswith('4_adim_tamamlandi')
    )

    now = datetime.now(timezone.utc).isoformat()
    payload.setdefault('meta', {})['four_pass_all_missing_updated_at'] = now
    base.OVERRIDES.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )

    summary = {
        'updated_at': now,
        'scope': 'Kurum kodu ve okul adı bulunan tüm eğitim kurumları; RAM/MEM/HEM/öğretmenevi ve öğrenci baş sayısı yerine farklı norm metriği kullanan kurumlar hariç.',
        'all_rows': len(rows),
        'school_scope_rows': len(scoped),
        'targets': len(targets),
        'accepted': accepted,
        'low_confidence_candidate_schools': candidates,
        'four_steps_completed_unresolved': unresolved,
        'status_label': '4_adim_tamamlandi_bulunamadi',
        'results': results,
    }
    base.OUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({
        key: summary[key]
        for key in [
            'all_rows', 'school_scope_rows', 'targets', 'accepted',
            'low_confidence_candidate_schools', 'four_steps_completed_unresolved'
        ]
    }, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
