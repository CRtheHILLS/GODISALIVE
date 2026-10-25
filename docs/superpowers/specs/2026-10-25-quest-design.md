# QUEST — 목표지향 검색·확보 에이전트 설계서

작성 2026-10-25 · Peter · CR 지시 반영 · 상태: v1 (구현과 함께 갱신)

## 0. CR의 지시 (원문 요지)

> 이 프로젝트는 "하나님은 살아계신다"와 성경의 근거를 deep thinking · deep research 하는 프로젝트다.
> 검색은 Manus AI처럼 **될 때까지 수행하는 에이전트** 개념이 필요하다. 브라우징, 사진 수집, 영상 확보, 저장과 용량,
> 분류화 추론, 학습의 재귀적 자기 개선을 코딩하라. Manus의 "컴퓨터" 개념을 적용해 검색을 획기적으로 올려라.
> 다른 프로젝트에서도 가져다 쓸 수 있게 만들라. 박물관·모든 웹사이트·접근하기 어려운 곳까지 뚫리게,
> 목적을 이루기 위해 우회하는 방법까지 포함한 **'목표지향적인 검색 및 확보'** 로 구현하라.

## 1. 무엇을 만드는가 — 한 문단

**QUEST**는 "목표 하나 = 컴퓨터 하나"로 움직이는 연구 에이전트 체계다. 목표(예: "라기스 부조의 책에 쓸 수 있는 이미지와
소장 정보, 1차 문헌 2건 확보")를 주면 전용 작업 폴더(컴퓨터)를 만들고, 그 안에서 **검색 → 읽기 → 확보 → 분류 → 기록**을
반복한다. 막히면 **우회 사다리**(합법적 대체 경로)를 타고, 완료 조건이 전부 체크될 때까지 또는 예산이 끝날 때까지 멈추지 않는다.
끝나면 무엇이 통했고 무엇이 막혔는지를 **플레이북**에 적어 다음 퀘스트의 길 찾기에 반영한다 — 이것이 자기 개선이다.
두뇌는 Peter(Claude)이고 손발은 Python 도구다. 도구는 GODISALIVE에 매이지 않게 설계해 다른 프로젝트로 폴더째 옮길 수 있다.

## 2. Manus에서 가져오는 것, 가져오지 않는 것

Manus(2025 블로그 "Context Engineering for AI Agents: Lessons from Building Manus", Yichao Ji)의 공개된 설계 원칙과
2차 자료에서 확인된 구조를 다음처럼 옮긴다.

| Manus 개념 | QUEST 구현 |
|---|---|
| 작업마다 샌드박스 VM("자기 컴퓨터": 브라우저·셸·파일시스템) | 퀘스트마다 폴더 `quest/runs/<id>/` = 컴퓨터. goal.md · todo.md · log.jsonl · findings.md · downloads/ · state.json |
| 에이전트 루프: 행동 선택 → 실행 → 관찰을 컨텍스트에 덧붙임 → 반복 | Peter가 `q.py` 도구를 한 번에 하나씩 호출. 모든 도구가 자동으로 log.jsonl에 행동·결과 요약을 남긴다 |
| todo.md 되뇌기(recitation)로 긴 작업에서 목표 유지 | `q.py brief`가 목표·완료조건·todo·최근 로그를 한 화면으로 출력. 매 단계 전에 읽고, todo를 갱신한다 |
| 파일 시스템을 무한 컨텍스트로 — 큰 결과는 파일에, 컨텍스트엔 참조만 | 검색 결과·본문·PDF 텍스트는 파일로 저장, 브리프에는 요약과 경로만 |
| 실패를 지우지 않고 남긴다 | log.jsonl에 403·0건·타임아웃이 그대로 남고, learn.py가 그것을 캐서 플레이북을 고친다 |
| 도구를 빼지 말고 가린다(mask) · 계층적 행동 공간 | 도구는 `q.py` 하위 명령 10개로 고정. 우회 사다리 단계가 "지금 쓸 수 있는 도구"를 제한한다 |
| 될 때까지 (수십 번의 도구 호출) | 완료 조건 체크리스트(`q.py check`) + 예산(기본 40행동). 사다리를 다 타기 전엔 "못 찾음"을 선언할 수 없다 |

가져오지 않는 것: 별도 LLM API 루프(지금은 Claude Code 세션 안에서 Peter가 루프를 돈다 — 키·비용·감독 문제), 클라우드 VM
(로컬 폴더로 충분), 자동 결제·계정 생성 같은 행동.

## 3. 목표 · 비목표 · 반목표

**목표**
1. 목표 문장 하나로 시작해 완료 조건이 전부 체크될 때까지 도는 루프와 그 규율(스킬).
2. 키 없이 바로 쓰는 검색 엔진 12종 이상(웹·백과·위키데이터·커먼즈·인터넷아카이브·박물관 API·학술 OA·의회도서관·지명·유대문헌·영상).
3. 어떤 URL이든 본문·링크·이미지·PDF 텍스트로 읽기, JS 페이지와 죽은 페이지(웨이백) 폴백.
4. 이미지·PDF·IIIF·영상 확보 — 라이선스 메타데이터를 함께 잡고, sha256·용량 한도·manifest, Railway 업로드와 catalog 등록까지.
5. 분류 추론 — 매체·라이선스(상업 이용 가능 여부)·출처 권위·증거 축·성경 구절·언어·중복을 자동 1차 판정, 최종은 Peter.
6. 자기 개선 — 엔진·도메인·우회 경로별 성공률을 플레이북에 축적해 다음 검색의 순서를 바꾼다. 교훈은 사람이 읽을 수 있는 문장으로도 남긴다.
7. 다른 프로젝트 이식 — `quest/` 폴더 + `config.json` + `plugins/<프로젝트>.py` 만 바꾸면 된다.

**비목표(지금은 안 함)**: 완전 무인 백그라운드 데몬, 플레이리스트 대량 수집, 벡터 검색(Phase 5), GUI.

**반목표(하면 실패)**: 유료 장벽 우회(Sci-Hub 류), 로그인·크리덴셜 공유, CAPTCHA 자동 해제, DRM 제거, robots.txt·이용약관을 어기는
대량 수집, 라이선스 미확인 이미지의 책 사용. **"우회"는 합법적 대체 경로를 뜻한다** — 다른 보관처, 아카이브 사본, 공개 API, 오픈액세스
판본, 기관 요청 양식. 이 선은 PLAN.md의 "저작권 준수" 원칙과 같다.

## 4. 컴퓨터(퀘스트 작업 폴더)의 구조

```
quest/runs/2026-10-25-lachish-reliefs/
  goal.md        목표 · 유형(image|text|paper|video|object|mixed) · 완료 조건(체크박스) · 제약 · 예산
  todo.md        계획 — 매 단계 갱신 (Manus recitation). 끝난 항목은 [x]
  log.jsonl      {ts, step, tool, args, ok, summary, path}  — 도구가 자동 기록, 실패도 남김
  findings.md    발견 — 출처 URL · 인용 · 등급 메모 (Peter가 쓴다)
  search/        엔진별 결과 JSON (q.py search가 저장)
  pages/         읽은 페이지 텍스트 (q.py read가 저장)
  downloads/     확보 파일 + manifest.json (sha256 · 크기 · 라이선스 · 출처 · 시각) — git 제외
  triage.json    분류 결과 (q.py classify)
  state.json     status(open|done|partial) · steps · budget · blocked(유형, 도메인) · criteria 체크 상태
```

## 5. 도구(행동 공간) — `python quest/q.py <명령>`

| 명령 | 역할 | 비고 |
|---|---|---|
| `new "<목표>" --type T --criteria "a;b;c" [--budget 40]` | 컴퓨터 생성, goal.md·todo.md 초기화 | id = 날짜-슬러그 |
| `brief` | 목표·완료조건·todo·최근 로그 8줄·막힘 상태·관련 교훈 3개 | 매 단계 전 필수 |
| `todo "- [ ] ..."` / `todo --done 3` | todo.md 갱신 | |
| `search "<질의>" [--engines a,b] [--lang ko,en] [--n 10]` | 멀티 엔진 검색 → search/*.json + 표 | 엔진 순서는 플레이북이 정함 |
| `read <url> [--js] [--pdf] [--links] [--images]` | 본문 추출 → pages/*.txt. 403/404/빈 본문이면 웨이백 자동 시도 | bs4 + readability-lite |
| `grab <url> [--kind image|pdf|video|iiif] [--license-from <url>] [--upload]` | 확보 → downloads/ + manifest. 한도 검사. `--upload`면 Railway + catalog | yt-dlp, IIIF |
| `classify [--path ...]` | 결과·파일 분류 → triage.json + 표 | 플러그인이 성경 구절·증거 축 태깅 |
| `escalate <blockage> [--domain d]` | 막힘 유형별 다음 시도 목록(명령어까지) | 403·404·no-results·empty-js·paywall·login·captcha·rate-limit |
| `check [--mark 2]` | 완료 조건 체크 상태 표시·표기 | 전부 ✓면 done 가능 |
| `done [--status done|partial] --lesson "..."` | 종료 — learn 실행, 플레이북 갱신, 남은 일·사람 경로 출력 | |
| `learn report` / `learn reset-domain d` | 플레이북 통계 | |
| `status` | 열린 퀘스트 목록 | |

## 6. 검색 엔진 (키 없음 → 바로 동작; 키 있으면 추가)

| 엔진 | 유형 | 방식 |
|---|---|---|
| ddg | web | DuckDuckGo HTML 엔드포인트 파싱 |
| bing | web | 검색 결과 HTML 파싱 (폴백) |
| wikipedia | text | MediaWiki API, 다국어 |
| wikidata | object | wbsearchentities + SPARQL(소장처 P195, 등록번호 P217, 이미지 P18, 커먼즈 분류 P373) |
| commons | image | Commons API imageinfo + extmetadata(라이선스·저작자·크레딧) |
| ia | text/image/video | Internet Archive advancedsearch + 메타데이터, 웨이백 CDX |
| met | object/image | Met Museum Open Access API (isPublicDomain) |
| loc | image/text | Library of Congress JSON (fo=json), Matson 컬렉션 |
| openalex | paper | OpenAlex works + oa_url (오픈액세스 PDF) |
| crossref | paper | 메타데이터·DOI |
| semanticscholar | paper | 무키 검색(속도 제한) |
| louvre | object | collections.louvre.fr 검색 HTML + ark .json |
| pleiades | place | 고대 지명 gazetteer |
| sefaria | text | 유대 문헌 API |
| youtube | video | yt-dlp ytsearch |
| europeana / smithsonian / harvard | object | **키 필요** — `.omc/secrets/`에 있으면 자동 활성 |

박물관 중 API가 없는 곳(대영박물관·이스라엘 박물관·페르가몬)은 **우회 사다리**가 커먼즈 분류·위키데이터 등록번호·웨이백·`read --js`
순으로 안내한다. 도메인별 접근 메모(JS 필요, 봇 차단, 웨이백 가능)는 플레이북에 쌓인다.

## 7. 우회 사다리 (escalate) — 합법 경로만

막힘 유형 → 순서대로 시도. 각 단계는 구체적 명령으로 출력된다.
1. **질의 변형**: 영어·독어·불어·히브리어 명칭, 학술 명칭, 등록번호(예: BM 124911), 발굴자 이름.
2. **다른 보관처**: Wikimedia Commons(박물관 촬영 사진), Wikidata, Europeana, Google Arts & Culture(읽기만).
3. **아카이브 사본**: 웨이백 CDX 최신 스냅샷, archive.today(읽기).
4. **구조화 API로 갈아타기**: 박물관 API·IIIF 매니페스트·OpenAlex→Unpaywall OA PDF·기관 리포지토리.
5. **JS 렌더링**: `read --js` (Playwright 설치 시) 또는 gstack 브라우저.
6. **사람 경로**: 박물관 이미지 요청 양식, 상호대차, 저자 연락 — Peter가 요청문 초안을 쓰고 "사람 액션 대기"로 기록.
금지선(§3 반목표)은 escalate 출력 끝에 항상 붙는다.

## 8. 분류 추론 (classify)

- 매체: image / pdf / video / text / object / paper / place
- 라이선스 → `commercial_ok`: PD·CC0·CC BY·CC BY-SA → true / NC·ND·ⓒ·unknown → false (책 출판의 생명선)
- 출처 권위 1~4등급: 1 박물관·도서관·대학·학술지·정부(.museum .edu .gov + 도메인표) / 2 백과·위키 / 3 언론 / 4 블로그·미상
  → **증거 등급 상한 제안**(A는 1~2등급 + 교차 확인 필요). 최종 판정은 Peter.
- 증거 축: archaeology / history / manuscripts / science (플러그인 키워드)
- 성경 구절: 한·영 참조 정규식 → `bible/lookup.py` BOOKS로 정규화
- 언어: 문자 체계 + 불용어로 ko/en/de/fr/he/el/la
- 중복: sha256 · 정규화 URL

## 9. 자기 개선 (learn)

`quest/playbook.json` (git 추적):
- `engines[엔진][목표유형]` = 시도·적중 수 → 검색 순서 = 적중률(라플라스 평활) 내림차순, 기본 순서로 타이브레이크
- `domains[도메인]` = status(ok|js-required|blocked|dead), 통한 우회 경로, 메모, 최근 시각
- `routes["403->wayback"]` 등 = 시도·성공
- `lessons[]` = {날짜, 퀘스트, 유형, 문장} — Peter가 `done --lesson`으로 적는 자연어 교훈. `brief`가 같은 유형의 최근 교훈 3개를 보여준다.
`learn`은 `done` 때 log.jsonl을 읽어 자동 집계한다. 숫자는 기계가, 문장은 Peter가 — 둘이 합쳐 재귀적으로 좋아진다.
플레이북은 사람이 읽고 고칠 수 있는 JSON이어야 한다(블랙박스 금지).

## 10. 저장과 용량

- 로컬 `quest/runs/*/downloads/`는 git 제외. 퀘스트당 500MB, 이미지 25MB, PDF 100MB, 영상 2GB(≤1080p) 한도 — config.json.
- Railway Volume: 총 4.8GB, 사용 6MB(2026-10-25). 업로드 전 `/api/usage/` 확인, 80% 넘으면 경고·중단. 경로 `/srv/<축>/<슬러그>/`.
- `assets/catalog.json` 등록(id 자동 증가 img-/doc-/vid-), `commercial_ok` 필수. 분기 백업 규칙은 assets/README.md 그대로.
- 로컬 디스크 여유 38GB — 영상은 필요한 것만.

## 11. 다른 프로젝트로 가져가기

`quest/` 폴더를 복사 → `config.json`에서 프로젝트명·저장 경로·업로드 대상·한도 수정 → `plugins/<이름>.py`에 그 프로젝트의
분류 규칙(키워드·도메인 신뢰표·태깅)을 쓰고 config에서 지정. 성경 전용 로직은 전부 `plugins/godisalive.py`에만 있다.
스킬 파일(`.claude/skills/godisalive-quest/SKILL.md`)의 루프 규율은 프로젝트 이름만 바꿔 재사용.

## 12. 검증 기준 (이 설계가 되었다는 증거)

1. `python quest/selftest.py` 전부 통과 (엔진 파서는 고정 HTML 픽스처로, 네트워크 없이).
2. 실전 퀘스트 1건 완료: **"라기스 부조(대영박물관) — 책에 쓸 수 있는 PD/CC 이미지 1장, 등록번호·소장 정보, 1차 문헌 2건"** →
   evidence 노트 ev-arch-lachish-reliefs(A) + catalog 등록 + Railway 업로드 + 플레이북에 첫 학습 기록.
3. 끊어진 부분(키 필요 엔진, Playwright 미설치)은 README에 명시.

## 13. 내가 내린 결정 (CR이 고칠 수 있음)

- 루프의 두뇌는 Claude Code 세션 안의 Peter다. 별도 LLM API 데몬은 만들지 않았다 (키·비용·감독).
- "우회"는 합법 경로로 한정했다 (§3).
- 폴더 이름 `quest/`, 명령 이름 `q.py`.
- 플레이북은 JSON 하나 + 교훈 문장. 벡터 DB 없음(Phase 5에서).
- 첫 실전 퀘스트는 NEXT.md의 A등급 대기 목록에서 라기스 부조를 골랐다.
