# knowledge/ — 지식 노트 (10년 축적의 본체)

봉독 · 연구 · 대화에서 얻은 모든 지식을 주제별 노트로 축적한다.
**이 폴더의 md 파일들이 Phase 5 성경 LLM의 학습/RAG 코퍼스가 된다** — 그래서 포맷 규율이 중요하다.

## 디렉터리

```
books/     성경 66권 권별 프로파일 (배경 · 연대 · 실존근거 · 원문 특이점)
people/    인물 — 특히 성경 외 사료로 확인된 인물 (구약만 50+명)
places/    지리 — Pleiades ID 연동
timeline/  연대기 — 이스라엘·유다 왕조 ↔ 앗수르·바벨론·이집트 대조
themes/    주제 — 예언과 성취, 언약, 성전, 절기, 부활
words/     원어 단어 연구 (히브리어 · 그리스어)
readings/  봉독 세션 기록 (본문 + 묵상 + 발견)
lectures/  설교·강의 소화 노트 — 공부 모드(study/README.md). id: kn-lectures-<날짜>-<슬러그>, speaker 필드 필수
graph/     [파생물] 지식 그래프 — graph.json(기계용) · map.html(지도). study/tools/graph.py가 재생성, 손으로 고치지 않음
```

## 노트 표준 frontmatter (필수)

```markdown
---
id: kn-people-hezekiah        # kn-<폴더>-<슬러그>
title: 히스기야
verses: [왕하 18-20, 대하 29-32, 사 36-39]
evidence: [ev-arch-hezekiah-bulla, ev-arch-siloam-inscription, ev-arch-taylor-prism]
sources: [출처 URL/문헌]
date: 2026-08-22
tags: [유다왕, 앗수르, 종교개혁]
---
본문...
관련 노트는 [[kn-people-isaiah]] 처럼 위키링크로 연결한다.
```

## 규칙

1. **한 노트 = 한 주제.** 파일이 길어지면 분리한다.
2. **출처 없는 문장은 쓰지 않는다.** 증거 인용은 `evidence/` 노트 id로 링크.
3. **위키링크(`[[id]]`)로 촘촘히 연결한다** — Phase 5 지식 그래프의 원료. `python study/tools/graph.py`가 지도를 그리고
   끊어진 링크(아직 없는 노트)를 알려준다 — 끊어진 링크는 오류가 아니라 **다음에 만들 노트 목록**이다.
4. 봉독 기록(`readings/`)은 날짜-본문 형식: `2026-08-29-john-21.md`.
5. 번역 인용 시 어느 번역인지 명시 (개역한글/사역/NIV...).
6. **새 개념은 노트로 만들어 점이 되게 한다.** 설교·봉독 노트 안에만 적힌 인물·단어·주제는 그래프에 선을 만들지 못한다.
   `verses:` 는 장 단위로 자동 연결되므로 (예: `약 2:1-13` → "약 2") 인용 구절을 빠짐없이 적는다.
