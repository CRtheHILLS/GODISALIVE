#!/usr/bin/env python3
"""우회 사다리 — 막힘 유형별로 합법적 대체 경로를 순서대로, 실행 가능한 명령으로 안내한다 (설계서 §7).
"우회"는 다른 보관처·아카이브 사본·공개 API·오픈액세스 판본·기관 요청을 뜻한다. 금지선은 항상 끝에 붙는다."""

BLOCKAGES = ["no-results", "403", "404", "empty-js", "paywall", "login", "captcha", "rate-limit"]

Q = "python quest/q.py"


def _dom(d):
    d = (d or "").lower().strip()
    return d[4:] if d.startswith("www.") else d


def ladder(blockage: str, *, domain: str | None = None, query: str | None = None, pb: dict | None = None) -> list:
    if blockage not in BLOCKAGES:
        raise ValueError(f"알 수 없는 막힘 유형: {blockage!r} (가능: {', '.join(BLOCKAGES)})")
    dom = _dom(domain) or "<domain>"
    q = query or "<query>"
    url = f"https://{dom}/" if domain else "<url>"
    wb = f"https://web.archive.org/web/2/{url}"

    S = {
        "variant": ("질의 변형 (언어·등록번호·학술명)", "영어·독어·불어·히브리어 명칭, 학술 명칭, 박물관 등록번호, 발굴자 이름으로 바꾸면 걸리는 경우가 많다.",
                    f'{Q} search "{q} inventory number" --engines wikidata,commons'),
        "alt": ("다른 보관처 (커먼즈·위키데이터·인터넷아카이브)", "박물관 소장품은 커먼즈·위키데이터에 사진과 등록번호로 따로 올라 있는 경우가 많다.",
                f'{Q} search "{q}" --engines commons,wikidata,ia'),
        "api": ("구조화 API로 갈아타기", "박물관·도서관 API와 학술 메타데이터는 HTML 페이지보다 막히지 않는다.",
                f'{Q} search "{q}" --engines met,louvre,loc,openalex'),
        "iiif": ("구조화 API: IIIF 매니페스트 추측", "기관 이미지는 대개 /iiif/…/manifest 로 공개되어 있다 (경로는 사이트마다 다름 — 열어 보고 확인).",
                 f"{Q} read https://{dom}/iiif/manifest.json"),
        "wayback": ("웨이백 아카이브 사본", "공개 아카이브에 저장된 사본을 읽는다 — 원 서버를 건드리지 않는다.",
                    f"{Q} read {wb}"),
        "retry": ("지연 후 재시도 1회", "차단·속도제한은 30~60초 쉰 뒤 한 번만 다시 시도한다. 반복 두드리지 않는다.",
                  f"{Q} read {url}"),
        "js": ("JS 렌더링으로 읽기 (read --js)", "본문이 스크립트로 그려지는 페이지는 브라우저 렌더링이 필요하다 (Playwright 설치 시).",
               f"{Q} read {url} --js"),
        "human": ("사람 경로", "이미지 요청 양식, 상호대차, 저자 연락 — Peter가 요청문 초안을 쓰고 '사람 액션 대기'로 기록한다.",
                  f'{Q} todo "사람 액션 대기: {dom if domain else q} — 이미지 요청 양식 / 상호대차 / 저자 연락 초안"'),
        "oa": ("오픈액세스 판본 찾기 (OpenAlex·Semantic Scholar)", "합법적으로 공개된 OA 판본·프리프린트가 있는지 먼저 본다.",
               f'{Q} search "{q}" --engines openalex,semanticscholar'),
        "book": ("인터넷아카이브 (책·대출 가능 판본)", "공개 도서관 사본·대출 가능한 판본을 확인한다.",
                 f'{Q} search "{q}" --engines ia'),
        "repo": ("저자·기관 리포지토리", "저자 홈페이지나 대학 리포지토리에 합법적으로 올린 사본이 있다.",
                 f'{Q} search "{q} pdf author repository" --engines ddg'),
        "newurl": ("위키데이터로 새 URL 찾기", "옮겨진 페이지는 위키데이터·커먼즈에 새 주소가 기록되어 있는 경우가 있다.",
                   f'{Q} search "{q}" --engines wikidata,commons'),
    }
    order = {
        "no-results": ["variant", "alt", "api", "human"],
        "403": ["retry", "wayback", "alt", "js", "human"],
        "rate-limit": ["retry", "wayback", "alt", "js", "human"],
        "404": ["wayback", "newurl", "alt"],
        "empty-js": ["js", "wayback", "iiif", "alt"],
        "paywall": ["oa", "book", "repo", "human"],
        "login": ["alt", "human"],
        "captcha": ["alt", "human"],
    }[blockage]

    status = ((pb or {}).get("domains", {}).get(_dom(domain)) or {}).get("status") if domain else None
    if status == "js-required" and blockage not in ("login", "captcha", "paywall", "no-results"):
        order = ["js"] + [k for k in order if k != "js"]

    out = []
    for i, key in enumerate(order, 1):
        title, why, cmd = S[key]
        out.append({"step": i, "title": title, "why": why, "command": cmd})
    return out


def forbidden_text() -> str:
    return ("⛔ 금지선 (설계서 §3 반목표): 유료 장벽 우회(Sci-Hub 류 해적 사이트), 로그인·크리덴셜 공유, CAPTCHA 자동 해제, DRM 제거, "
            "robots.txt·이용약관을 어기는 대량 수집은 어떤 경우에도 하지 않는다. 라이선스를 확인하지 못한 이미지는 책에 쓰지 않는다. "
            "여기서 '우회'란 다른 보관처, 아카이브 사본, 공개 API, 오픈액세스 판본, 기관 요청 양식 같은 합법적 대체 경로만 뜻한다.")
