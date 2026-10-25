#!/usr/bin/env python3
"""공부 모드 공통 유틸 — 영상 ID · VTT 정제 · frontmatter · 위키링크 · 구절 정규화.
외부 의존성 없음 (PyYAML이 있으면 쓰고, 없으면 내장 간이 파서로 대체)."""
import html, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 저장소 루트
STUDY = ROOT / "study"
SOURCES = STUDY / "sources"
CATALOG = STUDY / "catalog.json"

# ── 성경 책 이름표 (bible/lookup.py 재사용) ─────────────────────────────
sys.path.insert(0, str(ROOT / "bible"))
try:
    from lookup import BOOKS, NAME2ID            # (id, 한글, 한글약어, 영어, 영어약어들, sblgnt)
except Exception:                                # 본문 모듈이 없어도 도구는 돌아가야 한다
    BOOKS, NAME2ID = [], {}
ID2ABBR = {b[0]: b[2] for b in BOOKS}

# ── 영상 ID ────────────────────────────────────────────────────────────
_VID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})")
def extract_video_id(url: str):
    m = _VID.search(url or "")
    return m.group(1) if m else None

# ── 시간 표기 ──────────────────────────────────────────────────────────
def fmt_ts(sec: float) -> str:
    sec = int(sec); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def _ts2sec(ts: str) -> float:
    parts = [float(p) for p in ts.strip().split(":")]
    while len(parts) < 3: parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]

# ── VTT → (시작초, 문장) 목록 ────────────────────────────────────────────
_TIMING = re.compile(r"^(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
def vtt_to_segments(text: str):
    """유튜브 자동자막은 같은 줄이 다음 큐에 반복된다(굴러가는 표시). 직전 출력 줄과 같으면 건너뛴다.
    전역 집합이 아니라 '직전'과만 비교하므로 '아멘'처럼 정당하게 반복되는 말은 살아남는다.
    빈 줄(공백·&nbsp;)로 블록을 나누지 않고 타이밍 줄 기준으로 큐를 잡는다 — 공백 줄 뒤 첫 등장 문장을 잃지 않기 위해."""
    lines = text.replace("\r", "").split("\n")
    out, last, start = [], None, None
    for i, l in enumerate(lines):
        m = _TIMING.match(l.strip())
        if m: start = _ts2sec(m.group(1)); continue
        if start is None: continue                       # 헤더(WEBVTT, Kind, Language)
        s = l.strip()
        if not s: continue
        if s.isdigit() and i + 1 < len(lines) and _TIMING.match(lines[i + 1].strip()): continue   # 큐 번호
        clean = _WS.sub(" ", html.unescape(_TAG.sub("", l))).strip()
        if not clean or clean == last: continue
        out.append((start, clean)); last = clean
    return out

def segments_to_paragraphs(segs, max_secs=60, max_chars=350):
    """문장들을 시간(max_secs) 또는 길이(max_chars) 기준으로 단락으로 묶는다 → [(시작초, 단락)]"""
    paras, cur, cur_start = [], [], None
    for s, t in segs:
        if cur and (s - cur_start >= max_secs or len(" ".join(cur)) + 1 + len(t) > max_chars):
            paras.append((cur_start, " ".join(cur))); cur, cur_start = [], None
        if cur_start is None: cur_start = s
        cur.append(t)
    if cur: paras.append((cur_start, " ".join(cur)))
    return paras

# ── frontmatter ─────────────────────────────────────────────────────────
def _mini_yaml(src: str) -> dict:
    """PyYAML 없을 때의 최소 파서: 스칼라 / [a, b] / '- 항목' 블록 리스트."""
    d, key = {}, None
    for raw in src.split("\n"):
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"): continue
        if line.lstrip().startswith("- ") and key:
            if not isinstance(d.get(key), list): d[key] = []
            d[key].append(line.strip()[2:].strip()); continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":"); key = key.strip(); val = val.split(" #")[0].strip()
            if val.startswith("[") and val.endswith("]"):
                d[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            elif val == "": d[key] = []
            else: d[key] = val.strip("'\"")
    return d

def _to_str(v):
    if isinstance(v, list): return [_to_str(x) for x in v]
    if isinstance(v, dict): return {k: _to_str(x) for k, x in v.items()}
    if v is None: return ""
    return v if isinstance(v, str) else str(v)

def parse_frontmatter(text: str):
    """(frontmatter dict, 본문) — 모든 값은 str/list[str]로 정규화. frontmatter 없으면 ({}, 전체)."""
    m = re.match(r"^\ufeff?---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m: return {}, text
    src, body = m.group(1), m.group(2)
    try:
        import yaml
        data = yaml.safe_load(src) or {}
        if not isinstance(data, dict): data = {}
    except Exception:
        data = _mini_yaml(src)
    return {k: _to_str(v) for k, v in data.items()}, body

_WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
def extract_wikilinks(text: str):
    seen, out = set(), []
    for m in _WIKI.finditer(text):
        t = m.group(1).strip()
        if t and t not in seen: seen.add(t); out.append(t)
    return out

# ── 구절 정규화 → 장 단위 키 ("약 2") / 책 단위 키 ("시") ──────────────
_REF = re.compile(r"^([1-3]?\s*[A-Za-z가-힣]+\.?)\s*(?:(\d+)(?:\s*장)?(?:\s*[:：]\s*\d+[a-z]?)?(?:\s*[-~–]\s*(\d+)(?:\s*[:：]\s*\d+)?)?)?\s*(?:편|장|절|전체)?$")
def normalize_verses(refs):
    out, seen = [], set()
    for ref in refs or []:
        for piece in re.split(r"[;,·/]", str(ref)):
            piece = piece.strip()
            if not piece: continue
            m = _REF.match(piece)
            if not m: continue
            name = re.sub(r"\s+", "", m.group(1)).rstrip(".").lower()
            bid = NAME2ID.get(name) or NAME2ID.get(name.replace("전체", ""))
            if not bid: continue
            abbr = ID2ABBR[bid]
            ch1, ch2 = m.group(2), m.group(3)
            if ch1 is None:
                keys = [abbr]
            else:
                a = int(ch1)
                # "왕하 18-20"은 장 범위, "약 2:1-13"은 절 범위 → ':'가 있으면 장은 하나
                b = int(ch2) if (ch2 and ":" not in piece and "：" not in piece) else a
                if b < a or b - a > 150: b = a
                keys = [f"{abbr} {c}" for c in range(a, b + 1)]
            for k in keys:
                if k not in seen: seen.add(k); out.append(k)
    return out
