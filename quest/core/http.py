#!/usr/bin/env python3
"""QUEST 공용 HTTP — UA · 재시도 · 도메인별 예절 지연 · robots.txt · 웨이백.
네트워크 함수는 예외를 밖으로 던지지 않는다: fetch()는 항상 dict를 돌려준다."""
import re, time, urllib.parse, urllib.robotparser
from urllib.parse import urlparse

import requests

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]
_session = requests.Session()
_last_call: dict = {}
_robots_cache: dict = {}

def domain_of(url: str) -> str:
    try: return urlparse(url).netloc.lower()
    except Exception: return ""

def polite_delay(domain: str, seconds: float = 0.7) -> None:
    """같은 도메인 연속 호출 사이 최소 간격."""
    last = _last_call.get(domain)
    if last is not None:
        wait = seconds - (time.monotonic() - last)
        if wait > 0: time.sleep(wait)
    _last_call[domain] = time.monotonic()

MAX_BYTES = 50 * 1024 * 1024   # 비스트리밍 응답 본문 상한 — 거대한 PDF·매니페스트가 메모리를 삼키지 않도록

def _decode(content: bytes, headers: dict) -> str:
    ct = (headers.get("Content-Type") or "").lower()
    m = re.search(r"charset=([\w-]+)", ct)
    enc = m.group(1) if m else "utf-8"          # 헤더에 charset이 없으면 utf-8 (requests의 ISO-8859-1 기본값은 한글을 깨뜨린다)
    try: return content.decode(enc, "replace")
    except LookupError: return content.decode("utf-8", "replace")

def fetch(url: str, *, method: str = "GET", params=None, data=None, headers=None, timeout: int = 30,
          retries: int = 2, json_body=None, stream: bool = False, max_bytes: int = MAX_BYTES) -> dict:
    """→ {"ok", "status", "url", "text", "content", "headers", "error", "elapsed", "response"(stream일 때)}
    비스트리밍이면 본문을 max_bytes까지만 읽고 넘으면 error '응답 크기 초과'."""
    dom = domain_of(url); polite_delay(dom)
    out = {"ok": False, "status": 0, "url": url, "text": "", "content": b"", "headers": {}, "error": None, "elapsed": 0.0}
    ua_i = 0; delay = 1.0
    for attempt in range(retries + 1):
        h = {"User-Agent": UAS[ua_i % len(UAS)], "Accept-Language": "en,ko;q=0.8", "Accept": "*/*"}
        if headers: h.update(headers)
        t0 = time.monotonic()
        try:
            r = _session.request(method, url, params=params, data=data, json=json_body, headers=h, timeout=timeout,
                                 allow_redirects=True, stream=True)
            out.update({"status": r.status_code, "url": r.url, "headers": dict(r.headers), "elapsed": round(time.monotonic() - t0, 2)})
            if r.status_code == 403 and attempt < retries:
                r.close(); ua_i += 1; time.sleep(delay); continue      # 다른 브라우저 UA로 1회 재시도 (README에 명시)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                r.close(); time.sleep(delay); delay *= 2; continue
            if stream:
                out["response"] = r; out["ok"] = r.ok; return out
            buf = bytearray()
            for chunk in r.iter_content(1024 * 1024):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    r.close(); out["error"] = f"응답 크기 초과 > {max_bytes // 1048576} MB"; out["ok"] = False; return out
            r.close()
            out["content"] = bytes(buf); out["text"] = _decode(out["content"], out["headers"])
            out["ok"] = r.ok
            if not r.ok: out["error"] = f"HTTP {r.status_code}"
            return out
        except (requests.ConnectionError, requests.Timeout) as e:
            out["error"] = f"{e.__class__.__name__}: {str(e)[:160]}"; out["elapsed"] = round(time.monotonic() - t0, 2)
            if attempt < retries: time.sleep(delay); delay *= 2; continue
        except requests.RequestException as e:
            out["error"] = f"{e.__class__.__name__}: {str(e)[:160]}"; return out
    return out

def fetch_json(url: str, **kw):
    r = fetch(url, **kw)
    if not r["ok"]: return None
    try:
        import json; return json.loads(r["text"] or r["content"].decode("utf-8", "replace"))
    except Exception: return None

# ── robots.txt ───────────────────────────────────────────────────────────
def _allowed(robots_txt: str, url: str, ua: str = "*") -> bool:
    rp = urllib.robotparser.RobotFileParser(); rp.parse(robots_txt.splitlines())
    return rp.can_fetch(ua, url)

def robots_allowed(url: str, ua: str = "*") -> bool:
    """읽기(read)·확보(grab) 전에 확인. robots.txt를 못 받으면 허용으로 본다."""
    dom = domain_of(url)
    if not dom: return True
    if dom not in _robots_cache:
        p = urlparse(url)
        r = fetch(f"{p.scheme}://{dom}/robots.txt", timeout=10, retries=0)
        if r["ok"]: _robots_cache[dom] = r["text"] or ""
        elif 400 <= (r["status"] or 0) < 500: _robots_cache[dom] = ""          # robots.txt 없음 → 허용
        else: _robots_cache[dom] = "User-agent: *\nDisallow: /\n"     # 5xx·연결 실패 → 보수적으로 금지 (RFC 9309 §2.3.1.4)
    txt = _robots_cache[dom]
    if not txt: return True
    try: return _allowed(txt, url, ua)
    except Exception: return True

# ── 웨이백 ───────────────────────────────────────────────────────────────
def wayback_latest(url: str) -> str | None:
    d = fetch_json("https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""), timeout=20, retries=1)
    try:
        c = d["archived_snapshots"]["closest"]
        return c["url"] if c.get("available") else None
    except Exception: return None
