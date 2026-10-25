#!/usr/bin/env python3
"""QUEST 저장 — Railway filebrowser 업로드 + assets/catalog.json 등록.
upload는 예외를 던지지 않는다. credentials/login/usage는 설정·인증 실패 시 RuntimeError(upload가 잡는다)."""
import json, re, urllib.parse
from datetime import date
from pathlib import Path

from core.http import fetch
from core.workspace import CONFIG, ROOT

PREFIX = {"image": "img", "iiif": "img", "pdf": "doc", "file": "doc", "video": "vid"}

def credentials():
    st = CONFIG["storage"]
    txt = (ROOT / st["secret_file"]).read_text(encoding="utf-8")
    m = re.search(r"admin\s*/\s*(\S+)", txt)
    if not m: raise RuntimeError("secret 파일에서 'admin / 비밀번호'를 찾지 못함")
    return st["base_url"].rstrip("/"), "admin", m.group(1)

def login() -> str:
    base, user, pw = credentials()
    r = fetch(base + "/api/login", method="POST", json_body={"username": user, "password": pw}, timeout=30)
    tok = (r["text"] or "").strip().strip('"')
    if not r["ok"] or not tok: raise RuntimeError(f"로그인 실패: {r['error'] or r['status']}")
    return tok

def _auth(token): return {"X-Auth": token}

def usage(token: str | None = None) -> dict:
    base = credentials()[0]; token = token or login()
    r = fetch(base + "/api/usage/", headers=_auth(token), timeout=30)
    if not r["ok"]: raise RuntimeError(f"usage 실패: {r['error'] or r['status']}")
    d = json.loads(r["text"]) if r["text"] else {}
    total, used = int(d.get("total", 0) or 0), int(d.get("used", 0) or 0)
    return {"total": total, "used": used, "pct": round(used * 100 / total, 1) if total else 0.0}

def _quote(path): return urllib.parse.quote(path.strip("/"), safe="/")

def ensure_dir(remote_dir: str, token: str) -> None:
    base = credentials()[0]; cur = ""
    for part in [p for p in remote_dir.strip("/").split("/") if p]:
        cur += "/" + part
        fetch(f"{base}/api/resources{_quote(cur)}/", method="POST", headers=_auth(token), data=b"", timeout=30, retries=0)  # 409(이미 있음)은 무시

def normalize_remote(remote_path: str) -> str:
    """Git Bash(MSYS)가 '/srv/...' 인자를 'C:/Program Files/Git/srv/...'로 바꿔 넘기는 사고 방지 — 마지막 '/srv/'부터만 취한다."""
    p = str(remote_path).replace("\\", "/")
    root = CONFIG["storage"].get("root", "/srv")
    if re.match(r"^[A-Za-z]:", p) and (root + "/") in p: p = p[p.rindex(root + "/"):]
    return "/" + p.lstrip("/")

def upload(local: Path, remote_path: str, token: str | None = None) -> dict:
    try:
        remote_path = normalize_remote(remote_path)
        token = token or login()
        u = usage(token)
        if u["pct"] >= CONFIG["storage"]["warn_pct"]:
            return {"ok": False, "status": 0, "remote": remote_path, "error": f"용량 경고 {u['pct']}%"}
        ensure_dir(Path(remote_path.replace("\\", "/")).parent.as_posix(), token)
        base = credentials()[0]
        r = fetch(f"{base}/api/resources/{_quote(remote_path)}?override=true", method="POST", data=Path(local).read_bytes(),
                  headers={**_auth(token), "Content-Type": "application/octet-stream"}, timeout=600, retries=1)
        out = {"ok": bool(r["ok"]), "status": r["status"], "remote": remote_path}
        if not r["ok"]: out["error"] = r["error"]
        return out
    except Exception as e:
        return {"ok": False, "status": 0, "remote": remote_path, "error": f"{e.__class__.__name__}: {str(e)[:160]}"}

def next_asset_id(catalog: dict, prefix: str) -> str:
    n = 0
    for a in catalog.get("assets", []):
        m = re.fullmatch(re.escape(prefix) + r"-(\d+)", str(a.get("id", "")))
        if m: n = max(n, int(m.group(1)))
    return f"{prefix}-{n + 1:04d}"

def register_asset(entry: dict, *, title: str, source: str, source_url: str, railway_path: str, evidence_id: str | None,
                   verses: list, credit: str | None, catalog_path: Path | None = None) -> str:
    cp = Path(catalog_path) if catalog_path else ROOT / CONFIG["catalog"]
    cat = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {"assets": []}
    aid = next_asset_id(cat, PREFIX.get(entry.get("kind", "image"), "img"))
    try: local = Path(entry["path"]).resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception: local = str(entry.get("path", "")).replace("\\", "/")
    cat.setdefault("assets", []).append({
        "id": aid, "title": title, "source": source, "source_url": source_url, "license": entry.get("license"),
        "commercial_ok": entry.get("commercial_ok"), "credit": credit or entry.get("credit"), "railway_path": railway_path,
        "local_cache": local, "evidence_id": evidence_id, "verses": verses, "added": date.today().isoformat()})
    cp.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return aid
