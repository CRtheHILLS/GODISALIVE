#!/usr/bin/env python3
"""GODISALIVE 구절 조회 유틸리티 — 확보한 본문들을 병렬로 출력한다.

사용:
    python bible/lookup.py "요 21:15-17"
    python bible/lookup.py "창세기 1:1" --texts KRV,WLCa,LXX,KJV,WEB
    python bible/lookup.py "John 3:16" --texts all
    python bible/lookup.py "시 23"            # 장 전체
    python bible/lookup.py "창 1:1" --raw     # 스트롱 번호 태그 유지

본문: KRV(개역한글) · WLCa(히브리어 WLC+스트롱) · SBLGNT(그리스어 신약) ·
      LXX(칠십인역) · KJV · WEB   — 전부 퍼블릭 도메인/자유 라이선스.
      ESV — Crossway API 실시간 조회 (키: .omc/secrets/esv-api-key.txt).
      ⚖ ESV 약관 준수: 쿼리당 500절 이하, 로컬 저장·캐시 안 함, "(ESV)" 표기 유지.
"""
import argparse, gzip, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent

# (bolls id, 한글, 한글약어, 영어, 영어약어들, SBLGNT 파일명)
BOOKS = [
    (1,"창세기","창","Genesis",["Gen"],None),(2,"출애굽기","출","Exodus",["Exod","Ex"],None),
    (3,"레위기","레","Leviticus",["Lev"],None),(4,"민수기","민","Numbers",["Num"],None),
    (5,"신명기","신","Deuteronomy",["Deut"],None),(6,"여호수아","수","Joshua",["Josh"],None),
    (7,"사사기","삿","Judges",["Judg"],None),(8,"룻기","룻","Ruth",["Ruth"],None),
    (9,"사무엘상","삼상","1 Samuel",["1Sam"],None),(10,"사무엘하","삼하","2 Samuel",["2Sam"],None),
    (11,"열왕기상","왕상","1 Kings",["1Kgs"],None),(12,"열왕기하","왕하","2 Kings",["2Kgs"],None),
    (13,"역대상","대상","1 Chronicles",["1Chr"],None),(14,"역대하","대하","2 Chronicles",["2Chr"],None),
    (15,"에스라","스","Ezra",["Ezra"],None),(16,"느헤미야","느","Nehemiah",["Neh"],None),
    (17,"에스더","에","Esther",["Esth"],None),(18,"욥기","욥","Job",["Job"],None),
    (19,"시편","시","Psalms",["Ps","Pss","Psalm"],None),(20,"잠언","잠","Proverbs",["Prov"],None),
    (21,"전도서","전","Ecclesiastes",["Eccl"],None),(22,"아가","아","Song of Songs",["Song"],None),
    (23,"이사야","사","Isaiah",["Isa"],None),(24,"예레미야","렘","Jeremiah",["Jer"],None),
    (25,"예레미야애가","애","Lamentations",["Lam"],None),(26,"에스겔","겔","Ezekiel",["Ezek"],None),
    (27,"다니엘","단","Daniel",["Dan"],None),(28,"호세아","호","Hosea",["Hos"],None),
    (29,"요엘","욜","Joel",["Joel"],None),(30,"아모스","암","Amos",["Amos"],None),
    (31,"오바댜","옵","Obadiah",["Obad"],None),(32,"요나","욘","Jonah",["Jonah"],None),
    (33,"미가","미","Micah",["Mic"],None),(34,"나훔","나","Nahum",["Nah"],None),
    (35,"하박국","합","Habakkuk",["Hab"],None),(36,"스바냐","습","Zephaniah",["Zeph"],None),
    (37,"학개","학","Haggai",["Hag"],None),(38,"스가랴","슥","Zechariah",["Zech"],None),
    (39,"말라기","말","Malachi",["Mal"],None),
    (40,"마태복음","마","Matthew",["Matt","Mt"],"Matt"),(41,"마가복음","막","Mark",["Mark","Mk"],"Mark"),
    (42,"누가복음","눅","Luke",["Luke","Lk"],"Luke"),(43,"요한복음","요","John",["John","Jn"],"John"),
    (44,"사도행전","행","Acts",["Acts"],"Acts"),(45,"로마서","롬","Romans",["Rom"],"Rom"),
    (46,"고린도전서","고전","1 Corinthians",["1Cor"],"1Cor"),(47,"고린도후서","고후","2 Corinthians",["2Cor"],"2Cor"),
    (48,"갈라디아서","갈","Galatians",["Gal"],"Gal"),(49,"에베소서","엡","Ephesians",["Eph"],"Eph"),
    (50,"빌립보서","빌","Philippians",["Phil"],"Phil"),(51,"골로새서","골","Colossians",["Col"],"Col"),
    (52,"데살로니가전서","살전","1 Thessalonians",["1Thess"],"1Thess"),
    (53,"데살로니가후서","살후","2 Thessalonians",["2Thess"],"2Thess"),
    (54,"디모데전서","딤전","1 Timothy",["1Tim"],"1Tim"),(55,"디모데후서","딤후","2 Timothy",["2Tim"],"2Tim"),
    (56,"디도서","딛","Titus",["Titus"],"Titus"),(57,"빌레몬서","몬","Philemon",["Phlm"],"Phlm"),
    (58,"히브리서","히","Hebrews",["Heb"],"Heb"),(59,"야고보서","약","James",["Jas"],"Jas"),
    (60,"베드로전서","벧전","1 Peter",["1Pet"],"1Pet"),(61,"베드로후서","벧후","2 Peter",["2Pet"],"2Pet"),
    (62,"요한일서","요일","1 John",["1John"],"1John"),(63,"요한이서","요이","2 John",["2John"],"2John"),
    (64,"요한삼서","요삼","3 John",["3John"],"3John"),(65,"유다서","유","Jude",["Jude"],"Jude"),
    (66,"요한계시록","계","Revelation",["Rev"],"Rev"),
]

NAME2ID = {}
for bid, kf, ka, ef, eabbrs, _ in BOOKS:
    for n in [kf, ka, ef, ef.replace(" ", "")] + eabbrs:
        NAME2ID[n.lower()] = bid

TEXT_FILES = {  # code -> (경로, 언어 라벨)
    "KRV":  ("korean/KRV.json.gz",  "개역한글 (1961)"),
    "WLCa": ("hebrew/WLCa.json.gz", "히브리어 — Westminster Leningrad Codex"),
    "LXX":  ("greek/LXX.json.gz",   "그리스어 구약 — 칠십인역"),
    "KJV":  ("english/KJV.json.gz", "King James Version"),
    "WEB":  ("english/WEB.json.gz", "World English Bible"),
}
OT_ONLY, NT_ONLY = {"WLCa", "LXX"}, {"SBLGNT"}
DEFAULT_ORDER = ["KRV", "WLCa", "SBLGNT", "KJV", "WEB"]
ALL_ORDER = ["KRV", "WLCa", "SBLGNT", "LXX", "KJV", "WEB", "ESV"]

USFM = ["GEN","EXO","LEV","NUM","DEU","JOS","JDG","RUT","1SA","2SA","1KI","2KI","1CH","2CH",
        "EZR","NEH","EST","JOB","PSA","PRO","ECC","SNG","ISA","JER","LAM","EZK","DAN","HOS",
        "JOL","AMO","OBA","JON","MIC","NAM","HAB","ZEP","HAG","ZEC","MAL","MAT","MRK","LUK",
        "JHN","ACT","ROM","1CO","2CO","GAL","EPH","PHP","COL","1TH","2TH","1TI","2TI","TIT",
        "PHM","HEB","JAS","1PE","2PE","1JN","2JN","3JN","JUD","REV"]

def apibible_registry():
    p = ROOT / "apibible-ids.json"
    if not p.exists():
        return {}
    reg = json.loads(p.read_text(encoding="utf-8"))
    reg.pop("_comment", None)
    return reg

def fetch_apibible(entry, bid, ch, v1, v2):
    """api.bible 실시간 조회 (Starter: 월 5,000회 — 봉독용으로만, 대량 조회 금지). 저장·캐시 안 함."""
    key_path = ROOT.parent / ".omc" / "secrets" / "apibible-key.txt"
    if not key_path.exists():
        return None, "API 키 없음 (.omc/secrets/apibible-key.txt)"
    code = USFM[bid - 1]
    pid = f"{code}.{ch}" + (f".{v1}-{code}.{ch}.{v2}" if v1 and v2 and v2 != v1 else (f".{v1}" if v1 else ""))
    params = urllib.parse.urlencode({"content-type": "text", "include-verse-numbers": "true",
                                     "include-titles": "false", "include-notes": "false"})
    req = urllib.request.Request(
        f"https://rest.api.bible/v1/bibles/{entry['id']}/passages/{pid}?{params}",
        headers={"api-key": key_path.read_text().strip(), "User-Agent": "GODISALIVE-lookup",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode()).get("data", {})
    except Exception as e:
        return None, f"조회 실패: {e}"
    content = (data.get("content") or "").strip()
    cp = (data.get("copyright") or "").strip()
    return (content + (f"\n© {cp}" if cp else ""), None) if content else (None, "해당 구절 없음")

def fetch_esv(bid, ch, v1, v2):
    """Crossway ESV API 실시간 조회. 저장·캐시하지 않는다 (약관)."""
    key_path = ROOT.parent / ".omc" / "secrets" / "esv-api-key.txt"
    if not key_path.exists():
        return None, "API 키 없음 (.omc/secrets/esv-api-key.txt)"
    if v1 and v2 and (v2 - v1 + 1) > 500:
        return None, "ESV 약관: 쿼리당 500절 초과 불가"
    eng = next(b[3] for b in BOOKS if b[0] == bid)
    q = f"{eng} {ch}" + (f":{v1}" + (f"-{v2}" if v2 and v2 != v1 else "") if v1 else "")
    params = urllib.parse.urlencode({
        "q": q, "include-passage-references": "false", "include-headings": "false",
        "include-footnotes": "false", "include-verse-numbers": "true",
        "include-short-copyright": "true",
    })
    req = urllib.request.Request(
        f"https://api.esv.org/v3/passage/text/?{params}",
        headers={"Authorization": f"Token {key_path.read_text().strip()}",
                 "User-Agent": "GODISALIVE-lookup (personal study)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return None, f"조회 실패: {e}"
    passages = data.get("passages") or []
    return ("\n".join(p.strip() for p in passages), None) if passages else (None, "해당 구절 없음")

STRONG_RE = re.compile(r"<S>\d+</S>")   # 스트롱 번호(내용 포함) 제거
TAG_RE = re.compile(r"<[^>]*>")          # 기타 마크업 태그 제거
WS_RE = re.compile(r"\s{2,}")

def parse_ref(ref: str):
    ref = ref.strip()
    m = re.match(r"^(.+?)\s*(\d+)(?::(\d+)(?:\s*[-~]\s*(\d+))?)?$", ref)
    if not m:
        sys.exit(f"참조 형식을 이해하지 못함: {ref!r}  (예: '요 21:15-17', '시 23')")
    name, ch, v1, v2 = m.group(1).strip(), int(m.group(2)), m.group(3), m.group(4)
    bid = NAME2ID.get(name.lower().rstrip("."))
    if not bid:
        sys.exit(f"책 이름을 찾지 못함: {name!r}")
    return bid, ch, (int(v1) if v1 else None), (int(v2) if v2 else (int(v1) if v1 else None))

def load_bolls(code):
    path = ROOT / TEXT_FILES[code][0]
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    idx = {}
    for v in data:
        idx[(v["book"], v["chapter"], v["verse"])] = v["text"]
    return idx

def load_sblgnt(bid):
    fname = next(b[5] for b in BOOKS if b[0] == bid)
    if not fname:
        return None
    path = ROOT / "greek" / "sblgnt" / f"{fname}.txt"
    idx = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^\S+\s+(\d+):(\d+)\t(.*)$", line)
        if m:
            idx[(bid, int(m.group(1)), int(m.group(2)))] = m.group(3).strip()
    return idx

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", help="예: '요 21:15-17', '창세기 1:1', 'John 3:16', '시 23'")
    ap.add_argument("--texts", default=None, help="쉼표 구분 (KRV,WLCa,SBLGNT,LXX,KJV,WEB) 또는 'all'")
    ap.add_argument("--raw", action="store_true", help="스트롱 번호 등 태그 유지")
    args = ap.parse_args()

    bid, ch, v1, v2 = parse_ref(args.ref)
    is_nt = bid >= 40
    if args.texts:
        codes = ALL_ORDER if args.texts.lower() == "all" else [c.strip() for c in args.texts.split(",")]
    else:
        codes = DEFAULT_ORDER
    codes = [c for c in codes if not (is_nt and c in OT_ONLY) and not (not is_nt and c in NT_ONLY)]

    kf = next(b[1] for b in BOOKS if b[0] == bid)
    span = f"{ch}" + (f":{v1}" + (f"-{v2}" if v2 and v2 != v1 else "") if v1 else "")
    print(f"\n📖 {kf} {span}\n" + "=" * 60)

    apireg = apibible_registry()
    for code in codes:
        if code == "ESV":
            text, err = fetch_esv(bid, ch, v1, v2)
            print(f"\n── ESV · English Standard Version (Crossway API 실시간) " + "─" * 8)
            print(text if text else f"(불가 — {err})")
            continue
        if code in apireg:
            entry = apireg[code]
            text, err = fetch_apibible(entry, bid, ch, v1, v2)
            print(f"\n── {code} · {entry['name']} (api.bible 실시간) " + "─" * 8)
            print(text if text else f"(불가 — {err})")
            continue
        idx = load_sblgnt(bid) if code == "SBLGNT" else load_bolls(code)
        if idx is None:
            print(f"\n[{code}] 본문 파일 없음 — 건너뜀"); continue
        label = "그리스어 신약 — SBL Greek New Testament" if code == "SBLGNT" else TEXT_FILES[code][1]
        print(f"\n── {code} · {label} " + "─" * max(1, 40 - len(code)))
        verses = range(v1, v2 + 1) if v1 else range(1, 200)
        shown = 0
        for v in verses:
            t = idx.get((bid, ch, v))
            if t is None:
                if v1: print(f"{v}  (없음)")
                continue
            if not args.raw:
                t = WS_RE.sub(" ", TAG_RE.sub("", STRONG_RE.sub("", t)))
            print(f"{v}  {t.strip()}")
            shown += 1
        if shown == 0:
            print("(해당 장 없음)")

if __name__ == "__main__":
    main()
