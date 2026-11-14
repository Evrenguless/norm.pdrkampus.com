from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = Path("review-output")
USER_AGENT = "PDRKampusNormReviewBot/1.0 (+https://norm.pdrkampus.com/)"
MAX_BYTES = 1_500_000
MAX_PAGES = 8
DEFAULT_DELAY = 1.0
DISCOVERY_HINTS = ("okulumuz", "hakkimizda", "hakkında", "sayilarla", "sayılarla")

def fold(value):
    value = str(value or "").lower().replace("ı", "i")
    return "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))

def number_values(value):
    text = str(value or "")
    if any(x in fold(text) for x in ("altinda", "yaklasik", "veri yok", "ogrenci bulunmuyor")):
        return []
    values = []
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:[.\s,]\d{3})+|\d{1,5})(?!\d)", text):
        token = match.group(1)
        digits = re.sub(r"[.\s,]", "", token)
        try:
            n = int(digits)
        except ValueError:
            continue
        if 0 < n <= 10000:
            values.append(n)
    return values

def explicit_student_counts(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    candidates = []
    for node in soup.find_all(string=re.compile(r"öğrenci", re.I)):
        parent = node.parent
        for element in (parent, getattr(parent, "parent", None)):
            if element:
                text = " ".join(element.get_text(" ", strip=True).split())
                if text and len(text) <= 260:
                    candidates.append(text)
    candidates.append(" ".join(soup.get_text(" ", strip=True).split()))
    pattern = re.compile(
        r"(?:(?:toplam)\s+)?öğrenci(?:\s+(?:say(?:ı|i)s(?:ı|i)|sayımız))?\s*[:：\-]?\s*(\d{1,3}(?:[.\s,]\d{3})+|\d{1,5})(?!\d)",
        re.I,
    )
    found, evidence = set(), set()
    for source in set(candidates):
        for match in pattern.finditer(source):
            n = int(re.sub(r"[.\s,]", "", match.group(1)))
            if 0 < n <= 10000:
                found.add(n)
                evidence.add(" ".join(source[max(0, match.start()-65):match.end()+65].split())[:200])
    return sorted(found), sorted(evidence)[:8]

def official_host(url):
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    return host if host.endswith(".meb.k12.tr") and host != "meb.k12.tr" else None

class HostPolicy:
    def __init__(self):
        self._global = threading.Lock()
        self._locks = {}
        self._last = {}
        self._robots = {}
        self._delays = {}
        self._robots_lock = threading.Lock()

    def _host_lock(self, host):
        with self._global:
            return self._locks.setdefault(host, threading.Lock())

    def _raw(self, url, host):
        lock = self._host_lock(host)
        with lock:
            delay = self._delays.get(host, DEFAULT_DELAY)
            wait = delay - (time.monotonic() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()
            try:
                response = requests.get(
                    url, headers={"User-Agent": USER_AGENT},
                    timeout=(6, 15), allow_redirects=False, stream=True,
                )
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        response.close()
                        return None, b"", "oversized_page"
                status = response.status_code
                content_type = response.headers.get("Content-Type", "")
                response.close()
                if status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location", "")
                    target = urljoin(url, location)
                    if official_host(target) != host:
                        return status, b"", "external_redirect"
                    return status, target.encode(), "redirect"
                return status, bytes(body), content_type
            except requests.RequestException as exc:
                return None, b"", exc.__class__.__name__

    def allowed(self, url):
        host = official_host(url)
        if not host or urlsplit(url).scheme != "https":
            return False, "invalid_or_non_https"
        with self._robots_lock:
            cached = self._robots.get(host)
        if cached is None:
            origin = "https://" + host
            status, body, detail = self._raw(origin + "/robots.txt", host)
            parser = RobotFileParser()
            parser.set_url(origin + "/robots.txt")
            if status == 404:
                parser.parse([])
                cached = (parser, True, "robots_not_found", DEFAULT_DELAY)
            elif status == 200 and detail and "text" in detail.lower():
                try:
                    lines = body.decode("utf-8", errors="replace").splitlines()
                    parser.parse(lines)
                    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or DEFAULT_DELAY
                    cached = (parser, True, "robots_checked", max(DEFAULT_DELAY, float(delay)))
                except Exception:
                    cached = (None, False, "robots_unreadable", DEFAULT_DELAY)
            else:
                cached = (None, False, "robots_unavailable", DEFAULT_DELAY)
            with self._robots_lock:
                self._robots[host] = cached
                self._delays[host] = cached[3]
        parser, usable, status_name, _ = cached
        if not usable:
            return False, status_name
        try:
            return parser.can_fetch(USER_AGENT, url), status_name
        except Exception:
            return False, "robots_unreadable"

    def get_html(self, url):
        host = official_host(url)
        allowed, robot_status = self.allowed(url)
        if not allowed:
            return {"ok": False, "status": None, "url": url, "html": "", "error": robot_status}
        status, body, detail = self._raw(url, host)
        if status == 200 and isinstance(detail, str) and "html" in detail.lower():
            charset = "utf-8"
            match = re.search(r"charset=([\w\-]+)", detail, re.I)
            if match:
                charset = match.group(1)
            return {"ok": True, "status": status, "url": url, "html": body.decode(charset, errors="replace"), "error": None, "robots": robot_status}
        if status in (301, 302, 303, 307, 308) and detail == "redirect":
            target = body.decode("utf-8", errors="replace")
            allowed2, _ = self.allowed(target)
            if allowed2:
                status2, body2, detail2 = self._raw(target, host)
                if status2 == 200 and isinstance(detail2, str) and "html" in detail2.lower():
                    return {"ok": True, "status": status2, "url": target, "html": body2.decode("utf-8", errors="replace"), "error": None, "robots": robot_status}
            return {"ok": False, "status": status, "url": target, "html": "", "error": "redirect_not_allowed", "robots": robot_status}
        return {"ok": False, "status": status, "url": url, "html": "", "error": detail if isinstance(detail, str) else "http_error", "robots": robot_status}

def student_urls(row):
    site = str(row.get("web_sitesi") or "").strip()
    if not site:
        return []
    if not site.startswith(("https://", "http://")):
        site = "https://" + site
    host = official_host(site)
    if not host:
        return []
    parsed = urlsplit(site)
    base = f"https://{host}/"
    paths = ("", "tema/", "tema/okulumuz_hakkinda.php", "okulumuz_hakkinda.html", "okulumuz_hakkinda.php")
    return list(dict.fromkeys(urljoin(base, p) for p in paths))

def discover_links(html_text, page_url):
    soup = BeautifulSoup(html_text, "html.parser")
    host = official_host(page_url)
    found = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = " ".join(a.get_text(" ", strip=True).split()).lower()
        if not any(h in (href + " " + text).lower() for h in DISCOVERY_HINTS):
            continue
        url = urljoin(page_url, href)
        if official_host(url) == host and url not in found:
            found.append(url)
    return found[:MAX_PAGES]

def parse_roster(html_text, code):
    doc = BeautifulSoup(html_text, "html.parser")
    text = html_text
    codes = set(re.findall(r"/meb_iys_dosyalar/\d+/\d+/(\d+)/", text))
    if codes and str(code) not in codes:
        return {"status": "institution_mismatch", "count": None}
    title = " ".join(doc.title.stripped_strings) if doc.title else ""
    if not any(k in fold(title) for k in ("teskilat", "kadromuz", "ogretmen", "personel")):
        return {"status": "unexpected_page", "count": None}
    seen = {}
    for a in doc.select('a[href*="idari_personel/"]'):
        role = a.get("title") or " ".join(a.stripped_strings)
        t = fold(role)
        if re.search(r"sinif|sube|ogrenci rehber|mudur|yonetici", t):
            continue
        if not re.search(r"rehber(?:lik)?\s+(?:ogretmen|alan)|psikolojik\s+danisman|^rehberlik$|\bpdr\b", t):
            continue
        match = re.search(r"_(\d+)\.html", a.get("href", ""))
        key = match.group(1) if match else a.get("href")
        seen[key] = role
    if not seen:
        return {"status": "not_listed_unknown", "count": None}
    roles = list(seen.values())
    unknown = sum(1 for r in roles if not re.search(r"kadrolu|gorevlendir", fold(r)))
    return {"status": "listed", "count": len(seen), "unknown_role_count": unknown}

def baseline_student(row, override):
    vals = number_values(row.get("ogrenci_sayisi")) + number_values(row.get("ogrenci_sayilari"))
    ov = override.get("value")
    if isinstance(ov, (int, float)) and ov > 0:
        vals.append(int(ov))
    return max(vals) if vals else None

def norm_for(row, count):
    if count is None:
        return None
    kind = fold(row.get("okul_turu", ""))
    name = fold(row.get("okul_adi", ""))
    joined = kind + " " + name
    if "ram" in joined or "rehberlik ve arastirma" in joined:
        return None
    if "ozel egitim" in joined or any(x in joined for x in ("isitme engelliler", "gorme engelliler", "bedensel engelliler")):
        base, step = 25, 100
    elif "mesleki egitim merkezi" in joined:
        base, step = 200, 500
    elif "anaokulu" in kind or "ana sinifi" in kind:
        base, step = 150, 500
    elif "ilkokul" in kind or "ilkokul" in name:
        base, step = 300, 500
    else:
        base, step = 150, 500
    if count < base:
        value = 0
    else:
        value = 1 + count // step
    if any(x in joined for x in ("yatili", "pansiyon")):
        value = max(1, value)
    return value

def scan_school(row, overrides, staff, policy):
    code = str(row.get("kurum_kodu") or "").strip()
    school = row.get("okul_adi") or ""
    old_student = baseline_student(row, overrides.get(code, {}))
    ov = overrides.get(code, {})
    old_staff = staff.get(code)
    urls = student_urls(row)
    checked = datetime.now(timezone.utc).isoformat()
    if not urls:
        return make_result(row, code, old_student, None, old_staff, None, [], [], "no_official_website", "no_official_website", checked, ov)

    visited, queue, found, sources = set(), urls[:], set(), []
    student_errors = []
    while queue and len(visited) < MAX_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        result = policy.get_html(url)
        if not result["ok"]:
            student_errors.append(result.get("error") or "access_error")
            continue
        vals, evidence = explicit_student_counts(result["html"])
        if vals:
            found.update(vals)
            sources.append({"url": result["url"], "values": vals, "evidence": evidence})
        for link in discover_links(result["html"], result["url"]):
            if link not in visited and link not in queue:
                queue.append(link)

    candidate_student = next(iter(found)) if len(found) == 1 else None
    if len(found) > 1:
        student_status = "conflicting_page_counts"
    elif candidate_student is None:
        student_status = "no_student_count_found"
    elif old_student is None:
        student_status = "new_candidate"
    elif candidate_student == old_student:
        student_status = "unchanged"
    elif ov.get("manual_reviewed_at"):
        student_status = "manual_record_conflict"
    else:
        student_status = "update_candidate"

    host = official_host(urls[0])
    staff_url = "https://" + host + "/tema/teskilat.php"
    staff_page = policy.get_html(staff_url)
    if staff_page["ok"]:
        parsed = parse_roster(staff_page["html"], code)
        new_staff = parsed.get("count")
        if new_staff is None:
            staff_status = parsed["status"]
        elif old_staff is None:
            staff_status = "new_candidate"
        elif new_staff == old_staff:
            staff_status = "unchanged"
        else:
            staff_status = "update_candidate"
    else:
        parsed = {"status": "access_error", "count": None}
        new_staff = None
        staff_status = staff_page.get("error") or "access_error"

    return make_result(row, code, old_student, candidate_student, old_staff, new_staff, sources, student_errors, student_status, staff_status, checked, ov, staff_page.get("url"), parsed)

def make_result(row, code, old_student, new_student, old_staff, new_staff, sources, errors, student_status, staff_status, checked, override, staff_url="", parsed=None):
    delta = (new_student - old_student) if new_student is not None and old_student is not None else None
    pct = round((delta / old_student) * 100, 2) if delta is not None and old_student else None
    return {
        "code": code, "il": row.get("il", ""), "ilce": row.get("ilce", ""),
        "okul": row.get("okul_adi", ""), "okul_turu": row.get("okul_turu", ""),
        "eski_ogrenci": old_student, "aday_ogrenci": new_student, "ogrenci_farki": delta,
        "ogrenci_farki_yuzde": pct,
        "eski_norm": norm_for(row, old_student), "aday_norm": norm_for(row, new_student),
        "ogrenci_durumu": student_status,
        "ogrenci_kaynaklari": [s["url"] for s in sources],
        "ogrenci_kanit": [e for s in sources for e in s["evidence"]][:8],
        "eski_rehber_sayisi": old_staff, "aday_rehber_sayisi": new_staff,
        "rehber_farki": (new_staff-old_staff) if new_staff is not None and old_staff is not None else None,
        "rehber_durumu": staff_status, "rehber_kaynak": staff_url or "",
        "rehber_liste_durumu": (parsed or {}).get("status", ""),
        "manual_reviewed_at": override.get("manual_reviewed_at", ""),
        "generated_for_personal_use": bool(override.get("generated_for_personal_use")),
        "checked_at": checked, "tarama_hatalari": sorted(set(errors))[:10],
    }

def load_data():
    schools = json.loads(gzip.decompress((DATA / "schools-v1.json.gz").read_bytes()))
    cols = schools["columns"]
    rows = [dict(zip(cols, r)) for r in schools["rows"]]
    payload = json.loads(gzip.decompress((DATA / "overrides-v1.json.gz").read_bytes()))
    overrides = payload.get("schools", {})
    sp = json.loads(gzip.decompress((DATA / "staff-v1.json.gz").read_bytes()))
    staff = {}
    for r in sp.get("rows", []):
        if r and r[1] is not None:
            staff[str(r[0])] = int(r[1])
    return rows, overrides, staff

def shard_id(row, n):
    urls = student_urls(row)
    host = official_host(urls[0]) if urls else ""
    value = hashlib.sha256(host.encode("utf-8")).digest()
    return int.from_bytes(value[:4], "big") % n

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out-dir", default="review-output")
    args = parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("Invalid shard settings")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, overrides, staff = load_data()
    targets = [r for r in rows if shard_id(r, args.shard_count) == args.shard_index]
    policy = HostPolicy()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(scan_school, row, overrides, staff, policy) for row in targets]
        for i, future in enumerate(as_completed(futures), 1):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"code":"", "okul":"", "ogrenci_durumu":"scan_error", "rehber_durumu":"scan_error", "tarama_hatalari":[exc.__class__.__name__]})
            if i % 100 == 0:
                print(json.dumps({"shard":args.shard_index,"finished":i,"target":len(targets)},ensure_ascii=False), flush=True)
    results.sort(key=lambda r: str(r.get("code","")))
    path = out / f"school-review-{args.shard_index:02d}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    print(json.dumps({"shard":args.shard_index,"target":len(targets),"written":len(results),"file":str(path)},ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
