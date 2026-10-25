#!/usr/bin/env python3
"""공부 모드 ①-c 음성 인식 — 자막이 없는 영상을 로컬 Whisper(faster-whisper)로 받아쓴다. fetch.py가 자막이 없을 때 자동 호출한다.

사용:
    python study/tools/transcribe.py <video_id 또는 URL> [--model large-v3-turbo|large-v3|medium|small] [--lang ko] [--force]

방식 (2026-10-25 조사 반영 — study/README.md '자막 추출 방식' 참조):
  · 모델 기본값 large-v3-turbo: large-v3에 가까운 다국어 정확도를 몇 배 빠르게. 한국어 정밀이 필요하면 --model large-v3 (CPU에서 수 배 느림).
    (small은 한국어 고유명사·성경 용어 오류가 많아 기본값에서 뺐다)
  · BatchedInferencePipeline(배치 추론, CPU int8, 코어 전부) + VAD(무음 구간 제거)
  · condition_on_previous_text=False — 긴 설교에서 같은 문장이 반복 생성되는 환각 고리를 끊는다
  · hotwords — 제목의 설교 본문(예: 창 3:8-13)을 개역한글에서 뽑아 성경 어휘를 힌트로 준다 → 고유명사·구절 인용 정확도 개선
  · 디코딩은 ffmpeg 직접 호출 — faster-whisper 내장 PyAV 디코더가 PyAV 버전과 충돌하는 경우가 있다(2026-10 확인)
산출: transcript.<lang>.txt (fetch.py와 같은 형식) · transcript.<lang>.whisper.json · meta/catalog의 captions에 kind "whisper-<model>"
설치: pip install -U faster-whisper   (모델은 첫 실행 때 ~/.cache/huggingface 에 받는다: turbo ≈ 1.6GB)
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import common as C

DEFAULT_MODEL = "large-v3-turbo"
CHURCH_WORDS = "하나님 예수님 예수 그리스도 성령 여호와 아멘 할렐루야 십자가 부활 복음 은혜 말씀 성경 구원 회개"

def download_audio(vid: str, d: Path) -> Path | None:
    from fetch import ytdlp
    for ext in ("m4a", "webm", "opus", "mp3"):
        p = d / f"raw-audio.{ext}"
        if p.exists() and p.stat().st_size > 0: return p
    r = subprocess.run([*ytdlp(), "--encoding", "utf-8", "-f", "bestaudio[ext=m4a]/bestaudio", "--no-playlist",
                        "-o", str(d / "raw-audio.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"], capture_output=True)
    for ext in ("m4a", "webm", "opus", "mp3"):
        p = d / f"raw-audio.{ext}"
        if p.exists() and p.stat().st_size > 0: return p
    print(r.stderr.decode("utf-8", "replace")[-400:]); return None

def decode_ffmpeg(audio: Path):
    """16kHz 모노 float32 배열 (ffmpeg 직접)."""
    import numpy as np
    ff = shutil.which("ffmpeg")
    if not ff: raise RuntimeError("ffmpeg 없음")
    r = subprocess.run([ff, "-nostdin", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-loglevel", "error", "-"], capture_output=True)
    if r.returncode != 0: raise RuntimeError(r.stderr.decode("utf-8", "replace")[-300:])
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0

_REF_IN_TITLE = re.compile(r"\(([1-3]?[가-힣A-Za-z]+\.?\s*\d+(?::\d+(?:\s*[-~]\s*\d+)?)?)\)")
def hotwords_for(title: str, limit: int = 160) -> str:
    """제목 속 설교 본문 구절을 개역한글에서 찾아 어휘 힌트로. 실패하면 교회 공통 어휘만."""
    words = CHURCH_WORDS
    m = _REF_IN_TITLE.search(title or "")
    if m:
        try:
            sys.path.insert(0, str(C.ROOT / "bible"))
            from lookup import parse_ref, load_bolls
            bid, ch, v1, v2 = parse_ref(m.group(1)); idx = load_bolls("KRV") or {}
            text = " ".join(idx.get((bid, ch, v), "") for v in range(v1 or 1, (v2 or v1 or 1) + 1))
            words = (re.sub(r"\s+", " ", text)[:limit] + " " + words).strip()
        except Exception: pass
    return words

def run_transcribe(vid: str, model_name: str = DEFAULT_MODEL, lang: str | None = "ko", force: bool = False) -> dict | None:
    from fetch import load_catalog, save_catalog, write_transcript
    d = C.SOURCES / vid; meta_p = d / "meta.json"
    if not meta_p.exists(): print(f"meta.json 없음 — 먼저 fetch.py"); return None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    lang = lang or meta.get("orig_language") or None
    out_txt = d / f"transcript.{lang or 'auto'}.txt"
    if out_txt.exists() and not force: print(f"• 이미 있음: {out_txt} (--force로 다시)"); return meta
    audio = download_audio(vid, d)
    if not audio: print("오디오 다운로드 실패"); return None
    hot = hotwords_for(meta.get("title", ""))
    print(f"🎧 {audio.name} {audio.stat().st_size/1048576:.1f}MB → Whisper {model_name} ({lang or '자동 감지'}) · 힌트 {hot[:40]}…", flush=True)
    from faster_whisper import WhisperModel, BatchedInferencePipeline
    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    pipe = BatchedInferencePipeline(model=model)
    segments, info = pipe.transcribe(decode_ffmpeg(audio), language=lang, batch_size=8, beam_size=5, vad_filter=True,
                                     condition_on_previous_text=False, hotwords=hot)
    segs, raw = [], []
    for s in segments:
        t = " ".join(s.text.split())
        if not t: continue
        if raw and t == raw[-1]["text"]: continue            # 같은 문장 연속 반복(환각) 제거
        raw.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": t}); segs.append((s.start, t))
        if len(raw) % 100 == 0: print(f"   … {C.fmt_ts(s.start)} 까지 {len(raw)}문장 ({int(time.time()-t0)}초)", flush=True)
    secs = round(time.time() - t0); lang = lang or info.language
    (d / f"transcript.{lang}.whisper.json").write_text(json.dumps({"model": model_name, "language": info.language, "duration": info.duration,
        "hotwords": hot, "seconds": secs, "segments": raw}, ensure_ascii=False, indent=1), encoding="utf-8")
    cap = dict(write_transcript(d, meta, vid, lang, f"whisper-{model_name}", segs), via="faster-whisper", seconds=secs)
    meta.setdefault("captions", {})[lang] = cap
    meta["orig_language"] = meta.get("orig_language") or info.language
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cat = load_catalog()
    for r in cat["videos"]:
        if r["id"] == vid: r.setdefault("captions", {})[lang] = cap["kind"]; r["language"] = r.get("language") or info.language
    save_catalog(cat)
    rt = info.duration / secs if secs else 0
    print(f"✔ {cap['lines']}문장 · {cap['chars']:,}자 · {cap['paragraphs']}단락 · {secs}초 (실시간의 {rt:.1f}배) → {d / ('transcript.' + lang + '.txt')}")
    return meta

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("--model", default=DEFAULT_MODEL); ap.add_argument("--lang", default="ko")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    vid = C.extract_video_id(a.video) or a.video
    if not run_transcribe(vid, a.model, None if a.lang == "auto" else a.lang, a.force): sys.exit(1)

if __name__ == "__main__":
    main()
