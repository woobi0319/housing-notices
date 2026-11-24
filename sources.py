"""공고를 가져오는 곳들. 각 함수는 공고 목록(list[dict])을 돌려주고, 실패하면 예외를 낸다."""
import os
import re
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html import unescape

from bs4 import BeautifulSoup

from util import KST, date_range, make_notice, norm_date, norm_region, pick, today_kst

UA = {"User-Agent": "Mozilla/5.0 (housing-notice-collector; personal use)"}
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "45"))

# ---------------------------------------------------------------- 청약홈 (한국부동산원)
ODCLOUD = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/"
APPLYHOME = {
    # 오퍼레이션: (종류, 기본 유형, 원문 목록 링크)
    "getAPTLttotPblancDetail": ("sale", "APT", "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancListView.do"),
    "getUrbtyOfctlLttotPblancDetail": ("pri", "오피스텔·도시형·민간임대", "https://www.applyhome.co.kr/ai/aia/selectUrbtyOfctlLttotPblancListView.do"),
    "getPblPvtRentLttotPblancDetail": ("pri", "공공지원 민간임대", "https://www.applyhome.co.kr/ai/aia/selectPRMOLttotPblancListView.do"),
    "getRemndrLttotPblancDetail": ("rem", "무순위·잔여세대", "https://www.applyhome.co.kr/ai/aia/selectAPTRemndrLttotPblancListView.do"),
    "getOPTLttotPblancDetail": ("rem", "임의공급", "https://www.applyhome.co.kr/ai/aia/selectAPTRemndrLttotPblancListView.do"),
}


def parse_applyhome(op: str, rows: list) -> list:
    cat, default_type, list_url = APPLYHOME[op]
    out = []
    for r in rows:
        title = pick(r, "HOUSE_NM")
        if not title:
            continue
        addr = pick(r, "HSSPLY_ADRES")
        type_ = pick(r, "HOUSE_DTL_SECD_NM", "HOUSE_SECD_NM", "SEARCH_HOUSE_SECD_NM", default=default_type)
        rent = pick(r, "RENT_SECD_NM")
        this_cat = cat
        # APT 목록 안에 섞인 임대주택(공공지원 민간임대 등)은 민간임대로 분류
        if cat == "sale" and rent and "임대" in str(rent):
            this_cat, type_ = "pri", f"{type_} 임대"
        if op == "getPblPvtRentLttotPblancDetail":
            type_ = "공공지원 민간임대"
        out.append(make_notice(
            source="청약홈", cat=this_cat, type_=str(type_), title=title,
            region=norm_region(pick(r, "SUBSCRPT_AREA_CODE_NM"), addr),
            posted=pick(r, "RCRIT_PBLANC_DE"),
            start=pick(r, "RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE", "SPSPLY_RCEPT_BGNDE", "GNRL_RNK1_CRSPAREA_RCPTDE"),
            end=pick(r, "RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE", "GNRL_RNK2_ETC_AREA_ENDDE", "GNRL_RNK1_ETC_AREA_ENDDE"),
            announce=pick(r, "PRZWNER_PRESNATN_DE"),
            link=pick(r, "PBLANC_URL", "HMPG_ADRES", default=list_url),
            key=f"{pick(r, 'HOUSE_MANAGE_NO')}-{pick(r, 'PBLANC_NO')}",
        ))
    return out


def fetch_applyhome(session, op: str) -> list:
    key = os.environ["DATA_GO_KR_KEY"]
    since = (today_kst() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    rows, page = [], 1
    while page <= 20:
        res = session.get(ODCLOUD + op, params={
            "serviceKey": key, "page": page, "perPage": 100,
            "cond[RCRIT_PBLANC_DE::GTE]": since,
        }, timeout=30)
        res.raise_for_status()
        body = res.json()
        data = body.get("data") or []
        rows += data
        if len(rows) >= int(body.get("matchCount") or body.get("totalCount") or 0) or not data:
            break
        page += 1
    return parse_applyhome(op, rows)


# ---------------------------------------------------------------- LH 분양임대공고문
LH_URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
LH_LIST = "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do?mi=1026"
LH_SKIP = ("토지", "상가", "어린이집", "용지")


def _find_rows(obj, must="PAN_NM"):
    """LH 응답은 [{dsSch:..}, {dsList:[...]}] 식이라, PAN_NM 이 든 dict 목록을 찾아낸다."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and any(k.upper() == must for k in obj[0]):
            return obj
        for x in obj:
            got = _find_rows(x, must)
            if got:
                return got
    elif isinstance(obj, dict):
        for v in obj.values():
            got = _find_rows(v, must)
            if got:
                return got
    return []


def parse_lh(payload) -> list:
    out = []
    for r in _find_rows(payload):
        title = pick(r, "PAN_NM")
        upp = str(pick(r, "UPP_AIS_TP_NM"))
        sub = str(pick(r, "AIS_TP_CD_NM"))
        if any(w in upp + sub for w in LH_SKIP):
            continue
        cat = "sale" if ("분양" in upp + sub and "임대" not in sub) else "pub"
        out.append(make_notice(
            source="LH", cat=cat, type_=sub or upp, title=title,
            region=norm_region(pick(r, "CNP_CD_NM"), title),
            posted=pick(r, "PAN_NT_ST_DT", "PAN_DT"),
            end=pick(r, "CLSG_DT"),
            link=pick(r, "DTL_URL", default=LH_LIST),
            key=pick(r, "PAN_ID", default=title),
        ))
    return out


def fetch_lh(session) -> list:
    key = os.environ["DATA_GO_KR_KEY"]
    t = today_kst()
    res = session.get(LH_URL, params={
        "serviceKey": key, "PG_SZ": 300, "PAGE": 1,
        "PAN_NT_ST_DT": (t - timedelta(days=LOOKBACK_DAYS)).strftime("%Y.%m.%d"),
        "CLSG_DT": (t + timedelta(days=365)).strftime("%Y.%m.%d"),
    }, headers=UA, timeout=30)
    res.raise_for_status()
    return parse_lh(res.json())


# ---------------------------------------------------------------- SH (서울주택정보마당 목록)
SH_LISTS = {
    "https://housing.seoul.go.kr/site/main/sh/publicLease/list": "pub",
    "https://housing.seoul.go.kr/site/main/sh/publicSale/list": "sale",
}
RESULT_WORDS = ("당첨자", "발표", "결과", "서류제출", "계약안내", "동호")


def parse_sh(html: str, cat: str, base: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("table tbody tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < 5:
            continue
        a = tr.find("a", href=True)
        # 열: 번호 | 유형 | 공고명 | 공고일 | 마감일 | 상태 | 담당부서 | 바로가기
        title, type_ = tds[2], tds[1]
        if any(w in title for w in RESULT_WORDS):
            continue  # 당첨자 발표 같은 후속 글은 새 공고가 아님
        href = a["href"] if a else base
        if href.startswith("/"):
            href = "https://housing.seoul.go.kr" + href
        out.append(make_notice(source="SH", cat=cat, type_=type_, title=title, region="서울",
                               posted=tds[3], end=tds[4], link=href))
    return out


def fetch_sh(session) -> list:
    out = []
    for url, cat in SH_LISTS.items():
        res = session.get(url, headers=UA, timeout=30)
        res.raise_for_status()
        out += parse_sh(res.text, cat, url)
    since = (today_kst() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    return [n for n in out if not n["posted"] or n["posted"] >= since]


# ---------------------------------------------------------------- 자바스크립트로 그리는 사이트 (자동 브라우저)
SOCO_URL = "https://soco.seoul.go.kr/youth/bbs/BMSR00015/list.do?menuNo=400008"
ELYES_URL = "https://www.elyes.co.kr/post/recruit"


def _render(url: str, wait_selector: str = "body", wait_ms: int = 4000) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA["User-Agent"], locale="ko-KR")
        page.goto(url, wait_until="networkidle", timeout=60000)
        try:
            page.wait_for_selector(wait_selector, timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
    return html


def parse_soco(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("table tbody tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        # 열: 번호 | 구분 | 공고명 | 공고게시일 | 청약신청일 | 담당부서/사업자
        if len(tds) < 5 or not tds[2]:
            continue
        kind = tds[1]
        start, end = date_range(tds[4])
        out.append(make_notice(
            source="청년안심주택", cat="pub" if "공공" in kind else "pri",
            type_=f"청년안심주택 {kind}".strip(), title=tds[2], region="서울",
            posted=tds[3], start=start, end=end, link=SOCO_URL,
        ))
    return out


def fetch_soco(_session) -> list:
    return parse_soco(_render(SOCO_URL, "table tbody tr td"))


def parse_elyes(html: str) -> list:
    """엘리스 게시판 구조를 미리 알 수 없어서, 날짜가 붙은 글 링크를 넓게 찾는다."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        block = a.find_parent(["li", "tr", "div"]) or a
        around = block.get_text(" ", strip=True)
        if len(text) < 6 or not re.search(r"모집|공고|임차인|입주", text):
            continue
        href = a["href"]
        if href.startswith("/"):
            href = "https://www.elyes.co.kr" + href
        if href in seen:
            continue
        seen.add(href)
        posted, _ = date_range(around)
        out.append(make_notice(source="롯데 엘리스", cat="pri", type_="민간임대",
                               title=text, region=norm_region(text), posted=posted, link=href))
    return out


def fetch_elyes(_session) -> list:
    return parse_elyes(_render(ELYES_URL))


# ---------------------------------------------------------------- 네이버 뉴스 (기업형 임대 새 단지 소식)
NEWS_QUERIES = ["민간임대 임차인 모집", "공공지원 민간임대 공급", "기업형 임대주택 입주자 모집", "청년안심주택 모집"]


def parse_news(items: list, query: str) -> list:
    out = []
    for it in items:
        title = unescape(re.sub(r"<[^>]+>", "", it.get("title", "")))
        try:
            posted = parsedate_to_datetime(it.get("pubDate", "")).astimezone(KST).date().isoformat()
        except Exception:
            posted = ""
        out.append(make_notice(source="뉴스", cat="news", type_=query, title=title,
                               region=norm_region(title), posted=posted,
                               link=it.get("originallink") or it.get("link", "")))
    return out


def fetch_news(session) -> list:
    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        raise RuntimeError("SKIP: 네이버 키 없음")
    out = []
    for q in NEWS_QUERIES:
        res = session.get("https://openapi.naver.com/v1/search/news.json",
                          params={"query": q, "display": 20, "sort": "date"},
                          headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}, timeout=20)
        res.raise_for_status()
        out += parse_news(res.json().get("items", []), q)
    since = (today_kst() - timedelta(days=14)).isoformat()
    return [n for n in out if n["posted"] >= since]


# ---------------------------------------------------------------- 등록부
SOURCES = [
    ("청약홈 APT 분양", lambda s: fetch_applyhome(s, "getAPTLttotPblancDetail")),
    ("청약홈 오피스텔·민간임대", lambda s: fetch_applyhome(s, "getUrbtyOfctlLttotPblancDetail")),
    ("청약홈 공공지원 민간임대", lambda s: fetch_applyhome(s, "getPblPvtRentLttotPblancDetail")),
    ("청약홈 무순위·잔여세대", lambda s: fetch_applyhome(s, "getRemndrLttotPblancDetail")),
    ("청약홈 임의공급", lambda s: fetch_applyhome(s, "getOPTLttotPblancDetail")),
    ("LH 공고", fetch_lh),
    ("SH 공고", fetch_sh),
    ("청년안심주택", fetch_soco),
    ("롯데 엘리스", fetch_elyes),
    ("네이버 뉴스", fetch_news),
]
