#!/usr/bin/env python3
"""공부 모드 ① 수집기 — 유튜브 URL → 메타데이터 + 자막(원어) → study/sources/<id>/

사용:
    python study/tools/fetch.py "https://www.youtube.com/watch?v=XXXX" [URL ...]
    python study/tools/fetch.py URL --langs ko,en      # 자막 언어 지정 (기본: 원어 + 수동자막 전부)
    python study/tools/fetch.py URL --force            # 이미 받은 영상도 다시 받기

산출:
    study/sources/<id>/meta.json                 영상 정보 (git 추적)
    study/sources/<id>/transcript.<lang>.txt     타임스탬프 단락 텍스트 (git 제외 — 저작권)
    study/sources/<id>/transcript.<lang>.vtt.gz  원 자막 압축 (git 제외)
    study/catalog.json                           전체 영상 색인 (git 추적)

자막 확보 3단 사슬 (2026-10-25 최신 방식 조사 반영):
  ① yt-dlp (PyPI 최신판 우선, --ignore-config, 유튜브 JS 챌린지용 node 런타임) — 수동 자막 우선 → 원어 자동자막(<lang>-orig)
  ② youtube-transcript-api — 유튜브 개편으로 ①이 깨졌을 때 같은 자막을 다른 경로로
  ③ 로컬 Whisper(transcribe.py, large-v3-turbo · 배치 추론 · 성경 어휘 힌트) — 자막이 아예 없을 때 자동 실행 (--no-transcribe로 끔)
"""
import argparse, gzip, json, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import common as C

def ytdlp():
    """yt-dlp 명령 접두사(list). 최신을 쓰기 위해 pip 패키지(python -m yt_dlp, PyPI는 이 PC에서 갱신 가능)를 우선하고,
    없으면 ~/.local/bin 실행 파일. 공통 안전 옵션: 사용자 설정 무시(쿠키·계정 옵션 차단), 유튜브 JS 챌린지용 런타임(node)."""
    try:
        import importlib.util
        base = [sys.executable, "-m", "yt_dlp"] if importlib.util.find_spec("yt_dlp") else None
    except Exception: base = None
    if base is None:
        for p in [Path.home() / ".local/bin/yt-dlp.exe", Path.home() / ".local/bin/yt-dlp"]:
            if p.exists(): base = [str(p)]; break
    if base is None and shutil.which("yt-dlp"): base = ["yt-dlp"]
    if base is None: sys.exit("yt-dlp를 찾지 못함 — pip install -U \"yt-dlp[default]\"")
    base += ["--ignore-config", "--no-cookies-from-browser"]
    if shutil.which("deno") is None and shutil.which("node"): base += ["--js-runtimes", "node"]
    return base

def transcript_api(vid: str, prefer: list):
    """예비 경로 ② youtube-transcript-api — yt-dlp가 유튜브 개편으로 깨졌을 때. 같은 자막을 다른 경로로 받는다.
    → (lang, kind, [(start, text)]) 또는 None"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi(); tl = api.list(vid)
        items = list(tl)
        order = sorted(items, key=lambda t: (t.is_generated, (prefer.index(t.language_code) if t.language_code in prefer else 99)))
        if not order: return None
        t = order[0]; fetched = t.fetch()
        segs = [(float(x.start), " ".join(x.text.split())) for x in fetched if x.text.strip()]
        return t.language_code, ("auto" if t.is_generated else "manual"), segs
    except Exception as e:
        print(f"   (예비 경로 youtube-transcript-api: {e.__class__.__name__})"); return None

def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")

META_KEYS = ["id", "title", "channel", "channel_id", "channel_url", "uploader", "upload_date", "duration",
             "duration_string", "language", "view_count", "like_count", "webpage_url", "thumbnail",
             "description", "tags", "categories", "chapters"]

def load_catalog():
    if C.CATALOG.exists():
        return json.loads(C.CATALOG.read_text(encoding="utf-8"))
    return {"_about": "공부 모드 영상 색인 — fetch.py가 갱신. note/report는 Peter가 소화 후 기입.", "videos": []}

def save_catalog(cat):
    C.CATALOG.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

KIND_LABEL = {"manual": "수동", "auto": "자동생성"}

def write_transcript(d: Path, info: dict, vid: str, lang: str, kind: str, segs: list) -> dict:
    """세 경로(yt-dlp VTT · youtube-transcript-api · Whisper)가 모두 같은 형식으로 쓴다 → captions 항목 반환"""
    paras = C.segments_to_paragraphs(segs)
    label = KIND_LABEL.get(kind, kind)
    note = " — 오탈자·고유명사 오류 가능, 성경 구절은 본문으로 교차 확인" if kind != "manual" else ""
    NL = chr(10)
    head = NL.join([f"# {info.get('title')}",
                    f"# {info.get('channel')} · {info.get('upload_date')} · {info.get('duration_string')} · 자막: {lang} ({label}{note})",
                    f"# {info.get('webpage_url')}",
                    f"# 각 단락 앞 [시간]은 영상 위치. 링크: https://youtu.be/{vid}?t=<초>", "", ""])
    body = (NL + NL).join(f"[{C.fmt_ts(s)}] ({int(s)}s) {t}" for s, t in paras)
    (d / f"transcript.{lang}.txt").write_text(head + body + NL, encoding="utf-8")
    return {"kind": kind, "lines": len(segs), "chars": sum(len(t) for _, t in segs), "paragraphs": len(paras)}

def fetch(url, langs=None, force=False):
    vid = C.extract_video_id(url)
    if not vid:
        print(f"✖ 유튜브 영상 ID를 찾을 수 없음: {url}"); return None
    d = C.SOURCES / vid; d.mkdir(parents=True, exist_ok=True)
    meta_p = d / "meta.json"
    if meta_p.exists() and not force and any(d.glob("transcript.*.txt")):
        print(f"• {vid}: 이미 수집됨 (다시 받으려면 --force) → {d}")
        return json.loads(meta_p.read_text(encoding="utf-8"))

    y = ytdlp(); base = ["--encoding", "utf-8", "--skip-download", "--no-warnings", "-o", str(d / "raw")]
    rc, out = run([*y, *base, "--write-info-json", url])                    # 1) 정보 파일
    info_p = d / "raw.info.json"
    if rc != 0 or not info_p.exists():
        print(f"✖ {vid}: 정보 수집 실패\n{out[-800:]}"); return None
    info = json.loads(info_p.read_text(encoding="utf-8"))
    manual = [k for k in (info.get("subtitles") or {}) if k != "live_chat"]
    auto = info.get("automatic_captions") or {}
    orig = info.get("language") or next((k[:-5] for k in auto if k.endswith("-orig")), None)

    if langs: want = list(langs)                                            # 2) 받을 언어
    else:
        want = list(manual)
        if orig:
            if f"{orig}-orig" in auto: want.append(f"{orig}-orig")
            elif orig in auto: want.append(orig)
    want = [w for i, w in enumerate(want) if w not in want[:i]]
    captions = {}
    if want:
        rc, out = run([*y, *base, "--write-subs", "--write-auto-subs", "--sub-format", "vtt",
                       "--sub-langs", ",".join(want), url])
        for vtt in sorted(d.glob("raw.*.vtt")):
            lang = vtt.name[len("raw."):-len(".vtt")]
            kind = "manual" if lang in manual else "auto"
            segs = C.vtt_to_segments(vtt.read_text(encoding="utf-8"))
            captions[lang] = dict(write_transcript(d, info, vid, lang, kind, segs), via="yt-dlp")
            with gzip.open(d / f"transcript.{lang}.vtt.gz", "wb") as g: g.write(vtt.read_bytes())
            vtt.unlink()
    if not captions:                                                        # 2-b) 예비 경로: youtube-transcript-api
        got = transcript_api(vid, ([orig] if orig else []) + ["ko", "en"])
        if got and got[2]:
            lang, kind, segs = got
            captions[lang] = dict(write_transcript(d, info, vid, lang, kind, segs), via="youtube-transcript-api")

    meta = {k: info.get(k) for k in META_KEYS}                              # 3) meta.json
    meta.update({"fetched_at": datetime.now().isoformat(timespec="seconds"), "orig_language": orig,
                 "manual_subtitle_langs": manual, "auto_caption_langs_count": len(auto), "captions": captions,
                 "source_url": url})
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    info_p.unlink()

    cat = load_catalog(); rows = cat["videos"]                               # 4) 카탈로그
    row = next((r for r in rows if r["id"] == vid), None)
    if row is None: row = {"id": vid}; rows.append(row)
    row.update({"url": f"https://www.youtube.com/watch?v={vid}", "title": meta["title"], "channel": meta["channel"],
                "upload_date": meta["upload_date"], "duration": meta["duration_string"], "language": orig,
                "captions": {k: v["kind"] for k, v in captions.items()}, "fetched_at": meta["fetched_at"]})
    for k, v in (("note", None), ("report", None), ("status", "수집됨")): row.setdefault(k, v)
    save_catalog(cat)

    print(f"✔ {vid} · {meta['title']}")                                      # 5) 보고
    print(f"   채널 {meta['channel']} · 게시 {meta['upload_date']} · 길이 {meta['duration_string']} · 원어 {orig}")
    for lang, c in captions.items():
        print(f"   자막 {lang} [{KIND_LABEL.get(c['kind'], c['kind'])} · {c.get('via')}] {c['lines']}줄 · {c['chars']:,}자 · "
              f"{c['paragraphs']}단락 → {d / ('transcript.' + lang + '.txt')}")
    if not captions:
        print("   ⚠ 자막 없음 (yt-dlp·youtube-transcript-api 둘 다) → 음성 인식 경로")
    print(f"   메타 → {meta_p}")
    return meta

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+"); ap.add_argument("--langs", help="쉼표 구분 자막 언어 (예: ko,en)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-transcribe", action="store_true", help="자막이 없어도 Whisper 받아쓰기를 하지 않는다")
    ap.add_argument("--model", default=None, help="Whisper 모델 (기본 large-v3-turbo, 정밀: large-v3)")
    a = ap.parse_args()
    langs = [l.strip() for l in a.langs.split(",")] if a.langs else None
    ok = 0
    for u in a.urls:
        meta = fetch(u, langs, a.force)
        if not meta: continue
        if not meta.get("captions") and not a.no_transcribe:      # 3) 최종 경로: 로컬 음성 인식 (멈추지 않는다)
            import transcribe as T
            meta = T.run_transcribe(meta["id"], a.model or T.DEFAULT_MODEL, (langs or [meta.get("orig_language") or "ko"])[0], a.force)
        if meta: ok += 1
    if ok != len(a.urls): sys.exit(1)

if __name__ == "__main__":
    main()
