#!/usr/bin/env python3
"""QUEST — 목표지향 검색·확보 에이전트 CLI.  python quest/q.py <명령> ...

  new "<목표>" --type T --criteria "a;b" [--budget N]   컴퓨터(런 폴더) 생성
  brief                                               목표·완료조건·todo·최근 행동 되뇌기 (매 단계 전)
  todo "- [ ] ..." | todo --done N                    계획 갱신
  search "<질의>" [--engines a,b] [--lang en,ko] [--n 10] [--type T]
  read <url> [--js] [--force] [--no-links] [--no-images]
  grab <url> [--kind K] [--source-page P] [--license "<힌트>"] [--all-iiif]
             [--upload --remote /srv/<축>/<슬러그>/ --title T --evidence ev-id --verses "a;b"]
  classify                                            결과·파일 분류 → triage.json
  escalate <막힘> [--domain d] [--query q]             우회 사다리 (no-results|403|404|empty-js|paywall|login|captcha|rate-limit)
  finding "<문장>" --url U [--grade A|B|C]            findings.md에 출처 있는 발견 추가
  check [--mark N]                                    완료 조건 표시·표기
  done [--status done|partial] [--lesson "..."]       종료 + 플레이북 학습
  learn report                                        플레이북 통계
  status                                              열린 퀘스트 목록
설계: docs/superpowers/specs/2026-10-25-quest-design.md · 규율: .claude/skills/godisalive-quest/SKILL.md
"""
import argparse, importlib, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core import workspace as W

def need_run():
    run = W.current_run()
    if not run: sys.exit("열린 퀘스트가 없다 — 먼저: python quest/q.py new \"<목표>\" --type T --criteria \"a;b\"")
    return run

def playbook():
    try:
        from core import learn as L; return L, L.load_playbook()
    except Exception: return None, None

def plugin():
    try: return importlib.import_module(f"plugins.{W.CONFIG.get('plugin')}")
    except Exception: return None

# ── 명령 ─────────────────────────────────────────────────────────────────
def cmd_new(a):
    crit = [c for c in a.criteria.split(";")] if a.criteria else []
    run = W.new_run(a.goal, a.type, crit, a.budget, slug=a.slug)
    print(f"🧭 퀘스트 생성: {run}\n" + W.brief(run))

def cmd_brief(a):
    run = need_run(); L, pb = playbook()
    lessons = L.lessons_for(pb, W.load_state(run)["goal_type"]) if L else None
    print(W.brief(run, lessons))

def cmd_todo(a):
    run = need_run()
    if a.done: print("표기" if W.todo_done(run, a.done) else "번호 없음")
    elif a.text: W.todo_add(run, a.text)
    print(W.todo_text(run))

def cmd_check(a):
    run = need_run()
    for i, d, t in W.check(run, a.mark): print(f"   {'✓' if d else '☐'} {i}. {t}")
    if W.all_done(run): print("모든 완료 조건 ✓ — `done`으로 마무리")

def cmd_status(a):
    rows = W.list_runs()
    if not rows: print("퀘스트 없음"); return
    for s in rows: print(f"{s['id']:<42} {s['status']:<8} {s['steps']}/{s['budget']:<4} {s['goal'][:60]}")

def cmd_log(a):
    run = need_run(); step = W.log_action(run, a.tool, {}, not a.fail, a.summary); print(f"#{step} 기록")

def cmd_finding(a):
    run = need_run()
    line = f"- {a.text} — {a.url}" + (f" · 등급 {a.grade}" if a.grade else "") + f" · {W.now()[:10]}"
    with (run / "findings.md").open("a", encoding="utf-8") as f: f.write(line + "\n")
    W.log_action(run, "finding", {"url": a.url, "grade": a.grade}, True, a.text[:90]); print(line)

def cmd_search(a):
    run = need_run(); st = W.load_state(run); from core import search as S
    L, pb = playbook(); gtype = a.type or st["goal_type"]
    engines = a.engines.split(",") if a.engines else None
    rank = (lambda c, g: L.rank_engines(pb, g, c)) if L else None
    res = S.search(a.query, engines=engines, langs=tuple(a.lang.split(",")), n=a.n, goal_type=gtype, rank=rank)
    step = st["steps"] + 1; path = run / "search" / f"{step:03d}-{W.slugify(a.query, 30)}.json"
    path.write_text(json.dumps({"query": a.query, "goal_type": gtype, "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    per = {e: (len(v) if isinstance(v, list) else -1) for e, v in res.items()}
    total = sum(v for v in per.values() if v > 0)
    W.log_action(run, "search", {"q": a.query, "engines": list(res)}, total > 0, f"{a.query[:50]} → {total}건 " + " ".join(f"{e}:{v}" for e, v in per.items()),
                 path=str(path.relative_to(W.ROOT)), data={"per_engine": per, "goal_type": gtype})
    print(S.format_table(res, a.limit)); print(f"→ {path}")
    if total == 0: print("0건 — `python quest/q.py escalate no-results` 로 사다리를 보라")

def cmd_addresult(a):
    """Peter가 세션 도구(WebSearch 등)로 얻은 결과를 검색 기록에 편입 — ddg/bing이 봇 차단일 때의 공식 경로."""
    run = need_run(); st = W.load_state(run)
    row = {"engine": a.engine, "type": a.type or "web", "title": a.title, "url": a.url, "snippet": a.snippet or "", "license": a.license, "extra": {}}
    step = st["steps"] + 1; path = run / "search" / f"{step:03d}-{a.engine}-{W.slugify(a.title, 30)}.json"
    path.write_text(json.dumps({"query": a.query or a.title, "goal_type": st["goal_type"], "results": {a.engine: [row]}}, ensure_ascii=False, indent=1), encoding="utf-8")
    W.log_action(run, "search", {"q": a.query or a.title, "engines": [a.engine]}, True, f"[{a.engine}] {a.title[:60]} — {a.url[:60]}",
                 path=str(path.relative_to(W.ROOT)), data={"per_engine": {a.engine: 1}, "goal_type": st["goal_type"], "manual": True})
    print(f"＋ [{a.engine}] {a.title} — {a.url}\n→ {path}")

def cmd_read(a):
    run = need_run(); st = W.load_state(run); from core import read as R, http as H
    page = R.read_url(a.url, js=a.js, force=a.force, want_links=not a.no_links, want_images=not a.no_images)
    step = st["steps"] + 1; path = None
    if not page.get("error"): path = R.save_page(page, run / "pages", step)
    ok = not page.get("error")
    W.log_action(run, "read", {"url": a.url, "js": a.js}, ok, (f"{page.get('title','')[:50]} · {len(page.get('text',''))}자 · {page.get('via')}" if ok else f"실패 {page.get('error')}"),
                 path=str(path.relative_to(W.ROOT)) if path else None,
                 data={"domain": H.domain_of(a.url), "via": page.get("via"), "status": page.get("status"), "chars": len(page.get("text", ""))})
    if ok:
        print(f"📄 {page.get('title')} · {len(page['text'])}자 · via {page['via']} · 링크 {len(page.get('links', []))} · 이미지 {len(page.get('images', []))}\n→ {path}\n")
        print(page["text"][:1500] + ("\n…(이하 파일)" if len(page["text"]) > 1500 else ""))
    else:
        print(f"✖ {page.get('error')}")
        try:
            from core import escalate as E
            b = "403" if "403" in str(page.get("error")) else "404" if "404" in str(page.get("error")) else "empty-js" if "본문" in str(page.get("error")) else "403"
            first = E.ladder(b, domain=H.domain_of(a.url), pb=playbook()[1])[0]
            print(f"다음 시도 → {first['title']}: {first['command']}")
        except Exception: pass

def cmd_grab(a):
    run = need_run(); from core import grab as G, http as H
    entry = G.grab(a.url, run / "downloads", kind=a.kind, source_page=a.source_page, license_hint=a.license, limits=W.CONFIG["limits"], all_iiif=a.all_iiif)
    if "error" in entry:
        W.log_action(run, "grab", {"url": a.url}, False, entry["error"], data={"domain": H.domain_of(a.url)}); print(f"✖ {entry['error']}"); return
    uploaded = False; asset_id = None
    if a.upload:
        from core import storage as ST
        if not a.remote: sys.exit("--upload 에는 --remote /srv/<축>/<슬러그>/ 필요")
        remote = a.remote.rstrip("/") + "/" + Path(entry["path"]).name
        up = ST.upload(Path(entry["path"]), remote)
        uploaded = up.get("ok", False)
        if uploaded:
            asset_id = ST.register_asset(entry, title=a.title or Path(entry["path"]).stem, source=H.domain_of(a.source_page or a.url), source_url=a.source_page or a.url,
                                         railway_path=remote, evidence_id=a.evidence, verses=[v for v in (a.verses or "").split(";") if v], credit=entry.get("credit"))
            print(f"☁ 업로드 {remote} · catalog {asset_id}")
        else: print(f"✖ 업로드 실패: {up}")
    W.log_action(run, "grab", {"url": a.url, "kind": entry["kind"]}, True, f"{entry['kind']} {entry['bytes']:,}B · {entry.get('license')} · {Path(entry['path']).name}",
                 path=entry["path"], data={"domain": H.domain_of(a.url), "kind": entry["kind"], "bytes": entry["bytes"], "license": entry.get("license"), "uploaded": uploaded, "asset_id": asset_id})
    print(f"📦 {entry['kind']} · {entry['bytes']:,}B · 라이선스 {entry.get('license')} (상업 {entry.get('commercial_ok')}) · sha {entry['sha256'][:12]}\n→ {entry['path']}")
    if entry.get("meta", {}).get("duplicate"): print("   (이미 받은 파일 — 중복)")

def cmd_classify(a):
    run = need_run(); from core import classify as C, grab as G
    items = []
    for p in sorted((run / "search").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for eng, v in d.get("results", {}).items():
            if isinstance(v, list): items.extend(v)
    items.extend(G.load_manifest(run / "downloads"))
    rows = C.classify_items(items, plugin())
    (run / "triage.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    W.log_action(run, "classify", {}, True, f"{len(rows)}건 분류", path=str((run / 'triage.json').relative_to(W.ROOT)), data={"n": len(rows)})
    print(C.format_triage(rows)); print(f"→ {run / 'triage.json'}")

def cmd_escalate(a):
    run = need_run(); from core import escalate as E
    L, pb = playbook(); W.set_blocked(run, a.blockage, a.domain)
    steps = E.ladder(a.blockage, domain=a.domain, query=a.query, pb=pb)
    W.log_action(run, "escalate", {"blockage": a.blockage, "domain": a.domain}, True, f"{a.blockage} @ {a.domain or '-'} → {len(steps)}단계", data={"blockage": a.blockage, "domain": a.domain})
    print(f"🪜 우회 사다리 — {a.blockage} @ {a.domain or '-'}")
    for s in steps: print(f"  {s['step']}. {s['title']}\n     왜: {s['why']}\n     $ {s['command']}")
    print("\n" + E.forbidden_text())

def cmd_done(a):
    run = need_run(); st = W.load_state(run)
    remaining = [t for _, d, t in W.check(run) if not d]
    status = a.status
    if status == "done" and remaining:
        status = "partial"; print("완료 조건이 남아 있어 partial로 기록:"); [print(f"   ☐ {t}") for t in remaining]
    L, pb = playbook(); summary = {}
    if L:
        summary = L.record_run(run, pb)
        if a.lesson: L.add_lesson(pb, run.name, st["goal_type"], a.lesson)
        L.save_playbook(pb)
    W.finish(run, status, a.lesson)
    try:
        from core import grab as G; files = len(G.load_manifest(run / "downloads"))
    except Exception: files = "?"
    print(f"🏁 {status} · 행동 {st['steps']}/{st['budget']} · 확보 파일 {files} · 플레이북 {summary}")
    if remaining: print("남은 일 → NEXT.md에 올릴 것:"); [print(f"   - {t}") for t in remaining]

def cmd_learn(a):
    from core import learn as L; pb = L.load_playbook()
    if a.what == "report": print(L.report(pb))
    else: print("learn report")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("new"); p.add_argument("goal"); p.add_argument("--type", default="mixed", choices=["web", "text", "image", "object", "paper", "video", "place", "mixed"]); p.add_argument("--criteria", default=""); p.add_argument("--budget", type=int); p.add_argument("--slug", help="폴더 이름 (기본: 목표에서 생성)"); p.set_defaults(f=cmd_new)
    sp.add_parser("brief").set_defaults(f=cmd_brief)
    p = sp.add_parser("todo"); p.add_argument("text", nargs="?"); p.add_argument("--done", type=int); p.set_defaults(f=cmd_todo)
    p = sp.add_parser("check"); p.add_argument("--mark", type=int); p.set_defaults(f=cmd_check)
    sp.add_parser("status").set_defaults(f=cmd_status)
    p = sp.add_parser("log"); p.add_argument("tool"); p.add_argument("summary"); p.add_argument("--fail", action="store_true"); p.set_defaults(f=cmd_log)
    p = sp.add_parser("finding"); p.add_argument("text"); p.add_argument("--url", required=True); p.add_argument("--grade"); p.set_defaults(f=cmd_finding)
    p = sp.add_parser("search"); p.add_argument("query"); p.add_argument("--engines"); p.add_argument("--lang", default="en,ko"); p.add_argument("--n", type=int, default=10); p.add_argument("--type"); p.add_argument("--limit", type=int, default=12); p.set_defaults(f=cmd_search)
    p = sp.add_parser("addresult"); p.add_argument("title"); p.add_argument("url"); p.add_argument("--snippet"); p.add_argument("--engine", default="websearch"); p.add_argument("--type"); p.add_argument("--license"); p.add_argument("--query"); p.set_defaults(f=cmd_addresult)
    p = sp.add_parser("read"); p.add_argument("url"); p.add_argument("--js", action="store_true"); p.add_argument("--force", action="store_true"); p.add_argument("--no-links", action="store_true"); p.add_argument("--no-images", action="store_true"); p.set_defaults(f=cmd_read)
    p = sp.add_parser("grab"); p.add_argument("url"); p.add_argument("--kind"); p.add_argument("--source-page"); p.add_argument("--license"); p.add_argument("--all-iiif", action="store_true")
    p.add_argument("--upload", action="store_true"); p.add_argument("--remote"); p.add_argument("--title"); p.add_argument("--evidence"); p.add_argument("--verses"); p.set_defaults(f=cmd_grab)
    sp.add_parser("classify").set_defaults(f=cmd_classify)
    p = sp.add_parser("escalate"); p.add_argument("blockage"); p.add_argument("--domain"); p.add_argument("--query"); p.set_defaults(f=cmd_escalate)
    p = sp.add_parser("done"); p.add_argument("--status", default="done", choices=["done", "partial"]); p.add_argument("--lesson"); p.set_defaults(f=cmd_done)
    p = sp.add_parser("learn"); p.add_argument("what", nargs="?", default="report"); p.set_defaults(f=cmd_learn)
    a = ap.parse_args(); a.f(a)

if __name__ == "__main__":
    main()
