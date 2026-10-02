from __future__ import annotations

import csv
import glob
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT = DATA_DIR / "student-overrides.json"
SUMMARY_OUT = DATA_DIR / "student-scan-summary.json"

MAX_WORKERS = 10
TIMEOUT = 12
MAX_DISCOVERED_PAGES = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/2.0; +https://norm.pdrkampus.com)"
}

COUNT_PATTERNS = [
    re.compile(r"Öğrenci\\s*Say(?:ı|i)s(?:ı|i)\\s*[:\\-]?\\s*(\\d{1,5})", re.I),
    re.compile(r"Öğrenci\\s*Sayımız\\s*[:\\-]?\\s*(\\d{1,5})", re.I),
    re.compile(r"Toplam\\s*Öğrenci(?:\\s*Say(?:ı|i)s(?:ı|i))?\\s*[:\\-]?\\s*(\\d{1,5})", re.I),
]

ZERO_OR_DASH_PATTERNS = [
    re.compile(r"Öğrenci\\s*Say(?:ı|i)s(?:ı|i)\\s*[:\\-]?\\s*(?:0|[-–—])(?:\\D|$)", re.I),
    re.compile(r"Öğrenci\\s*Sayımız\\s*[:\\-]?\\s*(?:0|[-–—])(?:\\D|$)", re.I),
]

DISCOVERY_HINTS = (
    "okulumuz_hakkinda",
    "hakkimizda",
    "hakkında",
    "okulumuz",
    "sayilarla",
    "sayılarla",
)

NORMAL_TARGET_TYPES = {
    "İlkokul",
    "Ortaokul",
    "İmam Hatip Ortaokulu",
    "Yatılı Bölge Ortaokulu",
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


def extract_numbers(value):
    if value is None:
        return []
    vals = []
    for m in re.findall(r"\\d+(?:[.,]\\d+)?", str(value)):
        try:
            n = int(float(m.replace(",", ".")))
        except ValueError:
            continue
        if 0 <= n <= 10000:
            vals.append(n)
    return vals


def current_count(row):
    vals = extract_numbers(row.get("ogrenci_sayisi")) + extract_numbers(row.get("ogrenci_sayilari"))
    return max(vals) if vals else None


def base_urls(row):
    bases = []
    for key in ("web_sitesi", "kaynak_url"):
        value = (row.get(key) or "").strip()
        if value.startswith("http"):
            value = value.rstrip("/") + "/"
            if value not in bases:
                bases.append(value)
    return bases


def seed_urls(row):
    urls = []
    for base in base_urls(row):
        for rel in (
            "",
            "tema/",
            "tema/okulumuz_hakkinda.php",
            "okulumuz_hakkinda.html",
            "okulumuz_hakkinda.php",
        ):
            url = urljoin(base, rel)
            if url not in urls:
                urls.append(url)
    return urls


def same_meb_host(url, base_host):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in ("http", "https")
        and host == base_host
        and host.endswith(".meb.k12.tr")
    )


def normalize_space(text):
    return " ".join(str(text or "").split())


def parse_student_counts(html):
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    evidence = []

    candidates = []
    for node in soup.find_all(string=re.compile(r"Öğrenci", re.I)):
        parent = node.parent
        for element in (parent, getattr(parent, "parent", None)):
            if element:
                text = normalize_space(element.get_text(" ", strip=True))
                if text and len(text) <= 220:
                    candidates.append(text)

    candidates.append(normalize_space(soup.get_text(" ", strip=True)))

    seen_text = set()
    for source in candidates:
        if source in seen_text:
            continue
        seen_text.add(source)
        for pattern in COUNT_PATTERNS:
            for match in pattern.finditer(source):
                try:
                    value = int(match.group(1))
                except ValueError:
                    continue
                if 0 < value <= 10000:
                    found.add(value)
                    snippet = source[max(0, match.start() - 50): match.end() + 50]
                    evidence.append(normalize_space(snippet)[:180])

    zero_or_dash = any(
        pattern.search(source)
        for source in candidates
        for pattern in ZERO_OR_DASH_PATTERNS
    )
    return sorted(found), sorted(set(evidence)), zero_or_dash


def discover_links(html, page_url):
    base_host = (urlparse(page_url).hostname or "").lower()
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        text = normalize_space(anchor.get_text(" ", strip=True)).lower()
        joined = (href + " " + text).lower()
        if not any(hint in joined for hint in DISCOVERY_HINTS):
            continue
        url = urljoin(page_url, href)
        if same_meb_host(url, base_host) and url not in found:
            found.append(url)
    return found[:MAX_DISCOVERED_PAGES]


def fetch_page(session, url):
    last_status = None
    last_error = None
    for attempt in range(1):
        try:
            response = session.get(
                url,
                timeout=TIMEOUT,
                headers=HEADERS,
                allow_redirects=True,
            )
            last_status = response.status_code
            if response.status_code == 200 and response.text:
                return {
                    "ok": True,
                    "status": response.status_code,
                    "url": response.url,
                    "html": response.text,
                    "error": None,
                }
            if response.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as exc:
            last_error = exc.__class__.__name__
        if attempt == 0:
            time.sleep(0.5)

    return {
        "ok": False,
        "status": last_status,
        "url": url,
        "html": "",
        "error": last_error,
    }


def classify_failure(attempts, saw_zero_or_dash):
    if saw_zero_or_dash:
        return "published_zero_or_dash"
    if attempts and all(not attempt.get("ok") for attempt in attempts):
        statuses = {attempt.get("status") for attempt in attempts}
        if 403 in statuses:
            return "http_403"
        if 429 in statuses:
            return "http_429"
        if 404 in statuses:
            return "http_404_only"
        return "site_unreachable"
    if any(attempt.get("ok") for attempt in attempts):
        return "student_field_not_found"
    return "no_usable_url"


def scan(row):
    code = str(row.get("kurum_kodu") or "").strip()
    school = row.get("okul_adi") or ""
    existing = current_count(row)
    observed = set()
    sources = []
    attempts = []
    saw_zero_or_dash = False
    visited = set()
    queue = seed_urls(row)

    with requests.Session() as session:
        while queue and len(visited) < 3 + MAX_DISCOVERED_PAGES:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            result = fetch_page(session, url)
            attempts.append({
                "url": result["url"],
                "ok": result["ok"],
                "status": result["status"],
                "error": result["error"],
            })

            if not result["ok"]:
                continue

            values, evidence, zero_or_dash = parse_student_counts(result["html"])
            saw_zero_or_dash = saw_zero_or_dash or zero_or_dash
            if values:
                observed.update(values)
                sources.append({
                    "url": result["url"],
                    "values": values,
                    "evidence": evidence[:4],
                })

            for discovered in discover_links(result["html"], result["url"]):
                if discovered not in visited and discovered not in queue:
                    queue.append(discovered)

    if observed:
        value = max(([existing] if existing is not None else []) + list(observed))
        if value > 0:
            return code, {
                "value": value,
                "verified": True,
                "school": school,
                "province": row.get("il") or "",
                "district": row.get("ilce") or "",
                "school_type": row.get("okul_turu") or "",
                "observed_values": sorted(observed),
                "sources": sources,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "note": "MEB okul sayfalarında bulunan doğrulanabilir değerler arasından en yüksek öğrenci sayısı kullanıldı.",
            }, None

    diagnostic = {
        "school": school,
        "province": row.get("il") or "",
        "district": row.get("ilce") or "",
        "school_type": row.get("okul_turu") or "",
        "reason": classify_failure(attempts, saw_zero_or_dash),
        "attempted_urls": [attempt["url"] for attempt in attempts],
        "statuses": [
            attempt.get("status")
            for attempt in attempts
            if attempt.get("status") is not None
        ],
    }
    return code, None, diagnostic


def load_rows():
    paths = sorted(glob.glob(str(DATA_DIR / "chunk-*.csv")))
    if not paths:
        return []

    rows = []
    with open(paths[0], newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows.extend(reader)

    for path in paths[1:]:
        with open(path, newline="", encoding="utf-8-sig") as file:
            rows.extend(csv.DictReader(file, fieldnames=fieldnames))
    return rows


def load_existing():
    if not OUT.exists():
        return {"meta": {}, "schools": {}}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"meta": {}, "schools": {}}


def main():
    rows = load_rows()
    payload = load_existing()
    schools = payload.setdefault("schools", {})
    verified_before = len(schools)

    def needs_rescan(row):
        school_type = (row.get("okul_turu") or "").strip()
        code = str(row.get("kurum_kodu") or "").strip()
        if school_type not in NORMAL_TARGET_TYPES:
            return False
        if not code or code in schools:
            return False
        primary = extract_numbers(row.get("ogrenci_sayisi"))
        primary_zero = bool(primary) and max(primary) == 0
        missing = current_count(row) is None
        return (primary_zero or missing) and bool(seed_urls(row))

    targets = [row for row in rows if needs_rescan(row)]
    print(
        f"Loaded {len(rows)} schools; deep-scanning {len(targets)} "
        "unresolved normal schools (RAM/special education/MEM excluded)"
    )

    unresolved = {}
    recovered_by_type = Counter()
    unresolved_by_reason = Counter()
    unresolved_by_type = Counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(scan, row) for row in targets]
        for index, future in enumerate(as_completed(futures), 1):
            code, result, diagnostic = future.result()
            if result:
                previous = schools.get(code)
                if previous and isinstance(previous.get("value"), (int, float)):
                    result["value"] = max(int(previous["value"]), int(result["value"]))
                schools[code] = result
                recovered_by_type[result.get("school_type") or "Bilinmiyor"] += 1
            elif diagnostic:
                unresolved[code] = diagnostic
                unresolved_by_reason[diagnostic["reason"]] += 1
                unresolved_by_type[diagnostic.get("school_type") or "Bilinmiyor"] += 1

            if index % 50 == 0 or index == len(targets):
                print(
                    f"Scanned {index}/{len(targets)} | "
                    f"recovered={sum(recovered_by_type.values())}"
                )

    payload["meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "MEB school websites",
        "rule": "When conflicting counts exist, the highest verifiable count is used.",
        "scan_mode": "deep_second_pass",
        "targets_scanned": len(targets),
        "verified_records": len(schools),
        "new_verified_records": len(schools) - verified_before,
        "remaining_unresolved_normal_schools": len(unresolved),
        "unresolved_reason_counts": dict(sorted(unresolved_by_reason.items())),
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "targets_scanned": len(targets),
        "recovered": sum(recovered_by_type.values()),
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
        "sample_unresolved": list(unresolved.values())[:50],
    }
    SUMMARY_OUT.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Deep second-pass summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {len(schools)} verified overrides to {OUT}")
    print(f"Wrote scan diagnostics to {SUMMARY_OUT}")


if __name__ == "__main__":
    main()
