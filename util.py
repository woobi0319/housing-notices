"""공통 도우미: 날짜·지역 정리, 공고 레코드 만들기."""
import hashlib
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

REGIONS = [
    ("서울", "서울"), ("경기", "경기"), ("인천", "인천"), ("부산", "부산"), ("대구", "대구"),
    ("대전", "대전"), ("울산", "울산"), ("세종", "세종"), ("강원", "강원"), ("충북", "충북"),
    ("충청북", "충북"), ("충남", "충남"), ("충청남", "충남"), ("전북", "전북"), ("전라북", "전북"),
    ("전남", "전남·광주"), ("전라남", "전남·광주"), ("광주", "전남·광주"), ("경북", "경북"),
    ("경상북", "경북"), ("경남", "경남"), ("경상남", "경남"), ("제주", "제주"), ("전국", "전국"),
]


def today_kst() -> date:
    return datetime.now(KST).date()


def norm_date(value) -> str:
    """'2026.11.20', '20261120', '2026-11-20 10:00' 같은 값을 '2026-11-20'으로."""
    if not value:
        return ""
    s = str(value).strip()
    m = re.search(r"(20\d{2})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})", s)
    if not m:
        return ""
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


def date_range(text: str):
    """'2026.11.30 ~ 2026.12.02' 에서 (시작, 끝)을 꺼낸다."""
    found = re.findall(r"20\d{2}[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}", text or "")
    ds = [norm_date(x) for x in found]
    ds = [d for d in ds if d]
    if not ds:
        return "", ""
    return ds[0], ds[-1]


def norm_region(*texts) -> str:
    for t in texts:
        t = (t or "").strip()
        if not t:
            continue
        for key, short in REGIONS:
            if t.startswith(key) or key in t[:6]:
                return short
    return "기타"


def pick(row: dict, *keys, default=""):
    """API마다 필드명이 조금씩 달라서, 있는 것 중 첫 번째 값을 쓴다."""
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v not in (None, "", "null"):
            return v
    return default


def make_notice(*, source, cat, type_, title, region, posted="", start="", end="",
                announce="", link="", key="") -> dict:
    title = re.sub(r"\s+", " ", (title or "")).strip()
    uid = hashlib.sha1(f"{source}|{key or title}|{posted}".encode()).hexdigest()[:16]
    return {
        "id": uid,
        "source": source,
        "cat": cat,          # sale | pub | pri | rem | news
        "type": type_ or "",
        "title": title,
        "region": region or "기타",
        "posted": norm_date(posted),
        "start": norm_date(start),
        "end": norm_date(end),
        "announce": norm_date(announce),
        "link": link or "",
    }
