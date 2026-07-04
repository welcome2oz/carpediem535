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
실측 데이터로 교체하세요.

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
- **Cogoport 자동 조회**:
  - 경로 시뮬레이터의 "Cogoport에서 재조회" 버튼 → 현재 선택된 구간 1개만 즉시 조회
  - 해상운임 관리 탭의 "전체 자동 재조회" → 90개 구간을 순차 조회 (백그라운드 작업,
    수 분 소요, 진행 상황 폴링 표시)
  - 로그인이 필요하면 환경변수 `COGOPORT_EMAIL`, `COGOPORT_PASSWORD` 설정

### 스크래퍼 관련 주의사항

- `scraper/selectors.json`의 CSS 셀렉터는 실제 Cogoport 로그인 후 브라우저
  개발자 도구로 다시 확인/보정이 필요합니다. 사이트 구조가 바뀌면 코드가 아니라
  이 파일만 수정하면 됩니다.
- 자동 조회는 요청 사이에 지연(`--delay`, 기본 3초)을 두어 서버 부하를 줄입니다.
  Cogoport 이용약관 및 rate limit을 준수하는 선에서 사용하세요.
- CLI로 직접 실행도 가능합니다:
  ```bash
  python -m scraper.cogoport_scraper --origin KRPUS --dest USCKV
  python -m scraper.cogoport_scraper --all --write   # 전체 구간, 앱 저장소에 바로 기록
  ```

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
