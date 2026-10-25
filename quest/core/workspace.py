#!/usr/bin/env python3
"""QUEST 컴퓨터(작업 폴더) — Manus의 '작업마다 자기 컴퓨터' 개념.

퀘스트 하나 = 폴더 하나:
  goal.md · todo.md · log.jsonl · findings.md · state.json · search/ · pages/ · downloads/ · triage.json
모든 도구는 log_action()으로 행동과 결과(실패 포함)를 남기고, brief()가 그것을 한 화면으로 되뇌어 준다.
"""
import json, os, re, sys
from datetime import datetime
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]          # quest/ 폴더 (이름이 바뀌어도 동작)
ROOT = HOME.parent                                   # 프로젝트 루트
CONFIG = json.loads((HOME / "config.json").read_text(encoding="utf-8"))

def _runs_dir() -> Path:
    env = os.environ.get("QUEST_RUNS_DIR")
    return Path(env) if env else ROOT / CONFIG.get("runs_dir", "quest/runs")

RUNS_DIR = _runs_dir()

def now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def slugify(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:limit].strip("-") or "quest"

# ── 생성·현재 퀘스트 ────────────────────────────────────────────────────
def new_run(goal: str, goal_type: str, criteria: list, budget: int | None = None, slug: str | None = None) -> Path:
    runs = _runs_dir(); runs.mkdir(parents=True, exist_ok=True)
    budget = budget or CONFIG.get("default_budget", 40)
    rid = f"{datetime.now():%Y-%m-%d}-{slug or slugify(goal)}"
    run = runs / rid
    k = 2
    while run.exists():
        run = runs / f"{rid}-{k}"; k += 1
    for d in ("search", "pages", "downloads"): (run / d).mkdir(parents=True, exist_ok=True)
    crit = [c.strip() for c in criteria if c and c.strip()]
    state = {"id": run.name, "goal": goal, "goal_type": goal_type, "criteria": [{"text": c, "done": False} for c in crit],
             "budget": budget, "steps": 0, "status": "open", "blocked": None, "created": now(), "finished": None, "lesson": None}
    save_state(run, state)
    (run / "goal.md").write_text(
        f"# 목표\n{goal}\n\n- 유형: {goal_type} · 예산: {budget} 행동 · 생성: {state['created']}\n\n## 완료 조건\n"
        + "".join(f"- [ ] {c}\n" for c in crit)
        + f"\n## 제약\n- 합법 경로만 ({CONFIG.get('spec_ref', '설계서 반목표 절')}). 라이선스 미확인 이미지는 책에 쓰지 않음.\n"
        + "- 출처 없는 발견은 발견이 아니다 — findings.md의 모든 항목에 URL.\n", encoding="utf-8")
    (run / "todo.md").write_text("# TODO (매 단계 갱신 — Manus recitation)\n- [ ] 첫 검색: 목표의 핵심 명칭으로 기본 엔진 돌리기\n", encoding="utf-8")
    (run / "log.jsonl").write_text("", encoding="utf-8")
    (run / "findings.md").write_text(f"# 발견 — {goal}\n\n(항목마다 출처 URL · 날짜 · 등급 메모)\n", encoding="utf-8")
    set_current(run)
    return run

def set_current(run: Path) -> None:
    runs = _runs_dir(); runs.mkdir(parents=True, exist_ok=True)
    (runs / "CURRENT").write_text(run.name, encoding="utf-8")

def current_run() -> Path | None:
    p = _runs_dir() / "CURRENT"
    if not p.exists(): return None
    run = _runs_dir() / p.read_text(encoding="utf-8").strip()
    return run if run.exists() else None

def list_runs() -> list:
    runs = _runs_dir()
    if not runs.exists(): return []
    out = []
    for d in sorted(runs.iterdir()):
        if (d / "state.json").exists(): out.append(load_state(d))
    return out

# ── 상태·로그 ────────────────────────────────────────────────────────────
def load_state(run: Path) -> dict:
    return json.loads((run / "state.json").read_text(encoding="utf-8"))

def save_state(run: Path, state: dict) -> None:
    (run / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def log_action(run: Path, tool: str, args: dict, ok: bool, summary: str, path: str | None = None, data: dict | None = None) -> int:
    st = load_state(run); st["steps"] += 1; step = st["steps"]
    row = {"ts": now(), "step": step, "tool": tool, "args": args, "ok": bool(ok), "summary": summary, "path": path, "data": data or {}}
    with (run / "log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    save_state(run, st)
    return step

def read_log(run: Path) -> list:
    p = run / "log.jsonl"
    if not p.exists(): return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: continue          # 깨진 줄은 건너뛴다 (Review Focus 5)
    return rows

# ── todo ─────────────────────────────────────────────────────────────────
def todo_text(run: Path) -> str:
    return (run / "todo.md").read_text(encoding="utf-8")

def todo_add(run: Path, text: str) -> None:
    text = text.strip()
    if not text.startswith("- ["): text = f"- [ ] {text}"
    with (run / "todo.md").open("a", encoding="utf-8") as f: f.write(text + "\n")

def _todo_items(run: Path) -> list:
    return [(i, l) for i, l in enumerate((run / "todo.md").read_text(encoding="utf-8").split("\n")) if l.startswith("- [")]

def todo_done(run: Path, index: int) -> bool:
    lines = (run / "todo.md").read_text(encoding="utf-8").split("\n")
    items = [i for i, l in enumerate(lines) if l.startswith("- [")]
    if not 1 <= index <= len(items): return False
    i = items[index - 1]; lines[i] = lines[i].replace("- [ ]", "- [x]", 1)
    (run / "todo.md").write_text("\n".join(lines), encoding="utf-8")
    return True

# ── 완료 조건·막힘 ───────────────────────────────────────────────────────
def check(run: Path, mark: int | None = None) -> list:
    st = load_state(run)
    if mark is not None and 1 <= mark <= len(st["criteria"]):
        st["criteria"][mark - 1]["done"] = True; save_state(run, st)
    return [(i + 1, c["done"], c["text"]) for i, c in enumerate(st["criteria"])]

def all_done(run: Path) -> bool:
    return all(d for _, d, _ in check(run))

def set_blocked(run: Path, blockage: str | None, domain: str | None) -> None:
    st = load_state(run); st["blocked"] = {"type": blockage, "domain": domain} if blockage else None; save_state(run, st)

def finish(run: Path, status: str, lesson: str | None) -> dict:
    st = load_state(run); st["status"] = status; st["finished"] = now(); st["lesson"] = lesson; save_state(run, st); return st

# ── 브리프 (되뇌기) ──────────────────────────────────────────────────────
def brief(run: Path, lessons: list | None = None) -> str:
    st = load_state(run); rows = read_log(run)
    out = [f"🎯 {st['goal']}", f"   유형 {st['goal_type']} · 행동 {st['steps']}/{st['budget']} · 상태 {st['status']} · {st['id']}"]
    out.append("── 완료 조건")
    for i, c in enumerate(st["criteria"], 1): out.append(f"   {'✓' if c['done'] else '☐'} {i}. {c['text']}")
    if st.get("blocked"): out.append(f"── ⚠ 막힘: {st['blocked']['type']} @ {st['blocked'].get('domain') or '-'} → `python quest/q.py escalate {st['blocked']['type']}`")
    out.append("── TODO")
    for _, l in _todo_items(run): out.append("   " + l)
    out.append("── 최근 행동")
    for r in rows[-8:]:
        out.append(f"   #{r['step']} {r['tool']:<8} {'✔' if r['ok'] else '✖'} {str(r['summary'])[:90]}")
    if not rows: out.append("   (아직 없음)")
    if lessons:
        out.append("── 지난 퀘스트의 교훈")
        for l in lessons: out.append(f"   · {l}")
    rem = st["budget"] - st["steps"]
    if rem <= 5: out.append(f"── ⏳ 예산 {rem}행동 남음 — 정리 단계로")
    return "\n".join(out)
