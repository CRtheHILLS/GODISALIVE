#!/usr/bin/env python3
"""공부 모드 ② 지식 그래프 — knowledge/ · evidence/ 의 모든 노트를 뉴런처럼 잇는다.

사용:
    python study/tools/graph.py            # graph.json + map.html 생성, 끊어진 링크·고아 노트 보고
    python study/tools/graph.py --check    # 끊어진 [[링크]]가 있으면 종료코드 1 (세션 종료 점검용)
    python study/tools/graph.py --open     # 생성 후 브라우저로 지도 열기
    python study/tools/graph.py --no-desktop  # 바탕화면 복사 생략

점(노드): 지식 노트(kn-*) · 증거 노트(ev-*) · 성경 장("약 2") · 태그 · 설교자 · 끊어진 링크(아직 없는 노트)
선(엣지): [[위키링크]] · frontmatter evidence · 같은 성경 장 · 같은 태그
산출: knowledge/graph/graph.json (기계용) · knowledge/graph/map.html (CR용, 외부 의존성 없음)
"""
import argparse, json, os, shutil, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import common as C
from graph_html import render_html

SCAN_DIRS = ("knowledge", "evidence")
DESKTOP = Path.home() / "Desktop" / "GODISALIVE"

def iter_notes(root: Path):
    for top in SCAN_DIRS:
        base = root / top
        if not base.exists(): continue
        for p in sorted(base.rglob("*.md")):
            if p.name.upper() == "README.MD" or "graph" in p.parts: continue
            fm, body = C.parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            nid = (fm.get("id") or "").split("#")[0].strip()
            if not nid: continue
            rel = p.relative_to(root).as_posix()
            yield {
                "id": nid, "title": fm.get("title") or p.stem, "type": top,
                "subtype": p.parent.name if p.parent != base else top,
                "path": rel, "uri": p.resolve().as_uri(), "date": fm.get("date", ""),
                "grade": fm.get("grade", ""), "tags": _aslist(fm.get("tags")), "verses": _aslist(fm.get("verses")),
                "evidence": _aslist(fm.get("evidence")), "source": fm.get("source", ""),
                "speaker": fm.get("speaker", ""), "links": C.extract_wikilinks(body),
            }

def _aslist(v):
    if not v: return []
    return v if isinstance(v, list) else [str(v)]

def build_graph(root: Path):
    notes = list(iter_notes(root))
    nodes, edges, seen_pairs = {}, [], set()
    for n in notes:
        nodes[n["id"]] = {k: n[k] for k in ("id", "title", "type", "subtype", "path", "uri", "date", "grade",
                                              "tags", "verses", "source", "speaker")}
    def add_node(nid, **kw):
        if nid not in nodes: nodes[nid] = {"id": nid, "title": kw.pop("title", nid), "type": kw.pop("type"), **kw}
    def add_edge(s, t, kind):
        if s == t: return
        key = (min(s, t), max(s, t), "ref" if kind in ("link", "evidence") else kind)
        if key in seen_pairs: return
        seen_pairs.add(key); edges.append({"source": s, "target": t, "kind": kind})
    dangling = defaultdict(list)
    for n in notes:
        for ev in n["evidence"]:                       # frontmatter evidence 먼저 (링크보다 의미가 강함)
            if ev not in nodes: add_node(ev, type="missing", subtype="missing"); dangling[ev].append(n["id"])
            add_edge(n["id"], ev, "evidence")
        for t in n["links"]:
            if t not in nodes: add_node(t, type="missing", subtype="missing"); dangling[t].append(n["id"])
            add_edge(n["id"], t, "link")
        for vk in C.normalize_verses(n["verses"]):
            add_node(f"verse:{vk}", title=vk, type="verse", subtype="verse"); add_edge(n["id"], f"verse:{vk}", "verse")
        for tag in n["tags"]:
            tag = str(tag).strip()
            if tag: add_node(f"tag:{tag}", title=tag, type="tag", subtype="tag"); add_edge(n["id"], f"tag:{tag}", "tag")
        if n["speaker"]:                               # 설교자·강사 — 같은 사람의 강의들이 한 점으로 모인다
            sp = str(n["speaker"]).strip()
            add_node(f"speaker:{sp}", title=sp, type="speaker", subtype="speaker"); add_edge(n["id"], f"speaker:{sp}", "speaker")
    for sources in dangling.values(): sources[:] = sorted(set(sources))
    deg = Counter()
    for e in edges: deg[e["source"]] += 1; deg[e["target"]] += 1
    for nid, nd in nodes.items(): nd["degree"] = deg.get(nid, 0)
    # 고아: 다른 노트와 링크/증거로 한 번도 이어지지 않은 지식·증거 노트
    ref_touch = set()
    for e in edges:
        if e["kind"] in ("link", "evidence"): ref_touch.add(e["source"]); ref_touch.add(e["target"])
    orphans = sorted(nid for nid, nd in nodes.items() if nd["type"] in SCAN_DIRS and nid not in ref_touch)
    # 연결 성분 (태그 제외 — 태그는 너무 쉽게 모두를 잇는다)
    parent = {nid: nid for nid in nodes}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for e in edges:
        if e["kind"] != "tag": parent[find(e["source"])] = find(e["target"])
    comps = len({find(nid) for nid, nd in nodes.items() if nd["type"] != "tag"})
    hubs = sorted((nd for nd in nodes.values() if nd["type"] != "tag"), key=lambda d: -d["degree"])[:12]
    stats = {
        "notes": len(notes), "nodes": len(nodes), "edges": len(edges),
        "nodes_by_type": dict(Counter(nd["type"] for nd in nodes.values())),
        "edges_by_kind": dict(Counter(e["kind"] for e in edges)),
        "dangling": dict(sorted(dangling.items())), "orphans": orphans, "components": comps,
        "hubs": [{"id": h["id"], "title": h["title"], "degree": h["degree"]} for h in hubs],
    }
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "root": str(root),
            "nodes": list(nodes.values()), "edges": edges, "stats": stats}

def report(g):
    s = g["stats"]
    print(f"🧠 지식 그래프 — 노트 {s['notes']}개 → 점 {s['nodes']}개 · 선 {s['edges']}개 · 연결 덩어리 {s['components']}개")
    print("   점:", ", ".join(f"{k} {v}" for k, v in s["nodes_by_type"].items()), "| 선:", ", ".join(f"{k} {v}" for k, v in s["edges_by_kind"].items()))
    print("   허브:", ", ".join(f"{h['title']}({h['degree']})" for h in s["hubs"][:8]))
    if s["dangling"]:
        print(f"   ⚠ 끊어진 링크 {len(s['dangling'])}개 — 아직 없는 노트를 가리킨다 (만들거나 고칠 것):")
        for t, srcs in s["dangling"].items(): print(f"      [[{t}]]  ← {', '.join(srcs)}")
    else: print("   ✔ 끊어진 링크 없음")
    if s["orphans"]: print(f"   ⚠ 고아 노트 {len(s['orphans'])}개 (다른 노트와 링크 없음): {', '.join(s['orphans'])}")
    else: print("   ✔ 고아 노트 없음")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true"); ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-desktop", action="store_true"); ap.add_argument("--root", default=str(C.ROOT))
    a = ap.parse_args(); root = Path(a.root)
    g = build_graph(root)
    out = root / "knowledge" / "graph"; out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    html_p = out / "map.html"; html_p.write_text(render_html(g, root), encoding="utf-8")
    report(g)
    print(f"   → {out / 'graph.json'}\n   → {html_p}")
    if not a.no_desktop and DESKTOP.exists():
        shutil.copy2(html_p, DESKTOP / "지식지도.html"); print(f"   → {DESKTOP / '지식지도.html'} (바탕화면 복사)")
    if a.open: os.startfile(html_p)  # Windows
    if a.check and g["stats"]["dangling"]: sys.exit(1)

if __name__ == "__main__":
    main()
