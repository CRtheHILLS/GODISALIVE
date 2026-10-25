#!/usr/bin/env python3
"""플레이북 — 엔진·도메인·우회 경로별 성공률을 log.jsonl에서 자동 집계하고, 교훈 문장을 쌓는다.
playbook.json 은 사람이 읽고 고칠 수 있는 평범한 JSON이다(블랙박스 금지)."""
import json
from pathlib import Path

from core.workspace import ROOT, read_log, load_state, now

from core.workspace import HOME
PLAYBOOK_PATH = HOME / "playbook.json"


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
    tmp = PLAYBOOK_PATH.with_suffix(".json.tmp")          # 원자적 저장 — 쓰다 죽어도 기존 플레이북은 남는다
    tmp.write_text(json.dumps(pb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(PLAYBOOK_PATH)


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
    pending = {}   # escalate 뒤 같은 도메인에서 처음 성공한 read/grab → "<막힘>-><경로>" 성공으로 기록
    for row in read_log(run):
        tool, data, ok, ts = row.get("tool"), row.get("data") or {}, bool(row.get("ok")), row.get("ts") or now()
        if tool in ("read", "grab") and ok:
            d = _dom(data.get("domain"))
            if d in pending:
                r = _route(pb, f"{pending.pop(d)}->{data.get('via') or tool}"); r["tries"] += 1; r["success"] += 1
        if tool == "search":
            if data.get("manual"): continue                   # addresult(세션 WebSearch 편입)는 엔진 통계에 넣지 않는다
            gt = data.get("goal_type") or goal_type           # search --type X 로 돌린 검색은 X 유형으로 적립
            for eng, count in (data.get("per_engine") or {}).items():
                if not isinstance(count, (int, float)) or count < 0: continue   # -1 = 엔진 오류(키 없음 등) → 통계 제외
                rec = pb["engines"].setdefault(eng, {}).setdefault(gt, {"tries": 0, "hits": 0})
                rec["tries"] += 1
                if count > 0: rec["hits"] += 1
                engines_touched.add((eng, gt))
        elif tool == "read":
            domain = _dom(data.get("domain"))
            if not domain: continue
            via, status = data.get("via"), data.get("status")
            prev = pb["domains"].get(domain, {})
            if ok: st = "ok"
            elif status == 200 and (data.get("chars") or 0) < 200: st = "js-required"   # 200인데 본문이 거의 없음 → JS 렌더링 필요
            elif status in (401, 403, 429): st = "blocked"
            elif status in (404, 410): st = "dead"
            elif not status: st = "error"                                               # 연결 실패 — 차단이 아니다
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
            if b:
                _route(pb, f"{b}->*")["tries"] += 1
                if data.get("domain"): pending[_dom(data.get("domain"))] = b
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
