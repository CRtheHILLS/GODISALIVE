---
name: godisalive-quest
description: GODISALIVE 퀘스트 모드 — 목표지향 검색·확보 에이전트 루프. CR이 "찾아줘·확보해줘·조사해줘·이미지 구해줘·자료 찾아·deep research·퀘스트"라고 하거나 유물·문헌·사진·영상을 구해야 하는 모든 연구 작업에 발동. 퀘스트마다 전용 작업 폴더(컴퓨터)를 만들고 python quest/q.py 도구로 검색→읽기→확보→분류→기록을 완료 조건이 전부 체크될 때까지 반복한다. 막히면 우회 사다리(합법 경로)를 타고, 끝나면 플레이북에 학습을 남긴다.
---

# 퀘스트 모드 — 될 때까지 도는 연구 루프

설계: `docs/superpowers/specs/2026-10-25-quest-design.md` · 도구: `quest/README.md`. 여기는 **루프의 규율**이다.
Manus의 원칙을 따른다: 자기 컴퓨터(폴더) · 되뇌기(brief) · 파일이 기억 · 실패도 기록 · 될 때까지.

## 0. 시작 — 목표를 완료 조건으로 바꾼다
```
python quest/q.py new "<목표 한 문장>" --type <image|text|paper|video|object|place|web|mixed> \
   --criteria "<조건1>;<조건2>;<조건3>" --budget 40
```
- 완료 조건은 **검사할 수 있는 문장**으로 (예: "commercial_ok 이미지 1장 catalog 등록", "등록번호 확인", "1차 문헌 2건 URL").
- 목표 유형이 엔진 기본 순서를 정한다. 섞였으면 mixed.

## 1. 루프 — 한 번에 행동 하나
```
python quest/q.py brief                 # ① 되뇌기: 목표·조건·todo·최근 행동·교훈을 다시 읽는다
<도구 1개>                               # ② search | read | grab | classify | escalate | finding
python quest/q.py todo "- [ ] ..."       # ③ 다음 할 일을 적고, 끝난 일은 todo --done N
```
- **brief 없이 두 행동 연속 금지.** 긴 작업에서 목표를 잃는 것을 막는 유일한 장치다. (여러 도구를 한 응답에 묶어 돌릴 때도 묶음마다 brief 1회)
- 일반 웹 검색(ddg·bing)이 봇 차단으로 0건이면 Peter의 WebSearch 도구로 찾고 `addresult "<제목>" <url>`로 기록에 편입한다 — 기록 없는 검색은 학습되지 않는다.
- 큰 결과(검색 JSON·본문·파일)는 파일에 있다. 브리프와 대화에는 요약과 경로만 가져온다.
- 발견은 즉시 `finding "<문장>" --url <출처> --grade A|B|C` 로 기록한다. 출처 없는 발견은 발견이 아니다.
- 완료 조건이 하나 채워지면 즉시 `check --mark N`.

## 2. 멈춤 금지 조건 — "못 찾았다"를 말하기 전에
다음을 **모두** 했다는 기록(log.jsonl)이 없으면 못 찾았다고 말할 수 없다:
1. 질의 **3가지 변형 × 2개 언어** (한국어·영어 + 필요시 독·불·히브리어, 학술 명칭, 등록번호, 발굴자 이름)
2. **엔진 2종 이상** (목표 유형 기본 + 다른 유형의 엔진 1개)
3. **아카이브 경로 1회** (wayback 또는 Internet Archive)
4. **구조화 API 경로 1회** (wikidata·commons·met·openalex·iiif 중)
5. `escalate <막힘>` 사다리를 끝까지 탔다
그래도 없으면 `done --status partial`로 끝내고 **사람 경로**(요청 양식·상호대차·저자 연락)를 NEXT.md에 올린다.

## 3. 막힘 → 사다리
| 증상 | 명령 |
|---|---|
| 검색 0건 | `escalate no-results --query "<q>"` |
| 403 / 429 | `escalate 403 --domain <d>` (지연 재시도 → 웨이백 → 다른 보관처 → --js → 사람) |
| 404 | `escalate 404 --domain <d>` (웨이백 → 위키데이터로 새 URL) |
| 본문 비어 있음(JS) | `escalate empty-js --domain <d>` (`read --js` — Playwright 없으면 gstack browse 스킬) |
| 유료 논문 | `escalate paywall --query "<제목>"` (OpenAlex·S2 OA 판본 → IA → 리포지토리 → 상호대차) |
| 로그인·CAPTCHA | `escalate login` — **자동 우회 없음**, 즉시 다른 보관처·사람 경로 |

**금지선** (설계서 §3): 유료 장벽 우회(Sci-Hub 류), 로그인·크리덴셜 공유, CAPTCHA 자동 해제, DRM 제거, robots.txt·약관 위반
대량 수집, 라이선스 미확인 이미지의 책 사용. `read`가 robots.txt 금지를 알리면 `--force`는 **단건·기록 필수**.

## 4. 확보와 저장
```
python quest/q.py grab <파일URL> --source-page <출처페이지> --kind image \
   --upload --remote /srv/<archaeology|manuscripts|sites|maps|book>/<슬러그>/ \
   --title "<제목>" --evidence <ev-id> --verses "왕하 18:13;사 36:1"
```
- 라이선스는 `license_for`가 Commons·Met·LOC에서 자동으로 잡는다. **unknown이면 책 후보가 아니다** — 출처 페이지를 읽어 `--license "<문구>"`로 넘기거나 다른 사본을 찾는다.
- 한도(config.json limits)를 넘으면 grab이 거절한다. 영상은 필요한 것만 (≤1080p).
- Railway 용량 80% 경고가 나면 업로드를 멈추고 CR에게 보고.

## 5. 종료 — 세 가지를 남긴다
1. **지식**: evidence/ 또는 knowledge/ 노트 (등급·출처·[[링크]]) — findings.md를 재료로 Peter가 쓴다.
2. **자산**: catalog.json 등록 + Railway 업로드 (grab --upload가 했는지 확인).
3. **학습**: `python quest/q.py done --lesson "<무엇이 통했고 무엇이 막혔나 한 문장>"` → playbook.json 갱신.
   `learn report`로 엔진 적중률·도메인 메모가 바뀐 것을 확인한다.
그다음 `python study/tools/graph.py --check --no-desktop`(새 노트 연결), NEXT.md 갱신, 커밋.

## 6. 병렬 리드 (선택)
독립된 단서가 3개 이상이고 각각 10행동 이상이면, 단서마다 `new`로 하위 퀘스트를 만들어 explore 에이전트(haiku/sonnet)에 맡길 수 있다.
CR의 에이전트 절약 규칙: 같은 주제 재확인은 새 에이전트가 아니라 같은 에이전트에게 SendMessage.

## 7. CR에게 보고하는 형식
목표 한 줄 → 완료 조건 ✓/☐ → 확보한 것(파일·등록번호·문헌, 등급) → 막혔던 곳과 탄 사다리 → 플레이북에 남긴 교훈 → 남은 일(사람 경로).
