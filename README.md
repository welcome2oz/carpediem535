# Trade Cost Simulator

지정한 10개국 간 수출입 시 발생하는 **관세(수입세)를 제외한 물류 부대비용**을
시뮬레이션하는 웹앱입니다. 하나의 FastAPI 서버가 API와 프론트엔드를 함께 서빙하며,
변동성이 큰 **해상운임(Ocean Freight)** 은 수동 입력과 Cogoport 자동 조회(RPA) 두
방식으로 갱신할 수 있습니다.

기존에 두 개로 나뉘어 있던 산출물(정적 HTML 시뮬레이터 + 별도 Selenium 스크래퍼)을
하나의 앱으로 통합하고, 스크래퍼는 Playwright 기반으로 재작성했습니다.

## 구성

```
app/
  main.py              FastAPI 앱 (API + 정적 파일 서빙)
  storage.py           해상운임 데이터 저장소 (JSON 파일, 출처/갱신시각 기록)
  data/countries.json  10개국 내륙운송비/항만부대비용/통관비 샘플 데이터
  data/cargo_profiles.json  화물 프로필 (40ft 기준 중량 등)
scraper/
  cogoport_scraper.py  Cogoport 해상운임 스크래퍼 (Playwright, CLI 겸용)
  selectors.json       사이트 CSS 셀렉터 (구조 변경 시 여기만 수정)
frontend/
  index.html / styles.css / app.js   비용 매트릭스, 경로 시뮬레이터, 운임 관리 UI
```

비용 구조는 세 구간으로 나뉩니다:

1. **출발지 비용**: 내륙운송비, 항만 부대비용
2. **해상운임**: 국제 정세에 따라 크게 변동 — 별도 갱신 관리
3. **도착지 비용**: 항만 부대비용, 통관비(관세사 대행 수수료 — 관세/수입세 아님), 내륙운송비

`app/data/countries.json`의 수치는 전부 **샘플 값**입니다. 실제 운영 전 반드시
실측 데이터로 교체하세요. 실측 데이터를 구하는 방법은 아래 "실제 비용 데이터
확보 방법" 섹션 참고.

## 실행 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # Cogoport 자동 조회 기능을 쓸 경우에만 필요

uvicorn app.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000` 접속.

최초 실행 시 90개 구간(10개국 상호조합)의 해상운임이 샘플 값으로 자동
시딩됩니다 (`app/data/freight_rates.json`, git에는 포함되지 않음).

## 해상운임 갱신

- **수동 입력**: "해상운임 관리" 탭에서 구간별로 직접 입력 후 저장, 또는
  하단 "수동 일괄 업데이트"에 `{"KR-US": 6000, ...}` 형태 JSON을 붙여넣어 일괄 반영
- **Cogoport 자동 조회** (로그인 불필요 — 공개 운임 검색 폼을 그대로 사용):
  - 경로 시뮬레이터의 "Cogoport에서 재조회" 버튼 → 현재 선택된 구간 1개만 즉시 조회
  - 해상운임 관리 탭의 "전체 자동 재조회" → 90개 구간을 순차 조회 (백그라운드 작업,
    수 분 소요, 진행 상황 폴링 표시)
  - 검색어는 국가 데이터의 항구명에서 도시명을 추출해 `"Busan, South Korea"` 형태로
    자동 완성 검색창에 입력합니다 (`scraper/cogoport_scraper.py`의 `search_query_for`)

### 스크래퍼 셀렉터 보정이 필요한 이유

이 코드는 Claude Code 세션 환경에서 작성되었는데, 이 환경은 네트워크 정책상
`cogoport.com` 같은 일반 사이트에 접속할 수 없어 (레지스트리/anthropic.com만
허용) **실제 사이트 구조를 직접 열어보고 검증하지 못했습니다.** 따라서
`scraper/selectors.json`은 최선의 추정값이며, 실제 사용 전 아래 순서로
보정이 필요합니다:

1. 실제 인터넷 접속이 되는 환경(로컬 PC 등)에서 의존성 설치 후 진단 모드 실행:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   python -m scraper.cogoport_scraper --discover --show-browser
   ```
   페이지의 모든 `<input>`/`<button>` 요소(placeholder, aria-label, id, 텍스트)를
   출력하고 `scraper/discover_screenshot.png`에 스크린샷을 저장합니다.
2. 출력된 목록에서 출발지/도착지 입력창과 검색 버튼에 해당하는 항목을 찾아
   `scraper/selectors.json`의 `search.origin_input` / `destination_input` /
   `search_button` 배열 맨 앞에 정확한 셀렉터를 추가합니다.
3. 단일 구간으로 테스트:
   ```bash
   python -m scraper.cogoport_scraper --origin "Busan, South Korea" --dest "Clarksville, United States" --show-browser
   ```
   `--show-browser`로 브라우저 창을 띄워 자동완성 클릭과 검색 결과 표시가 실제로
   일어나는지 눈으로 확인한 뒤 결과가 정상 파싱되면 `--headless`(기본값)로 되돌려 사용하세요.
4. 각 셀렉터는 배열이라 실패하면 다음 후보를 자동으로 시도합니다 — 여러 페이지
   버전(A/B 테스트 등)이 섞여 있다면 후보를 여러 개 남겨둬도 됩니다.

### 스크래퍼 관련 주의사항

- 자동 조회는 요청 사이에 지연(`--delay`, 기본 3초)을 두어 서버 부하를 줄입니다.
  Cogoport 이용약관 및 rate limit을 준수하는 선에서 사용하세요.
- Chromium 실행 파일 경로를 직접 지정해야 하는 환경(도커/샌드박스 등)이면
  환경변수 `PLAYWRIGHT_CHROMIUM_EXECUTABLE`로 override 가능합니다.
- CLI로 직접 실행도 가능합니다:
  ```bash
  python -m scraper.cogoport_scraper --origin "Busan, South Korea" --dest "Clarksville, United States"
  python -m scraper.cogoport_scraper --all --write   # 전체 구간, 앱 저장소에 바로 기록
  python -m scraper.cogoport_scraper --discover      # 셀렉터 보정용 진단 모드
  ```

## 실제 비용 데이터 확보 방법

`countries.json`의 내륙운송비/항만 부대비용/통관비는 해상운임과 달리 매번 검색할
필요는 없지만, 상용 마켓플레이스에서 실시간으로 공개 조회되는 값이 아니라서
스크래핑으로 자동 수집하기 어렵습니다. 아래 경로로 직접 확보하는 것을 권장합니다.

1. **거래 중인 포워더에게 구간별 견적(all-in quote) 요청** — 가장 정확하고 빠른
   방법입니다. 대부분의 포워더가 "Origin charges / Ocean freight / Destination
   charges"로 항목을 나눠 견적을 주므로, 여기서 해상운임을 뺀 나머지를 그대로
   `inlandTrucking` / `portHandling` / `customsClearance`에 대입하면 됩니다.
2. **항만 부대비용(THC 등)** — 많은 선사(Maersk, MSC, CMA CGM, HMM, ONE 등)가
   자사 웹사이트에 지역별 "Local Charges / Tariff" 페이지를 공개합니다. 또는 각
   항만공사(예: 부산항만공사, PSA Singapore)가 공식 터미널 하역료를 게시합니다.
3. **내륙운송비** — 국가별 트럭 운송 협회나 벤치마킹 플랫폼을 참고하세요
   (예: 미국은 DAT Freight & Analytics, 국내는 한국통합물류협회/관련 운송사 견적).
   포워더가 트럭킹까지 포함한 door-to-port 견적을 주는 경우가 많아 실무에서는
   이 편이 더 간단합니다.
4. **통관비(관세사 수수료, 관세와는 별개)** — 각국 관세사(customs broker) 요금표를
   참고하세요. 한국은 관세사회 공표 수수료 기준, 그 외 국가는 현지 관세사/포워더
   견적을 받는 것이 일반적입니다. DHL, Flexport 같은 글로벌 포워더는 브로커리지
   수수료를 웹사이트에 공개하는 경우도 있습니다.
5. **벤치마킹/조사 플랫폼** — Xeneta, Freightos(FBX), Drewry 등은 유료 구독이지만
   구간별 컨테이너 물류비를 벤치마킹할 수 있는 리서치 자료를 제공합니다. 초기
   데이터 검증 용도로 유용합니다.

일반 원칙: 해상운임처럼 자주 안 바뀌는 항목이라도 **데이터를 넣을 때마다 출처와
확인 날짜를 어딘가에 기록**해 두면(예: 스프레드시트 별도 관리, 또는
`countries.json`에 주석성 필드 추가) 나중에 "이 숫자가 언제 기준인지" 추적하기
쉬워집니다.

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/config` | 국가/화물 프로필 설정 |
| GET | `/api/rates` | 전체 해상운임 (구간별 rate/출처/갱신시각) |
| PUT | `/api/rates/{ORIGIN-DEST}` | 단일 구간 수동 갱신 |
| POST | `/api/rates/bulk` | 여러 구간 일괄 수동 갱신 |
| POST | `/api/rates/refresh` | 단일 구간 Cogoport 즉시 조회 (동기) |
| POST | `/api/rates/refresh-all` | 전체 구간 Cogoport 조회 (비동기 job 시작) |
| GET | `/api/jobs/{job_id}` | 전체 조회 작업 진행 상태 |
