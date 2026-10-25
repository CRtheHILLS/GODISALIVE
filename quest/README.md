# quest/ — 목표지향 검색·확보 에이전트 (QUEST)

> "검색은 Manus AI처럼 될 때까지 수행하는 에이전트여야 한다." — CR, 2026-10-25
> 설계서: [docs/superpowers/specs/2026-10-25-quest-design.md](../docs/superpowers/specs/2026-10-25-quest-design.md) ·
> 계획: [docs/superpowers/plans/2026-10-25-quest-plan.md](../docs/superpowers/plans/2026-10-25-quest-plan.md) ·
> 루프 규율: [.claude/skills/godisalive-quest/SKILL.md](../.claude/skills/godisalive-quest/SKILL.md)

## 한 문단
목표 하나 = 컴퓨터 하나. `q.py new`가 전용 폴더를 만들고, Peter(Claude)가 `search → read → grab → classify → finding`을
한 번에 하나씩 호출하며 `brief`로 목표를 되뇌인다. 모든 행동은 `log.jsonl`에 남고(실패도), 끝나면 `done`이 그 기록으로
`playbook.json`을 갱신해 다음 퀘스트의 엔진 순서와 도메인 접근법을 바꾼다. 막히면 `escalate`가 합법적 우회 사다리를 준다.

## 컴퓨터(런 폴더)
```
quest/runs/<날짜>-<슬러그>/
  goal.md  todo.md  log.jsonl  findings.md  state.json  triage.json     ← git 추적
  search/  pages/  downloads/(+manifest.json)                            ← 캐시, git 제외
```

## 명령
| 명령 | 역할 |
|---|---|
| `new "<목표>" --type T --criteria "a;b" [--budget 40]` | 컴퓨터 생성 (T: image·text·paper·video·object·place·web·mixed) |
| `brief` | 목표·완료조건·todo·최근 행동 8줄·막힘·교훈 — 매 단계 전 |
| `todo "- [ ] ..."` · `todo --done N` | 계획 갱신 |
| `search "<q>" [--engines a,b] [--lang en,ko] [--n 10] [--type T]` | 멀티 엔진 검색 → `search/NNN-*.json` |
| `read <url> [--js] [--force]` | 본문·링크·이미지·PDF 텍스트 → `pages/NNN-*.txt`, 막히면 웨이백 자동 |
| `grab <url> [--kind K] [--source-page P] [--license "<힌트>"] [--upload --remote /srv/… --title --evidence --verses]` | 확보 + manifest, 업로드·catalog 등록 |
| `classify` | 검색 결과·확보 파일 분류 → `triage.json` |
| `escalate <막힘> [--domain d] [--query q]` | 우회 사다리 + 금지선 |
| `finding "<문장>" --url U [--grade A/B/C]` | findings.md에 출처 있는 발견 |
| `addresult "<제목>" <url> [--snippet] [--engine websearch]` | 세션 도구(WebSearch)로 얻은 결과를 검색 기록에 편입 |
| `check [--mark N]` · `done [--status] [--lesson]` · `learn report` · `status` | 완료 조건 · 종료+학습 · 플레이북 · 목록 |

## 검색 엔진
| 엔진 | 유형 | 키 | 비고 |
|---|---|---|---|
| ddg · bing | web | 없음 | HTML 파싱 — 구조가 바뀌면 0건(엔진 실패로 표시, 다른 엔진은 계속) |
| wikipedia · wikidata · commons | text · object · image | 없음 | Wikidata: 소장처(P195)·등록번호(P217)·이미지(P18)·커먼즈 분류(P373) |
| ia | text·image·video | 없음 | Internet Archive + 웨이백 |
| met · loc · louvre | object·image | 없음 | Met Open Access(CC0 여부), LOC(Matson PD), 루브르 컬렉션 |
| openalex · crossref · semanticscholar | paper | 없음 | 오픈액세스 PDF URL |
| pleiades · sefaria · youtube | place · text · video | 없음 | 고대 지명 · 유대 문헌 · yt-dlp |
| europeana · smithsonian | object | **필요** | `.omc/secrets/europeana-key.txt`, `smithsonian-key.txt` 있으면 자동 활성 |

엔진 순서 = `config.json engines_default[유형]`을 `playbook.json`의 적중률로 재정렬.

## 우회 사다리 (합법 경로만)
질의 변형(언어·등록번호·학술명) → 다른 보관처(Commons·Wikidata·Europeana) → 아카이브(웨이백) → 구조화 API(박물관 API·IIIF·OpenAlex OA)
→ JS 렌더링(`read --js`, Playwright 설치 시 / gstack browse) → 사람 경로(요청 양식·상호대차·저자 연락, Peter가 초안).
**금지**: 유료 장벽 우회(Sci-Hub), 로그인·크리덴셜 공유, CAPTCHA 자동 해제, DRM 제거, robots.txt·약관 위반 대량 수집.

## 저장과 용량 (`config.json limits/storage`)
퀘스트당 500MB · 이미지 25MB · PDF 100MB · 영상 2GB(≤1080p). Railway Volume 4.8GB(2026-10-25 사용 6MB) — 업로드 전 용량 확인, 80% 경고.
`grab --upload`가 `/srv/<축>/<슬러그>/`에 올리고 `assets/catalog.json`에 `commercial_ok`와 함께 등록한다.

## 자기 개선 (`playbook.json`)
- `engines[엔진][유형]` 시도·적중 → 다음 검색 순서
- `domains[도메인]` ok / js-required / blocked / dead + 통한 경로 → 사다리가 그 도메인은 통한 길을 먼저 권한다
- `routes` 우회 경로 성공률 · `lessons[]` Peter가 `done --lesson`으로 남긴 문장 → `brief`에 되뇌임
사람이 읽고 고칠 수 있는 JSON이다. 블랙박스 없음.

## 다른 프로젝트로 가져가기
1. `quest/` 폴더를 복사한다 (runs/·playbook.json은 비워도 된다).
2. `config.json`: project · runs_dir · storage(업로드 대상, 없으면 `"kind": "none"`) · catalog · limits · engines_default.
3. `plugins/<이름>.py`에 `authority_override / axis / tag_verses / license_hint / tags`를 그 프로젝트에 맞게 쓰고 config `plugin`을 바꾼다. 성경 전용 로직은 전부 `plugins/godisalive.py`에만 있다.
4. 스킬 파일을 복사해 프로젝트 이름만 바꾼다. `python quest/selftest.py`가 전부 통과하면 준비 끝.

## 알려진 한계
- Playwright **설치됨(2026-10-25)** → `read --js`가 JS 페이지(대영박물관 소장 페이지 등)를 렌더링해 읽는다. 재설치: `pip install playwright && python -m playwright install chromium`.
- DDG·Bing·Mojeek·LOC는 **이 PC의 IP에서 봇 차단**(2026-10-25 확인: DDG 202 챌린지, Bing 무관 결과, LOC/BM 403, Mojeek CAPTCHA). web 유형은
  Peter의 세션 WebSearch로 URL을 얻고 `python quest/q.py addresult "<제목>" <url> --snippet "..."`로 기록에 편입한다. 파서는 픽스처로 검증돼 있어 차단이 풀리면 바로 동작.
- Git Bash에서 `--remote /srv/...` 는 MSYS가 `C:/Program Files/Git/srv/...`로 바꾼다 — `MSYS_NO_PATHCONV=1`을 붙이거나 storage의 자동 정규화에 맡긴다.
- 박물관 중 API 없는 곳(대영박물관·이스라엘 박물관·페르가몬)은 Commons·Wikidata 경로가 기본이다.
- 두뇌는 Claude Code 세션의 Peter다. 무인 데몬이 아니다 (설계서 §13).

## 검증 기록
- `python quest/selftest.py` 215건 통과 (네트워크 없이 픽스처) · 실전 1호 라기스 부조 완료(26행동, 4/4) — `quest/runs/2026-10-25-lachish-reliefs/`
- 2026-10-25 architect 검토(설계서 §3 금지선·예외 누출·용량 한도·플레이북 일관성) → **고침**: 영상 사후 용량 검사·부산물 정리, 퀘스트 총량(quest_mb) 강제,
  부분 파일 finally 정리·고유 .part 이름, fetch 본문 50MB 상한, yt-dlp `--ignore-config --no-cookies-from-browser`, 영상 외 모든 grab에 robots 확인,
  Playwright finally 종료, storage usage 무예외·스트리밍 업로드·용량 확인 실패 시 중단, `read --force` 기록, 200·본문 없음 → js-required 판정과
  empty-js 사다리, 검색 유형별 적립·addresult 통계 제외·엔진 오류 통계 제외, done 중복 적립 방지, 플레이북 원자적 저장, 폴더 이름 독립(HOME).
- **남긴 LOW(후속)**: manifest가 절대 경로를 저장(폴더 이동 시 깨짐) · robots.txt를 못 받으면 허용으로 간주 · 403 뒤 다른 브라우저 UA로 1회 재시도(차단 회피가
  아니라 통상 재시도지만 명시함) · ddg/bing/louvre 검색 결과 HTML은 단건 질의라 robots 확인 생략 · `--all-iiif` 최대 50장.
