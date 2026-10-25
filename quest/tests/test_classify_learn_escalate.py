"""Task 4 테스트 — classify · learn · escalate · godisalive 플러그인. 네트워크 없음, 실제 playbook.json은 건드리지 않는다."""
import json, os, tempfile
from pathlib import Path


def run(check):
    import core.workspace as W
    import core.classify as C
    import core.learn as L
    import core.escalate as E
    import plugins.godisalive as P

    # ── classify: 라이선스 (license_class 재사용) ────────────────────────
    lic = [("CC BY-SA 4.0", "CC-BY-SA", True), ("cc-by-sa-4.0", "CC-BY-SA", True), ("Public domain", "PD", True), ("PD-US", "PD", True),
           ("CC0 1.0", "CC0", True), ("CC BY-NC-ND", "CC-BY-NC", False), ("CC BY 4.0", "CC-BY", True),
           ("© Trustees of the British Museum", "ⓒ", False), ("", "unknown", None)]
    items = [{"engine": "t", "type": "image", "title": f"t{i}", "url": f"https://example.org/{i}", "snippet": "", "license": s, "extra": {}} for i, (s, _, _) in enumerate(lic)]
    rows = C.classify_items(items)
    for (s, cls, ok), r in zip(lic, rows):
        check(f"classify license {s!r}", (r["license_class"], r["commercial_ok"]), (cls, ok))
    check("classify keys", sorted(rows[0]), sorted(["ref", "media", "license_class", "commercial_ok", "authority_tier", "grade_ceiling", "axis", "verses", "lang", "dup_of", "title"]))

    # ── authority / ceiling / lang ───────────────────────────────────────
    check("tier britishmuseum", C.authority_tier("https://www.britishmuseum.org/collection/object/W_1856-0909-14"), 1)
    check("tier wikipedia", C.authority_tier("https://en.wikipedia.org/x"), 2)
    check("tier tistory", C.authority_tier("https://someblog.tistory.com/1"), 4)
    check("tier .edu", C.authority_tier("https://oi.uchicago.edu/x"), 1)
    check("tier .ac.uk", C.authority_tier("https://www.ox.ac.uk/x"), 1)
    check("tier news", C.authority_tier("https://www.bbc.com/news/1"), 3)
    check("tier plugin override", C.authority_tier("https://x.example.com/", plugin=type("P", (), {"authority_override": staticmethod(lambda d: 3)})()), 3)
    check("ceiling", [C.grade_ceiling(t) for t in (1, 2, 3, 4)], ["A", "B", "C", "C"])
    check("lang ko", C.detect_lang("라기스 부조는 산헤립의"), "ko")
    check("lang en", C.detect_lang("The Lachish reliefs depict"), "en")
    check("lang he", C.detect_lang("בראשית ברא אלהים"), "he")
    check("lang el", C.detect_lang("Ἐν ἀρχῇ ἦν ὁ λόγος"), "el")
    check("lang de", C.detect_lang("Der König und die Stadt ist nicht mit dem Heer"), "de")
    check("media_of", [C.media_of({"type": "image"}), C.media_of({"kind": "pdf"}), C.media_of({"url": "u", "text": "x"})], ["image", "pdf", "text"])

    # ── 중복 ─────────────────────────────────────────────────────────────
    d = C.classify_items([
        {"engine": "commons", "type": "image", "title": "Lachish", "url": "https://commons.wikimedia.org/wiki/File:Lachish.jpg", "snippet": "", "license": "CC BY-SA 4.0", "extra": {}},
        {"engine": "ddg", "type": "web", "title": "Lachish", "url": "http://www.commons.wikimedia.org/wiki/File:Lachish.jpg/?utm=1#x", "snippet": "", "license": None, "extra": {}},
    ])
    check("dup_of first none", d[0]["dup_of"], None)
    check("dup_of second", d[1]["dup_of"], d[0]["ref"])
    s = C.classify_items([{"id": "a", "url": "u1", "sha256": "ff", "kind": "image"}, {"id": "b", "url": "u2", "sha256": "ff", "kind": "image"}])
    check("dup by sha", s[1]["dup_of"], "a")
    check("format_triage", "CC-BY-SA" in C.format_triage(d) and "Lachish" in C.format_triage(d), True)

    # ── 플러그인 ─────────────────────────────────────────────────────────
    check("tag_verses", P.tag_verses("왕하 18:13-19:37과 2 Kings 18 그리고 Isa 36-37"), ["왕하 18", "왕하 19", "사 36", "사 37"])
    check("tag_verses single", P.tag_verses("삼하 7:14 참조"), ["삼하 7"])
    check("axis arch", P.axis("excavation of the tell revealed pottery 발굴"), "archaeology")
    check("axis none", P.axis("lorem ipsum"), None)
    check("override", (P.authority_override("www.biblicalarchaeology.org"), P.authority_override("random.com")), (3, None))
    check("license_hint", P.license_hint("https://www.loc.gov/pictures/item/matpc.12345/"), "Public domain")
    check("tags", "라기스 부조" in P.tags("The Lachish reliefs from Nineveh"), True)

    # ── learn ────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get("QUEST_RUNS_DIR"); os.environ["QUEST_RUNS_DIR"] = td
        try:
            run_dir = W.new_run("라기스 이미지", "image", ["이미지 1장"], budget=10)
            W.log_action(run_dir, "search", {"q": "x"}, True, "3건", data={"per_engine": {"commons": 3, "ddg": 0, "bing": -1}})
            W.log_action(run_dir, "read", {"url": "u"}, True, "ok", data={"domain": "britishmuseum.org", "via": "wayback", "status": 200, "chars": 500})
            with (run_dir / "log.jsonl").open("a", encoding="utf-8") as f: f.write('{"broken":\n')
            pb = {"engines": {}, "domains": {}, "routes": {}, "lessons": []}
            res = L.record_run(run_dir, pb)
            check("record summary", res, {"engines_updated": 2, "domains_updated": 1})   # bing=-1(엔진 오류)은 통계 제외
            check("engine commons", pb["engines"]["commons"]["image"], {"tries": 1, "hits": 1})
            check("engine ddg", pb["engines"]["ddg"]["image"], {"tries": 1, "hits": 0})
            check("engine error excluded", "bing" in pb["engines"], False)   # 검증 지적 4.6: 키 없음·오류는 적중률을 깎지 않는다
            check("domain status", pb["domains"]["britishmuseum.org"]["status"], "ok")
            check("domain via", pb["domains"]["britishmuseum.org"]["via_success"], ["wayback"])
            check("route wayback", pb["routes"]["blocked->wayback"]["success"], 1)
        finally:
            if old is None: del os.environ["QUEST_RUNS_DIR"]
            else: os.environ["QUEST_RUNS_DIR"] = old

        # 실패 read 분류 · grab · escalate
        os.environ["QUEST_RUNS_DIR"] = td
        try:
            r2 = W.new_run("x", "image", ["a"], slug="second")
            W.log_action(r2, "read", {}, False, "403", data={"domain": "a.org", "via": "direct", "status": 403, "chars": 0})
            W.log_action(r2, "read", {}, False, "empty", data={"domain": "b.org", "via": "direct", "status": 200, "chars": 0})
            W.log_action(r2, "read", {}, False, "404", data={"domain": "c.org", "via": "direct", "status": 404, "chars": 0})
            W.log_action(r2, "grab", {}, True, "ok", data={"domain": "a.org"})
            W.log_action(r2, "escalate", {}, True, "x", data={"blockage": "403"})
            pb2 = {"engines": {}, "domains": {}, "routes": {}, "lessons": []}
            L.record_run(r2, pb2)
            check("status blocked", pb2["domains"]["a.org"]["status"], "blocked")
            check("status js", pb2["domains"]["b.org"]["status"], "js-required")
            check("status dead", pb2["domains"]["c.org"]["status"], "dead")
            check("grabs", pb2["domains"]["a.org"]["grabs"], 1)
            check("route 403->*", pb2["routes"]["403->*"]["tries"], 1)
        finally:
            if old is None: del os.environ["QUEST_RUNS_DIR"]
            else: os.environ["QUEST_RUNS_DIR"] = old

    check("rank_engines", L.rank_engines(pb, "image", ["ddg", "commons"]), ["commons", "ddg"])
    check("rank ties stable", L.rank_engines(pb, "paper", ["z", "a", "m"]), ["z", "a", "m"])
    L.add_lesson(pb, "run1", "image", "커먼즈가 박물관 사진에 강하다")
    check("lessons_for len", len(L.lessons_for(pb, "image")), 1)
    L.add_lesson(pb, "run2", "paper", "OA 판본은 openalex 먼저")
    check("lessons_for pads", L.lessons_for(pb, "image"), ["커먼즈가 박물관 사진에 강하다", "OA 판본은 openalex 먼저"])
    check("domain_note", L.domain_note(pb, "britishmuseum.org")["status"], "ok")
    check("domain_note none", L.domain_note(pb, "nope.org"), None)
    check("report", "commons" in L.report(pb) and "britishmuseum.org" in L.report(pb), True)
    check("playbook path", L.PLAYBOOK_PATH.name, "playbook.json")
    real = json.loads(L.PLAYBOOK_PATH.read_text(encoding="utf-8"))   # 실제 플레이북은 퀘스트가 돌수록 채워진다 — 구조(키)만 검사
    check("playbook structure", sorted(real.keys()), ["domains", "engines", "lessons", "routes"])
    check("default playbook", L._empty(), {"engines": {}, "domains": {}, "routes": {}, "lessons": []})

    # ── escalate ─────────────────────────────────────────────────────────
    lad = E.ladder("403", domain="www.britishmuseum.org")
    check("403 wayback step", any("웨이백" in x["title"] for x in lad), True)
    check("ladder item keys", sorted(lad[0]), ["command", "step", "title", "why"])
    check("ladder steps numbered", [x["step"] for x in lad], list(range(1, len(lad) + 1)))
    check("forbidden Sci-Hub", "Sci-Hub" in E.forbidden_text(), True)
    check("forbidden terms", all(t in E.forbidden_text() for t in ("로그인", "CAPTCHA", "DRM", "robots.txt")), True)
    lg = E.ladder("login")
    check("login first q.py", "q.py" in lg[0]["command"], True)
    check("login no cookies", any("cookie" in json.dumps(x, ensure_ascii=False).lower() for x in lg), False)
    check("all blockages", all(E.ladder(b) for b in E.BLOCKAGES), True)
    pbj = {"domains": {"b.org": {"status": "js-required"}}}
    check("js first", "--js" in E.ladder("empty-js", domain="b.org", pb=pbj)[0]["command"], True)
    check("js first for 403 too", "--js" in E.ladder("403", domain="www.b.org", pb=pbj)[0]["command"], True)
    check("no-results query used", "라기스" in E.ladder("no-results", query="라기스")[0]["command"], True)
