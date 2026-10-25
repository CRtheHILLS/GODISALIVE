"""test_search — core/search.py parsers on captured fixtures. No network.

FIXTURE NOTES (captured 2026-10-25):
- real captures: commons.json, met_object.json, met_search.json, openalex.json (trimmed), wikidata_search.json,
  wikidata_entity.json (claims trimmed), ia.json, crossref.json, pleiades.rss, wikipedia.json, bing.html (trimmed to 5 li.b_algo).
- HAND-MADE (live endpoint blocked): ddg.html (DDG 202 bot-challenge page), loc.json (loc.gov Cloudflare 403),
  s2.json (Semantic Scholar 429 without key; schema from API docs).
- louvre.html: NOT captured - collections.louvre.fr serves a WADP bot check (429). Louvre engine is best-effort and
  returns {"error": ...} when no result selector matches.
- Met API changed 2026-10: /v1/search retired -> /v1.1/search; objects now expose accessionNumber (no objectNumber).
- Bing returned off-topic results for this IP on 2026-10-25 (structure fine); bing hrefs are ck/a redirects with u=a1+base64.

LIVE SMOKE (2026-10-25): see SMOKE RESULT line below.
SMOKE RESULT 2026-10-25, 'Lachish reliefs British Museum' n=5 -> commons 5 (CC BY-SA 4.0) | wikidata 0 (long phrase has no
  entity match; not an error) | openalex 5. 2/3 engines with results.
  Extra live probe, query 'Lachish' n=3: wikipedia 6 (en+ko), ia 3, met 3 (v1.1), crossref 3, pleiades 3, sefaria 3, youtube 3,
  bing 3 (off-topic results from this IP). FAILED live: ddg (HTTP 202 bot challenge), loc (403 Cloudflare),
  semanticscholar (429 no key), louvre (429 WADP bot check), europeana (no key file, by design).
"""
import json
from pathlib import Path

FX = Path(__file__).resolve().parent / "fixtures"
KEYS = {"engine", "type", "title", "url", "snippet", "license", "extra"}

def _txt(n): return (FX / n).read_text(encoding="utf-8")
def _js(n): return json.loads(_txt(n))

def run(check):
    import core.search as S
    from core.workspace import CONFIG

    allkeys = lambda rs: all(set(r) == KEYS for r in rs)

    ddg = S.parse_ddg(_txt("ddg.html"))
    check("ddg >=3", len(ddg) >= 3, True)
    check("ddg url http", ddg[0]["url"].startswith("http"), True)
    check("ddg no redirect", all("duckduckgo.com/l/" not in r["url"] for r in ddg), True)
    check("ddg first url", ddg[0]["url"], "https://en.wikipedia.org/wiki/Lachish_reliefs")
    check("ddg title", bool(ddg[0]["title"]), True)
    check("ddg snippet stripped", "<b>" in ddg[0]["snippet"], False)
    check("ddg keys", allkeys(ddg), True)
    check("ddg empty", S.parse_ddg(""), [])
    check("bing empty", S.parse_bing("<html></html>"), [])
    bing = S.parse_bing(_txt("bing.html"))
    check("bing >=1", len(bing) >= 1, True)
    check("bing real url", all(r["url"].startswith("http") and "bing.com/ck/a" not in r["url"] for r in bing), True)
    check("bing keys", allkeys(bing), True)

    com = S.parse_commons(_js("commons.json"))
    check("commons >=1", len(com) >= 1, True)
    check("commons type", {r["type"] for r in com}, {"image"})
    pages = list(_js("commons.json")["query"]["pages"].values())
    lic = {p["title"]: p["imageinfo"][0]["extmetadata"].get("LicenseShortName", {}).get("value") for p in pages}
    check("commons license", all(r["license"] == lic[r["title"]] for r in com), True)
    check("commons original", all("upload.wikimedia.org" in r["extra"]["original"] for r in com), True)
    check("commons keys", allkeys(com), True)
    check("commons empty", S.parse_commons({}), [])

    mo = _js("met_object.json")
    met = S.parse_met_object(mo)
    check("met license", met["license"], "CC0" if mo["isPublicDomain"] else "ⓒ Met")
    check("met accession", met["extra"]["accession"], mo.get("objectNumber") or mo.get("accessionNumber"))
    check("met url", met["url"], mo["objectURL"])
    check("met keys", set(met), KEYS)

    oa = S.parse_openalex(_js("openalex.json"))
    check("openalex >=1", len(oa) >= 1, True)
    check("openalex type", {r["type"] for r in oa}, {"paper"})
    check("openalex url", all(r["url"] for r in oa), True)
    check("openalex keys", allkeys(oa), True)

    ent = _js("wikidata_entity.json")["entities"]["Q516354"]
    wd = S.parse_wikidata_entity(ent)
    check("wikidata P217/P195", bool(wd["extra"].get("P217") or wd["extra"].get("P195")), True)
    check("wikidata P18", wd["extra"].get("P18"), "JRSLM 300116 Tel Dan Stele 01.jpg")
    check("wikidata url", wd["url"], "https://www.wikidata.org/wiki/Q516354")
    check("wikidata keys", set(wd), KEYS)

    for name, rs in [("loc", S.parse_loc(_js("loc.json"))), ("ia", S.parse_ia(_js("ia.json"))),
                     ("crossref", S.parse_crossref(_js("crossref.json"))), ("s2", S.parse_s2(_js("s2.json"))),
                     ("pleiades", S.parse_pleiades_rss(_txt("pleiades.rss"))),
                     ("wikipedia", S.parse_wikipedia(_js("wikipedia.json"), "en"))]:
        check(f"{name} >=1", len(rs) >= 1, True)
        check(f"{name} keys", allkeys(rs), True)
        check(f"{name} url", all(r["url"].startswith("http") for r in rs), True)
    loc = S.parse_loc(_js("loc.json"))
    check("loc image_url list", isinstance(loc[0]["extra"]["image_url"], list), True)
    ia = S.parse_ia(_js("ia.json"))
    check("ia url", ia[0]["url"].startswith("https://archive.org/details/"), True)
    pl = S.parse_pleiades_rss(_txt("pleiades.rss"))
    check("pleiades type", pl[0]["type"], "place")
    wp = S.parse_wikipedia(_js("wikipedia.json"), "en")
    check("wikipedia url", wp[0]["url"], "https://en.wikipedia.org/wiki/Lachish_reliefs")
    check("wikipedia no tags", "<" in wp[0]["snippet"], False)
    check("s2 pdf preferred", S.parse_s2(_js("s2.json"))[0]["url"], "https://example.org/lachish.pdf")
    check("bad input empty", [S.parse_loc({}), S.parse_ia({}), S.parse_crossref({}), S.parse_s2({}), S.parse_openalex({}),
                              S.parse_pleiades_rss("not xml"), S.parse_wikipedia({}, "en")], [[]] * 7)

    check("default_engines image", S.default_engines("image"), CONFIG["engines_default"]["image"])
    check("default_engines unknown", S.default_engines("zzz"), CONFIG["engines_default"]["mixed"])
    check("ENGINES has 15", {"ddg", "bing", "wikipedia", "wikidata", "commons", "ia", "met", "loc", "openalex", "crossref",
                             "semanticscholar", "louvre", "pleiades", "sefaria", "youtube"} <= set(S.ENGINES), True)
    check("ENGINES shape", all({"fn", "types", "needs_key", "label"} <= set(v) for v in S.ENGINES.values()), True)

    r = S.search("x", engines=["nonexistent"])
    check("unknown engine", r, {"nonexistent": {"error": "unknown engine"}})

    res = {"ddg": [{"engine": "ddg", "type": "web", "title": "T", "url": "http://u", "snippet": "", "license": "CC0", "extra": {}}],
           "met": {"error": "e"}, "commons": []}
    t = S.format_table(res)
    check("table ddg 1", "ddg 1" in t, True)
    check("table met x", "met ✖" in t, True)
    check("table commons 0", "commons 0" in t, True)
    check("table row", "[ddg] T — http://u (CC0)" in t, True)
