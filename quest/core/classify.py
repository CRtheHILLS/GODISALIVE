#!/usr/bin/env python3
"""분류 추론 — 매체·라이선스·권위·증거 축·구절·언어·중복. 1차 판정일 뿐, 최종 판정은 Peter."""
import re, sys
from urllib.parse import urlparse

from core.license import license_class          # 단일 정의: core/license.py
from core.workspace import ROOT, CONFIG

NEWS = ("nytimes.com", "bbc.com", "bbc.co.uk", "cnn.com", "theguardian.com", "washingtonpost.com", "reuters.com", "apnews.com",
        "haaretz.com", "timesofisrael.com", "jpost.com", "chosun.com", "joongang.co.kr", "donga.com", "hani.co.kr", "khan.co.kr",
        "yna.co.kr", "kbs.co.kr", "sbs.co.kr", "mbc.co.kr", "christianitytoday.com", "foxnews.com", "time.com", "newsweek.com")
ENCYCLOPEDIA = ("wikipedia.org", "wikidata.org", "wikimedia.org", "britannica.com")


def _domain(url: str) -> str:
    try: return (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    except ValueError: return ""


def _in(domain: str, names) -> bool:
    return any(domain == n or domain.endswith("." + n) for n in names)


def default_plugin():
    """config.json 의 plugin 이름으로 quest/plugins/<name>.py 를 불러온다. 실패하면 None."""
    try:
        import importlib
        qdir = str(ROOT / "quest")
        if qdir not in sys.path: sys.path.insert(0, qdir)
        return importlib.import_module(f"plugins.{CONFIG.get('plugin', 'godisalive')}")
    except Exception:
        return None


def authority_tier(url: str, plugin=None) -> int:
    domain = _domain(url)
    plugin = plugin or default_plugin()
    if plugin is not None and hasattr(plugin, "authority_override"):
        t = plugin.authority_override(domain)
        if t is not None: return int(t)
    if re.search(r"\.(museum|edu|gov)$|\.go\.kr$|\.ac\.[a-z]{2}$|\.edu\.[a-z]{2}$|\.gov\.[a-z]{2}$", domain): return 1
    if _in(domain, ENCYCLOPEDIA): return 2
    if _in(domain, NEWS): return 3
    return 4


def grade_ceiling(tier: int) -> str:
    return {1: "A", 2: "B"}.get(tier, "C")


_STOP = {
    "en": "the of and to in is that with for were was are this from by as on at which it an be or".split(),
    "de": "der die und das nicht ist mit den von zu dem ein eine auf für sich des im auch".split(),
    "fr": "le la les des et est une du dans que qui pour pas sur au avec ce il elle par".split(),
    "la": "et in est non ad cum quod ut sed qui quae ab ex de per sunt esse atque".split(),
}


def detect_lang(text: str) -> str:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters: return "und"
    n = len(letters)
    cnt = lambda lo, hi: sum(1 for c in letters if lo <= c <= hi)
    if cnt("가", "힣") + cnt("ㄱ", "ㆎ") > 0.3 * n: return "ko"
    if cnt("֐", "׿") > 0.3 * n: return "he"
    if cnt("Ͱ", "Ͽ") + cnt("ἀ", "῿") > 0.3 * n: return "el"
    if cnt("A", "ɏ") > 0.5 * n:
        words = re.findall(r"[^\W\d_]+", text.lower())
        scores = {k: sum(1 for w in words if w in sw) for k, sw in _STOP.items()}
        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 0: return best
    return "und"


def media_of(item: dict) -> str:
    return item.get("type") or item.get("kind") or "text"


def _norm_url(url: str) -> str:
    p = urlparse(url or "")
    host = (p.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host + p.path.rstrip("/")


def classify_items(items: list, plugin=None) -> list:
    plugin = plugin or default_plugin()
    seen_sha, seen_url, rows = {}, {}, []
    for i, it in enumerate(items):
        url = it.get("url") or it.get("final_url") or ""
        ref = it.get("id") or url or f"item-{i}"
        title = it.get("title") or ""
        lic = it.get("license")
        if not lic and plugin is not None and hasattr(plugin, "license_hint"): lic = plugin.license_hint(url)
        cls, ok = license_class(lic)
        text = " ".join(str(x) for x in (title, it.get("snippet"), (it.get("text") or "")[:2000]) if x)
        tier = authority_tier(url, plugin) if url else 4
        dup = None
        sha, nu = it.get("sha256"), (_norm_url(url) if url else None)
        if sha and sha in seen_sha: dup = seen_sha[sha]
        elif nu and nu in seen_url: dup = seen_url[nu]
        if sha: seen_sha.setdefault(sha, ref)
        if nu: seen_url.setdefault(nu, ref)
        rows.append({"ref": ref, "media": media_of(it), "license_class": cls, "commercial_ok": ok, "authority_tier": tier,
                     "grade_ceiling": grade_ceiling(tier),
                     "axis": plugin.axis(text) if plugin is not None and hasattr(plugin, "axis") else None,
                     "verses": plugin.tag_verses(text) if plugin is not None and hasattr(plugin, "tag_verses") else [],
                     "lang": detect_lang(text), "dup_of": dup, "title": title})
    return rows


def format_triage(rows: list) -> str:
    out = [f"{'#':>2} {'매체':<7} {'라이선스':<14} {'등급':<5} {'축':<12} {'구절':<18} 제목"]
    for i, r in enumerate(rows, 1):
        com = {True: "✓", False: "✗", None: "?"}[r["commercial_ok"]]
        lic = f"{r['license_class']}({com})"
        verses = ",".join(r["verses"][:3])
        dup = f" [중복→{r['dup_of'][:20]}]" if r.get("dup_of") else ""
        out.append(f"{i:>2} {r['media']:<7} {lic:<14} {r['authority_tier']}/{r['grade_ceiling']:<3} {(r['axis'] or '-'):<12} {verses:<18} {r['title'][:50]}{dup}")
    return "\n".join(out)
