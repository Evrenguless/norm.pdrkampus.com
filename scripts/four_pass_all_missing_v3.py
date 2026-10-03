from __future__ import annotations

import four_pass_all_missing_v2 as base


def broad_school_scope(row):
    """Include every institution row except institution types whose norm metric is not student count."""
    blob = base.norm((row.get('okul_turu') or '') + ' ' + (row.get('okul_adi') or ''))
    if any(x in blob for x in base.EXCLUDE):
        return False
    code = str(row.get('kurum_kodu') or '').strip()
    name = (row.get('okul_adi') or '').strip()
    return bool(code and name)


base.school_scope = broad_school_scope

if __name__ == '__main__':
    base.main()
