---
name: godisalive-study
description: GODISALIVE 공부 모드 — CR이 유튜브 설교·강의·기독교 지식 영상 링크(어느 언어든)를 붙이거나 "공부 모드", "이 설교 정리해줘", "이 강의 공부하자"라고 하면 발동. 자막을 수집해 Peter가 쉬운 한국어 HTML 보고서로 소화하고, 지식 노트·개념 노드·증거 노트를 만들어 지식 그래프(뉴런)에 연결한다. 메인 프로젝트(시편 연구 등)와 별도로 수동으로만 돈다.
---

# GODISALIVE 공부 모드 (수동 발동)

설계·규칙의 원본: `study/README.md`. 여기는 **실행 순서**만 적는다. 한 영상 = 한 회차.

## 0. 발동 확인
- 링크가 유튜브인지, 영상 하나인지(플레이리스트면 어느 것부터인지 CR에게 묻지 말고 첫 영상부터) 확인.
- 이미 수집된 영상이면 `study/catalog.json`에서 note/report를 보고 "이미 공부함"을 알린다.

## 1. 수집
```
python study/tools/fetch.py "<URL>"
```
- 출력의 자막 종류(수동/자동)와 글자 수를 확인. **자막 없음**이면 Whisper가 필요하다고 CR에게 보고하고 멈춘다(오디오 크기 명시).
- 자동자막은 오탈자가 있다 — 성경 구절 번호·고유명사는 본문으로 교차 확인한다.
- 영상 설명란의 저작권 문구를 읽고 보고서 영상 카드에 반영한다.

## 2. 소화 (Peter가 직접 — 심부름꾼에게 맡기지 않는다)
- `study/sources/<id>/transcript.<lang>.txt` **전체**를 읽는다. 부분만 읽고 요약하지 않는다.
- 설교 본문 구절을 `python bible/lookup.py "<구절>" --texts KRV,SBLGNT`(구약은 WLCa)로 뽑는다.
- 설교자의 **사실 주장**(역사·배경·원어·인용)을 목록으로 뽑아 자료로 확인 → 등급(A/B/C/D, 정정, 해석). 간단하면 WebSearch 1~3회,
  유물·문헌·이미지를 실제로 확보해야 하면 **퀘스트 모드**(`.claude/skills/godisalive-quest/SKILL.md`)로 넘긴다.
- 기존 노트와의 연결점을 찾는다: `python study/tools/graph.py --no-desktop`으로 현재 점들을 보고, 같은 구절·인물·주제가 있으면 [[링크]].

## 3. 산출 (순서대로)
1. `knowledge/lectures/YYYY-MM-DD-<슬러그>.md` — frontmatter 필수: id(kn-lectures-…), title, type: lecture, source, video_id, speaker, channel, lang, duration, delivered, verses, evidence, sources, report, date, tags. 본문: 한눈에 / 흐름(타임스탬프 표) / 핵심 메시지 / 원어 / ⚖ 검증 / 🧠 연결 / 다음.
2. 새 개념마다 노드 노트 — `knowledge/words/` `themes/` `people/` `places/` `books/` (한 노트 = 한 주제, 출처 필수, 설교 노트로 [[역링크]]).
3. 역사 주장이 있으면 `evidence/<축>/ev-…md` (evidence/README.md 템플릿·등급제).
4. `reports/YYYY-MM-DD-공부-<주제>.html` — 구성은 study/README.md §보고서 표준 구성. 기존 보고서의 CSS를 재사용. 외부 의존성 없음, 큰 활자, 쉬운 한국어. 타임스탬프는 `https://youtu.be/<id>?t=<초>` 링크.
5. `study/catalog.json`의 해당 영상에 note·report 경로, status: "공부완료" 기입.

## 4. 그래프와 보관
```
python study/tools/selftest.py            # 도구를 고쳤다면
python study/tools/graph.py --open        # 지도 재생성 + 바탕화면 복사 + 열기. 끊어진 링크 목록 확인
```
- 보고서를 바탕화면 `C:\Users\droli\Desktop\GODISALIVE\`에 복사하고 `Start-Process`로 브라우저에 띄운다.
- Railway Volume 업로드 (filebrowser API, 자격증명 `.omc/secrets/railway.md`): 보고서 → `/srv/reports/`, 자막 원문 → `/srv/study/<id>/`.
- 끊어진 링크 중 이번에 만들지 않은 것은 NEXT.md '대기 중'에 올린다.

## 5. 종료
- NEXT.md 갱신(공부 모드 섹션에 회차 기록) → `git add` (transcript는 gitignore로 자동 제외) → 커밋 → push.
- CR에게 보고: 영상 한 줄, 한눈에 요약, 검증 노트에서 C가 나온 것, 새로 생긴 점·선 수, 파일 경로.

## 금지
- 설교 전문을 보고서나 노트에 옮기지 않는다 (인용은 짧게, 저작권).
- 설교자의 신앙 메시지를 '검증'하지 않는다 — 사실 주장만 등급을 단다.
- 출처 없는 문장, 등급 없는 역사 주장은 쓰지 않는다. 과장은 복음의 적.
