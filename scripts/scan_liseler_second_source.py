from __future__ import annotations

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from refresh_student_counts import load_rows, load_existing, current_count

BASE = "https://liseler.com.tr/"
DATA_DIR = Path("data")
OVERRIDES = DATA_DIR / "student-overrides.json"
OUT = DATA_DIR / "liseler-com-tr-second-pass.json"
TIMEOUT = 8
WORKERS = 20

HIGH_SCHOOL_TYPES = {
    "Anadolu Lisesi","Mesleki ve Teknik Anadolu Lisesi","Anadolu İmam Hatip Lisesi",
    "Çok Programlı Anadolu Lisesi","Fen Lisesi","Lise","Spor Lisesi",
    "Güzel Sanatlar Lisesi","Sosyal Bilimler Lisesi","Açık/Akşam Lisesi",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PDRKampusNormBot/3.0; +https://norm.pdrkampus.com)"}

def norm(s):
    s=(s or "").strip().lower().replace("ı","i")
    s=unicodedata.normalize("NFKD",s)
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def get(url):
    r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def unresolved():
    rows=load_rows(); existing=load_existing(); verified=set((existing.get("schools") or {}).keys())
    out=[]
    for row in rows:
        if (row.get("okul_turu") or "").strip() not in HIGH_SCHOOL_TYPES: continue
        code=str(row.get("kurum_kodu") or "").strip()
        if not code or code in verified: continue
        if current_count(row) not in (None,0): continue
        out.append(row)
    if len(out)!=235:
        raise RuntimeError(f"Expected exactly 235 unresolved high schools, got {len(out)}")
    return out

def total_pages(path):
    text=BeautifulSoup(get(BASE+path+"?sayfa=1&view=list"),"html.parser").get_text(" ",strip=True)
    m=re.search(r"sayfa\s+1\s*/\s*(\d+)",text,re.I)
    return int(m.group(1)) if m else 1

def extract_detail_urls(html):
    soup=BeautifulSoup(html,"html.parser")
    out=[]
    for a in soup.find_all("a",href=True):
        href=urljoin(BASE,a["href"])
        if "liseler.com.tr/" not in href: continue
        if not re.search(r"-\d+-(?:obp|lgs)(?:$|[?#])",href): continue
        node=a
        for _ in range(7):
            if node.parent is None: break
            node=node.parent
            h=node.find(["h2","h3","h4"])
            if h:
                txt=node.get_text(" ",strip=True)
                if len(txt)<1500:
                    out.append((h.get_text(" ",strip=True),txt,href))
                    break
    return out

def build_index():
    jobs=[]
    for path in ("liseler.php","obp-liseler.php"):
        pages=total_pages(path)
        for p in range(1,pages+1):
            jobs.append(f"{BASE}{path}?sayfa={p}&view=list")
    cards=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs=[ex.submit(get,u) for u in jobs]
        for i,f in enumerate(as_completed(futs),1):
            try: cards.extend(extract_detail_urls(f.result()))
            except Exception as e: print("LIST_FAIL",repr(e))
            if i%50==0: print("pages",i,"/",len(jobs),"cards",len(cards))
    idx={}
    seen=set()
    for name,txt,url in cards:
        if url in seen: continue
        seen.add(url)
        idx.setdefault(norm(name),[]).append((txt,url))
    return idx

def pick(row,idx):
    cands=idx.get(norm(row.get("okul_adi") or ""),[])
    prov=norm(row.get("il") or ""); dist=norm(row.get("ilce") or "")
    scored=[]
    for txt,url in cands:
        t=norm(txt); score=(3 if dist and dist in t else 0)+(2 if prov and prov in t else 0)
        scored.append((score,url))
    scored.sort(reverse=True)
    if not scored or scored[0][0]<2: return None
    if len(scored)>1 and scored[0][0]==scored[1][0]: return None
    return scored[0][1]

def parse_count(url):
    text=BeautifulSoup(get(url),"html.parser").get_text(" ",strip=True)
    vals=[]
    for pat in (r"Öğrenci\s+Sayısı\s*:\s*(\d{1,5})",r"(\d{1,5})\s+Öğrenci\b",r"Öğrenci\s+(\d{1,5})\s+Derslik"):
        vals += [int(x) for x in re.findall(pat,text,re.I)]
    vals=[x for x in vals if 0<x<=10000]
    return max(vals) if vals else None

def main():
    targets=unresolved()
    print("targets",len(targets))
    idx=build_index()
    print("indexed_names",len(idx))
    found={}; misses=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={}
        for row in targets:
            url=pick(row,idx)
            if not url:
                misses.append({"kurum_kodu":str(row.get("kurum_kodu") or ""),"okul_adi":row.get("okul_adi"),"reason":"no_unique_match"})
                continue
            futs[ex.submit(parse_count,url)]=(row,url)
        for f in as_completed(futs):
            row,url=futs[f]; code=str(row.get("kurum_kodu") or "")
            try: count=f.result()
            except Exception:
                count=None
            if count:
                found[code]={"student_count":count,"school":row.get("okul_adi"),"province":row.get("il"),"district":row.get("ilce"),"school_type":row.get("okul_turu"),"source":"liseler.com.tr","source_url":url}
            else:
                misses.append({"kurum_kodu":code,"okul_adi":row.get("okul_adi"),"reason":"count_not_found","source_url":url})
    existing=load_existing()
    schools=existing.setdefault("schools",{})
    for code,item in found.items():
        prev=schools.get(code)
        if prev and isinstance(prev,dict):
            old=prev.get("student_count")
            try: old=int(old)
            except Exception: old=None
            if old and old>item["student_count"]:
                item["student_count"]=old
        schools[code]=item
    OVERRIDES.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    result={"targets":len(targets),"recovered":len(found),"remaining":len(targets)-len(found),"schools":found,"unresolved":misses}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("targets","recovered","remaining")},ensure_ascii=False))

if __name__=="__main__":
    main()
