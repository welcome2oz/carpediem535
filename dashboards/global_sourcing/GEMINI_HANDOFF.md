# 글로벌 소싱 대시보드 — Gemini 데이터 갱신 가이드

이 대시보드는 **화면(코드)** 과 **데이터** 가 분리되어 있습니다. Gemini에게는 데이터(JSON)만 맡기고, 디자인과 계산 코드는 건드리지 않게 하는 것이 핵심입니다.

```
global_sourcing_dashboard.html
 ├─ 화면·계산 코드          ← 건드리지 않음
 └─ <script id="dashboard-data">  ← 데이터 블록 (Gemini가 채우는 곳)
dashboard_data.json          ← 위 데이터 블록과 같은 내용의 스냅샷 (Gemini에 첨부용)
```

> HTML 파일 전체를 Gemini에게 주고 "내용을 채워줘"라고 하지 마세요. 코드가 다시 쓰이면서 디자인·계산식이 깨질 수 있습니다. 항상 **JSON만** 주고받습니다.

---

## 1. 작업 흐름 (코딩 없이 3단계)

대시보드를 브라우저로 열고 오른쪽 위 **Settings › 04 데이터 교체**에서 진행합니다.

| 단계 | 할 일 | 결과 |
|---|---|---|
| ① | **현재 데이터 JSON 내려받기** 클릭 | `dashboard_data_<기준일>.json` 저장 |
| ② | 그 JSON을 Gemini에 첨부하고, 아래 3장의 프롬프트 중 하나를 붙여넣기 | Gemini가 **바뀐 부분만** 담은 JSON을 돌려줌 |
| ③ | Gemini 답변을 통째로 **붙여넣기 칸**에 넣고 **검증 후 적용** | 자동 검증 → 통과하면 즉시 화면 반영 / 실패하면 고칠 항목 표시 |
| ④ | 결과가 맞으면 **이 데이터로 HTML 저장** | 새 데이터가 들어간 HTML 파일이 내려받아짐 → 이 파일을 공유 |

- 붙여넣을 때 Gemini의 설명 문장과 ` ```json ` 코드블록이 섞여 있어도 됩니다. JSON 부분만 자동으로 골라냅니다.
- **부분 갱신이 기본입니다.** 운임만, 관세는 품목 하나씩처럼 나눠서 받으세요. 받은 행만 키(`mat`/`orig`/`dest`)로 찾아 덮어쓰고, 나머지는 그대로 둡니다.
- 마음에 들지 않으면 **원래 데이터로 되돌리기**를 누르면 파일을 열었을 때 상태로 돌아갑니다. 저장 전에는 원본 파일이 바뀌지 않습니다.

---

## 2. 데이터 구조

| 섹션 | 내용 | 단위·형식 | 키 |
|---|---|---|---|
| `meta` | 제목, 호수(edition), 기준일(asOf), 작성자, 출처 목록 | 문자열 | — |
| `origins` | 생산국 5개 (KR, CN, TH, IN, US) — 이름·선적항 | 문자열 | `id` |
| `destinations` | 법인 거점 11개 — 도착항, LOCODE, 내륙운송비, 물류 메모 | `inlandBoxUsd`: USD/Box | `id` |
| `materials` | 품목 6개 — HS코드, 컨테이너 적재량, **생산국별 FOB**, FOB 출처 | `defaultFob`: USD/MT, 생산 없으면 `null` | `id` |
| `freight.routes` | 55개 항로 × 3개 지수 운임 | `drewry`·`freightos`·`cogoport`: USD/Box | `orig` + `dest` |
| `tariffs.rows` | 330개 구간 (품목 6 × 생산국 5 × 거점 11) | `mfn`·`fta`·`adCvd`: **% 숫자** (25.75) | `mat` + `orig` + `dest` |
| `scenarios.krChinaSteelAd` | 한국의 중국산 도금·컬러강판 AD 선택지 | % 숫자 | — |
| `policy` | 마나우스 ZFM 기본관세 배수(0.12 = 88% 감면), 태국 AD 면제 품목 | 숫자 / 품목 id 배열 | — |
| `changeLog` | 변경 이력 — 무엇을, 무엇에서 무엇으로, 어떤 출처로 | 배열 | — |

관세 행 필드 의미:

- `mfn` 일반 관세율, `fta` 협정 세율 (협정이 없으면 `mfn`과 같은 값), `ftaName` 협정 이름
- `adCvd` 기본관세 위에 **더해지는** 무역구제 합계 %p (반덤핑·상계·232조·301조·보복관세)
- `note` 근거 법령·고시 번호와 시행일, `sourceUrl` 원문 주소
- 생산국과 거점이 같은 나라(예: KR→KR)는 내수 조달이라 모두 0입니다.

경로 표기 (`changeLog.path`): `freight.routes[KR>CN].drewry`, `tariffs.rows[GI/CN>KR].adCvd`, `materials[GI].defaultFob.CN`

---

## 3. Gemini 프롬프트

웹 검색이 켜진 Gemini(예: Gemini 앱의 Deep Research)를 쓰세요. 모든 프롬프트 맨 앞에 **공통 규칙**을 붙입니다.

### 공통 규칙 (모든 프롬프트 앞에 붙여넣기)

```text
[역할] 너는 구매 데이터 리서처다. 첨부한 dashboard_data.json의 "값"만 최신 공식 자료로 갱신한다.

[절대 규칙]
1. 직접 열어서 확인한 공식 출처(정부 고시·관보, 세관 관세율표, 지수 발행기관의 공표 페이지)의 값만 쓴다.
   확인하지 못한 항목은 기존 값을 그대로 두고, changeLog에 note "미확인: 이유"로 남긴다.
   추정·평균·과거 기억에 의존한 값은 절대 넣지 않는다.
2. sourceUrl에는 실제로 열어 본 페이지 주소만 넣는다. 주소를 지어내지 않는다.
3. 키 이름과 id는 바꾸지 않는다. 행을 추가하거나 삭제하지 않는다.
   생산국 id: KR, CN, TH, IN, US / 거점 id: KR, CN, IN_NOI, IN_PUN, TH, ID, SA, BR, EG, US, NO
   품목 id: GI, PCM, ABS, CPP, HIPS, EPS
4. 숫자는 따옴표 없는 숫자로 쓴다. 퍼센트는 25.75 형식(0.2575 아님). 운임은 USD/Box, FOB는 USD/MT.
5. 생산업체가 없는 국가의 FOB는 null로 쓴다.
6. 문자열에 HTML 태그나 < 기호를 쓰지 않는다.
7. 값을 하나 바꿀 때마다 changeLog에 한 줄을 추가한다:
   {"date":"YYYY-MM-DD","path":"tariffs.rows[GI/CN>KR].adCvd","old":25.75,"new":24.1,"sourceUrl":"https://...","note":"근거 요약"}
8. 출력은 "바뀐 부분만" 담은 JSON 하나를 ```json 코드블록으로 낸다.
   행을 바꿀 때는 그 행의 키(mat/orig/dest 또는 orig/dest)와 바뀐 필드만 넣는다.
   코드블록 밖 설명은 3줄 이내.
```

### A. 해상운임 갱신 (55개 항로)

```text
[작업] freight 섹션을 갱신해줘.
- 대상: freight.routes 55개 항로의 drewry, freightos, cogoport 값 (USD/Box)
- 각 지수 발행처(Drewry WCI·IACI / SCFI, Freightos FBX, Cogoport)의 가장 최근 공표값을 쓴다.
- 지수가 해당 항구 쌍을 직접 공표하지 않으면 값을 바꾸지 말고 changeLog에 "미확인: 직접 공표 항로 아님"으로 남긴다.
- freight.asOf는 사용한 공표일(YYYY-MM-DD), freight.sources.drewry/freightos/cogoport.url은 실제 공표 페이지로 채운다.

[출력 형식]
{"freight":{"asOf":"...","sources":{"drewry":{"url":"..."}},"routes":[{"orig":"KR","dest":"CN","drewry":0}]},"changeLog":[...]}
```

### B. 관세·무역구제 갱신 (품목 하나씩 — 예: GI)

```text
[작업] tariffs.rows 중 mat이 "GI"인 55개 행을 검토해줘.
- 각 행의 mfn, fta, ftaName, adCvd를 도착국 세관 관세율표와 현행 반덤핑·상계·232조·301조 고시 기준으로 확인한다.
- adCvd는 기본관세 위에 더해지는 무역구제 합계 %p다.
- note에는 근거 법령·고시 번호와 시행일을 한국어로 쓴다. sourceUrl에 원문 주소를 넣는다.
- 생산국과 거점이 같은 나라인 행(KR→KR, CN→CN, IN→IN_NOI/IN_PUN, TH→TH, US→US)은 내수 조달이므로 건드리지 않는다.
- 한국의 중국산 도금·컬러강판 AD(GI·PCM, CN→KR)가 바뀌면 scenarios.krChinaSteelAd의 default와 options도 같이 맞춘다.
- tariffs.asOf를 확인한 기준일로 바꾼다.

[출력 형식]
{"tariffs":{"asOf":"...","rows":[{"mat":"GI","orig":"CN","dest":"TH","adCvd":35.5,"note":"...","sourceUrl":"https://..."}]},"changeLog":[...]}
```

품목을 바꿔 가며 `"GI"` 자리에 PCM, ABS, CPP, HIPS, EPS를 넣어 6번 실행합니다. 한 번에 330행을 다 받으면 답변이 잘리거나 형식이 깨지기 쉽습니다.

### C. 생산국별 FOB 시장가 갱신

```text
[작업] materials[].defaultFob (생산국별 FOB, USD/MT)를 갱신해줘.
- 공개된 가격 평가·통계 자료에서 확인되는 값만 쓴다. 유료 리포트라 수치를 직접 확인할 수 없으면 바꾸지 않는다.
- 해당 품목을 생산·수출하는 업체가 없는 국가는 null로 한다.
- 각 품목의 fobSource에 출처 이름과 기준일(또는 URL)을 쓴다.

[출력 형식]
{"materials":[{"id":"GI","defaultFob":{"CN":650},"fobSource":"출처명, YYYY-MM-DD, https://..."}],"changeLog":[...]}
```

FOB는 공개 자료로 확인되지 않는 경우가 많으므로, 사내 견적·계약 단가를 직접 넣는 편이 더 정확할 수 있습니다. 화면의 Settings › 01 FOB 단가에서 바로 입력해도 되고, 그 경우 위 JSON 형식으로 직접 써서 붙여넣으면 이력도 남습니다.

### D. 출처 URL만 채우기 (값은 그대로) — 가장 먼저 권장

현재 데이터는 Gemini 초안이라 출처 URL이 0/330입니다. 값을 바꾸기 전에 근거부터 확인하는 단계입니다.

```text
[작업] 값은 하나도 바꾸지 말고, tariffs.rows 중 mat이 "GI"인 행의 note에 적힌 근거(고시·법령)의 원문 URL을 찾아 sourceUrl만 채워줘.
- 원문 내용이 현재 값(mfn/fta/adCvd)과 다르면 값은 그대로 두고 changeLog에 note "불일치: 원문 xx%, 현재 yy%"로 보고한다.
- 원문을 찾지 못하면 sourceUrl을 비워 두고 changeLog에 "미확인"으로 남긴다.

[출력 형식]
{"tariffs":{"rows":[{"mat":"GI","orig":"CN","dest":"KR","sourceUrl":"https://..."}]},"changeLog":[...]}
```

"불일치"로 보고된 항목만 골라 B 프롬프트로 다시 갱신하면 됩니다.

---

## 4. 적용 후 체크리스트

1. **검증 결과 확인:** 초록 상자("적용 완료")인지, 경고 목록에 무엇이 남았는지 봅니다.
2. **출처 스팟체크:** changeLog의 URL 3~5개를 직접 열어 숫자가 맞는지 대조합니다. Gemini가 존재하지 않는 주소나 다른 문서를 붙이는 경우가 있습니다.
3. **상식 점검:** 커버스토리 헤드라인과 매트릭스 1위가 갑자기 크게 바뀌었다면, 해당 구간의 changeLog를 먼저 봅니다.
4. **저장과 공유:** **이 데이터로 HTML 저장** → 파일 이름에 기준일이 붙습니다. 저장한 HTML을 다시 열면 Settings › 04에서 출처 URL 개수와 변경 기록을 볼 수 있습니다.

---

## 5. 자주 나오는 검증 메시지

| 메시지 | 의미 | 해결 |
|---|---|---|
| JSON 문법 오류 | 쉼표·따옴표·괄호 누락, 또는 답변이 중간에 잘림 | Gemini에게 "같은 내용을 유효한 JSON으로 다시 출력"을 요청 |
| 형식 오류 … `tariffs.rows[GI/CN>KR].adCvd` | 숫자 자리에 `"25.75"`처럼 따옴표가 있거나 범위를 벗어남 | 해당 필드를 따옴표 없는 숫자로 |
| 관세율이 모두 1 이하 … 소수로 넣은 것 같습니다 | 25.75% 를 0.2575로 씀 (엑셀 % 서식에서 자주 발생) | % 숫자로 다시 요청 |
| … 없는 구간 / 없는 id | 키 오타 또는 행·국가 추가 시도 | id 목록(3장 공통 규칙 3번) 확인 |
| 문자열에 < 기호 | 텍스트에 HTML 태그 | 태그 없이 다시 요청 |
| changeLog가 비어 있습니다 | 값은 바뀌었는데 이력이 없음 | 적용은 됐지만, 출처 추적을 위해 changeLog를 요청해 다시 붙여넣기 |
| 관세 행 출처 URL 미기재 n/330 | 경고(적용은 됨) | D 프롬프트로 채우기 |

---

## 6. 알아둘 점

- **구조는 고정입니다.** 생산국·거점·품목을 추가하거나 빼려면 코드 수정이 필요합니다. 데이터 교체로는 값만 바뀝니다.
- **기준 데이터는 HTML 안 데이터 블록입니다.** 같은 폴더의 `global_sourcing_freight_tariff_raw_data_2026.xlsx`는 최초 원본(참고용)이며, 데이터 교체 후에는 자동으로 갱신되지 않습니다.
- **직접 고치고 싶을 때:** HTML을 텍스트 편집기로 열어 `DASHBOARD DATA` 주석 아래 `<script type="application/json" id="dashboard-data">` 구간의 값만 고쳐도 됩니다. 저장 후 열었을 때 형식이 틀리면 화면 상단에 오류 목록이 뜨고, 대시보드는 그려지지 않습니다.
- 인니·인도·한국·이집트 보세 면제 체크박스는 아직 계산식에 연결되어 있지 않습니다(원본과 동일). 이 규칙은 데이터가 아니라 계산 로직이라 Gemini 데이터 교체로는 바뀌지 않습니다.
