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

## 확보 현황 (2026-08-22 — 1차 확보 완료)

| 파일 | 본문 | 비고 |
|---|---|---|
| `korean/KRV.json.gz` | **개역한글(1961)** 전 66권 31,103절 | bolls.life, 퍼블릭 도메인 ✅ |
| `hebrew/WLCa.json.gz` | **WLC 히브리어 구약** 39권 23,213절 | 모음·악센트·스트롱 번호 포함 ✅ |
| `greek/sblgnt/*.txt` | **SBLGNT 신약** 27권 | LogosBible 공식 배포본, 라이선스 동봉 ✅ |
| `greek/LXX.json.gz` | 칠십인역 (외경 포함 52권) | ⚠ bolls판은 lemma(원형) 처리 본문 — 검색용. 굴절형 본문은 추후 CCAT/Swete로 교체 |
| `english/KJV.json.gz` | KJV + 스트롱 번호 (외경 포함) | 퍼블릭 도메인 ✅ |
| `english/WEB.json.gz` | World English Bible | 퍼블릭 도메인 ✅ |

**구절 조회**: `python bible/lookup.py "요 21:15-17"` — 옵션: `--texts all` (전 본문), `--texts KRV,WLCa`, `--raw`(스트롱 태그 유지). 검증 완료: 창 1:1 · 요 3:16 · 요 21:15 · 벧후 1:16.

bolls.life에 추가로 있는 것 (필요 시 열람/API — 저작권 주의): 새번역(RNKSV), 알레포 사본(HAC),
Delitzsch 히브리어 신약(DHNT), Tischendorf(TISCH), Textus Receptus(TR).

## 남은 확보 과제

- [ ] ESV API 키 (api.esv.org — CR 등록) · api.bible 키 (scripture.api.bible — NIV 접근)
- [ ] NET Bible 확보 (netbible.org — 역주 60,000개)
- [ ] LXX 굴절형 본문 교체 (저순위)
- [ ] morphhb 형태소 분석 XML (Phase 4 단어 연구 시작 시)
