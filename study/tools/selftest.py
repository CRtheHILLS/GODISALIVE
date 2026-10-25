#!/usr/bin/env python3
"""공부 모드 도구 자가 테스트 — 파서·링크·그래프.  실행: python study/tools/selftest.py"""
import sys, json, tempfile
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import common as C
import graph as G

FAILS = []
def check(name, got, want):
    ok = got == want
    print(("  ok  " if ok else "  FAIL") + f" {name}" + ("" if ok else f"\n        got : {got!r}\n        want: {want!r}"))
    if not ok: FAILS.append(name)

# 1. 영상 ID 추출
for url in ["https://www.youtube.com/watch?v=6UTOoMArLkI", "https://youtu.be/6UTOoMArLkI?t=30",
            "https://www.youtube.com/shorts/6UTOoMArLkI", "https://m.youtube.com/watch?feature=share&v=6UTOoMArLkI",
            "https://www.youtube.com/live/6UTOoMArLkI"]:
    check(f"video_id {url[:40]}", C.extract_video_id(url), "6UTOoMArLkI")
check("video_id invalid", C.extract_video_id("https://example.com/x"), None)

# 2. VTT 정제 — 유튜브 자동자막의 '굴러가는 중복' 패턴
VTT = """WEBVTT
Kind: captions
Language: ko

00:00:03.080 --> 00:00:06.190 align:start position:0%
 
네.<00:00:03.399><c> 오늘</c><00:00:03.879><c> 10월</c>

00:00:06.190 --> 00:00:06.200 align:start position:0%
네. 오늘 10월
 

00:00:06.200 --> 00:00:09.950 align:start position:0%
네. 오늘 10월
주신<00:00:06.480><c> 말씀은</c>

00:00:09.950 --> 00:00:09.960 align:start position:0%
주신 말씀은
 

00:00:09.960 --> 00:00:12.190 align:start position:0%
주신 말씀은
아멘<00:00:10.800><c>.</c>

00:00:12.190 --> 00:00:12.200 align:start position:0%
아멘.
 

00:00:12.200 --> 00:00:16.109 align:start position:0%
아멘.
다시<00:00:13.639><c> 아멘</c>

00:00:16.200 --> 00:00:18.109 align:start position:0%
다시 아멘
아멘<00:00:17.639><c>.</c>
"""
segs = C.vtt_to_segments(VTT)
check("vtt lines", [t for _, t in segs], ["네. 오늘 10월", "주신 말씀은", "아멘.", "다시 아멘", "아멘."])
check("vtt start times", [round(s, 2) for s, _ in segs], [3.08, 6.2, 9.96, 12.2, 16.2])

MANUAL = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
First line &amp; more

2
00:00:03.000 --> 00:00:05.000
Second line
"""
check("manual vtt", C.vtt_to_segments(MANUAL), [(1.0, "First line & more"), (3.0, "Second line")])

# 3. 단락 묶기
paras = C.segments_to_paragraphs([(0, "가"), (10, "나"), (70, "다"), (75, "라")], max_secs=60, max_chars=1000)
check("paragraphs by time", paras, [(0, "가 나"), (70, "다 라")])
paras = C.segments_to_paragraphs([(0, "a" * 300), (1, "b" * 300), (2, "c")], max_secs=600, max_chars=350)
check("paragraphs by chars", [(s, len(t)) for s, t in paras], [(0, 300), (1, 302)])
check("fmt_ts", [C.fmt_ts(65), C.fmt_ts(3725), C.fmt_ts(0)], ["01:05", "1:02:05", "00:00"])

# 4. frontmatter 파싱
NOTE = """---
id: kn-test-one
title: 테스트
verses: [약 2:1-13, 시 2]
evidence: [ev-arch-tel-dan-stele]
sources:
  - 출처 A
  - 출처 B
date: 2026-10-25
tags: [설교, 야고보서]
---
본문 [[kn-books-james]] 과 [[ev-arch-tel-dan-stele]] 그리고 [[kn-books-james|야고보서]].
"""
fm, body = C.parse_frontmatter(NOTE)
check("fm id", fm["id"], "kn-test-one")
check("fm inline list", fm["verses"], ["약 2:1-13", "시 2"])
check("fm block list", fm["sources"], ["출처 A", "출처 B"])
check("fm date->str", fm["date"], "2026-10-25")
check("no frontmatter", C.parse_frontmatter("# 제목\n본문")[0], {})
check("wikilinks", C.extract_wikilinks(body), ["kn-books-james", "ev-arch-tel-dan-stele"])

# 5. 구절 정규화 (장 단위 노드)
check("verses normalize", C.normalize_verses(["약 2:1-13", "왕하 18-20", "시편 전체", "Ps 2", "삼하 7장", "요 21:15-17; 행 4:25-27", "창세기 1:1"]),
      ["약 2", "왕하 18", "왕하 19", "왕하 20", "시", "시 2", "삼하 7", "요 21", "행 4", "창 1"])
check("verses junk", C.normalize_verses(["알 수 없음"]), [])

# 6. 그래프 구축 (합성 노트 3개)
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "knowledge" / "people").mkdir(parents=True); (root / "evidence" / "archaeology").mkdir(parents=True)
    (root / "knowledge" / "people" / "a.md").write_text(
        "---\nid: kn-people-a\ntitle: A\nverses: [시 2]\nevidence: [ev-arch-x]\ntags: [왕]\ndate: 2026-01-01\n---\n[[kn-people-b]] [[kn-missing]]", encoding="utf-8")
    (root / "knowledge" / "people" / "b.md").write_text(
        "---\nid: kn-people-b\ntitle: B\nverses: [시 2:7]\ntags: [왕]\nspeaker: 조정민\n---\n본문", encoding="utf-8")
    (root / "evidence" / "archaeology" / "x.md").write_text(
        "---\nid: ev-arch-x\ntitle: X\ngrade: A\ncategory: archaeology\nverses: [삼하 7]\n---\n", encoding="utf-8")
    g = G.build_graph(root)
    types = {}
    for n in g["nodes"]: types[n["type"]] = types.get(n["type"], 0) + 1
    check("graph node types", types, {"knowledge": 2, "evidence": 1, "verse": 2, "tag": 1, "missing": 1, "speaker": 1})
    kinds = {}
    for e in g["edges"]: kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    check("graph edge kinds", kinds, {"link": 2, "evidence": 1, "verse": 3, "tag": 2, "speaker": 1})
    check("dangling", g["stats"]["dangling"], {"kn-missing": ["kn-people-a"]})
    deg = {n["id"]: n["degree"] for n in g["nodes"]}
    check("degree a", deg["kn-people-a"], 5)   # b, missing, ev-x, 시 2, 왕
    check("verse hub", deg["verse:시 2"], 2)
    check("orphans", g["stats"]["orphans"], [])  # 모두 연결됨 (b는 a가 링크)
    html = G.render_html(g, root)
    check("html has data", '"kn-people-a"' in html and "<canvas" in html, True)

print()
if FAILS:
    print(f"실패 {len(FAILS)}건: {FAILS}"); sys.exit(1)
print("전부 통과 ✔")
