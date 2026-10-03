from __future__ import annotations

import io
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

DATA_DIR = Path("data")
OVERRIDES = DATA_DIR / "student-overrides.json"
SCAN_SUMMARY = DATA_DIR / "student-scan-summary.json"
OUT = DATA_DIR / "layered-rescue-summary.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/6.0; +https://norm.pdrkampus.com)"}
TIMEOUT = 12
WORKERS = 8
TARGET_GROUP = os.getenv("TARGET_GROUP", "kindergarten").strip().lower()


def norm(s):
    s = (s or "").strip().lower().replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def nums(v):
    if v is None:
        return []
    out = []
    for x in re.findall(r"\d+", str(v).replace(".", "")):
        n = int(x)
        if 0 <= n <= 10000:
            out.append(n)
    return out


def current_override(code, schools):
    o = schools.get(code) or {}
    vals = nums(o.get("value"))
    for v in o.get("observed_values") or []:
        vals += nums(v)
    vals = [v for v in vals if v > 0]
    return max(vals) if vals else None


def extract_count(text):
    pats = [
        r"Öğrenci\s+Sayısı\s*[:\-]?\s*(?:Kız\s*\d+\s*Erkek\s*\d+\s*)?(?:Toplam\s*)?(\d{1,5})",
        r"Toplam\s+Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})",
        r"Öğrenci\s+Mevcudu\s*[:\-]?\s*(\d{1,5})",
        r"Toplam\s+Öğrenci\s*[:\-]?\s*(\d{1,5})",
        r"(\d{1,5})\s+öğrenci\s+(?:ile\s+)?eğitim",
    ]
    vals = []
    for pat in pats:
        vals.extend(int(x) for x in re.findall(pat, text or "", flags=re.I | re.S))
    vals = [x for x in vals if 0 < x <= 10000]
    return max(vals) if vals else None


def strong_match(text, row):
    nt = norm(text)
    name = norm(row.get("okul_adi"))
    il = norm(row.get("il"))
    ilce = norm(row.get("ilce"))
    code = str(row.get("kurum_kodu") or "").strip()
    if not name or name not in nt:
        return False
    location_ok = (il and il in nt) or (ilce and ilce in nt)
    return bool(location_ok or (code and code in (text or "")))


def official_host(host):
    host = (host or "").lower().split(":")[0]
    return host.endswith("meb.gov.tr") or host.endswith("meb.k12.tr")


def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        ct = (r.headers.get("content-type") or "").lower()
        if "pdf" in ct or r.url.lower().endswith(".pdf"):
            return None, r.url
        return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True), r.url
    except Exception:
        return None, None


def fetch_pdf_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200 or len(r.content) > 25_000_000:
            return None, None
        reader = PdfReader(io.BytesIO(r.content))
        parts = []
        for page in reader.pages[:80]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(parts), r.url
    except Exception:
        return None, None


def search_results(query):
    url = "https://www.bing.com/search?q=" + quote_plus(query) + "&count=20"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            p = li.select_one(".b_caption p")
            if not a:
                continue
            out.append({
                "href": a.get("href") or "",
                "title": a.get_text(" ", strip=True),
                "snippet": p.get_text(" ", strip=True) if p else "",
            })
        return out
    except Exception:
        return []


def scan(row):
    name = row["okul_adi"]
    il = row["il"]
    ilce = row["ilce"]
    code = row["kurum_kodu"]
    queries = [
        f'"{name}" "{ilce}" "{il}" "öğrenci sayısı" filetype:pdf',
        f'"{name}" "stratejik plan" "öğrenci"',
        f'"{code}" "öğrenci sayısı"',
        f'"{name}" "{ilce}" site:meb.gov.tr öğrenci',
        f'"{name}" "{ilce}" site:meb.k12.tr dosyalar öğrenci',
    ]
    candidates = []
    seen = set()
    for q in queries:
        for item in search_results(q):
            href = item["href"]
            if not href or href in seen:
                continue
            seen.add(href)
            host = urlparse(href).netloc.lower()
            blob = " ".join([item["title"], item["snippet"]])
            if not strong_match(blob, row) and code not in blob:
                continue
            if not official_host(host):
                c = extract_count(blob)
                if c:
                    candidates.append({"value": c, "source_url": href, "source_type": "D_WEB_SNIPPET", "confidence": "D", "snippet": blob[:500]})
                continue

            is_pdf = href.lower().endswith(".pdf") or "meb_iys_dosyalar" in href.lower()
            if is_pdf:
                text, final_url = fetch_pdf_text(href)
                if text and strong_match(text, row):
                    c = extract_count(text)
                    if c:
                        return {"accepted": {"value": c, "source_url": final_url or href, "source_type": "B_MEB_PDF", "confidence": "B"}, "candidates": candidates}
                c = extract_count(blob)
                if c:
                    candidates.append({"value": c, "source_url": href, "source_type": "B_MEB_PDF_SNIPPET", "confidence": "B-candidate", "snippet": blob[:500]})
            else:
                text, final_url = fetch_html(href)
                if text and strong_match(text, row):
                    c = extract_count(text)
                    if c:
                        return {"accepted": {"value": c, "source_url": final_url or href, "source_type": "B_MEB_LOCAL_PAGE", "confidence": "B"}, "candidates": candidates}
        time.sleep(0.12)
    return {"accepted": None, "candidates": candidates}


def main():
    payload = load_json(OVERRIDES, {"schools": {}})
    schools = payload.setdefault("schools", {})
    scan_summary = load_json(SCAN_SUMMARY, {})
    unresolved = scan_summary.get("unresolved") or {}

    if TARGET_GROUP != "kindergarten":
        raise RuntimeError(f"Unsupported target group: {TARGET_GROUP}")

    baseline = []
    for code, info in unresolved.items():
        if (info.get("school_type") or "").strip() != "Anaokulu":
            continue
        baseline.append({
            "kurum_kodu": str(code).strip(),
            "okul_adi": info.get("school") or "",
            "il": info.get("province") or "",
            "ilce": info.get("district") or "",
            "previous_reason": info.get("reason") or "",
        })
    if len(baseline) != 245:
        raise RuntimeError(f"Safety check: expected 245 kindergarten baseline, got {len(baseline)}")

    targets = [r for r in baseline if not current_override(r["kurum_kodu"], schools)]
    if len(targets) != 225:
        raise RuntimeError(f"Safety check: expected exactly 225 third-pass targets, got {len(targets)}")

    accepted, candidates = {}, {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(scan, row): row for row in targets}
        for i, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            code = row["kurum_kodu"]
            result = future.result()
            hit = result.get("accepted")
            if hit:
                old = schools.get(code) or {}
                observed = []
                for v in old.get("observed_values") or []:
                    observed.extend(nums(v))
                observed.extend(nums(old.get("value")))
                observed.append(hit["value"])
                positive = sorted(set(v for v in observed if v > 0))
                value = max(positive)
                schools[code] = {
                    **old,
                    "value": value,
                    "verified": True,
                    "observed_values": positive,
                    "source": hit["source_type"],
                    "source_url": hit["source_url"],
                    "confidence": hit["confidence"],
                    "note": f"Üçüncü turda resmî kaynakta {hit['value']} öğrenci bulundu; doğrulanmış değerlerle karşılaştırılıp en yüksek {value} kullanıldı.",
                }
                accepted[code] = {"school": row["okul_adi"], "province": row["il"], "district": row["ilce"], **hit, "final_value": value}
            if result.get("candidates"):
                candidates[code] = {"school": row["okul_adi"], "province": row["il"], "district": row["ilce"], "items": result["candidates"]}
            if i % 25 == 0 or i == len(targets):
                print(f"scanned {i}/{len(targets)} accepted={len(accepted)} candidates={len(candidates)}", flush=True)

    payload.setdefault("meta", {})["third_pass_updated_at"] = datetime.now(timezone.utc).isoformat()
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = {
        "target_group": TARGET_GROUP,
        "pass": "official_pdf_mem_third_pass",
        "targets": len(targets),
        "accepted": len(accepted),
        "candidate_only": len(candidates),
        "remaining_without_accepted": len(targets) - len(accepted),
        "accepted_schools": accepted,
        "candidate_schools": candidates,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ["targets", "accepted", "candidate_only", "remaining_without_accepted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
