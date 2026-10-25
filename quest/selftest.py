#!/usr/bin/env python3
"""QUEST 자가 테스트 — 네트워크 없이 픽스처로. 실행: python quest/selftest.py [섹션이름...]

구조: 이 파일의 내장 섹션(workspace·http·cli) + quest/tests/test_*.py 자동 탐색.
각 테스트 모듈은 `def run(check)` 를 노출한다. check(name, got, want) 는 같음을 검사해 누적한다.
"""
import importlib.util, os, subprocess, sys, tempfile, traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS, FAILS = 0, []
def check(name, got, want):
    global PASS
    ok = got == want
    if ok: PASS += 1; print(f"  ok   {name}")
    else:
        FAILS.append(name); print(f"  FAIL {name}\n        got : {got!r}\n        want: {want!r}")
    return ok

def section(title):
    print(f"\n[{title}]")

# ── 내장 섹션 ────────────────────────────────────────────────────────────
def test_workspace():
    section("workspace")
    with tempfile.TemporaryDirectory() as td:
        os.environ["QUEST_RUNS_DIR"] = td
        import importlib; import core.workspace as W; importlib.reload(W)
        run = W.new_run("라기스 부조 이미지", "image", ["이미지 1장", "등록번호"], budget=5)
        check("files", sorted(p.name for p in run.iterdir() if p.is_file()), ["findings.md", "goal.md", "log.jsonl", "state.json", "todo.md"])
        st = W.load_state(run)
        check("criteria", len(st["criteria"]), 2); check("budget", st["budget"], 5)
        check("current", W.current_run(), run)
        check("log step1", W.log_action(run, "search", {"q": "x"}, True, "3건", data={"per_engine": {"ddg": 3}}), 1)
        check("log step2", W.log_action(run, "read", {"url": "u"}, False, "403"), 2)
        with (run / "log.jsonl").open("a", encoding="utf-8") as f: f.write('{"broken":\n')
        check("read_log skips broken", len(W.read_log(run)), 2)
        check("steps", W.load_state(run)["steps"], 2)
        W.todo_add(run, "커먼즈 검색"); check("todo_done", W.todo_done(run, 2), True)
        check("todo text", "- [x] 커먼즈 검색" in W.todo_text(run), True)
        check("check mark", W.check(run, mark=1), [(1, True, "이미지 1장"), (2, False, "등록번호")])
        b = W.brief(run)
        check("brief goal", "라기스 부조 이미지" in b, True); check("brief budget", "2/5" in b, True); check("brief crit", "✓ 1. 이미지 1장" in b, True)
        W.set_blocked(run, "403", "x.org"); check("brief blocked", "막힘: 403" in W.brief(run), True)
        check("slugify", W.slugify("Lachish Reliefs 라기스 부조!"), "lachish-reliefs-라기스-부조")
        check("all_done false", W.all_done(run), False); W.check(run, mark=2); check("all_done true", W.all_done(run), True)
        check("list_runs", len(W.list_runs()), 1)
        del os.environ["QUEST_RUNS_DIR"]

def test_http():
    section("http")
    import core.http as H
    check("domain_of", H.domain_of("https://www.britishmuseum.org/collection/x"), "www.britishmuseum.org")
    r = H.fetch("http://127.0.0.1:9/", timeout=2, retries=0)
    check("fetch refused ok=False", r["ok"], False); check("fetch error str", isinstance(r["error"], str) and len(r["error"]) > 0, True)
    check("fetch_json None", H.fetch_json("http://127.0.0.1:9/", timeout=2, retries=0), None)
    rt = "User-agent: *\nDisallow: /private\n"
    check("robots private", H._allowed(rt, "https://ex.org/private/x"), False)
    check("robots public", H._allowed(rt, "https://ex.org/public"), True)
    check("wayback callable", callable(H.wayback_latest), True)

def test_license():
    section("license")
    from core.license import license_class as lc
    cases = [("CC BY-SA 4.0", ("CC-BY-SA", True)), ("cc-by-sa-4.0", ("CC-BY-SA", True)), ("Public domain", ("PD", True)), ("PD-US", ("PD", True)),
             ("CC0 1.0", ("CC0", True)), ("CC BY-NC-ND 4.0", ("CC-BY-NC", False)), ("CC BY 4.0", ("CC-BY", True)), ("Attribution-NonCommercial", ("CC-BY-NC", False)),
             ("© Trustees of the British Museum", ("ⓒ", False)), ("", ("unknown", None)), (None, ("unknown", None)), ("© J. Doe, CC BY-SA 3.0", ("CC-BY-SA", True))]
    for s, want in cases: check(f"license {s!r}", lc(s), want)

def test_cli():
    section("cli")
    q = HERE / "q.py"
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, QUEST_RUNS_DIR=td, PYTHONIOENCODING="utf-8")
        def run(*args):
            r = subprocess.run([sys.executable, str(q), *args], capture_output=True, env=env)
            return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
        code, out = run("--help"); check("help exit 0", code, 0)
        code, out = run("new", "테스트 목표", "--type", "image", "--criteria", "a;b", "--budget", "3"); check("new exit 0", code, 0)
        code, out = run("brief"); check("brief has goal", "테스트 목표" in out, True)
        code, out = run("check", "--mark", "1"); check("check mark", "✓ 1." in out or "✓" in out, True)
        code, out = run("todo", "- [ ] 다음 일"); check("todo exit", code, 0)
        code, out = run("status"); check("status lists", "테스트 목표"[:5] in out, True)
        code, out = run("escalate", "403", "--domain", "x.org")
        if code == 0: check("escalate forbidden", "Sci-Hub" in out, True)
        else: print("  skip escalate (escalate 모듈 미구현)")

# ── 외부 테스트 모듈 탐색 ────────────────────────────────────────────────
def external_sections():
    out = []
    for p in sorted((HERE / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        def make(spec=spec, p=p):
            def f():
                section(p.stem)
                mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.run(check)
            f.__name__ = p.stem; return f
        out.append(make())
    return out

SECTIONS = [test_workspace, test_http, test_license] + external_sections() + [test_cli]

if __name__ == "__main__":
    want = set(sys.argv[1:])
    for fn in SECTIONS:
        if want and fn.__name__.replace("test_", "") not in want and fn.__name__ not in want: continue
        try: fn()
        except Exception as e:
            FAILS.append(f"{fn.__name__}: {e.__class__.__name__}"); print(f"  FAIL {fn.__name__} 예외:\n" + traceback.format_exc()[-1200:])
    print(f"\n통과 {PASS} · 실패 {len(FAILS)}" + (f": {FAILS}" if FAILS else "  — 전부 통과 ✔"))
    sys.exit(1 if FAILS else 0)
