# 스모크 기록 (2026-10-25, 실제 네트워크):
#  - read_url("https://en.wikipedia.org/wiki/Lachish_reliefs") → via=direct, status 200, text 20571자, 링크 620·이미지 5, error None
#  - grab(Commons 500px 썸네일 Lachish_Relief,_British_Museum_1.jpg, source_page=Commons 파일 페이지) → 83,773 B, kind image,
#    license "CC BY-SA 4.0", commercial_ok True, credit "Photograph by Mike Peel ..., Own work" (license_for 성공)
#  - storage.login/upload 는 Railway 에 실행하지 않음 (Task 6 에서 Peter 가)
"""Task 3 테스트 — read · grab · storage. 네트워크 없음, 실제 assets/catalog.json 건드리지 않음."""
import io, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

def run(check):
    from core import read as R, grab as G, storage as S
    html = (HERE / "fixtures" / "article.html").read_text(encoding="utf-8")
    title, text, links, images = R.extract_main(html, "https://ex.org/p/1")
    check("extract title", title, "The Siege of Lachish")
    check("extract first sentence", "Sennacherib besieged the Judean city" in text, True)
    check("extract no aside", "광고" in text, False)
    check("extract text length", len(text) >= 800, True)
    check("extract img rel", images[0]["url"], "https://ex.org/p/img/a.jpg")
    check("extract img abs", images[1]["url"], "https://cdn.example.org/b.png")
    check("extract link abs", any(l["url"] == "https://ex.org/related/nineveh" for l in links), True)

    check("is_pdf magic", R.is_pdf(b"%PDF-1.7 xx", "text/html", "x.pdf"), True)
    check("is_pdf ctype", R.is_pdf(b"<html>", "application/pdf", "x"), True)
    check("is_pdf ext only", R.is_pdf(b"<html>", "text/html", "x.pdf"), False)

    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(width=200, height=200); buf = io.BytesIO(); w.write(buf)
    t, n = R.pdf_text(buf.getvalue())
    check("pdf_text", (isinstance(t, str), n), (True, 1))

    p = R.read_url("http://127.0.0.1:9/x")
    check("read_url error", bool(p["error"]), True)
    check("read_url via", bool(p["via"]), True)
    check("read_url keys", sorted(p), sorted(["url", "final_url", "status", "title", "text", "links", "images", "via", "path", "error"]))
    with tempfile.TemporaryDirectory() as td:
        sp = R.save_page({**p, "title": "t", "text": "본문"}, Path(td), 3)
        check("save_page name", sp.name.startswith("003-") and sp.suffix == ".txt", True)

    check("sniff image", G.sniff_kind("https://a/b.jpg", None), "image")
    check("sniff iiif", G.sniff_kind("https://a/manifest.json", "application/ld+json"), "iiif")
    check("sniff video", G.sniff_kind("https://www.youtube.com/watch?v=x", None), "video")
    check("sniff pdf", G.sniff_kind("https://a/b.pdf", "application/pdf"), "pdf")
    man = {"sequences": [{"canvases": [{"images": [{"resource": {"service": {"@id": "https://iiif.ex.org/img/1"}}}]}]}]}
    check("iiif v2", G.iiif_image_urls(man), ["https://iiif.ex.org/img/1/full/max/0/default.jpg"])
    man3 = {"items": [{"items": [{"items": [{"body": {"service": [{"id": "https://iiif.ex.org/img/2"}]}}]}]}]}
    check("iiif v3", G.iiif_image_urls(man3), ["https://iiif.ex.org/img/2/full/max/0/default.jpg"])

    from PIL import Image
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as src:
        td = Path(td); img = Path(src) / "t.png"
        Image.new("RGB", (40, 40), (200, 30, 30)).save(img)
        e = G.grab(img.as_uri(), td, limits={"image_mb": 1}, license_hint="CC BY-SA 4.0")
        check("grab kind", e.get("kind"), "image")
        check("grab sha", len(e.get("sha256", "")), 64)
        check("grab license ok", (e.get("license"), e.get("commercial_ok")), ("CC BY-SA 4.0", True))
        check("grab file exists", Path(e["path"]).exists(), True)
        check("manifest 1", len(G.load_manifest(td)), 1)
        e2 = G.grab(img.as_uri(), td, limits={"image_mb": 1})
        check("grab dup", e2.get("meta", {}).get("duplicate"), True)
        check("manifest still 1", len(G.load_manifest(td)), 1)
        big = Path(src) / "big.jpg"; big.write_bytes(b"\xff\xd8" + b"0" * (2 * 1024 * 1024))
        td2 = td / "b"; td2.mkdir()
        r = G.grab(big.as_uri(), td2, limits={"image_mb": 1})
        check("limit error", "한도 초과" in r.get("error", ""), True)
        check("no partial", [x.name for x in td2.iterdir() if x.name != "manifest.json"], [])

    check("next id", S.next_asset_id({"assets": [{"id": "img-0003"}]}, "img"), "img-0004")
    check("next id empty", S.next_asset_id({"assets": [{"id": "img-0003"}]}, "doc"), "doc-0001")
    with tempfile.TemporaryDirectory() as td:
        cat = Path(td) / "catalog.json"; cat.write_text('{"assets": []}', encoding="utf-8")
        entry = {"id": "ima-1", "path": str(S.ROOT / "assets" / "cache" / "x.jpg"), "license": "CC0", "commercial_ok": True}
        aid = S.register_asset(entry, title="t", source="s", source_url="u", railway_path="/srv/x", evidence_id=None,
                               verses=["v"], credit="c", catalog_path=cat)
        row = json.loads(cat.read_text(encoding="utf-8"))["assets"][0]
        check("register id", aid, "img-0001")
        check("register keys", sorted(row), sorted(["id", "title", "source", "source_url", "license", "commercial_ok", "credit",
                                                    "railway_path", "local_cache", "evidence_id", "verses", "added"]))
        check("local_cache rel", row["local_cache"], "assets/cache/x.jpg")
