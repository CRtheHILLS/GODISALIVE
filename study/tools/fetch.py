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

자막 선택: 수동 자막(사람이 만든 것) 우선 → 원어 자동자막(<lang>-orig) → 없으면 'Whisper 필요' 보고.
Whisper(음성→문자)는 오디오 다운로드가 크므로 CR 확인 후 별도 진행한다.
"""
import argparse, gzip, json, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import common as C

def ytdlp():
    for p in [Path.home() / ".local/bin/yt-dlp.exe", Path.home() / ".local/bin/yt-dlp"]:
        if p.exists(): return str(p)
    if shutil.which("yt-dlp"): return "yt-dlp"
    sys.exit("yt-dlp를 찾지 못함 — https://github.com/yt-dlp/yt-dlp 설치 필요")

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
    rc, out = run([y, *base, "--write-info-json", url])                    # 1) 정보 파일
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
        rc, out = run([y, *base, "--write-subs", "--write-auto-subs", "--sub-format", "vtt",
                       "--sub-langs", ",".join(want), url])
        for vtt in sorted(d.glob("raw.*.vtt")):
            lang = vtt.name[len("raw."):-len(".vtt")]
            kind = "manual" if lang in manual else "auto"
            segs = C.vtt_to_segments(vtt.read_text(encoding="utf-8"))
            paras = C.segments_to_paragraphs(segs)
            head = (f"# {info.get('title')}\n# {info.get('channel')} · {info.get('upload_date')} · {info.get('duration_string')}"
                    f" · 자막: {lang} ({'수동' if kind == 'manual' else '자동생성'})\n# {info.get('webpage_url')}\n"
                    f"# 각 단락 앞 [시간]은 영상 위치. 링크: https://youtu.be/{vid}?t=<초>\n\n")
            body = "\n\n".join(f"[{C.fmt_ts(s)}] ({int(s)}s) {t}" for s, t in paras)
            (d / f"transcript.{lang}.txt").write_text(head + body + "\n", encoding="utf-8")
            with gzip.open(d / f"transcript.{lang}.vtt.gz", "wb") as g: g.write(vtt.read_bytes())
            vtt.unlink()
            captions[lang] = {"kind": kind, "lines": len(segs), "chars": sum(len(t) for _, t in segs), "paragraphs": len(paras)}

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
        print(f"   자막 {lang} [{'수동' if c['kind']=='manual' else '자동'}] {c['lines']}줄 · {c['chars']:,}자 · "
              f"{c['paragraphs']}단락 → {d / ('transcript.' + lang + '.txt')}")
    if not captions:
        print("   ⚠ 자막 없음 → Whisper 음성 인식 필요 (오디오 크기 확인 후 CR 승인 받고 진행)")
    print(f"   메타 → {meta_p}")
    return meta

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+"); ap.add_argument("--langs", help="쉼표 구분 자막 언어 (예: ko,en)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    langs = [l.strip() for l in a.langs.split(",")] if a.langs else None
    ok = sum(1 for u in a.urls if fetch(u, langs, a.force))
    if ok != len(a.urls): sys.exit(1)

if __name__ == "__main__":
    main()
