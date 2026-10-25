#!/usr/bin/env python3
"""GODISALIVE 플러그인 — 성경 구절·증거 축·도메인 신뢰표. 다른 프로젝트는 이 파일만 바꿔 이식한다."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 기관 도메인 → 권위 등급 (sources/SOURCES.md §4–§9 + 계획서 목록)
TRUSTED_DOMAINS = {d: 1 for d in [
    "britishmuseum.org", "imj.org.il", "louvre.fr", "smb.museum", "metmuseum.org", "loc.gov", "archive.org", "sefaria.org",
    "perseus.tufts.edu", "scaife.perseus.org", "antiquities.org.il", "deadseascrolls.org.il", "jstor.org", "brill.com",
    "cambridge.org", "degruyter.com", "tandfonline.com", "uchicago.edu", "penn.museum", "getty.edu", "pleiades.stoa.org",
    "cityofdavid.org.il", "isac.uchicago.edu", "asor.org", "nasa.gov", "custodia.org",
]}
TRUSTED_DOMAINS.update({"biblicalarchaeology.org": 3, "academia.edu": 3})

# URL → 공유저작물 단서 (라이선스 메타데이터가 없을 때의 힌트일 뿐, 최종 확인은 사람)
PD_HINTS = [
    (re.compile(r"loc\.gov/.*(matpc|matson)", re.I), "Public domain"),
    (re.compile(r"loc\.gov/pictures/.*matpc", re.I), "Public domain"),
    (re.compile(r"nasa\.gov/", re.I), "Public domain"),
]

AXIS_KEYWORDS = {
    "archaeology": ["archaeolog", "excavat", "tell ", "stratum", "pottery", "inscription", "stele", "ostracon", "artifact", "relief", "ossuary",
                    "고고", "발굴", "유물", "비문", "비석", "토기", "부조", "유적", "봉인"],
    "history": ["chronicle", "annals", "empire", "dynasty", "king of", "reign", "historian", "josephus", "herodotus", "campaign", "siege",
                "역사", "연대기", "왕조", "제국", "통치", "사료", "포위", "원정"],
    "manuscripts": ["manuscript", "scroll", "codex", "papyrus", "textual criticism", "septuagint", "masoretic", "qumran", "dead sea",
                    "사본", "두루마리", "사해", "파피루스", "본문비평", "칠십인역", "마소라"],
    "science": ["radiocarbon", "carbon dating", "dendro", "geolog", "spectroscop", "dna", "isotope", "climate", "astronom", "eclipse",
                "탄소", "연대측정", "지질", "분광", "천문", "일식", "기후"],
}

TAG_DICT = {
    "라기스 부조": ["lachish relief", "lachish reliefs", "라기스 부조"],
    "산헤립 프리즘": ["sennacherib prism", "taylor prism", "산헤립 프리즘", "테일러 프리즘"],
    "실로암 비문": ["siloam inscription", "hezekiah's tunnel", "hezekiah tunnel", "실로암 비문", "히스기야 터널"],
    "텔 단 비문": ["tel dan stele", "house of david", "텔 단", "다윗의 집"],
    "메사 비문": ["mesha stele", "moabite stone", "메사 비문", "모압 비석"],
    "메르넵타 비문": ["merneptah stele", "israel stele", "메르넵타"],
    "검은 오벨리스크": ["black obelisk", "shalmaneser", "검은 오벨리스크", "살만에셀"],
    "고레스 원통": ["cyrus cylinder", "고레스 원통"],
    "사해 사본": ["dead sea scrolls", "qumran", "사해 사본", "쿰란"],
    "이사야 대두루마리": ["great isaiah scroll", "1qisa", "이사야 두루마리"],
    "빌라도 비석": ["pilate stone", "pontius pilate", "빌라도 비석"],
    "가야바 납골함": ["caiaphas ossuary", "caiaphas", "가야바"],
    "히스기야": ["hezekiah", "히스기야"],
    "산헤립": ["sennacherib", "산헤립", "센나케립"],
    "느부갓네살": ["nebuchadnezzar", "nebuchadrezzar", "느부갓네살"],
    "니느웨": ["nineveh", "니느웨"],
}


def _domain_match(domain: str, table: dict):
    d = (domain or "").lower().strip(".")
    best = None
    for k, v in table.items():
        if d == k or d.endswith("." + k):
            if best is None or len(k) > len(best[0]): best = (k, v)
    return best[1] if best else None


def authority_override(domain: str):
    return _domain_match(domain, TRUSTED_DOMAINS)


def axis(text: str):
    low = (text or "").lower()
    best, best_n = None, 0
    for name, kws in AXIS_KEYWORDS.items():
        n = sum(low.count(k) for k in kws)
        if n > best_n: best, best_n = name, n
    return best


# ── 성경 구절 → 장 단위 ──────────────────────────────────────────────────
try:
    import importlib.util
    _tools = str(ROOT / "study" / "tools")
    if _tools not in sys.path: sys.path.insert(0, _tools)      # study/tools 가 형제 모듈을 쓸 경우 대비
    _spec = importlib.util.spec_from_file_location("study_tools_common", ROOT / "study" / "tools" / "common.py")
    _mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
    normalize_verses, NAME2ID = _mod.normalize_verses, _mod.NAME2ID
except Exception:
    normalize_verses, NAME2ID = None, {}

_REF = re.compile(r"(?<![A-Za-z가-힣])((?:[1-3]\s*)?[A-Za-z가-힣]+\.?)\s*(\d+)(?:\s*장)?(?:\s*[:：]\s*(\d+))?(?:\s*[-~–]\s*(\d+)(?:\s*[:：]\s*(\d+))?)?")


def tag_verses(text: str) -> list:
    if not normalize_verses or not text: return []
    refs, pos = [], 0
    while True:
        m = _REF.search(text, pos)
        if not m: break
        name = re.sub(r"\s+", "", m.group(1)).rstrip(".").lower()
        if name not in NAME2ID:
            pos = m.start(1) + 1; continue        # '과 2 Kings' 처럼 앞말이 숫자를 삼킨 경우 다시 훑는다
        c1, v1, c2, v2 = m.group(2), m.group(3), m.group(4), m.group(5)
        if v1 is None and c2: refs.append(f"{m.group(1)} {c1}-{c2}")             # 18-20 (장 범위)
        elif v1 is not None and v2 is not None and c2: refs.append(f"{m.group(1)} {c1}-{c2}")   # 18:13-19:37 (장을 가로지름)
        else: refs.append(f"{m.group(1)} {c1}")
        pos = m.end()
    return normalize_verses(refs)


def license_hint(url: str):
    for rx, lic in PD_HINTS:
        if rx.search(url or ""): return lic
    return None


def tags(text: str) -> list:
    low = (text or "").lower()
    return [name for name, keys in TAG_DICT.items() if any(k in low for k in keys)]
