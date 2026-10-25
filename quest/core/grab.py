#!/usr/bin/env python3
"""QUEST 확보 — 이미지·PDF·IIIF·영상 다운로드 + manifest.json + 라이선스 조회.
한도(스트리밍 누적) · sha256 중복 방지. 예외를 밖으로 던지지 않는다: grab은 Entry 또는 {"error": ...}."""
import hashlib, json, mimetypes, re, shutil, subprocess, urllib.parse, urllib.request
from pathlib import Path
from urllib.parse import urlparse, unquote

from core.http import fetch, fetch_json, robots_allowed
from core.license import license_class
from core.workspace import CONFIG, now

CHUNK = 1024 * 1024
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp", ".svg")
VID_EXT = (".mp4", ".webm", ".mkv", ".mov")
VID_HOSTS = ("youtube.com", "youtu.be", "vimeo.com")
LIMIT_KEY = {"image": "image_mb", "iiif": "image_mb", "pdf": "pdf_mb", "video": "video_mb", "file": "pdf_mb"}

def sniff_kind(url: str, content_type: str | None) -> str:
    u = (url or "").lower(); ct = (content_type or "").lower(); p = urlparse(u); path = p.path
    host = p.netloc
    if any(host == h or host.endswith("." + h) for h in VID_HOSTS) or path.endswith(VID_EXT) or ct.startswith("video/"): return "video"
    if "ld+json" in ct or path.endswith(("manifest.json", "/manifest", "info.json")) or "iiif" in ct: return "iiif"
    if ct.startswith("image/") or path.endswith(IMG_EXT): return "image"
    if "application/pdf" in ct or path.endswith(".pdf"): return "pdf"
    return "file"

# ── 라이선스 조회 ────────────────────────────────────────────────────────
def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip() or None

def _commons_title(url):
    p = urlparse(url or "")
    if p.netloc == "commons.wikimedia.org" and "/wiki/" in p.path:
        t = unquote(p.path.split("/wiki/", 1)[1])
        return t if t.startswith("File:") else None
    if p.netloc == "upload.wikimedia.org" and "/wikipedia/commons/" in p.path:
        parts = unquote(p.path).split("/")
        rest = parts[parts.index("commons") + 1:]
        if rest and rest[0] == "thumb": name = rest[3] if len(rest) > 3 else None
        else: name = rest[2] if len(rest) > 2 else None
        return ("File:" + name) if name else None
    return None

def license_for(url: str, source_page: str | None) -> dict:
    out = {"license": None, "credit": None, "source": None}
    try:
        for u in (url, source_page):
            if not u: continue
            title = _commons_title(u)
            if title:
                d = fetch_json("https://commons.wikimedia.org/w/api.php", params={"action": "query", "titles": title, "prop": "imageinfo",
                               "iiprop": "extmetadata", "format": "json"}, timeout=20, retries=1)
                for pg in ((d or {}).get("query") or {}).get("pages", {}).values():
                    em = (pg.get("imageinfo") or [{}])[0].get("extmetadata", {})
                    g = lambda k: _strip_html((em.get(k) or {}).get("value"))
                    if g("LicenseShortName"):
                        art, cr = g("Artist"), g("Credit")
                        out.update(license=g("LicenseShortName"), credit=", ".join(x for x in (art, cr) if x) or None,
                                   source="https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")))
                        return out
            m = re.search(r"metmuseum\.org/art/collection/search/(\d+)", u)
            if m:
                d = fetch_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{m.group(1)}", timeout=20, retries=1)
                if d:
                    out["source"] = u
                    out["credit"] = ", ".join(x for x in (d.get("title"), d.get("repository"), d.get("creditLine")) if x) or None
                    out["license"] = "CC0" if d.get("isPublicDomain") else "ⓒ The Metropolitan Museum of Art (not public domain)"
                    return out
            if "loc.gov" in urlparse(u).netloc:
                d = fetch_json(u.split("?")[0], params={"fo": "json"}, timeout=20, retries=1)
                rights = _find_rights(d)
                if rights:
                    out.update(license=rights, source=u, credit="Library of Congress"); return out
    except Exception:
        pass
    return out

def _find_rights(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if k in ("rights", "rights_advisory") and v:
                return _strip_html(v if isinstance(v, str) else " ".join(map(str, v)) if isinstance(v, list) else str(v))
        for v in d.values():
            r = _find_rights(v)
            if r: return r
    elif isinstance(d, list):
        for v in d:
            r = _find_rights(v)
            if r: return r
    return None

# ── IIIF ─────────────────────────────────────────────────────────────────
def iiif_image_urls(manifest: dict) -> list:
    out = []
    def add(svc):
        if isinstance(svc, list): svc = svc[0] if svc else None
        if isinstance(svc, dict):
            sid = svc.get("@id") or svc.get("id")
            if sid: out.append(sid.rstrip("/") + "/full/max/0/default.jpg")
    try:
        for seq in manifest.get("sequences", []) or []:
            for cv in seq.get("canvases", []):
                for im in cv.get("images", [])[:1]: add((im.get("resource") or {}).get("service"))
        for cv in manifest.get("items", []) or []:
            for page in cv.get("items", []):
                for anno in page.get("items", []):
                    body = anno.get("body") or {}
                    if isinstance(body, list): body = body[0] if body else {}
                    add(body.get("service"))
    except Exception:
        pass
    return out

# ── manifest ─────────────────────────────────────────────────────────────
def load_manifest(dest_dir: Path) -> list:
    p = Path(dest_dir) / "manifest.json"
    if not p.exists(): return []
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return []

def _save_manifest(dest_dir, rows):
    (Path(dest_dir) / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(CHUNK), b""): h.update(c)
    return h.hexdigest()

def _ext_for(url, ctype):
    ext = Path(unquote(urlparse(url).path)).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext or ""):
        ext = mimetypes.guess_extension((ctype or "").split(";")[0].strip()) or ".bin"
        if ext == ".jpe": ext = ".jpg"
    return ext

def _limit_mb(kind, limits):
    lim = dict(CONFIG["limits"]); lim.update(limits or {})
    return lim, lim.get(LIMIT_KEY.get(kind, "pdf_mb"), 100)

def _dup(rows, sha):
    for e in rows:
        if e.get("sha256") == sha:
            e = dict(e); e["meta"] = dict(e.get("meta") or {}, duplicate=True); return e
    return None

def _finish(dest, part, kind, url, source_page, license_hint, ext):
    """part 파일 → 최종 이름·manifest. 중복이면 part 삭제."""
    sha = _sha_file(part); rows = load_manifest(dest)
    d = _dup(rows, sha)
    if d:
        Path(part).unlink(missing_ok=True); return d
    final = Path(dest) / f"{kind[:3]}-{sha[:8]}{ext}"
    Path(part).replace(final)
    lf = {"license": None, "credit": None, "source": None}
    if not url.startswith("file:"): lf = license_for(url, source_page)
    lic = license_hint or lf["license"]
    entry = {"id": f"{kind[:3]}-{sha[:8]}", "url": url, "source_page": source_page, "kind": kind, "path": str(final), "sha256": sha,
             "bytes": final.stat().st_size, "license": lic, "commercial_ok": license_class(lic)[1], "credit": lf["credit"],
             "retrieved_at": now(), "meta": {}}
    rows.append(entry); _save_manifest(dest, rows)
    return entry

def _yt_dlp():
    p = Path.home() / ".local" / "bin" / "yt-dlp.exe"
    return str(p) if p.exists() else shutil.which("yt-dlp")

def _grab_video(url, dest, source_page, license_hint, limits):
    exe = _yt_dlp()
    if not exe: return {"error": "yt-dlp 없음: pip install yt-dlp 또는 ~/.local/bin/yt-dlp.exe"}
    lim, _ = _limit_mb("video", limits); h = lim.get("video_max_height", 1080)
    before = {p.name for p in Path(dest).iterdir()}
    try:
        r = subprocess.run([exe, "-f", f"bestvideo[height<={h}]+bestaudio/best", "--merge-output-format", "mp4", "--write-info-json",
                            "--encoding", "utf-8", "--max-filesize", f"{int(lim.get('video_mb', 2048))}M", "--no-playlist",
                            "-o", str(Path(dest) / "%(id)s.%(ext)s"), url], capture_output=True, timeout=3600)
    except Exception as e:
        return {"error": f"yt-dlp 실행 실패: {e.__class__.__name__}"}
    new = [p for p in Path(dest).iterdir() if p.name not in before]
    vids = [p for p in new if p.suffix.lower() in VID_EXT]
    if r.returncode != 0 or not vids:
        return {"error": "yt-dlp 실패: " + (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["?"])[-1][:200]}
    vid = max(vids, key=lambda p: p.stat().st_size); meta = {}
    info = next((p for p in new if p.name.endswith(".info.json")), None)
    if info:
        try:
            d = json.loads(info.read_text(encoding="utf-8"))
            meta = {k: d.get(k) for k in ("title", "duration", "uploader")}
        except Exception: pass
    sha = _sha_file(vid); rows = load_manifest(dest)
    d = _dup(rows, sha)
    if d: return d
    entry = {"id": f"vid-{sha[:8]}", "url": url, "source_page": source_page, "kind": "video", "path": str(vid), "sha256": sha,
             "bytes": vid.stat().st_size, "license": license_hint, "commercial_ok": license_class(license_hint)[1],
             "credit": meta.get("uploader"), "retrieved_at": now(), "meta": meta}
    rows.append(entry); _save_manifest(dest, rows)
    return entry

def _mb(n): return round(n / 1048576, 1)

def _download(url, dest, kind, limits):
    """→ (part_path, ctype, ext, kind) | {"error"}. 스트리밍 누적 한도 검사."""
    dest = Path(dest); part = dest / ".part"
    if url.startswith("file:"):
        src = Path(urllib.request.url2pathname(urlparse(url).path))
        if not src.exists(): return {"error": f"파일 없음: {src}"}
        ctype = mimetypes.guess_type(src.name)[0] or ""
        kind = kind or sniff_kind(src.name, ctype)
        _, mx = _limit_mb(kind, limits)
        if src.stat().st_size > mx * 1048576: return {"error": f"한도 초과 {_mb(src.stat().st_size)} MB > {mx} MB"}
        shutil.copyfile(src, part)
        return part, ctype, src.suffix.lower() or ".bin", kind
    r = fetch(url, stream=True, timeout=60)
    resp = r.get("response")
    if resp is None: return {"error": r["error"] or "연결 실패"}
    try:
        if not r["ok"]: return {"error": f"HTTP {r['status']}"}
        ctype = resp.headers.get("Content-Type", "")
        kind = kind or sniff_kind(r["url"], ctype)
        if kind == "file" and ctype.lower().startswith("image/"): kind = "image"
        _, mx = _limit_mb(kind, limits); cap = mx * 1048576
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit() and int(cl) > cap: return {"error": f"한도 초과 {_mb(int(cl))} MB > {mx} MB"}
        total = 0
        with open(part, "wb") as f:
            for chunk in resp.iter_content(CHUNK):
                total += len(chunk)
                if total > cap:
                    f.close(); part.unlink(missing_ok=True)
                    return {"error": f"한도 초과 {_mb(total)}+ MB > {mx} MB"}
                f.write(chunk)
        return part, ctype, _ext_for(r["url"], ctype), kind
    except Exception as e:
        part.unlink(missing_ok=True); return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}
    finally:
        try: resp.close()
        except Exception: pass

def grab(url: str, dest_dir: Path, *, kind: str | None = None, source_page: str | None = None, license_hint: str | None = None,
         limits: dict | None = None, all_iiif: bool = False):
    try:
        dest = Path(dest_dir); dest.mkdir(parents=True, exist_ok=True)
        is_file = url.startswith("file:")
        kind = kind or (None if is_file else sniff_kind(url, None))
        if kind == "video": return _grab_video(url, dest, source_page, license_hint, limits)
        if not is_file and urlparse(url).netloc != "upload.wikimedia.org" and not robots_allowed(url):
            return {"error": "robots.txt 금지"}
        if kind == "iiif" and not url.lower().split("?")[0].endswith(IMG_EXT):
            man = fetch_json(url, timeout=30)
            urls = iiif_image_urls(man) if isinstance(man, dict) else []
            if not urls: return {"error": "IIIF 매니페스트에서 이미지를 찾지 못함"}
            ents = [grab(u, dest, kind="image", source_page=source_page or url, license_hint=license_hint, limits=limits)
                    for u in (urls if all_iiif else urls[:1])]
            good = [e for e in ents if "error" not in e]
            if not good: return ents[0]
            first = dict(good[0]); first["meta"] = dict(first.get("meta") or {}, iiif_manifest=url, iiif_ids=[e["id"] for e in good])
            return first
        res = _download(url, dest, kind, limits)
        if isinstance(res, dict): return res
        part, ctype, ext, kind = res
        return _finish(dest, part, kind, url, source_page, license_hint, ext)
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}
