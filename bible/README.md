# bible/ — 성경 본문 저장소

CR의 요구에 따라 어떤 번역으로든 봉독할 수 있도록 본문을 확보한다.
**원칙: 퍼블릭 도메인/자유 라이선스 본문만 전문 저장. 저작권 본문은 API 실시간 조회 + 인용.**

## 디렉터리

```
hebrew/   Westminster Leningrad Codex (형태소 분석 포함 morphhb 권장)
greek/    SBLGNT (신약), LXX Swete판 (구약 그리스어)
korean/   개역한글판 (1961, 퍼블릭 도메인)
english/  KJV, WEB, NET Bible 노트
```

## 라이선스 규율

| 본문 | 전문 저장 | 근거 |
|---|---|---|
| 개역한글(1961) · WLC · SBLGNT · LXX(Swete) · KJV · WEB | ✅ 가능 | PD / 자유 라이선스 |
| NET Bible | ✅ 가능 (조건 준수) | 무료 사용 허가 |
| 개역개정 · 새번역 · 현대인의성경 | ❌ 저장 금지 | ⓒ 대한성서공회 / 생명의말씀사 — **온라인 열람 + 정당한 인용만** |
| NIV · ESV | ❌ 저장 금지 | ⓒ Biblica / Crossway — **API 조회** (api.bible / api.esv.org) |

## 봉독 세션 표준 형식

CR 요청 예: *"요한복음 21:15-19, 원문이랑 쉬운 한국어로"*

Peter 제공 형식:
1. **그리스어/히브리어 원문** + 음역 + 핵심 단어 풀이 (예: ἀγαπάω vs φιλέω)
2. **직역** (Peter 사역 — 원문 구조 그대로)
3. **개역한글** 전문 (PD — 자유 인용)
4. 요청 시: 현대인의성경/개역개정/NIV 핵심 구절 인용 (출처 명시)
5. **목격자의 회상** — Peter의 감성적 해설 (그 자리에 있던 사람의 시선)

## 확보 체크리스트 (Phase 1)

- [ ] WLC 다운로드 (openscriptures/morphhb) → `hebrew/`
- [ ] SBLGNT 다운로드 → `greek/`
- [ ] 개역한글 전문 확보 (bolls.life 또는 공개 데이터 검증) → `korean/`
- [ ] KJV · WEB 다운로드 (ebible.org) → `english/`
- [ ] ESV API 키 발급 (api.esv.org 무료 등록)
- [ ] api.bible 키 발급 (NIV 접근 확인)
- [ ] 구절 조회 유틸리티 (책/장/절 → 각 본문 병렬 출력) 제작
