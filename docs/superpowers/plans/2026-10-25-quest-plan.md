# QUEST 목표지향 검색·확보 에이전트 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목표 문장 하나로 시작해 완료 조건이 전부 체크될 때까지 검색·읽기·확보·분류·기록을 반복하고, 결과를 플레이북에 학습시키는 연구 에이전트 도구 모음(`quest/`)과 그 루프 규율(스킬)을 만든다.

**Architecture:** 퀘스트마다 폴더(컴퓨터)를 만들고 Peter(Claude)가 `q.py` 하위 명령을 한 번에 하나씩 호출하는 에이전트 루프. 모듈은 `core/`에 책임별로 하나씩(workspace·http·search·read·grab·classify·learn·escalate·storage), 프로젝트 특화 로직은 `plugins/godisalive.py`에만. 모든 도구는 `log.jsonl`에 기계가 읽을 수 있는 `data`를 남기고, `learn.py`가 그것으로 `playbook.json`을 갱신해 다음 검색 순서를 바꾼다.

**Tech Stack:** Python 3.14 표준 라이브러리 + requests 2.32 · beautifulsoup4 4.14 · lxml · pypdf 6 · Pillow 12 (전부 설치 확인됨). yt-dlp 2026.08.19 실행 파일(`~/.local/bin/yt-dlp.exe`). Playwright는 **선택**(미설치 — `read --js`는 안내 메시지).

**Spec:** `docs/superpowers/specs/2026-10-25-quest-design.md`

**실행 방식(CR 지시 "바로 구현 수행"):** Task 1·5·6·7은 Peter가 직접, Task 2·3·4는 executor 서브에이전트(sonnet) 3명이 병렬로. 과제별 리뷰어는 두지 않고(CR의 에이전트 절약 규칙) 마지막에 architect-medium 1회 검증 + selftest + 실전 퀘스트 1건으로 증명한다.

## Global Constraints

- 외부 의존성은 위 Tech Stack만. 새 pip 설치 금지 (Playwright 제외 — 선택).
- 모든 모듈은 `sys.stdout.reconfigure(encoding="utf-8")` 또는 `print`를 UTF-8로 — Windows 콘솔 cp949 깨짐 방지.
- 네트워크를 쓰는 함수는 예외를 밖으로 던지지 않고 `{"error": "..."}` 또는 `ok=False`로 돌려준다. 엔진 하나가 죽어도 검색은 계속된다.
- 사용자 이메일 등 개인정보를 외부 서비스에 보내지 않는다 (OpenAlex `mailto` 미사용).
- 반목표(설계서 §3): 유료 장벽 우회·크리덴셜·CAPTCHA·DRM·robots/약관 위반 대량 수집 코드를 쓰지 않는다. `read`는 robots.txt를 확인하고 금지면 멈춘다(`--force`는 기록을 남기고 1건만).
- 용량 한도(config.json `limits`): quest_mb 500 · image_mb 25 · pdf_mb 100 · video_mb 2048 · video_max_height 1080.
- 파일 인코딩 UTF-8, 경로는 `pathlib.Path`, 저장소 루트는 `Path(__file__).resolve().parents[2]` (core/ 기준) 로 계산.
- 한국어 사용자 메시지, 영어 코드·주석 허용.

## Review Focus

1. **DDG/Bing HTML 구조 변경** — 파서가 0건을 돌려주면 "엔진 실패"로 표시하고 다른 엔진 결과는 그대로 나와야 한다 (Task 2 테스트: 빈 HTML → `[]`, 오류 아님).
2. **PDF가 아닌데 .pdf로 끝나는 URL / content-type이 거짓인 응답** — `read`는 content-type과 매직 바이트(`%PDF`) 둘 다 보고, 아니면 HTML로 처리 (Task 3 테스트).
3. **다운로드 중 한도 초과** — Content-Length 없을 때 스트리밍 중 누적 바이트가 한도를 넘으면 중단·부분 파일 삭제 (Task 3 테스트: 가짜 스트림).
4. **라이선스 문자열 변형** — "CC BY-SA 4.0", "cc-by-sa-4.0", "Public domain", "PD-US", "CC0 1.0", "CC BY-NC-ND", "© Trustees of the British Museum", 빈 문자열 → 분류와 `commercial_ok`가 표대로 (Task 4 테스트).
5. **log.jsonl 손상(마지막 줄 깨짐)** — `learn.record_run`은 깨진 줄을 건너뛰고 나머지를 집계 (Task 4 테스트).

---

## 파일 구조

```
quest/
  README.md                 운영·이식 문서 (Task 5)
  config.json               프로젝트 설정 (Task 1)
  playbook.json             학습 지식 — 초기값 {"engines":{},"domains":{},"routes":{},"lessons":[]} (Task 4)
  q.py                      CLI 진입점 (Task 1 뼈대, Task 5 완성)
  selftest.py               전 모듈 자가 테스트 — 네트워크 없이 픽스처로 (각 Task가 자기 섹션 추가)
  tests/fixtures/           ddg.html bing.html commons.json met_search.json met_object.json openalex.json wikidata.json loc.json ia.json article.html
  core/__init__.py
  core/workspace.py         컴퓨터(런 폴더) 생성·상태·로그·브리프·todo·check (Task 1)
  core/http.py              fetch · robots · wayback · UA · 지연 (Task 1)
  core/search.py            엔진 레지스트리 + 파서 (Task 2)
  core/read.py              URL → Page (Task 3)
  core/grab.py              파일 확보 + manifest (Task 3)
  core/storage.py           Railway 업로드·용량·catalog 등록 (Task 3)
  core/classify.py          분류 추론 (Task 4)
  core/learn.py             플레이북 (Task 4)
  core/escalate.py          우회 사다리 (Task 4)
  plugins/__init__.py
  plugins/godisalive.py     성경 구절·증거 축·도메인 신뢰표 (Task 4)
  runs/                     컴퓨터들 — downloads/ pages/ search/ 는 .gitignore
.claude/skills/godisalive-quest/SKILL.md   루프 규율 (Task 5)
```

### 공용 데이터 형식 (모든 Task가 지킨다)

```python
Result = {"engine": str, "type": str,  # web|text|image|object|paper|video|place
          "title": str, "url": str, "snippet": str, "license": str | None, "extra": dict}
Page   = {"url": str, "final_url": str, "status": int, "title": str, "text": str,
          "links": list[{"text": str, "url": str}], "images": list[{"url": str, "alt": str}],
          "via": str,  # direct|wayback|js|pdf
          "path": str | None, "error": str | None}
Entry  = {"id": str, "url": str, "source_page": str | None, "kind": str,  # image|pdf|video|iiif|file
          "path": str, "sha256": str, "bytes": int, "license": str | None, "commercial_ok": bool | None,
          "credit": str | None, "retrieved_at": str, "meta": dict}
Triage = {"ref": str, "media": str, "license_class": str, "commercial_ok": bool | None,
          "authority_tier": int, "grade_ceiling": str, "axis": str | None, "verses": list[str],
          "lang": str, "dup_of": str | None, "title": str}
LogRow = {"ts": str, "step": int, "tool": str, "args": dict, "ok": bool, "summary": str,
          "path": str | None, "data": dict}
```

---

### Task 1: 뼈대 — config · workspace · http · q.py 골격 · selftest 하네스

**Files:**
- Create: `quest/config.json`, `quest/core/__init__.py`, `quest/core/workspace.py`, `quest/core/http.py`, `quest/q.py`, `quest/selftest.py`, `quest/tests/fixtures/.gitkeep`, `quest/runs/.gitkeep`
- Modify: `.gitignore` (append `quest/runs/*/downloads/`, `quest/runs/*/pages/`, `quest/runs/*/search/`, `quest/runs/CURRENT`)

**Interfaces (Produces):**
```python
# core/workspace.py
ROOT: Path; CONFIG: dict; RUNS_DIR: Path
def new_run(goal: str, goal_type: str, criteria: list[str], budget: int | None = None, slug: str | None = None) -> Path
def current_run() -> Path | None            # runs/CURRENT 파일이 가리키는 폴더
def set_current(run: Path) -> None
def load_state(run: Path) -> dict           # {"id","goal","goal_type","criteria":[{"text","done"}],"budget","steps","status","blocked":{"type","domain"}|None,"created","finished","lesson"}
def save_state(run: Path, state: dict) -> None
def log_action(run: Path, tool: str, args: dict, ok: bool, summary: str, path: str | None = None, data: dict | None = None) -> int   # step 번호 반환, state.steps += 1
def read_log(run: Path) -> list[dict]       # 깨진 줄은 건너뜀
def todo_text(run: Path) -> str
def todo_add(run: Path, text: str) -> None  # "- [ ] text" 줄 추가
def todo_done(run: Path, index: int) -> bool  # 1-based, "- [ ]" → "- [x]"
def check(run: Path, mark: int | None = None) -> list[tuple[int, bool, str]]
def set_blocked(run: Path, blockage: str | None, domain: str | None) -> None
def brief(run: Path, lessons: list[str] | None = None) -> str   # 목표·유형·완료조건(✓/☐)·예산 "steps/budget"·todo·최근 로그 8줄(step tool ok summary)·blocked·교훈
def slugify(text: str) -> str               # 한글 유지, 공백→-, 40자 제한
# core/http.py
UAS: list[str]
def fetch(url: str, *, method="GET", params=None, data=None, headers=None, timeout=30, retries=2, json_body=None) -> dict
#   → {"ok": bool, "status": int, "url": str(final), "text": str, "content": bytes, "headers": dict, "error": str|None, "elapsed": float}
def fetch_json(url: str, **kw) -> dict | list | None
def robots_allowed(url: str, ua: str = "*") -> bool      # robotparser, 도메인별 캐시, 실패 시 True
def wayback_latest(url: str) -> str | None               # archive.org/wayback/available → closest.url
def domain_of(url: str) -> str
def polite_delay(domain: str, seconds: float = 0.7) -> None   # 같은 도메인 연속 호출 간격
```

- [ ] **Step 1: config.json 작성** — 설계서 §10 값 그대로:
```json
{"project":"GODISALIVE","runs_dir":"quest/runs","plugin":"godisalive","default_budget":40,
 "limits":{"quest_mb":500,"image_mb":25,"pdf_mb":100,"video_mb":2048,"video_max_height":1080},
 "storage":{"kind":"filebrowser","base_url":"https://assets-production-f04b.up.railway.app","secret_file":".omc/secrets/railway.md","root":"/srv","warn_pct":80},
 "catalog":"assets/catalog.json",
 "engines_default":{"web":["ddg","bing","wikipedia"],"text":["wikipedia","ia","sefaria","ddg"],"image":["commons","met","loc","wikidata","ddg"],
   "object":["wikidata","met","louvre","commons","ddg"],"paper":["openalex","crossref","semanticscholar","ia"],"video":["youtube","ia"],
   "place":["pleiades","wikipedia","wikidata"],"mixed":["ddg","wikipedia","commons","wikidata","openalex"]},
 "secrets":{"europeana":".omc/secrets/europeana-key.txt","smithsonian":".omc/secrets/smithsonian-key.txt"}}
```
- [ ] **Step 2: selftest 하네스 작성** — `quest/selftest.py`: `check(name, got, want)` 누적, 섹션 함수 `test_workspace()`, `test_http()`를 두고 모듈 import 실패는 FAIL로 기록(다른 섹션은 계속). 끝에 통과/실패 수 출력, 실패면 exit 1. 각 Task는 `test_<module>()` 함수를 추가하고 `SECTIONS` 리스트에 등록한다.
- [ ] **Step 3: workspace 테스트 작성** (tempdir에 RUNS_DIR을 바꿔서):
  - `new_run("라기스 부조 이미지", "image", ["이미지 1장", "등록번호"], budget=5)` → 폴더에 goal.md·todo.md·log.jsonl·findings.md·state.json 존재, state.criteria 길이 2, state.budget 5
  - `log_action(run, "search", {"q": "x"}, True, "3건", data={"per_engine": {"ddg": 3}})` → 1 반환, 두 번째 호출 → 2, `read_log` 길이 2, state.steps 2
  - log.jsonl에 깨진 줄 `{"broken":` 추가 후 `read_log` 길이 여전히 2
  - `todo_add(run, "커먼즈 검색")`, `todo_done(run, 1)` → todo_text에 "- [x] 커먼즈 검색"
  - `check(run, mark=1)` → `[(1, True, "이미지 1장"), (2, False, "등록번호")]`
  - `brief(run)` 문자열에 "라기스 부조 이미지", "2/5", "✓ 이미지 1장" 포함
  - `slugify("Lachish Reliefs 라기스 부조!")` == "lachish-reliefs-라기스-부조"
- [ ] **Step 4: 실행해 실패 확인** — `python quest/selftest.py` → ImportError/FAIL
- [ ] **Step 5: workspace.py 구현** — goal.md 형식:
```
# 목표
<goal>
- 유형: <goal_type>  · 예산: <budget> 행동 · 생성: <ts>
## 완료 조건
- [ ] <criteria 1> ...
## 제약
- 합법 경로만 (설계서 §3). 라이선스 미확인 이미지는 책에 쓰지 않음.
```
  brief()의 최근 로그 형식 `#{step} {tool:8} {✔|✖} {summary[:90]}`.
- [ ] **Step 6: http 테스트 작성** — `domain_of("https://www.britishmuseum.org/collection/x")=="www.britishmuseum.org"`; `fetch("http://127.0.0.1:9/")` → ok False, error 문자열; `wayback_latest` 는 함수 존재와 반환 타입만(네트워크 없음); `robots_allowed`는 로컬 임시 robots 텍스트를 `urllib.robotparser.RobotFileParser.parse`로 넣는 내부 함수 `_allowed(robots_txt, url, ua)` 로 테스트: `"User-agent: *\nDisallow: /private"` → `/private/x` False, `/public` True.
- [ ] **Step 7: http.py 구현** — UAS 3개(Chrome Win/Edge Win/Firefox Win 최신), `fetch`는 requests.Session, 429/5xx·ConnectionError·Timeout에 `retries`회 지수 백오프(1s,2s), 403은 UA 바꿔 1회 재시도, `polite_delay` 도메인별 마지막 호출 시각 dict. `wayback_latest`: `https://archive.org/wayback/available?url=<quote>` → `archived_snapshots.closest.url` (없으면 None).
- [ ] **Step 8: q.py 골격** — argparse 하위명령 `new/brief/todo/check/status/log`만 동작(나머지는 Task 5). `new`는 `--type` 기본 mixed, `--criteria "a;b"` 세미콜론 분리, `--budget`. `status`는 runs/ 아래 state.json을 읽어 `id · status · steps/budget · goal[:60]` 표. 모든 명령 끝에 `set_current`.
- [ ] **Step 9: 테스트 통과 확인** — `python quest/selftest.py` → "전부 통과"
- [ ] **Step 10: 커밋** — `git add quest .gitignore && git commit -m "quest: 뼈대 — config·workspace·http·q.py 골격·selftest"`

---

### Task 2: 검색 엔진 레지스트리 (`core/search.py`) — executor A

**Files:**
- Create: `quest/core/search.py`, `quest/tests/fixtures/{ddg.html,bing.html,commons.json,met_search.json,met_object.json,openalex.json,wikidata_search.json,wikidata_entity.json,loc.json,ia.json,crossref.json,s2.json,pleiades.rss,wikipedia.json}`
- Modify: `quest/selftest.py` (test_search 섹션 + SECTIONS 등록)

**Interfaces:**
- Consumes: `core.http.fetch`, `fetch_json`, `polite_delay`, `domain_of`; `core.workspace.CONFIG["engines_default"]`, `CONFIG["secrets"]`, `ROOT`.
- Produces:
```python
ENGINES: dict[str, dict]   # name → {"fn": callable(query, lang, n) -> list[Result], "types": list[str], "needs_key": str|None, "label": str}
def parse_ddg(html: str) -> list[Result]
def parse_bing(html: str) -> list[Result]
def parse_commons(data: dict) -> list[Result]       # extmetadata → license(LicenseShortName), extra{artist,credit,description,thumb,original,width,height,mime}
def parse_met_object(obj: dict) -> Result           # license "CC0" if isPublicDomain else "ⓒ Met"; extra{accession, culture, period, primaryImage, objectURL}
def parse_openalex(data: dict) -> list[Result]      # type paper, url=oa_url or doi or landing, license=oa_status, extra{year, authors, doi}
def parse_wikidata_entity(entity: dict) -> Result   # extra{P18 image filename, P195 collection QIDs, P217 inventory, P373 commons category}
def parse_loc(data: dict) -> list[Result]           # extra{image_url list, original_format, date}
def parse_ia(data: dict) -> list[Result]            # url https://archive.org/details/<identifier>, license=licenseurl
def parse_crossref(data: dict) -> list[Result]
def parse_s2(data: dict) -> list[Result]
def parse_pleiades_rss(xml: str) -> list[Result]
def parse_wikipedia(data: dict, lang: str) -> list[Result]
def default_engines(goal_type: str) -> list[str]
def search(query: str, engines: list[str] | None = None, langs: tuple[str, ...] = ("en", "ko"), n: int = 10,
           goal_type: str = "mixed", rank: callable | None = None) -> dict[str, list[Result] | dict]
#   rank(candidates: list[str], goal_type) -> list[str]  (learn.rank_engines를 q.py가 넘긴다; None이면 기본 순서)
#   반환: {"ddg": [Result...], "commons": {"error": "..."}, ...}  — 엔진별. 예외는 전부 {"error"}로.
def format_table(results: dict, limit: int = 12) -> str   # 엔진별 건수 요약 + 상위 결과 "[engine] title — url (license)"
```
- 엔진 URL/파라미터는 설계서 §6 표 + 아래:
  - ddg: `POST https://html.duckduckgo.com/html/` data `{"q": query, "kl": "wt-wt"}`; 결과 `a.result__a`(href, 제목) · `a.result__snippet`; href가 `//duckduckgo.com/l/?uddg=` 리다이렉트면 `uddg` 파라미터 unquote.
  - bing: `GET https://www.bing.com/search?q=&setlang=en`; `li.b_algo h2 a`, `li.b_algo .b_caption p`.
  - wikipedia: 각 lang에 대해 `/w/api.php?action=query&list=search&srsearch=&srlimit=n&format=json`; snippet의 HTML 태그 제거.
  - wikidata: `wbsearchentities(language=en, limit=min(n,5))` → `wbgetentities(ids=..., props=claims|labels|descriptions|sitelinks, languages=en|ko)`; claims에서 P18(mainsnak.datavalue.value 파일명), P195, P217, P373 추출. title = 라벨(ko 우선 en), url = `https://www.wikidata.org/wiki/<QID>`.
  - commons: `generator=search&gsrsearch=<q>&gsrnamespace=6&gsrlimit=n&prop=imageinfo&iiprop=url|extmetadata|size|mime&iiurlwidth=1600`.
  - met: search `hasImages=true&q=` → objectIDs[:n] → 객체마다 `/objects/{id}` (polite_delay).
  - loc: `https://www.loc.gov/search/?q=<q>&fo=json&c=<n>`; 결과 `results[]` 의 `title`, `id`(URL), `image_url`, `original_format`, `date`.
  - ia: `advancedsearch.php?q=<q>&fl[]=identifier&fl[]=title&fl[]=mediatype&fl[]=licenseurl&fl[]=description&rows=n&output=json`.
  - openalex: `https://api.openalex.org/works?search=<q>&per-page=n` (mailto 없음).
  - crossref: `https://api.crossref.org/works?query=<q>&rows=n`.
  - semanticscholar: `https://api.semanticscholar.org/graph/v1/paper/search?query=<q>&limit=n&fields=title,url,year,openAccessPdf,externalIds,authors`.
  - louvre: `GET https://collections.louvre.fr/recherche?q=<q>` HTML — 실제 응답을 한 번 받아 셀렉터를 정하고 그 HTML을 픽스처로 저장(`louvre.html`, 20KB 이하로 잘라서). 실패 시 `{"error": "louvre: 셀렉터 미확인"}`.
  - pleiades: `https://pleiades.stoa.org/search_rss?SearchableText=<q>` RSS → xml.etree (item title/link/description).
  - sefaria: `POST https://www.sefaria.org/api/search-wrapper` json `{"query": q, "type": "text", "size": n}` → `hits.hits[]._source.ref`, `_id`; 실패 시 error.
  - youtube: `subprocess.run([yt-dlp, f"ytsearch{n}:{q}", "--flat-playlist", "--print", "%(id)s|%(title)s|%(channel)s|%(duration)s"])` → url `https://www.youtube.com/watch?v=<id>`; yt-dlp 경로는 `Path.home()/.local/bin/yt-dlp.exe` 우선, 없으면 `shutil.which`.
  - europeana(`https://api.europeana.eu/record/v2/search.json?wskey=&query=&rows=`)·smithsonian(`https://api.si.edu/openaccess/api/v1.0/search?api_key=&q=&rows=`)은 `CONFIG["secrets"]` 파일이 있을 때만 ENGINES에 활성(`needs_key`), 없으면 `{"error": "키 없음: <경로>"}`.

- [ ] **Step 1: 픽스처 수집** — 각 엔진의 실제 응답을 1회 받아 `quest/tests/fixtures/`에 저장(개인정보 없음, 20KB 이하로 잘라도 구조 유지). DDG/Bing이 봇 차단 페이지를 주면 그 사실을 selftest 주석에 적고 최소 구조의 수제 HTML 픽스처로 대체.
- [ ] **Step 2: 실패하는 테스트 작성** (`test_search`):
  - `parse_ddg(ddg.html)` → 길이 ≥ 3, 첫 결과 url이 `http`로 시작하고 `duckduckgo.com/l/` 포함 안 함, title 비어 있지 않음
  - `parse_ddg("")` == `[]`, `parse_bing("<html></html>")` == `[]`
  - `parse_commons(commons.json)` → 각 Result.type == "image", license 값이 extmetadata.LicenseShortName과 같음, extra.original이 `upload.wikimedia.org` 포함
  - `parse_met_object(met_object.json)` → isPublicDomain이면 license "CC0", extra.accession == objectNumber
  - `parse_openalex(openalex.json)` → type "paper", url 비어 있지 않음
  - `parse_wikidata_entity(wikidata_entity.json)` → extra.P217 또는 P195 중 하나 이상 존재
  - `parse_loc(loc.json)` · `parse_ia(ia.json)` · `parse_crossref` · `parse_s2` · `parse_pleiades_rss` · `parse_wikipedia(…, "en")` → 길이 ≥ 1, 모든 Result에 7개 키 존재
  - `default_engines("image")` == CONFIG 값
  - `search("x", engines=["nonexistent"])` → `{"nonexistent": {"error": ...}}` (네트워크 없이)
  - `format_table({"ddg": [Result], "met": {"error": "e"}})` 문자열에 "ddg 1" 과 "met ✖" 포함
- [ ] **Step 3: 실패 확인** — `python quest/selftest.py`
- [ ] **Step 4: search.py 구현** — 엔진 함수마다 try/except → `{"error": f"{name}: {e.__class__.__name__}: {e}"}`; `search()`는 `rank`가 있으면 엔진 순서를 그것으로, 각 엔진 호출 사이 `polite_delay(domain)`; 결과 Result에 7개 키를 항상 채운다(`license` None 가능).
- [ ] **Step 5: 통과 확인** — selftest 전부 통과
- [ ] **Step 6: 실제 1회 스모크** — `python -c "from quest.core.search import search, format_table; print(format_table(search('Lachish reliefs British Museum', engines=['commons','wikidata','openalex'], n=5)))"` → 엔진 3개 중 2개 이상 결과. 결과 수와 실패 엔진을 selftest 파일 상단 주석에 기록(날짜 포함).
- [ ] **Step 7: 커밋** — `git add quest && git commit -m "quest: 검색 엔진 레지스트리 15종 + 파서 테스트"`

---

### Task 3: 읽기·확보·저장 (`core/read.py`, `core/grab.py`, `core/storage.py`) — executor B

**Files:**
- Create: `quest/core/read.py`, `quest/core/grab.py`, `quest/core/storage.py`, `quest/tests/fixtures/article.html`
- Modify: `quest/selftest.py` (test_read, test_grab, test_storage 섹션)

**Interfaces:**
- Consumes: `core.http.fetch`, `robots_allowed`, `wayback_latest`, `domain_of`; `core.workspace.CONFIG["limits"]`, `CONFIG["storage"]`, `CONFIG["catalog"]`, `ROOT`.
- Produces:
```python
# read.py
def extract_main(html: str, base_url: str) -> tuple[str, str, list[dict], list[dict]]   # (title, text, links, images). script/style/nav/header/footer/aside/form 제거 → article/main/[role=main]/본문 밀도 최대 블록. 제목 h1~h3는 "# " 접두. 링크·이미지는 urljoin으로 절대경로, 중복 제거.
def pdf_text(content: bytes, max_pages: int = 50) -> tuple[str, int]                      # (텍스트, 총 페이지수) pypdf
def is_pdf(content: bytes, content_type: str, url: str) -> bool                           # 매직 %PDF 또는 content-type application/pdf (확장자만으로는 판단 안 함)
def read_url(url: str, *, js: bool = False, force: bool = False, want_links: bool = True, want_images: bool = True) -> Page
#   순서: robots_allowed(url) 아니고 force 아니면 error "robots.txt 금지 — --force" / fetch → PDF면 via "pdf" / HTML이면 extract_main
#   status 403·404·410·5xx 또는 text<200자이면 wayback_latest(url) 로 재시도 → via "wayback"
#   js=True: `import playwright.sync_api` 성공 시 chromium headless로 렌더 후 extract_main, via "js"; 실패 시 error "Playwright 미설치: pip install playwright && playwright install chromium (또는 gstack browse 스킬)"
def save_page(page: Page, dest_dir: Path, step: int) -> Path   # pages/<step:03d>-<slug>.txt — 머리글(url·title·via·status·retrieved) + 본문 + "## 링크"(상위 60) + "## 이미지"(상위 40)
# grab.py
def license_class(text: str | None) -> tuple[str, bool | None]   # Task 4 classify.license_class 를 import 해 재수출 (단일 정의: classify.py)
def sniff_kind(url: str, content_type: str | None) -> str          # image|pdf|video|iiif|file
def license_for(url: str, source_page: str | None) -> dict        # {"license": str|None, "credit": str|None, "source": str|None}
#   commons 파일 페이지/업로드 URL → Commons API extmetadata; metmuseum objects URL → isPublicDomain→"CC0"; loc.gov → 결과 JSON "rights" 있으면 그대로; 그 외 None
def iiif_image_urls(manifest: dict) -> list[str]                   # v2 sequences[0].canvases[].images[0].resource.service['@id'] / v3 items[].items[].items[].body.service[].id → f"{service}/full/max/0/default.jpg"
def grab(url: str, dest_dir: Path, *, kind: str | None = None, source_page: str | None = None, license_hint: str | None = None, limits: dict | None = None, all_iiif: bool = False) -> Entry | dict
#   한도: HEAD/Content-Length 또는 스트리밍 누적으로 초과 시 중단·삭제 → {"error": "한도 초과 N MB > M MB"}; sha256 중복이면 기존 Entry 반환(meta.duplicate=True)
#   video: yt-dlp `-f "bestvideo[height<=H]+bestaudio/best" --merge-output-format mp4 --write-info-json -o dest/%(id)s.%(ext)s`; Entry.meta에 title·duration·uploader
#   manifest.json(dest_dir/manifest.json)에 append; id = f"{kind[:3]}-{sha[:8]}"
def load_manifest(dest_dir: Path) -> list[Entry]
# storage.py
def credentials() -> tuple[str, str, str]           # (base_url, user, password) — secret_file에서 "admin / <pw>" 정규식
def login() -> str                                   # JWT
def usage() -> dict                                  # {"total": int, "used": int, "pct": float}
def ensure_dir(remote_dir: str, token: str) -> None
def upload(local: Path, remote_path: str, token: str | None = None) -> dict   # {"ok", "status", "remote"}; 업로드 전 usage pct ≥ warn_pct 면 {"ok": False, "error": "용량 경고 N%"}
def next_asset_id(catalog: dict, prefix: str) -> str                           # img-0004 식 (prefix img|doc|vid)
def register_asset(entry: Entry, *, title: str, source: str, source_url: str, railway_path: str, evidence_id: str | None, verses: list[str], credit: str | None) -> str
#   assets/catalog.json 스키마(assets/README.md) 그대로 append, commercial_ok는 entry.commercial_ok, added=오늘. id 반환
```

- [ ] **Step 1: 픽스처** — `article.html`: nav(링크 5개)+header+article(제목 h1, 단락 4개 총 800자 이상, 이미지 2개 중 하나는 상대경로 `img/a.jpg`)+aside(광고 텍스트)+footer. 수제로 작성.
- [ ] **Step 2: 실패하는 테스트** (`test_read`):
  - `extract_main(article.html, "https://ex.org/p/1")` → title == h1 텍스트, text에 단락 첫 문장 포함, text에 aside의 "광고" 미포함, images[0].url == "https://ex.org/p/img/a.jpg" 또는 절대 URL
  - `is_pdf(b"%PDF-1.7...", "text/html", "x.pdf")` True; `is_pdf(b"<html>", "application/pdf", "x")` True; `is_pdf(b"<html>", "text/html", "x.pdf")` False
  - `pdf_text(최소 PDF 바이트)` → (str, 1) — pypdf로 1페이지 PDF를 메모리에서 만들어 사용
  - `read_url("http://127.0.0.1:9/x")` → Page.error 비어 있지 않음, via 값 존재
  (`test_grab`):
  - `sniff_kind("https://a/b.jpg", None)` "image"; `(".../manifest.json", "application/ld+json")` "iiif"; `("https://www.youtube.com/watch?v=x", None)` "video"; `("https://a/b.pdf", "application/pdf")` "pdf"
  - `iiif_image_urls(v2 매니페스트 dict)` → `[".../full/max/0/default.jpg"]`
  - `grab(file:// 임시 이미지, tmpdir, limits={"image_mb": 1})` → Entry.kind "image", sha256 64자, manifest 길이 1; 같은 파일 다시 → meta.duplicate True, manifest 길이 1
  - 한도: 2MB 임시 파일 + `limits={"image_mb": 1}` → `{"error": "...한도 초과..."}`, 부분 파일 없음
  (`test_storage`):
  - `next_asset_id({"assets":[{"id":"img-0003"}]}, "img")` == "img-0004"; `("doc")` == "doc-0001"
  - `register_asset` 를 임시 catalog 경로로(함수에 `catalog_path` 키워드 인자 허용) → 파일에 항목 추가, 필수 키 12개 존재
- [ ] **Step 3: 실패 확인**
- [ ] **Step 4: 구현** — `grab`의 `file://` 지원은 테스트용(로컬 경로 복사). 다운로드는 `requests` stream=True, chunk 1MB, 누적 바이트 검사.
- [ ] **Step 5: 통과 확인**
- [ ] **Step 6: 스모크** — `read_url("https://en.wikipedia.org/wiki/Lachish_reliefs")` → text 2,000자 이상, via direct; `grab` 으로 Commons 썸네일 1장(≤1MB) 임시 폴더에 → license 채워짐. 결과를 selftest 주석에 기록. **Railway 업로드는 실행하지 않는다**(Task 6에서 Peter가).
- [ ] **Step 7: 커밋** — `git commit -m "quest: read(본문·PDF·웨이백) · grab(이미지·PDF·IIIF·영상·manifest) · storage(Railway·catalog)"`

---

### Task 4: 분류·학습·우회·플러그인 (`core/classify.py`, `core/learn.py`, `core/escalate.py`, `plugins/godisalive.py`) — executor C

**Files:**
- Create: `quest/core/classify.py`, `quest/core/learn.py`, `quest/core/escalate.py`, `quest/plugins/__init__.py`, `quest/plugins/godisalive.py`, `quest/playbook.json`
- Modify: `quest/selftest.py` (test_classify, test_learn, test_escalate)

**Interfaces:**
- Consumes: `core.workspace.ROOT`, `CONFIG["plugin"]`, `read_log(run)`; `bible/lookup.py`의 `BOOKS`, `NAME2ID` (sys.path에 ROOT/bible 추가; import 실패 시 빈 표).
- Produces:
```python
# classify.py
LICENSE_TABLE: list[tuple[regex, class, commercial_ok]]
def license_class(text: str | None) -> tuple[str, bool | None]
#   "Public domain"/"PD-US"/"public domain" → ("PD", True); "CC0"→("CC0",True); "CC BY 4.0"/"cc-by-4.0"→("CC-BY",True); "CC BY-SA"→("CC-BY-SA",True);
#   "CC BY-NC"/"CC BY-NC-SA"/"CC BY-NC-ND"→("CC-BY-NC",False); "CC BY-ND"→("CC-BY-ND",False); "©"/"(c)"/"copyright"/"All rights reserved"→("ⓒ",False); None/""/기타→("unknown",None)
def authority_tier(url: str, plugin=None) -> int        # plugin.authority_override(domain) 우선; .museum/.edu/.gov/.ac.*/ .go.kr → 1; wikipedia/wikidata/commons/britannica → 2; 언론(nytimes, bbc, chosun, joongang, donga…) → 3; 그 외 4
def grade_ceiling(tier: int) -> str                    # 1→"A", 2→"B", 3→"C", 4→"C"
def detect_lang(text: str) -> str                      # 한글 비율>0.3 ko; 히브리 he; 그리스 el; 라틴 문자면 불용어로 en/de/fr/la 중 최다; 기타 "und"
def media_of(item: dict) -> str                        # Result.type / Entry.kind / Page→"text"
def classify_items(items: list[dict], plugin=None) -> list[Triage]   # dup_of: 같은 sha256 또는 정규화 URL(스킴·www·쿼리 제거)이 앞에 있으면 그 ref
def format_triage(rows: list[Triage]) -> str
# learn.py
PLAYBOOK_PATH: Path   # quest/playbook.json
def load_playbook() -> dict; def save_playbook(pb: dict) -> None
def record_run(run: Path, pb: dict | None = None) -> dict
#   log.jsonl에서 tool=="search": data.per_engine {engine: count} → pb.engines[engine][goal_type] tries+=1, hits+=1 if count>0
#   tool=="read": data.domain, data.via, ok → pb.domains[domain] = {"status": "ok"|"blocked"|"dead"|"js-required", "via_success": [...], "last": ts}; ok and via=="wayback" → pb.routes["blocked->wayback"].success+=1
#   tool=="grab": pb.domains[domain].grabs += 1 (ok)
#   tool=="escalate": pb.routes[f"{data.blockage}->*"].tries += 1
#   반환 summary {"engines_updated": n, "domains_updated": n}
def rank_engines(pb: dict, goal_type: str, candidates: list[str]) -> list[str]   # score=(hits+1)/(tries+2), 내림차순, 동점이면 candidates 순서 유지
def add_lesson(pb: dict, run_id: str, goal_type: str, text: str) -> None
def lessons_for(pb: dict, goal_type: str, k: int = 3) -> list[str]   # 같은 유형 최근 k개, 부족하면 다른 유형으로 채움
def domain_note(pb: dict, domain: str) -> dict | None
def report(pb: dict) -> str
# escalate.py
BLOCKAGES = ["no-results", "403", "404", "empty-js", "paywall", "login", "captcha", "rate-limit"]
def ladder(blockage: str, *, domain: str | None = None, query: str | None = None, pb: dict | None = None) -> list[dict]
#   각 항목 {"step": int, "title": str, "why": str, "command": str}. 설계서 §7의 6단계를 막힘 유형별로 재배열:
#   no-results → 질의변형(언어·등록번호·학술명) → 다른 보관처(commons/wikidata/ia) → 구조화 API → 사람 경로
#   403/rate-limit → 지연 후 재시도 1회 → wayback → 다른 보관처 → read --js → 사람 경로
#   404 → wayback → wikidata로 새 URL → 다른 보관처
#   empty-js → read --js → wayback → 구조화 API(iiif/manifest 추측) → 다른 보관처
#   paywall → openalex/semanticscholar OA 판본 → ia(책) → 저자 리포지토리 → 사람 경로(상호대차·저자 연락)
#   login/captcha → 즉시 다른 보관처·사람 경로 (자동 우회 금지)
#   pb.domains[domain].status == "js-required" 이면 read --js를 1순위로. command는 실제 `python quest/q.py ...` 문자열.
def forbidden_text() -> str   # 설계서 §3 반목표 한 단락 — ladder 출력 끝에 항상 붙인다
# plugins/godisalive.py
TRUSTED_DOMAINS: dict[str, int]   # sources/SOURCES.md의 기관 도메인 → 1 (britishmuseum.org, imj.org.il, louvre.fr, smb.museum, metmuseum.org, loc.gov, archive.org, sefaria.org, perseus.tufts.edu, scaife.perseus.org, antiquities.org.il, deadseascrolls.org.il, jstor.org, brill.com, cambridge.org, degruyter.com, tandfonline.com, uchicago.edu, penn.museum, getty.edu, pleiades.stoa.org, biblicalarchaeology.org→3, academia.edu→3)
PD_HINTS: list[tuple[regex, str]]  # loc.gov matpc(Matson) → "Public domain" 등
AXIS_KEYWORDS: dict[str, list[str]]  # archaeology/history/manuscripts/science 한·영 키워드
def authority_override(domain: str) -> int | None
def axis(text: str) -> str | None
def tag_verses(text: str) -> list[str]     # 한·영 참조("삼하 7:14", "2 Kings 18-20", "Isa 36") → BOOKS로 "삼하 7" 형식 장 단위 정규화 (study/tools/common.normalize_verses 재사용 가능)
def license_hint(url: str) -> str | None
def tags(text: str) -> list[str]           # 유물명·왕 이름 등 간단 사전 매칭 (10~20개로 시작)
```

- [ ] **Step 1: 실패하는 테스트** (`test_classify`): Review Focus 4의 라이선스 9종 표; `authority_tier("https://www.britishmuseum.org/collection/object/W_1856-0909-14")` 1 (플러그인); `("https://en.wikipedia.org/x")` 2; `("https://someblog.tistory.com/1")` 4; `detect_lang("라기스 부조는 산헤립의")` "ko"; `("The Lachish reliefs depict")` "en"; `classify_items([Result(image, license "CC BY-SA 4.0", url commons), Result(web, url 동일 www 제거 변형)])` → 두 번째 dup_of == 첫 ref; `tag_verses("왕하 18:13-19:37과 2 Kings 18 그리고 Isa 36-37")` == ["왕하 18", "왕하 19", "사 36", "사 37"] (중복 제거, 순서 유지).
  (`test_learn`): 임시 run에 log.jsonl 3줄(search per_engine {"commons": 3, "ddg": 0}, read ok via wayback domain britishmuseum.org, 깨진 줄) → `record_run` 후 pb.engines.commons.image == {"tries":1,"hits":1}, ddg hits 0, pb.domains["britishmuseum.org"].status == "ok", routes["blocked->wayback"].success == 1; `rank_engines(pb, "image", ["ddg","commons"])` == ["commons","ddg"]; `add_lesson`+`lessons_for("image")` 길이 1.
  (`test_escalate`): `ladder("403", domain="www.britishmuseum.org")` 의 title들에 "웨이백" 포함, 마지막 요소 뒤 `forbidden_text()`에 "Sci-Hub" 포함; `ladder("login")` 첫 항목 command에 "q.py" 포함하고 어떤 항목에도 "cookies" 미포함; pb.domains js-required 이면 `ladder("empty-js", domain, pb)[0].command`에 "--js" 포함.
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — playbook.json 초기값 `{"engines":{},"domains":{},"routes":{},"lessons":[]}`. `record_run`은 깨진 줄 무시(`read_log`가 이미 함).
- [ ] **Step 4: 통과 확인**
- [ ] **Step 5: 커밋** — `git commit -m "quest: classify(라이선스·권위·언어·중복) · learn(플레이북) · escalate(우회 사다리) · godisalive 플러그인"`

---

### Task 5: q.py 완성 · 스킬 · README (Peter)

**Files:**
- Modify: `quest/q.py` (search/read/grab/classify/escalate/done/learn 명령), `quest/selftest.py` (test_cli: `python quest/q.py --help` 종료코드 0, `new`→`brief` 왕복)
- Create: `.claude/skills/godisalive-quest/SKILL.md`, `quest/README.md`

**Interfaces:** Consumes Task 1~4 전부. 명령 ↔ 모듈:
- `search "<q>" [--engines a,b] [--lang en,ko] [--n 10] [--type T]` → `search.search(..., rank=lambda c,g: learn.rank_engines(pb,g,c))` → `search/<step:03d>-<slug>.json` 저장, `format_table` 출력, `log_action(tool="search", data={"per_engine": {e: len or -1}, "goal_type": T})`
- `read <url> [--js] [--force] [--no-links] [--no-images]` → `read.read_url` → `save_page` → log data `{"domain", "via", "status", "chars"}`; error면 escalate 힌트 한 줄(`escalate.ladder` 첫 항목)
- `grab <url> [--kind K] [--source-page P] [--license "<hint>"] [--upload --remote /srv/archaeology/<slug>/ --title T --evidence ev-id --verses "a;b"] [--all-iiif]` → `grab.grab` → 업로드/등록 시 `storage.upload` + `storage.register_asset`; log data `{"domain","kind","bytes","license","uploaded": bool}`
- `classify [--latest]` → 최근 search JSON들 + manifest + pages 머리글을 모아 `classify.classify_items` → `triage.json`, `format_triage`
- `escalate <blockage> [--domain d] [--query q]` → `set_blocked` + `ladder` 출력 + `forbidden_text`; log data `{"blockage","domain"}`
- `done [--status done|partial] [--lesson "..."]` → `check` 전부 ✓가 아니면 `--status partial` 강제 + 남은 조건 출력; `learn.record_run`, `add_lesson`, `save_playbook`; state.finished; 요약(행동 수·확보 파일 수·플레이북 변경)
- `learn report` → `learn.report(pb)`
- `brief` → `workspace.brief(run, lessons_for(pb, goal_type))`

- [ ] **Step 1: test_cli 작성·실패 확인** — subprocess로 `q.py new "테스트 목표" --type image --criteria "a;b" --budget 3` → exit 0, `q.py brief` 출력에 "테스트 목표" 포함, `q.py escalate 403 --domain x.org` 출력에 "Sci-Hub" 포함. (임시 RUNS_DIR: 환경변수 `QUEST_RUNS_DIR` 지원을 workspace에 추가 — Task 1 수정)
- [ ] **Step 2: q.py 구현**
- [ ] **Step 3: SKILL.md 작성** — 트리거: "찾아줘·확보해줘·조사해줘·퀘스트·deep research·이미지 구해줘·자료 찾아" 또는 CR이 `quest`를 말할 때. 본문 = 루프 규율(설계서 §2 표의 QUEST 열) + 멈춤 금지 조건("못 찾음" 전에 질의 3변형×2언어, 엔진 2종, 아카이브 1회, 구조화 API 1회) + 매 단계 `brief` + 종료 산출물(findings.md, evidence/knowledge 노트, catalog, `done --lesson`, NEXT.md) + 병렬 리드(선택: explore 에이전트에 하위 런) + 금지선.
- [ ] **Step 4: README.md 작성** — 설계 요약 링크, 명령 표, 엔진 표(키 필요 표시), 우회 사다리, 저장 정책, **다른 프로젝트로 가져가기** 절차, 알려진 한계(Playwright 미설치, DDG/Bing 파서 취약, 키 엔진).
- [ ] **Step 5: selftest 전부 통과 확인**, 커밋 `quest: q.py 완성 · godisalive-quest 스킬 · README`

---

### Task 6: 실전 퀘스트 — 라기스 부조 (Peter)

**Files:**
- Create: `quest/runs/2026-10-25-lachish-reliefs/` (goal·todo·log·findings·triage·state 커밋, downloads/pages/search 제외), `evidence/archaeology/ev-arch-lachish-reliefs.md`
- Modify: `assets/catalog.json`, `NEXT.md`, `PLAN.md`(Phase 0 표), `PETER.md`(§4), `README.md`(디렉터리·핵심 문서), `.claude/skills/godisalive-study/SKILL.md`(소화 단계에서 검증 자료 찾기에 quest 사용 한 줄)

- [ ] **Step 1**: `q.py new "라기스 부조(대영박물관) — 책에 쓸 수 있는 PD/CC 이미지 1장, 등록번호·소장 정보, 1차 문헌 2건" --type object --criteria "commercial_ok 이미지 1장 확보·업로드·catalog 등록;BM 등록번호와 전시실 확인;1차 문헌(발굴 보고·학술) 2건 URL;evidence 노트 A등급 작성" --budget 40`
- [ ] **Step 2**: 스킬 루프대로 수행 — 매 단계 `brief` → 도구 1개 → `todo` 갱신. 막히면 `escalate`.
- [ ] **Step 3**: `grab --upload --remote /srv/archaeology/lachish-reliefs/ --evidence ev-arch-lachish-reliefs --verses "왕하 18:13-17;대하 32:9;사 36:1-2;미 1:13"`
- [ ] **Step 4**: evidence 노트 작성(템플릿·등급 A·출처 4건 이상), findings.md 정리, `classify`, `check --mark` 전부, `done --lesson "..."`
- [ ] **Step 5**: `learn report`로 플레이북 변화 확인(엔진 적중·BM 도메인 메모). 문서 갱신(NEXT·PLAN·PETER·README), 커밋 `quest: 실전 1호 라기스 부조 — 이미지·등록번호·문헌 확보, 플레이북 첫 학습`

---

### Task 7: 검증 (Peter + architect-medium 1회)

- [ ] **Step 1**: `python quest/selftest.py` 전부 통과, `python study/tools/selftest.py` 전부 통과(회귀), `python study/tools/graph.py --check --no-desktop` (새 evidence 노트 연결 확인)
- [ ] **Step 2**: `oh-my-claudecode:architect-medium`(sonnet, 읽기 전용)에 설계서·계획·`quest/` 를 주고 "설계서 §3 반목표 위반 코드가 있는가, 예외가 밖으로 새는 네트워크 함수가 있는가, 한도 검사가 빠진 다운로드 경로가 있는가, 플레이북 갱신이 로그 형식과 맞는가" 4문항 검토 → 지적 사항 수정 → selftest 재실행
- [ ] **Step 3**: 메모리 파일 `quest-mode.md` + MEMORY.md 색인, 최종 커밋·push

---

## Self-Review 기록

- 설계서 §5 명령 11개 ↔ Task 1(new·brief·todo·check·status·log) + Task 5(search·read·grab·classify·escalate·done·learn) — 전부 매핑.
- §6 엔진 15종 + 키 엔진 2종 ↔ Task 2. §7 사다리 ↔ Task 4 escalate. §8 ↔ Task 4 classify. §9 ↔ Task 4 learn + Task 5 done. §10 ↔ Task 3 grab 한도·storage usage. §11 이식 ↔ Task 5 README. §12 검증 ↔ Task 6·7.
- 형식 일관성: `Result/Page/Entry/Triage/LogRow` 키를 상단에 고정, `license_class`는 classify.py 단일 정의(grab이 import).
- Review Focus 5건 → Task 2(1), Task 3(2·3), Task 4(4·5) 테스트에 배정.
- 분량: 계획은 설계서의 약 1.5배 — 인터페이스 선언이 대부분, 본문 코드는 없음.
