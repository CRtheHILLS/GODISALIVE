#!/usr/bin/env python3
"""QUEST 검색 엔진 레지스트리 — 엔진별 파서 + search() + format_table().

모든 엔진 함수는 예외를 밖으로 던지지 않는다: 실패하면 {"error": "<name>: <ExcType>: <msg>"}.
Result = {engine, type, title, url, snippet, license, extra} — 7개 키는 항상 채운다.
"""
import base64, html as _html, json, re, shutil, subprocess, sys
import urllib.parse as up
import xml.etree.ElementTree as ET
from pathlib import Path

try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from core.http import fetch, domain_of, polite_delay, robots_allowed
from core.workspace import CONFIG, ROOT

# ── 공용 헬퍼 ────────────────────────────────────────────────────────────
def _res(engine, typ, title, url, snippet="", license=None, extra=None) -> dict:
    return {"engine": engine, "type": typ, "title": (title or "").strip(), "url": url or "",
            "snippet": (snippet or "").strip(), "license": license or None, "extra": extra or {}}

def _strip(s) -> str:
    if s is None: return ""
    if isinstance(s, list): s = " ".join(str(x) for x in s)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", str(s)))).strip()

def _first(v):
    if isinstance(v, list): return v[0] if v else None
    return v

def _get(url: str, **kw) -> dict:
    r = fetch(url, retries=kw.pop("retries", 1), **kw)
    if not r["ok"]: raise RuntimeError(r["error"] or f"HTTP {r['status']}")
    return r

def _getj(url: str, **kw):
    r = _get(url, **kw)
    return json.loads(r["text"] or r["content"].decode("utf-8", "replace"))

def _safe(name):
    """엔진 함수 → 예외를 {"error"}로 바꾸는 래퍼."""
    def deco(fn):
        def wrapper(query, lang="en", n=10):
            try: return fn(query, lang, n)
            except Exception as e: return {"error": f"{name}: {e.__class__.__name__}: {str(e)[:200]}"}
        wrapper.__name__ = f"engine_{name}"; return wrapper
    return deco

def _key_path(name: str) -> Path:
    return ROOT / CONFIG["secrets"][name]

# ── 파서 ─────────────────────────────────────────────────────────────────
def parse_ddg(html: str) -> list:
    if not html: return []
    from bs4 import BeautifulSoup
    out = []
    for a in BeautifulSoup(html, "lxml").select("a.result__a"):
        href = a.get("href") or ""
        if href.startswith("//"): href = "https:" + href
        if "duckduckgo.com/l/" in href:
            href = up.unquote(up.parse_qs(up.urlparse(href).query).get("uddg", [""])[0])
        if not href.startswith("http"): continue
        box = a.find_parent(class_="result")
        sn = box.select_one(".result__snippet") if box else None
        out.append(_res("ddg", "web", a.get_text(" ", strip=True), href, sn.get_text(" ", strip=True) if sn else ""))
    return out

def _bing_url(href: str) -> str:
    if "bing.com/ck/a" not in href: return href
    u = up.parse_qs(up.urlparse(href).query).get("u", [""])[0]
    if u.startswith("a1"):
        try:
            b = u[2:]; return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "replace")
        except Exception: pass
    return href

def parse_bing(html: str) -> list:
    if not html: return []
    from bs4 import BeautifulSoup
    out = []
    for li in BeautifulSoup(html, "lxml").select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a or not a.get("href"): continue
        p = li.select_one(".b_caption p") or li.select_one("p")
        out.append(_res("bing", "web", a.get_text(" ", strip=True), _bing_url(a["href"]), p.get_text(" ", strip=True) if p else ""))
    return out

def parse_commons(data: dict) -> list:
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    out = []
    for p in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        em = ii.get("extmetadata") or {}
        val = lambda k: _strip((em.get(k) or {}).get("value"))
        out.append(_res("commons", "image", p.get("title", ""), ii.get("descriptionurl") or "", val("ImageDescription"),
                        val("LicenseShortName") or None,
                        {"artist": val("Artist"), "credit": val("Credit"), "description": val("ImageDescription"),
                         "thumb": ii.get("thumburl"), "original": ii.get("url"), "width": ii.get("width"),
                         "height": ii.get("height"), "mime": ii.get("mime")}))
    return out

def parse_met_object(obj: dict) -> dict:
    acc = obj.get("objectNumber") or obj.get("accessionNumber")        # API renamed the field in 2026-10
    bits = [obj.get("objectName"), obj.get("culture"), obj.get("period"), obj.get("department")]
    return _res("met", "object", obj.get("title"), obj.get("objectURL"), " · ".join(b for b in bits if b),
                "CC0" if obj.get("isPublicDomain") else "ⓒ Met",
                {"accession": acc, "culture": obj.get("culture"), "period": obj.get("period"),
                 "primaryImage": obj.get("primaryImage"), "objectURL": obj.get("objectURL")})

def parse_openalex(data: dict) -> list:
    out = []
    for w in (data or {}).get("results") or []:
        oa = w.get("open_access") or {}
        loc = w.get("primary_location") or {}
        url = oa.get("oa_url") or w.get("doi") or loc.get("landing_page_url") or w.get("id") or ""
        auth = [(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []]
        out.append(_res("openalex", "paper", w.get("display_name") or w.get("title"), url,
                        f"{w.get('publication_year') or ''} · {', '.join(a for a in auth if a)[:120]}", oa.get("oa_status"),
                        {"year": w.get("publication_year"), "authors": [a for a in auth if a], "doi": w.get("doi")}))
    return out

def _claim_values(entity: dict, pid: str) -> list:
    vals = []
    for c in (entity.get("claims") or {}).get(pid, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict): v = v.get("id")
        if v: vals.append(v)
    return vals

def parse_wikidata_entity(entity: dict) -> dict:
    labels, descs = entity.get("labels") or {}, entity.get("descriptions") or {}
    label = (labels.get("ko") or labels.get("en") or {}).get("value") or entity.get("id", "")
    desc = (descs.get("en") or descs.get("ko") or {}).get("value", "")
    extra = {}
    if (v := _claim_values(entity, "P18")): extra["P18"] = v[0]
    if (v := _claim_values(entity, "P195")): extra["P195"] = v
    if (v := _claim_values(entity, "P217")): extra["P217"] = v
    if (v := _claim_values(entity, "P373")): extra["P373"] = v[0]
    extra["qid"] = entity.get("id")
    return _res("wikidata", "object", label, f"https://www.wikidata.org/wiki/{entity.get('id', '')}", desc, "CC0", extra)

def parse_loc(data: dict) -> list:
    out = []
    for r in (data or {}).get("results") or []:
        url = r.get("id") or r.get("url") or ""
        if not url.startswith("http"): continue
        imgs = r.get("image_url") or []
        if isinstance(imgs, str): imgs = [imgs]
        rights = _strip(r.get("rights") or r.get("rights_advisory")) or None
        out.append(_res("loc", "image", r.get("title"), url, _strip(r.get("description")), rights,
                        {"image_url": imgs, "original_format": r.get("original_format"), "date": r.get("date")}))
    return out

def parse_ia(data: dict) -> list:
    out = []
    for d in ((data or {}).get("response") or {}).get("docs") or []:
        ident = d.get("identifier")
        if not ident: continue
        mt = d.get("mediatype")
        typ = {"movies": "video", "image": "image"}.get(mt, "text")
        out.append(_res("ia", typ, d.get("title"), f"https://archive.org/details/{ident}", _strip(d.get("description"))[:300],
                        d.get("licenseurl"), {"identifier": ident, "mediatype": mt}))
    return out

def parse_crossref(data: dict) -> list:
    out = []
    for it in ((data or {}).get("message") or {}).get("items") or []:
        title = _strip(_first(it.get("title")))
        auth = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in it.get("author") or []]
        year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        lic = _first([l.get("URL") for l in it.get("license") or []])
        out.append(_res("crossref", "paper", title, it.get("URL") or (f"https://doi.org/{it['DOI']}" if it.get("DOI") else ""),
                        f"{_strip(_first(it.get('container-title')))} {year or ''}".strip(), lic,
                        {"year": year, "authors": auth, "doi": it.get("DOI"), "type": it.get("type")}))
    return [r for r in out if r["url"]]

def parse_s2(data: dict) -> list:
    out = []
    for p in (data or {}).get("data") or []:
        pdf = (p.get("openAccessPdf") or {}).get("url")
        url = pdf or p.get("url") or ""
        if not url: continue
        auth = [a.get("name") for a in p.get("authors") or [] if a.get("name")]
        out.append(_res("semanticscholar", "paper", p.get("title"), url, f"{p.get('year') or ''} · {', '.join(auth)[:120]}",
                        "OA " + ((p.get("openAccessPdf") or {}).get("status") or "") if pdf else None,
                        {"year": p.get("year"), "authors": auth, "doi": (p.get("externalIds") or {}).get("DOI"), "s2_url": p.get("url")}))
    return out

def parse_pleiades_rss(xml: str) -> list:
    try: root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except Exception: return []
    out = []
    for it in root.iter():
        if it.tag.rsplit("}", 1)[-1] != "item": continue
        g = lambda t: next((_strip(c.text) for c in it if c.tag.rsplit("}", 1)[-1] == t), "")
        link = g("link") or it.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
        if not link: continue
        out.append(_res("pleiades", "place", g("title"), link, g("description")[:300], g("rights") or None,
                        {"subject": g("subject"), "date": g("date"), "kind": g("type")}))
    return out

def parse_wikipedia(data: dict, lang: str) -> list:
    out = []
    for s in ((data or {}).get("query") or {}).get("search") or []:
        t = s.get("title", "")
        out.append(_res("wikipedia", "text", t, f"https://{lang}.wikipedia.org/wiki/" + up.quote(t.replace(" ", "_")),
                        _strip(s.get("snippet")), "CC BY-SA 4.0", {"lang": lang, "pageid": s.get("pageid"), "wordcount": s.get("wordcount")}))
    return out

def _parse_louvre(html: str) -> list:
    from bs4 import BeautifulSoup
    out, seen = [], set()
    for a in BeautifulSoup(html or "", "lxml").select("a[href*='/ark:/']"):
        href = up.urljoin("https://collections.louvre.fr/", a["href"])
        t = a.get_text(" ", strip=True)
        if href in seen or not t: continue
        seen.add(href); out.append(_res("louvre", "object", t, href, "", "ⓒ Louvre"))
    return out

# ── 엔진 함수 ────────────────────────────────────────────────────────────
@_safe("ddg")
def _e_ddg(q, lang, n):
    if not robots_allowed("https://html.duckduckgo.com/html/"): raise RuntimeError("robots.txt 금지")
    r = _get("https://html.duckduckgo.com/html/", method="POST", data={"q": q, "kl": "wt-wt"}, retries=0)
    res = parse_ddg(r["text"])[:n]
    if not res: raise RuntimeError(f"0건 — 봇 차단 또는 구조 변경 (HTTP {r['status']})")
    return res

@_safe("bing")
def _e_bing(q, lang, n):
    if not robots_allowed("https://www.bing.com/search?q=x"): raise RuntimeError("robots.txt 금지")
    r = _get("https://www.bing.com/search", params={"q": q, "setlang": "en"})
    res = parse_bing(r["text"])[:n]
    if not res: raise RuntimeError("0건 — 구조 변경 가능")
    return res

@_safe("wikipedia")
def _e_wikipedia(q, lang, n):
    d = _getj(f"https://{lang}.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": q, "srlimit": n, "format": "json"})
    return parse_wikipedia(d, lang)

@_safe("wikidata")
def _e_wikidata(q, lang, n):
    d = _getj("https://www.wikidata.org/w/api.php", params={"action": "wbsearchentities", "search": q, "language": "en", "limit": min(n, 5), "format": "json"})
    ids = [s["id"] for s in d.get("search") or []]
    if not ids: return []
    d = _getj("https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels|descriptions|sitelinks",
                                                              "languages": "en|ko", "format": "json"})
    ents = d.get("entities") or {}
    return [parse_wikidata_entity(ents[i]) for i in ids if i in ents]

@_safe("commons")
def _e_commons(q, lang, n):
    d = _getj("https://commons.wikimedia.org/w/api.php", params={"action": "query", "format": "json", "generator": "search", "gsrsearch": q,
              "gsrnamespace": 6, "gsrlimit": n, "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1600})
    return parse_commons(d)

@_safe("ia")
def _e_ia(q, lang, n):
    d = _getj("https://archive.org/advancedsearch.php", params=[("q", q), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "mediatype"),
              ("fl[]", "licenseurl"), ("fl[]", "description"), ("rows", n), ("output", "json")])
    return parse_ia(d)

@_safe("met")
def _e_met(q, lang, n):
    d = _getj("https://collectionapi.metmuseum.org/public/collection/v1.1/search", params={"hasImages": "true", "q": q, "limit": n})
    out = []
    for oid in (d.get("objectIDs") or [])[:n]:
        polite_delay("collectionapi.metmuseum.org")
        try: out.append(parse_met_object(_getj(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")))
        except Exception: continue
    return out

@_safe("loc")
def _e_loc(q, lang, n):
    return parse_loc(_getj("https://www.loc.gov/search/", params={"q": q, "fo": "json", "c": n}, retries=0))

@_safe("openalex")
def _e_openalex(q, lang, n):
    return parse_openalex(_getj("https://api.openalex.org/works", params={"search": q, "per-page": n}))

@_safe("crossref")
def _e_crossref(q, lang, n):
    return parse_crossref(_getj("https://api.crossref.org/works", params={"query": q, "rows": n}))

@_safe("semanticscholar")
def _e_s2(q, lang, n):
    return parse_s2(_getj("https://api.semanticscholar.org/graph/v1/paper/search", params={"query": q, "limit": n,
                    "fields": "title,url,year,openAccessPdf,externalIds,authors"}, retries=0))

@_safe("louvre")
def _e_louvre(q, lang, n):
    if not robots_allowed("https://collections.louvre.fr/recherche?q=x"): raise RuntimeError("robots.txt 금지")
    r = _get("https://collections.louvre.fr/recherche", params={"q": q}, retries=0)
    res = _parse_louvre(r["text"])[:n]
    if not res: raise RuntimeError("louvre: 셀렉터 미확인 (봇 차단 또는 구조 변경)")
    return res

@_safe("pleiades")
def _e_pleiades(q, lang, n):
    r = _get("https://pleiades.stoa.org/search_rss", params={"SearchableText": q})
    return parse_pleiades_rss(r["text"])[:n]

@_safe("sefaria")
def _e_sefaria(q, lang, n):
    d = _getj("https://www.sefaria.org/api/search-wrapper", method="POST", json_body={"query": q, "type": "text", "size": n}, retries=0)
    out = []
    for h in ((d.get("hits") or {}).get("hits")) or []:
        src = h.get("_source") or {}
        ref = src.get("ref") or h.get("_id") or ""
        if not ref: continue
        hl = " ".join(sum(((h.get("highlight") or {}).values()), [])) if isinstance(h.get("highlight"), dict) else ""
        out.append(_res("sefaria", "text", ref, "https://www.sefaria.org/" + up.quote(ref.replace(" ", "_"), safe="_.:,-()"), _strip(hl)[:300],
                        None, {"version": src.get("version"), "lang": src.get("lang")}))
    return out

def _yt_dlp():
    p = Path.home() / ".local" / "bin" / "yt-dlp.exe"
    return str(p) if p.exists() else shutil.which("yt-dlp")

@_safe("youtube")
def _e_youtube(q, lang, n):
    exe = _yt_dlp()
    if not exe: raise RuntimeError("yt-dlp 없음")
    p = subprocess.run([exe, "--ignore-config", "--no-cookies-from-browser", f"ytsearch{n}:{q}", "--flat-playlist", "--encoding", "utf-8", "--print", "%(id)s|%(title)s|%(channel)s|%(duration)s"],
                       capture_output=True, timeout=90)
    if p.returncode != 0 and not p.stdout: raise RuntimeError(p.stderr.decode("utf-8", "replace")[-200:])
    out = []
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split("|")
        if len(parts) < 4 or not parts[0]: continue
        vid, dur, chan = parts[0], parts[-1], parts[-2]; title = "|".join(parts[1:-2])
        out.append(_res("youtube", "video", title, f"https://www.youtube.com/watch?v={vid}", f"{chan} · {dur}s", None, {"channel": chan, "duration": dur, "id": vid}))
    return out

def _keyed(name, label, builder):
    @_safe(name)
    def fn(q, lang, n):
        kp = _key_path(name)
        if not kp.exists(): return {"error": f"키 없음: {CONFIG['secrets'][name]}"}
        return builder(q, n, kp.read_text(encoding="utf-8").strip())
    return fn

def _europeana(q, n, key):
    d = _getj("https://api.europeana.eu/record/v2/search.json", params={"wskey": key, "query": q, "rows": n})
    return [_res("europeana", "object", _first(it.get("title")), it.get("guid") or "", _strip(_first(it.get("dcDescription"))),
                 _first(it.get("rights")), {"image": _first(it.get("edmPreview")), "provider": _first(it.get("dataProvider"))}) for it in d.get("items") or []]

def _smithsonian(q, n, key):
    d = _getj("https://api.si.edu/openaccess/api/v1.0/search", params={"api_key": key, "q": q, "rows": n})
    out = []
    for r in ((d.get("response") or {}).get("rows")) or []:
        c = r.get("content") or {}
        out.append(_res("smithsonian", "object", r.get("title"), (c.get("descriptiveNonRepeating") or {}).get("record_link") or "", "",
                        ((c.get("descriptiveNonRepeating") or {}).get("metadata_usage") or {}).get("access"), {"id": r.get("id")}))
    return out

_e_europeana = _keyed("europeana", "Europeana", _europeana)
_e_smithsonian = _keyed("smithsonian", "Smithsonian", _smithsonian)

def _eng(fn, types, label, needs_key=None, multilang=False):
    return {"fn": fn, "types": types, "needs_key": needs_key, "label": label, "multilang": multilang}

ENGINES = {
    "ddg": _eng(_e_ddg, ["web"], "DuckDuckGo"),
    "bing": _eng(_e_bing, ["web"], "Bing"),
    "wikipedia": _eng(_e_wikipedia, ["text", "place"], "Wikipedia", multilang=True),
    "wikidata": _eng(_e_wikidata, ["object", "place"], "Wikidata"),
    "commons": _eng(_e_commons, ["image"], "Wikimedia Commons"),
    "ia": _eng(_e_ia, ["text", "video", "image"], "Internet Archive"),
    "met": _eng(_e_met, ["object", "image"], "Met Museum"),
    "loc": _eng(_e_loc, ["image"], "Library of Congress"),
    "openalex": _eng(_e_openalex, ["paper"], "OpenAlex"),
    "crossref": _eng(_e_crossref, ["paper"], "Crossref"),
    "semanticscholar": _eng(_e_s2, ["paper"], "Semantic Scholar"),
    "louvre": _eng(_e_louvre, ["object"], "Louvre"),
    "pleiades": _eng(_e_pleiades, ["place"], "Pleiades"),
    "sefaria": _eng(_e_sefaria, ["text"], "Sefaria"),
    "youtube": _eng(_e_youtube, ["video"], "YouTube (yt-dlp)"),
    "europeana": _eng(_e_europeana, ["object", "image"], "Europeana", needs_key=CONFIG["secrets"].get("europeana")),
    "smithsonian": _eng(_e_smithsonian, ["object", "image"], "Smithsonian", needs_key=CONFIG["secrets"].get("smithsonian")),
}

# ── 공개 API ─────────────────────────────────────────────────────────────
def default_engines(goal_type: str) -> list:
    d = CONFIG["engines_default"]
    return list(d.get(goal_type) or d["mixed"])

def search(query: str, engines=None, langs=("en", "ko"), n: int = 10, goal_type: str = "mixed", rank=None) -> dict:
    names = list(engines) if engines else default_engines(goal_type)
    if rank:
        try: names = list(rank(names, goal_type))
        except Exception: pass
    out = {}
    for name in names:
        spec = ENGINES.get(name)
        if not spec: out[name] = {"error": "unknown engine"}; continue
        try:
            if spec["multilang"]:
                res, errs = [], []
                for lang in langs:
                    r = spec["fn"](query, lang, n)
                    if isinstance(r, dict): errs.append(r["error"])
                    else: res += r
                out[name] = res if (res or not errs) else {"error": errs[0]}
            else:
                out[name] = spec["fn"](query, langs[0] if langs else "en", n)
        except Exception as e:
            out[name] = {"error": f"{name}: {e.__class__.__name__}: {e}"}
    return out

def format_table(results: dict, limit: int = 12) -> str:
    parts, lists = [], []
    for name, r in results.items():
        if isinstance(r, dict):
            msg = str(r.get("error", "")); msg = "키 없음" if msg.startswith("키 없음") else msg[:60]
            parts.append(f"{name} ✖ {msg}")
        else:
            parts.append(f"{name} {len(r)}"); lists.append(list(r))
    rows = []
    for i in range(max((len(l) for l in lists), default=0)):          # 엔진 번갈아 — 한 엔진이 표를 독점하지 않게
        for l in lists:
            if i < len(l): rows.append(l[i])
    lines = [" · ".join(parts)]
    for r in rows[:limit]:
        lic = f" ({r['license']})" if r.get("license") else ""
        lines.append(f"[{r['engine']}] {r['title']} — {r['url']}{lic}")
    return "\n".join(lines)
