# Graph Report - carpediem535  (2026-10-24)

## Corpus Check
- 18 files · ~6,666 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 1, .css 1)

## Summary
- 154 nodes · 296 edges · 13 communities (7 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `614bffbb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- cogoport_scraper.py
- scheduler.py
- storage.py
- app.js
- Trade Cost Simulator
- graphify-setup.sh
- setup-graphify.sh
- CLAUDE.md
- .claude/CLAUDE.md
- graphify 설정 (여러 컴퓨터 공용)

## God Nodes (most connected - your core abstractions)
1. `init()` - 14 edges
2. `renderRatesTable()` - 13 edges
3. `buildMatrix()` - 11 edges
4. `CogoportScraper` - 11 edges
5. `refreshOneRoute()` - 9 edges
6. `scrape_all_and_store()` - 9 edges
7. `main()` - 8 edges
8. `_read_raw()` - 7 edges
9. `set_rate()` - 7 edges
10. `set_many()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `해상운임 갱신` --references--> `search_query_for()`  [INFERRED]
  README.md → scraper/cogoport_scraper.py
- `refresh_one()` --uses--> `CogoportScraper`  [INFERRED]
  app/main.py → scraper/cogoport_scraper.py
- `_run_batch_refresh()` --calls--> `scrape_all_and_store()`  [EXTRACTED]
  app/main.py → scraper/cogoport_scraper.py
- `scrape_all_and_store()` --calls--> `set_many()`  [EXTRACTED]
  scraper/cogoport_scraper.py → app/storage.py
- `run_daily_refresh()` --calls--> `scrape_all_and_store()`  [EXTRACTED]
  app/scheduler.py → scraper/cogoport_scraper.py

## Import Cycles
- None detected.

## Communities (13 total, 6 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.10
Nodes (17): BulkRateUpdate, _country_codes(), get_config(), get_job(), get_rates(), _load_json(), ManualRateUpdate, _now_iso() (+9 more)

### Community 1 - "cogoport_scraper.py"
Cohesion: 0.11
Nodes (10): build_all_routes(), CogoportScraper, discover(), _first_matching(), load_countries(), load_selectors(), main(), scrape_all() (+2 more)

### Community 2 - "scheduler.py"
Cohesion: 0.16
Nodes (9): get_scheduler_status(), get_next_run_time(), _merge_status(), _now_iso(), run_daily_refresh(), start_scheduler(), get_scheduler_status(), set_scheduler_status() (+1 more)

### Community 3 - "storage.py"
Cohesion: 0.27
Nodes (8): get_all(), get_rate(), _now(), _read_raw(), seed_if_empty(), set_many(), set_rate(), _write_raw()

### Community 4 - "app.js"
Cohesion: 0.18
Nodes (30): allRouteKeys(), buildLegend(), buildMatrix(), bulkSync(), calcRoute(), calculateCost(), cargoById(), countryByCode() (+22 more)

### Community 5 - "Trade Cost Simulator"
Cohesion: 0.20
Nodes (9): API, Trade Cost Simulator, 구성, 매일 자동 갱신 설정 (환경변수), 스크래퍼 관련 주의사항, 스크래퍼 셀렉터 보정이 필요한 이유, 실제 비용 데이터 확보 방법, 실행 방법 (+1 more)

### Community 12 - "graphify 설정 (여러 컴퓨터 공용)"
Cohesion: 0.33
Nodes (5): graphify 설정 (여러 컴퓨터 공용), 이 저장소에 이미 들어있는 것 (git으로 모든 컴퓨터에 동기화됨), 자주 쓰는 명령, 참고, 컴퓨터별 1회 설정 (권장 — 다른 프로젝트에서도 `/graphify`를 쓰려면)

## Knowledge Gaps
- **2 isolated node(s):** `PATH`, `PATH`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 53 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `search_query_for()` connect `cogoport_scraper.py` to `Trade Cost Simulator`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `init()` (e.g. with `bulkSync()` and `calculateCost()`) actually correct?**
  _`init()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PATH`, `PATH` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1010752688172043 - nodes in this community are weakly interconnected._
- **Why does `해상운임 갱신` connect `Trade Cost Simulator` to `cogoport_scraper.py`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Should `cogoport_scraper.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11182795698924732 - nodes in this community are weakly interconnected._
- **Why does `CogoportScraper` connect `cogoport_scraper.py` to `main.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._