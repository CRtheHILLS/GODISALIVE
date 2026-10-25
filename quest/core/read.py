#!/usr/bin/env python3
"""QUEST 읽기 — 본문 추출 · PDF · 웨이백 폴백 · (선택) JS 렌더. 예외를 밖으로 던지지 않는다: read_url은 항상 Page dict."""
import io, re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.http import fetch, robots_allowed, wayback_latest, UAS
from core.workspace import now, slugify

NOISE = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg"]
PW_MSG = "Playwright 미설치: pip install playwright && playwright install chromium (또는 gstack browse 스킬)"

def _page(url, **kw) -> dict:
    p = {"url": url, "final_url": url, "status": 0, "title": "", "text": "", "links": [], "images": [],
         "via": "direct", "path": None, "error": None}
    p.update(kw); return p

def _soup(html):
    try: return BeautifulSoup(html, "lxml")
    except Exception: return BeautifulSoup(html, "html.parser")

def _collect(root, base_url, want_links=True, want_images=True):
    links, images, seen_l, seen_i = [], [], set(), set()
    if want_links:
        for a in root.find_all("a", href=True):
            u = urljoin(base_url, a["href"].strip())
            if not u.startswith(("http://", "https://")) or u in seen_l: continue
            seen_l.add(u); links.append({"text": a.get_text(" ", strip=True)[:120], "url": u})
    if want_images:
        for im in root.find_all("img"):
            src = im.get("src") or im.get("data-src") or ""
            if not src.strip() or src.startswith("data:"): continue
            u = urljoin(base_url, src.strip())
            if u in seen_i: continue
            seen_i.add(u); images.append({"url": u, "alt": (im.get("alt") or "").strip()})
    return links, images

def extract_main(html: str, base_url: str, want_links: bool = True, want_images: bool = True):
    """→ (title, text, links, images). 링크·이미지는 본문 블록 안에서 우선, 없으면 문서 전체."""
    soup = _soup(html or "")
    h1 = soup.find("h1")
    title = (h1.get_text(" ", strip=True) if h1 else "") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    # JS 앱의 <noscript>에는 종종 '진짜' 본문(박물관 소장 데이터 등)이 들어 있다 — 버리기 전에 따로 보관
    noscript_text = "\n".join(n.get_text("\n", strip=True) for n in soup.find_all("noscript"))
    for t in soup.find_all(NOISE): t.decompose()
    # 쿠키 동의 대화상자(Quantcast·OneTrust 류)는 수천 줄의 '파트너 목록'을 본문에 쏟아 넣는다 — 제거
    _junk = re.compile(r"consent|cookie|gdpr|qc-cmp|onetrust|didomi|cmp-", re.I)
    for t in soup.find_all(lambda tag: tag.get("role") == "dialog" or _junk.search(tag.get("id", "") or "") or _junk.search(" ".join(tag.get("class", []) or []))):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"})
    if root is None:
        best, best_len = None, 0
        for c in soup.find_all(["div", "section", "td"]):
            n = sum(len(p.get_text(" ", strip=True)) for p in c.find_all("p"))
            if n > best_len: best, best_len = c, n
        root = best or soup.body or soup
    parts = []
    for el in root.find_all(["h1", "h2", "h3", "p", "li", "blockquote", "pre"]):
        s = el.get_text(" ", strip=True)
        if not s: continue
        parts.append("# " + s if el.name in ("h1", "h2", "h3") else s)
    text = "\n\n".join(parts) if parts else root.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 200:
        # 박물관 소장 페이지처럼 <p> 없이 <dl>/<dd>/<table>로만 짜인 문서 — 본문 전체 텍스트로 대체 (더 길면)
        body = soup.body or soup
        full = re.sub(r"[ \t]+", " ", body.get_text("\n", strip=True)); full = re.sub(r"\n{3,}", "\n\n", full).strip()
        if len(full) > len(text): text = full
    if len(text) < 200 and len(noscript_text) > len(text):
        text = re.sub(r"\n{3,}", "\n\n", noscript_text).strip()
    # 공백 없는 초장문 줄(base64·JSON 덩어리)은 본문이 아니다
    text = "\n".join(l for l in text.split("\n") if not (len(l) > 1500 and " " not in l.strip()))
    links, images = _collect(root, base_url, want_links, want_images)
    if want_links and not links: links, _ = _collect(soup, base_url, True, False)
    if want_images and not images: _, images = _collect(soup, base_url, False, True)
    return title, text, links, images

def pdf_text(content: bytes, max_pages: int = 50):
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(content)); total = len(rd.pages); out = []
    for i in range(min(total, max_pages)):
        try: out.append(rd.pages[i].extract_text() or "")
        except Exception: out.append("")
    return "\n\n".join(out).strip(), total

def is_pdf(content: bytes, content_type: str, url: str) -> bool:
    if content and content[:5].lstrip()[:4] == b"%PDF": return True
    return "application/pdf" in (content_type or "").lower()

def _from_response(p, r, want_links, want_images):
    ctype = r["headers"].get("Content-Type", "") if r.get("headers") else ""
    p.update(final_url=r["url"], status=r["status"])
    if is_pdf(r["content"], ctype, r["url"]):
        try:
            t, n = pdf_text(r["content"]); p.update(text=t, via="pdf", title=f"PDF {n}쪽")
        except Exception as e: p["error"] = f"PDF 읽기 실패: {e.__class__.__name__}"
        return
    html = r["text"] or r["content"].decode("utf-8", "replace")
    title, text, links, images = extract_main(html, r["url"], want_links, want_images)
    p.update(title=title, text=text, links=links, images=images)

def _render_js(url, p, want_links, want_images):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        p["error"] = PW_MSG; return p
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            try:
                ctx = b.new_context(user_agent=UAS[0], viewport={"width": 1280, "height": 900}, locale="en-US")
                pg = ctx.new_page()
                resp = pg.goto(url, timeout=40000, wait_until="domcontentloaded")   # networkidle은 추적 스크립트 때문에 영원히 안 끝날 수 있다
                try: pg.wait_for_load_state("networkidle", timeout=8000)
                except Exception: pg.wait_for_timeout(3000)
                html = pg.content(); final = pg.url
            finally:
                b.close()                                                          # 예외가 나도 크로미움 프로세스를 남기지 않는다
        title, text, links, images = extract_main(html, final, want_links, want_images)
        p.update(final_url=final, status=resp.status if resp else 200, title=title, text=text, links=links, images=images, via="js", error=None)
    except Exception as e:
        p["error"] = f"Playwright 실행 실패: {str(e)[:160]}"
    return p

def read_url(url: str, *, js: bool = False, force: bool = False, want_links: bool = True, want_images: bool = True) -> dict:
    p = _page(url)
    try:
        if not force and not robots_allowed(url):
            p["error"] = "robots.txt 금지 — --force"; return p
        if js: return _render_js(url, p, want_links, want_images)
        r = fetch(url)
        if not r["status"]:
            p["error"] = r["error"] or "연결 실패"; return p
        _from_response(p, r, want_links, want_images)
        st = r["status"]
        if st in (403, 404, 410) or st >= 500 or (p["via"] != "pdf" and not p["error"] and len(p["text"]) < 200):
            wb = wayback_latest(url)
            r2 = fetch(wb) if wb else None
            if r2 and r2["ok"]:
                p2 = _page(url, via="wayback"); _from_response(p2, r2, want_links, want_images)
                if len(p2["text"]) > len(p["text"]):
                    p2["final_url"] = r2["url"]; p2["via"] = "pdf" if p2["via"] == "pdf" else "wayback"; return p2
        if not r["ok"] and not p["error"]: p["error"] = r["error"] or f"HTTP {st}"
    except Exception as e:
        p["error"] = f"{e.__class__.__name__}: {str(e)[:160]}"
    return p

def save_page(page: dict, dest_dir: Path, step: int) -> Path:
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(page.get("title") or urlparse(page.get("url", "")).netloc or "page", 40)
    path = dest_dir / f"{step:03d}-{slug}.txt"
    out = [f"url: {page.get('url')}", f"title: {page.get('title')}", f"via: {page.get('via')}", f"status: {page.get('status')}",
           f"retrieved: {now()}", "", "---", "", page.get("text") or ""]
    if page.get("links"):
        out += ["", "## 링크"] + [f"- {l['text']} <{l['url']}>" for l in page["links"][:60]]
    if page.get("images"):
        out += ["", "## 이미지"] + [f"- {i['url']} ({i['alt']})" for i in page["images"][:40]]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path
