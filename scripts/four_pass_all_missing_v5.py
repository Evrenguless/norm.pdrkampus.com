from __future__ import annotations

import csv
from pathlib import Path

import four_pass_all_missing_v4 as scan

# Canonical schema shared by chunk-001 and the headerless continuation chunks.
HEADERS = [
    'il','ilce','okul_adi','kurum_kodu','okul_turu','web_sitesi','adres','telefon',
    'harita','cekim_tarihi','ogrenci_sayisi','ogrenci_sayilari','durum','kaynak_url',
    'kontrol_tarihi','egitim_yili','kanit'
]


def fixed_load_rows():
    rows = []
    for path in sorted(Path('data').glob('chunk-*.csv')):
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.reader(handle)
            for index, values in enumerate(reader):
                if not values:
                    continue
                # chunk-001 carries the canonical header; later chunks start directly with data.
                if index == 0 and values[0].strip().lower() == 'il':
                    continue
                if len(values) < len(HEADERS):
                    values = values + [''] * (len(HEADERS) - len(values))
                elif len(values) > len(HEADERS):
                    # Preserve unexpected commas in evidence by folding overflow into the final field.
                    values = values[:len(HEADERS)-1] + [','.join(values[len(HEADERS)-1:])]
                rows.append(dict(zip(HEADERS, values)))
    return rows


scan.base.load_rows = fixed_load_rows

if __name__ == '__main__':
    scan.main()
