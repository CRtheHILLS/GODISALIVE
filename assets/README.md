# assets/ — 시각 자료 (사진 · 도판 · 지도)

책 출간과 지식베이스를 뒷받침하는 시각 자료 관리.
**바이너리 원본은 Railway Volume에, 메타데이터(catalog.json)는 이 저장소에.** repo가 진실의 원천이다.

## 구조

```
assets/
├── catalog.json    # 전 자산 색인 (아래 스키마) — git 관리
├── cache/          # 로컬 작업 캐시 (.gitignore — 대용량 git 금지)
└── maps/           # 직접 제작한 지도/도해 (경량, git 관리 가능)
```

## catalog.json 스키마

```json
{
  "assets": [
    {
      "id": "img-0001",
      "title": "텔단 석비",
      "source": "Wikimedia Commons",
      "source_url": "https://commons.wikimedia.org/...",
      "license": "CC BY-SA 4.0",
      "commercial_ok": true,
      "credit": "촬영자/기관 표기 문자열",
      "railway_path": "/srv/archaeology/tel-dan-stele/main.jpg",
      "evidence_id": "ev-arch-tel-dan-stele",
      "verses": ["삼하 7장"],
      "added": "2026-08-22"
    }
  ]
}
```

**`commercial_ok` 필드가 책 출간의 생명선이다** — NC(비상업) 라이선스는 false로 표기하고 책에는 쓰지 않는다.

## Railway Volume — 가동 중 (2026-08-22 프로비저닝 완료)

- **웹 UI**: https://assets-production-f04b.up.railway.app (filebrowser — 로그인 정보는 `.omc/secrets/railway.md`, git 제외)
- 구성: Railway 프로젝트 내 `assets` 서비스 (도커 이미지 `filebrowser/filebrowser`) + Volume 마운트 **`/srv`**
- 폴더 구조: `/srv/{archaeology|manuscripts|sites|maps|book}/<slug>/` (5개 폴더 생성 완료)
- 필수 환경변수: `FB_DATABASE=/srv/filebrowser.db`, `RAILWAY_RUN_UID=0` (볼륨 권한 — 제거하면 crash loop)
- API 자동화: `POST /api/login` → JWT → `X-Auth` 헤더로 업로드/조회 (Peter가 스크립트로 처리 가능)
- 업로드 절차: 라이선스 확인 → catalog.json 등록 → 업로드 → evidence 노트에 image id 링크
- **백업**: 분기 1회 전체 스냅샷을 로컬 외장으로 (Railway 볼륨은 자동 백업 아님). 10GB 초과 시 Cloudflare R2 병행 검토.

## 수집 우선순위

1. A등급 유물 20점의 PD/CC0 이미지 (Wikimedia → Met CC0 → LOC Matson 순으로 탐색)
2. 성지 항공/위성 이미지 (NASA PD)
3. 20세기 초 성지 사진 (LOC Matson Collection — 책의 분위기 재료)
4. 직접 제작 지도 (전도여행 경로, 왕조 연대표 인포그래픽)
