---
name: godisalive-export
description: GODISALIVE 프로젝트 산출물을 Word(.docx), PDF, Markdown, TXT로 바탕화면 GODISALIVE 폴더에 출력한다. 사용자가 "출력해줘", "워드로 뽑아줘", "PDF로 저장", "보고서로 만들어줘"라고 요청하거나 연구 결과·봉독 자료·책 원고를 파일로 내보낼 때 사용.
---

# GODISALIVE 문서 출력 스킬

## 출력 위치 (고정)

```
C:\Users\droli\Desktop\GODISALIVE\
```

파일명 규칙: `{YYYY-MM-DD}_{제목-슬러그}.{ext}` — 예: `2026-08-22_텔단석비-연구노트.docx`
같은 산출물의 중간본은 저장소 `outputs/`에 두고, **완성본만 바탕화면에** 낸다.

## 형식별 절차

| 형식 | 방법 |
|---|---|
| **Markdown** | Write 도구로 직접 작성 → 바탕화면 경로에 저장 |
| **TXT** | Write 도구로 직접 작성 (UTF-8, BOM 없이) |
| **Word (.docx)** | 내장 `docx` 스킬 호출 → 생성 후 바탕화면으로 복사. 한글 글꼴: 본문 **맑은 고딕**, 제목 굵게. 표지(제목·날짜·GODISALIVE)와 목차 포함 (3쪽 이상 문서) |
| **PDF** | 내장 `pdf` 스킬 호출. **한글 폰트 임베드 필수** (맑은 고딕 `C:\Windows\Fonts\malgun.ttf`) — 임베드 없으면 한글이 깨진다 |

## 문서 공통 규격

1. 머리: 제목 / 날짜 / "GODISALIVE — 하나님은 살아계신다"
2. 본문: 성경 인용 시 번역본 명시 (개역한글/사역/NIV 등), 저작권 번역은 인용 범위 내
3. 증거 서술에는 등급(A/B/C) 표기 — evidence/README.md 등급제 준수
4. 꼬리: 출처 목록 (유물명·소장처·문헌·URL) — **출처 없는 문서는 내보내지 않는다**
5. 책 원고 출력 시: book/README.md의 원고 규율 적용

## 출력 후

- 산출물 사본(md 원본)을 저장소 `outputs/`에 남긴다 (재현 가능성).
- 바탕화면 파일 경로를 사용자에게 보고한다.
