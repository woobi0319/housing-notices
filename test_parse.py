"""인터넷 없이 돌리는 점검: 각 출처의 응답 모양을 흉내 내서 해석이 맞는지 본다.
실행: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
import collect  # noqa: E402
import sources  # noqa: E402
from util import date_range, norm_date, norm_region  # noqa: E402


class Util(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(norm_date("2026.11.20"), "2026-11-20")
        self.assertEqual(norm_date("20261120"), "2026-11-20")
        self.assertEqual(norm_date("2026-11-20 10:00"), "2026-11-20")
        self.assertEqual(norm_date(""), "")
        self.assertEqual(date_range("2026.11.30 ~ 2026.12.02"), ("2026-11-30", "2026-12-02"))

    def test_regions(self):
        self.assertEqual(norm_region("서울특별시"), "서울")
        self.assertEqual(norm_region("", "경상남도 양산시"), "경남")
        self.assertEqual(norm_region("전남광주통합특별시"), "전남·광주")
        self.assertEqual(norm_region("충청북도"), "충북")


class Applyhome(unittest.TestCase):
    def test_apt(self):
        rows = [{"HOUSE_MANAGE_NO": "2026000123", "PBLANC_NO": "2026000123", "HOUSE_NM": "소사 휴먼빌",
                 "HOUSE_DTL_SECD_NM": "민영", "RENT_SECD_NM": "분양주택", "SUBSCRPT_AREA_CODE_NM": "경기",
                 "HSSPLY_ADRES": "경기도 부천시", "RCRIT_PBLANC_DE": "2026-11-20", "RCEPT_BGNDE": "2026-11-30",
                 "RCEPT_ENDDE": "2026-12-02", "PRZWNER_PRESNATN_DE": "2026-12-08",
                 "PBLANC_URL": "https://www.applyhome.co.kr/x"}]
        n = sources.parse_applyhome("getAPTLttotPblancDetail", rows)[0]
        self.assertEqual((n["cat"], n["region"], n["start"], n["end"], n["announce"]),
                         ("sale", "경기", "2026-11-30", "2026-12-02", "2026-12-08"))

    def test_rent_inside_apt_goes_to_private(self):
        rows = [{"HOUSE_NM": "어느 임대", "RENT_SECD_NM": "임대주택", "HSSPLY_ADRES": "부산광역시",
                 "RCRIT_PBLANC_DE": "2026-11-02"}]
        self.assertEqual(sources.parse_applyhome("getAPTLttotPblancDetail", rows)[0]["cat"], "pri")

    def test_remainder_fields(self):
        rows = [{"HOUSE_NM": "더샵 송도", "HOUSE_SECD_NM": "무순위", "HSSPLY_ADRES": "인천광역시 연수구",
                 "RCRIT_PBLANC_DE": "2026-11-04", "SUBSCRPT_RCEPT_BGNDE": "2026-11-09",
                 "SUBSCRPT_RCEPT_ENDDE": "2026-11-09"}]
        n = sources.parse_applyhome("getRemndrLttotPblancDetail", rows)[0]
        self.assertEqual((n["cat"], n["region"], n["end"]), ("rem", "인천", "2026-11-09"))


class LH(unittest.TestCase):
    payload = [{"dsSch": [{"PAN_NT_ST_DT": "2026.10.01"}]},
               {"dsList": [
                   {"PAN_ID": "1", "PAN_NM": "서울 영구임대 예비입주자 모집", "UPP_AIS_TP_NM": "임대주택",
                    "AIS_TP_CD_NM": "영구임대", "CNP_CD_NM": "서울특별시", "PAN_SS": "공고중",
                    "PAN_NT_ST_DT": "2026.11.19", "CLSG_DT": "2026.12.04", "DTL_URL": "https://apply.lh.or.kr/a"},
                   {"PAN_ID": "2", "PAN_NM": "어린이집 운영자 모집", "UPP_AIS_TP_NM": "임대주택",
                    "AIS_TP_CD_NM": "가정어린이집", "CNP_CD_NM": "경기도"},
                   {"PAN_ID": "3", "PAN_NM": "고양창릉 공공분양", "UPP_AIS_TP_NM": "분양주택",
                    "AIS_TP_CD_NM": "공공분양", "CNP_CD_NM": "경기도", "PAN_NT_ST_DT": "2026.11.10"}],
                "resHeader": [{"SS_CODE": "Y"}]}]

    def test_parse(self):
        out = sources.parse_lh(self.payload)
        self.assertEqual(len(out), 2)  # 어린이집 제외
        self.assertEqual((out[0]["cat"], out[0]["region"], out[0]["end"]), ("pub", "서울", "2026-12-04"))
        self.assertEqual(out[1]["cat"], "sale")


class Seoul(unittest.TestCase):
    sh_html = """<table><tbody>
      <tr><td>16</td><td>매입임대주택</td><td><a href="/site/main/sh/publicLease/view?seq=1">2026년 1차 청년 매입임대 입주자모집 공고</a></td>
          <td>2026-11-20</td><td>2026-12-01</td><td>모집중</td><td>매입주택공급부</td><td>바로가기</td></tr>
      <tr><td>15</td><td>국민임대</td><td>국민임대 예비10차 당첨자 발표</td><td>2026-11-19</td><td>-</td><td>모집마감</td><td>부서</td><td></td></tr>
    </tbody></table>"""

    soco_html = """<table><tbody>
      <tr><td>3</td><td>민간</td><td>동묘앞역 청계로벤하임 추가모집</td><td>2026-11-12</td><td>2026-11-16 ~ 2026-11-16</td><td>사업자</td></tr>
      <tr><td>2</td><td>공공</td><td>2026년 3차 청년안심주택(공공임대)</td><td>2026-11-20</td><td>2026-12-01 ~ 2026-12-03</td><td>SH</td></tr>
    </tbody></table>"""

    def test_sh(self):
        out = sources.parse_sh(self.sh_html, "pub", "https://housing.seoul.go.kr")
        self.assertEqual(len(out), 1)  # 당첨자 발표 글 제외
        self.assertTrue(out[0]["link"].startswith("https://housing.seoul.go.kr/site/"))

    def test_soco(self):
        out = sources.parse_soco(self.soco_html)
        self.assertEqual([n["cat"] for n in out], ["pri", "pub"])
        self.assertEqual(out[1]["end"], "2026-12-03")

    def test_elyes(self):
        html = """<ul><li><a href="/post/recruit/12">○○ 롯데캐슬 임차인 모집공고</a><span>2026.11.18</span></li>
                  <li><a href="/about">회사소개</a></li></ul>"""
        out = sources.parse_elyes(html)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["posted"], "2026-11-18")


class News(unittest.TestCase):
    def test_parse(self):
        items = [{"title": "KT에스테이트, &quot;리마크빌 마포&quot; <b>입주자 모집</b>",
                  "originallink": "https://news.example/1", "pubDate": "Mon, 23 Nov 2026 09:00:00 +0900"}]
        n = sources.parse_news(items, "q")[0]
        self.assertEqual((n["title"], n["posted"]), ('KT에스테이트, "리마크빌 마포" 입주자 모집', "2026-11-23"))


class Merge(unittest.TestCase):
    def test_first_seen_and_failed_source_kept(self):
        a = {"id": "a", "source": "LH", "posted": "2099-01-01", "end": "", "first_seen": "old"}
        b = {"id": "b", "source": "청약홈", "posted": "2099-01-01", "end": ""}
        c = {"id": "c", "source": "청약홈", "posted": "2099-01-02", "end": ""}
        prev = {"items": [a, dict(b, first_seen="old")]}
        status = [{"name": "LH 공고", "ok": False}, {"name": "청약홈 APT 분양", "ok": True}]
        items, new = collect.merge(prev, [dict(b), dict(c)], status, "now")
        ids = {n["id"]: n for n in items}
        self.assertEqual(set(ids), {"a", "b", "c"})   # 실패한 LH 공고는 남김
        self.assertEqual(ids["b"]["first_seen"], "old")
        self.assertEqual([n["id"] for n in new], ["c"])


class Redact(unittest.TestCase):
    def test_key_never_leaks(self):
        import os
        os.environ["DATA_GO_KR_KEY"] = "abc+DEF/ghi=="
        s = "url /x?serviceKey=abc%2BDEF%2Fghi%3D%3D&page=1 raw abc+DEF/ghi=="
        out = collect.redact(s)
        self.assertNotIn("abc", out)


if __name__ == "__main__":
    unittest.main()
