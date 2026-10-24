# graphify 설정 (여러 컴퓨터 공용)

[graphify](https://github.com/Graphify-Labs/graphify)는 프로젝트(코드, 문서, PDF, 이미지)를
지식 그래프로 바꿔서, Claude가 파일을 전부 다시 읽는 대신 그래프를 조회하게 해주는 도구입니다.
PyPI 패키지명은 `graphifyy`(y 두 개)이고, 명령어는 `graphify`입니다.

## 이 저장소에 이미 들어있는 것 (git으로 모든 컴퓨터에 동기화됨)

| 경로 | 역할 |
|---|---|
| `.claude/skills/graphify/` | `/graphify` 스킬 (프로젝트 범위 설치) |
| `.claude/settings.json` | 훅: 세션 시작 시 자동 설치/그래프 갱신, 검색 전 그래프 우선 사용 안내 |
| `.claude/hooks/graphify-setup.sh` | graphify CLI가 없으면 자동 설치 → `graphify update .` 실행 |
| `CLAUDE.md`, `.claude/CLAUDE.md` | Claude에게 그래프를 먼저 조회하라는 규칙 |
| `graphify-out/graph.json`, `GRAPH_REPORT.md`, `graph.html` | 생성된 지식 그래프 (캐시 `graphify-out/cache/`는 제외) |

따라서 어느 컴퓨터든 이 저장소를 `git pull` 받고 Claude Code를 열면 자동으로 적용됩니다.
(조건: 해당 컴퓨터에 Python 3.10+ 와 `uv` 또는 `pipx`가 있어야 자동 설치가 성공합니다.)

## 컴퓨터별 1회 설정 (권장 — 다른 프로젝트에서도 `/graphify`를 쓰려면)

**macOS / Linux**
```bash
bash scripts/setup-graphify.sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-graphify.ps1
```

스크립트는 `uv tool install graphifyy` 후 `graphify install`을 실행해서
사용자 프로필(`~/.claude/skills/graphify`)에 스킬을 등록합니다.

## 자주 쓰는 명령

```
/graphify .                         # 그래프 새로 생성 (Claude Code 안에서)
graphify update .                   # 코드 변경분만 다시 반영 (LLM 비용 없음)
graphify query "질문"               # 그래프 질의
graphify path "A" "B"               # 두 개념 사이 연결 경로
graphify explain "개념"             # 개념 하나 설명
```

## 참고
- 코드 파싱은 로컬(tree-sitter)에서 처리되어 외부로 전송되지 않습니다. 문서/PDF/이미지의 의미 추출은 Claude 세션 모델을 사용합니다.
- 질의 로그는 `~/.cache/graphify-queries.log`에 남습니다. 끄려면 `GRAPHIFY_QUERY_LOG_DISABLE=1`.
- 제거: `graphify uninstall`
