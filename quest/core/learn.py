#!/usr/bin/env python3
"""플레이북 — 엔진·도메인·우회 경로별 성공률을 log.jsonl에서 자동 집계하고, 교훈 문장을 쌓는다.
playbook.json 은 사람이 읽고 고칠 수 있는 평범한 JSON이다(블랙박스 금지)."""
import json
from pathlib import Path

from core.workspace import ROOT, read_log, load_state, now

PLAYBOOK_PATH = ROOT / "quest" / "playbook.json"


def _empty() -> dict:
    return {"engines": {}, "domains": {}, "routes": {}, "lessons": []}


def load_playbook() -> dict:
    if not PLAYBOOK_PATH.exists():
        save_playbook(_empty())
    try:
        pb = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        pb = _empty()
    for k, v in _empty().items(): pb.setdefault(k, v)
    return pb


def save_playbook(pb: dict) -> None:
    PLAYBOOK_PATH.write_text(json.dumps(pb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _dom(d) -> str:
    d = (d or "").lower().strip()
    return d[4:] if d.startswith("www.") else d


def _route(pb: dict, key: str) -> dict:
    return pb.setdefault("routes", {}).setdefault(key, {"tries": 0, "success": 0})


def _domain_entry(pb: dict, domain: str, ts: str) -> dict:
    return pb.setdefault("domains", {}).setdefault(domain, {"status": "ok", "via_success": [], "last": ts, "grabs": 0})


def record_run(run: Path, pb: dict | None = None) -> dict:
    own = pb is None
    pb = load_playbook() if own else pb
    for k, v in _empty().items(): pb.setdefault(k, v)
    goal_type = load_state(run).get("goal_type", "mixed")
    engines_touched, domains_touched = set(), set()
    for row in read_log(run):
        tool, data, ok, ts = row.get("tool"), row.get("data") or {}, bool(row.get("ok")), row.get("ts") or now()
        if tool == "search":
            for eng, count in (data.get("per_engine") or {}).items():
                rec = pb["engines"].setdefault(eng, {}).setdefault(goal_type, {"tries": 0, "hits": 0})
                rec["tries"] += 1
                if isinstance(count, (int, float)) and count > 0: rec["hits"] += 1      # -1 = 엔진 오류 → 시도만 센다
                engines_touched.add((eng, goal_type))
        elif tool == "read":
            domain = _dom(data.get("domain"))
            if not domain: continue
            via, status = data.get("via"), data.get("status")
            prev = pb["domains"].get(domain, {})
            if ok: st = "ok"
            elif data.get("chars") == 0 and status == 200: st = "js-required"
            elif status in (401, 403, 429): st = "blocked"
            elif status in (404, 410): st = "dead"
            else: st = "blocked"
            vias = set(prev.get("via_success", []))
            if ok and via: vias.add(via)
            pb["domains"][domain] = {**prev, "status": st, "via_success": sorted(vias), "last": ts, "grabs": prev.get("grabs", 0)}
            if ok and via == "wayback":
                r = _route(pb, "blocked->wayback"); r["tries"] += 1; r["success"] += 1
            domains_touched.add(domain)
        elif tool == "grab" and ok:
            domain = _dom(data.get("domain"))
            if not domain: continue
            e = _domain_entry(pb, domain, ts); e["grabs"] = e.get("grabs", 0) + 1; e["last"] = ts
            domains_touched.add(domain)
        elif tool == "escalate":
            b = data.get("blockage")
            if b: _route(pb, f"{b}->*")["tries"] += 1
    if own: save_playbook(pb)
    return {"engines_updated": len(engines_touched), "domains_updated": len(domains_touched)}


def rank_engines(pb: dict, goal_type: str, candidates: list) -> list:
    def score(e):
        r = (pb.get("engines", {}).get(e, {}) or {}).get(goal_type) or {}
        return (r.get("hits", 0) + 1) / (r.get("tries", 0) + 2)
    return sorted(candidates, key=lambda e: -score(e))       # sorted 는 안정 정렬 → 동점이면 candidates 순서


def add_lesson(pb: dict, run_id: str, goal_type: str, text: str) -> None:
    pb.setdefault("lessons", []).append({"date": now()[:10], "run": run_id, "goal_type": goal_type, "text": text})


def lessons_for(pb: dict, goal_type: str, k: int = 3) -> list:
    ls = list(reversed(pb.get("lessons", [])))
    same = [l["text"] for l in ls if l.get("goal_type") == goal_type]
    other = [l["text"] for l in ls if l.get("goal_type") != goal_type]
    return (same + other)[:k]


def domain_note(pb: dict, domain: str) -> dict | None:
    return pb.get("domains", {}).get(_dom(domain))


def report(pb: dict) -> str:
    out = ["── 엔진 (목표유형별 적중/시도)"]
    rows = [(e, gt, r) for e, d in pb.get("engines", {}).items() for gt, r in d.items()]
    for e, gt, r in sorted(rows, key=lambda x: (x[1], -(x[2]["hits"] + 1) / (x[2]["tries"] + 2))):
        t, h = r["tries"], r["hits"]
        out.append(f"   {gt:<7} {e:<14} {h}/{t}  적중률 {h / t:.0%}" if t else f"   {gt:<7} {e:<14} 0/0")
    if not rows: out.append("   (기록 없음)")
    out.append("── 도메인")
    for d, v in sorted(pb.get("domains", {}).items()):
        out.append(f"   {d:<30} {v.get('status', '?'):<12} via={','.join(v.get('via_success', [])) or '-'} grabs={v.get('grabs', 0)}")
    if not pb.get("domains"): out.append("   (기록 없음)")
    out.append("── 우회 경로")
    for k, v in sorted(pb.get("routes", {}).items()):
        out.append(f"   {k:<22} 성공 {v.get('success', 0)}/{v.get('tries', 0)}")
    if not pb.get("routes"): out.append("   (기록 없음)")
    out.append("── 최근 교훈")
    for l in pb.get("lessons", [])[-5:]:
        out.append(f"   [{l['date']}] ({l['goal_type']}) {l['text']}")
    if not pb.get("lessons"): out.append("   (기록 없음)")
    return "\n".join(out)
