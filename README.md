# 분양·임대 공고 알림

청약홈, LH, SH, 서울 청년안심주택, 롯데 엘리스의 새 공고를 하루 두 번 자동으로 모아서
휴대폰에서 보는 웹앱으로 보여 줍니다. 원하면 새 공고를 텔레그램으로 알려 줍니다.
돈은 들지 않습니다(GitHub 무료 기능만 씀).

```
GitHub Actions (하루 2번)  →  collector/collect.py  →  docs/notices.json  →  GitHub Pages 웹앱 (docs/index.html)
                                                     ↘  텔레그램으로 새 공고 알림 (선택)
```

## 모으는 곳

| 출처 | 방식 | 필요한 것 |
|---|---|---|
| 청약홈: APT 분양, 오피스텔·도시형·민간임대, 공공지원 민간임대, 무순위·잔여세대, 임의공급 | 공공데이터 API | 공공데이터포털 키 |
| LH 분양·임대 공고 | 공공데이터 API | 같은 키 |
| SH 임대·분양 공고 | 서울주택정보마당 목록 | 없음 |
| 서울 청년안심주택 | 자동 브라우저 | 없음 |
| 롯데 엘리스 임차인 모집 | 자동 브라우저 | 없음 |
| 기업형 임대 새 단지 소식 | 네이버 뉴스 검색 API | 네이버 키 (선택) |

---

## 설치 (PC에서 30분 정도)

### 1. 공공데이터포털 키 받기
1. https://www.data.go.kr 에 가입하고 로그인합니다.
2. 아래 두 서비스를 검색해서 각각 **활용신청**을 누릅니다(활용 목적: 개인 공고 알림).
   - 한국부동산원_청약홈 분양정보 조회 서비스
   - 한국토지주택공사_분양임대공고문 조회 서비스
3. 마이페이지 → 개발계정 → 신청한 서비스 → **일반 인증키(Decoding)** 를 복사해 둡니다.
   두 서비스 모두 같은 키를 씁니다. 승인 직후 1~2시간은 키가 동작하지 않을 수 있습니다.

### 2. GitHub 저장소 만들기
1. https://github.com 에 가입합니다.
2. 오른쪽 위 **+ → New repository**. 이름은 예를 들어 `housing-notices`, **Public** 을 고릅니다
   (무료로 웹앱 주소를 쓰려면 Public 이어야 합니다. 공개되는 것은 공고 목록뿐이고 키는 공개되지 않습니다).
3. **Create repository** → 화면의 **uploading an existing file** 을 누릅니다.
4. 받은 압축 파일을 풀고, 폴더 **안의 내용 전부**를 끌어다 놓은 뒤 **Commit changes**.
5. 저장소 첫 화면에 `.github` 폴더가 보이는지 확인합니다. 안 보이면(맥 Finder 는 숨김 폴더를 안 보여 줌):
   **Add file → Create new file** 에서 파일 이름 칸에 `.github/workflows/collect.yml` 을 입력하고,
   압축 파일 속 같은 파일의 내용을 붙여 넣은 뒤 **Commit changes**.

### 3. 키 넣기 (Secrets)
저장소 **Settings → Secrets and variables → Actions → New repository secret**

| Name | Secret |
|---|---|
| `DATA_GO_KR_KEY` | 1단계에서 복사한 인증키 |

### 4. 자동 실행 허용
1. **Settings → Actions → General** 맨 아래 **Workflow permissions** 에서
   **Read and write permissions** 를 고르고 **Save**.
2. 위쪽 **Actions** 탭에서 "I understand… enable" 같은 버튼이 보이면 눌러 켭니다.

### 5. 웹앱 주소 켜기
**Settings → Pages** 에서 Source: **Deploy from a branch**, Branch: **main**, 폴더: **/docs** → **Save**.
1~2분 뒤 `https://<내 아이디>.github.io/housing-notices/` 주소가 생깁니다.

### 6. 첫 수집
**Actions → 공고 모으기 → Run workflow** 를 누릅니다. 3~5분 뒤 초록 체크가 뜨면 웹앱을 열어 봅니다.
그 뒤로는 매일 아침 7시, 저녁 6시 무렵 저절로 돕니다.

### 7. 아이폰 홈 화면에 추가
사파리로 웹앱 주소를 열고 **공유 → 홈 화면에 추가**. 앱처럼 열립니다.

---

## 선택: 텔레그램으로 새 공고 알림
1. 텔레그램에서 **@BotFather** → `/newbot` → 이름을 정하면 **토큰**을 줍니다.
2. 만든 봇과 대화를 열고 아무 말이나 보냅니다.
3. PC 브라우저로 `https://api.telegram.org/bot<토큰>/getUpdates` 를 열어 `"chat":{"id":숫자` 의 숫자를 복사합니다.
4. Secrets 에 `TELEGRAM_BOT_TOKEN`(토큰), `TELEGRAM_CHAT_ID`(숫자)를 추가합니다.

첫 수집 때는 "알림을 시작했어요" 한 통만 오고, 다음부터 새로 생긴 공고만 옵니다.

## 선택: 네이버 뉴스 (기업형 임대 새 단지 소식)
https://developers.naver.com → Application 등록 → 사용 API: **검색** →
받은 값을 Secrets 에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 으로 넣습니다.
검색어는 `collector/sources.py` 의 `NEWS_QUERIES` 에서 바꿀 수 있습니다.

---

## 문제가 생기면

- **웹앱 아래 '모은 곳'에 실패가 뜰 때**: 눌러서 어느 출처인지 봅니다. 한 곳이 실패해도 나머지는 계속 모이고,
  실패한 곳의 공고는 지난번 것이 그대로 남습니다.
- **청약홈·LH 가 둘 다 실패**: 키가 아직 활성화 전이거나 Secrets 이름이 틀린 경우가 대부분입니다.
- **LH·SH·청년안심주택만 계속 실패**: 일부 공공기관 사이트는 해외 서버 접속을 막습니다. GitHub 서버는 미국에 있어서
  이 경우 그 출처만 비게 됩니다. 이때는 집 PC에서 아래를 돌리고 `docs/notices.json` 을 올리는 방법이 있습니다.
  ```
  pip install -r requirements.txt && python -m playwright install chromium
  DATA_GO_KR_KEY=키 python collector/collect.py "LH 공고" "SH 공고" "청년안심주택"
  ```
- **사이트 모양이 바뀌어 0건이 나올 때**: `collector/sources.py` 의 해당 `parse_…` 함수를 고치면 됩니다.
  `python -m unittest discover tests` 로 인터넷 없이 해석 부분을 점검할 수 있습니다.

## 파일 구성
```
.github/workflows/collect.yml   하루 2번 자동 실행
collector/collect.py            모으기·합치기·저장·텔레그램 알림
collector/sources.py            출처별로 가져오고 해석하는 코드
collector/util.py               날짜·지역 정리
docs/index.html                 웹앱 화면
docs/notices.json               모은 공고 (자동 갱신)
tests/test_parse.py             인터넷 없이 돌리는 점검
```

수집은 하루 2번으로 각 사이트에 부담을 주지 않게 했고, 자동 수집을 막아 둔 사이트(예: 리마크빌)는 넣지 않았습니다.
공고 내용은 각 기관의 원문이 기준입니다.
