from __future__ import annotations

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

DATA_DIR = Path("data")
OVERRIDES = DATA_DIR / "student-overrides.json"
SCAN_SUMMARY = DATA_DIR / "student-scan-summary.json"
OUT = DATA_DIR / "layered-rescue-summary.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/5.3; +https://norm.pdrkampus.com)"}
TIMEOUT = 10
WORKERS = 12
TARGET_GROUP = os.getenv("TARGET_GROUP", "kindergarten").strip().lower()
TRUSTED_EXTERNAL = {
    "anaokullar.com.tr": "C_ANAOKULLAR_COM_TR",
    "www.anaokullar.com.tr": "C_ANAOKULLAR_COM_TR",
    "okullarhakkinda.com": "C_OKULLARHAKKINDA",
    "www.okullarhakkinda.com": "C_OKULLARHAKKINDA",
    "okulailem.com": "C_OKULAILEM",
    "www.okulailem.com": "C_OKULAILEM",
}


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
        r"Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})",
        r"Toplam\s+Öğrenci\s+Sayısı\s*[:\-]?\s*(\d{1,5})",
        r"(\d{1,5})\s+öğrenci\s+(?:ile\s+)?eğitim",
        r"(\d{1,5})\s+Öğrenci\b",
    ]
    vals = []
    for pat in pats:
        vals.extend(int(x) for x in re.findall(pat, text, flags=re.I | re.S))
    vals = [x for x in vals if 0 < x <= 10000]
    return max(vals) if vals else None


def fetch_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        ct = (r.headers.get("content-type") or "").lower()
        if "pdf" in ct or url.lower().endswith(".pdf"):
            return None, r.url
        return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True), r.url
    except Exception:
        return None, None


def strong_match(text, row):
    nt = norm(text)
    name = norm(row.get("okul_adi"))
    il = norm(row.get("il"))
    ilce = norm(row.get("ilce"))
    if not name or name not in nt:
        return False
    return bool(il and il in nt and ilce and ilce in nt)


def meb_direct(row):
    code = str(row.get("kurum_kodu") or "").strip()
    for url in [f"https://{code}.meb.k12.tr/", f"https://{code}.meb.k12.tr/tema/"]:
        text, final_url = fetch_text(url)
        if not text:
            continue
        count = extract_count(text)
        if count:
            return {"value": count, "source_url": final_url or url, "source_type": "A_MEB_SITE", "confidence": "A"}
    return None


def search_engine(row, external_only=False):
    name = row.get("okul_adi") or ""
    il = row.get("il") or ""
    ilce = row.get("ilce") or ""
    code = str(row.get("kurum_kodu") or "").strip()
    if external_only:
        queries = [
            f'"{name}" "{ilce}" "{il}" "Öğrenci Sayısı"',
            f'"{name}" "{ilce}" "{il}" öğrenci',
        ]
    else:
        queries = [
            f'"{name}" "Öğrenci Sayısı" site:meb.k12.tr',
            f'"{code}" "Öğrenci Sayısı" site:meb.k12.tr',
        ]
    candidates = []
    for q in queries:
        url = "https://www.bing.com/search?q=" + quote_plus(q) + "&count=15"
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for li in soup.select("li.b_algo"):
                a = li.select_one("h2 a")
                p = li.select_one(".b_caption p")
                if not a:
                    continue
                href = a.get("href") or ""
                host = urlparse(href).netloc.lower()
                snippet = p.get_text(" ", strip=True) if p else ""
                blob = " ".join([a.get_text(" ", strip=True), snippet])
                if not strong_match(blob, row) and code not in blob:
                    continue

                if "meb.k12.tr" in host and not external_only:
                    if href.lower().endswith(".pdf") or "meb_iys_dosyalar" in href:
                        candidates.append({"value": extract_count(blob), "source_url": href, "source_type": "B_MEB_PDF_CANDIDATE", "confidence": "B-candidate", "snippet": blob[:500]})
                    else:
                        text, final_url = fetch_text(href)
                        count = extract_count(text or "") or extract_count(blob)
                        if count and (strong_match(text or blob, row) or code in (text or blob)):
                            return {"accepted": {"value": count, "source_url": final_url or href, "source_type": "A_MEB_SEARCH_HIT", "confidence": "A"}, "candidates": candidates}

                if external_only and host in TRUSTED_EXTERNAL:
                    text, final_url = fetch_text(href)
                    if not text or not strong_match(text, row):
                        continue
                    count = extract_count(text)
                    if count:
                        return {"accepted": {"value": count, "source_url": final_url or href, "source_type": TRUSTED_EXTERNAL[host], "confidence": "C"}, "candidates": candidates}

                if extract_count(blob):
                    candidates.append({"value": extract_count(blob), "source_url": href, "source_type": "D_SEARCH_SNIPPET", "confidence": "D", "snippet": blob[:500]})
        except Exception:
            pass
        time.sleep(0.15)
    return {"accepted": None, "candidates": candidates}


def scan(row):
    direct = meb_direct(row)
    if direct:
        return {"accepted": direct, "candidates": []}
    meb = search_engine(row, external_only=False)
    if meb.get("accepted"):
        return meb
    ext = search_engine(row, external_only=True)
    return {"accepted": ext.get("accepted"), "candidates": (meb.get("candidates") or []) + (ext.get("candidates") or [])}


def main():
    payload = load_json(OVERRIDES, {"schools": {}})
    schools = payload.setdefault("schools", {})
    scan_summary = load_json(SCAN_SUMMARY, {})
    unresolved = scan_summary.get("unresolved") or {}

    if TARGET_GROUP != "kindergarten":
        raise RuntimeError(f"Unsupported target group for exact-summary rescue: {TARGET_GROUP}")

    baseline = []
    for code, info in unresolved.items():
        if (info.get("school_type") or "").strip() != "Anaokulu":
            continue
        baseline.append({
            "kurum_kodu": str(code).strip(),
            "okul_adi": info.get("school") or "",
            "il": info.get("province") or "",
            "ilce": info.get("district") or "",
            "okul_turu": info.get("school_type") or "Anaokulu",
            "previous_reason": info.get("reason") or "",
        })

    if len(baseline) != 245:
        raise RuntimeError(f"Safety check failed: expected exactly 245 unresolved kindergarten baseline targets, got {len(baseline)}")

    targets = [r for r in baseline if not current_override(r["kurum_kodu"], schools)]
    if len(targets) != 244:
        raise RuntimeError(f"Safety check failed: expected exactly 244 still-unresolved kindergarten targets after accepted overrides, got {len(targets)}")

    accepted = {}
    candidates = {}
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
                positive = [v for v in observed if v > 0]
                value = max(positive)
                schools[code] = {
                    **old,
                    "value": value,
                    "verified": True,
                    "observed_values": sorted(set(positive)),
                    "source": hit["source_type"],
                    "source_url": hit["source_url"],
                    "confidence": hit["confidence"],
                    "note": f"Katmanlı taramada {hit['source_type']} kaynağında {hit['value']} öğrenci bulundu; mevcut doğrulanmış değerlerle karşılaştırılıp en yüksek {value} kullanıldı.",
                }
                accepted[code] = {"school": row["okul_adi"], "province": row["il"], "district": row["ilce"], "previous_reason": row["previous_reason"], **hit, "final_value": value}
            if result.get("candidates"):
                candidates[code] = {"school": row["okul_adi"], "province": row["il"], "district": row["ilce"], "previous_reason": row["previous_reason"], "items": result["candidates"]}
            if i % 25 == 0 or i == len(targets):
                print(f"scanned {i}/{len(targets)} accepted={len(accepted)} candidates={len(candidates)}", flush=True)

    payload.setdefault("meta", {})["layered_rescue_updated_at"] = datetime.now(timezone.utc).isoformat()
    OVERRIDES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = {
        "target_group": TARGET_GROUP,
        "baseline_unresolved": len(baseline),
        "targets": len(targets),
        "accepted": len(accepted),
        "candidate_only": len(candidates),
        "remaining_without_accepted": len(targets) - len(accepted),
        "accepted_schools": accepted,
        "candidate_schools": candidates,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ["target_group", "targets", "accepted", "candidate_only", "remaining_without_accepted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
