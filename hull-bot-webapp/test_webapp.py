"""웹 콘솔 자체 점검: 가짜 bot.py로 시작·정지·LIVE 확인·설정 검사·보안 검사. 실행: python test_webapp.py"""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

bot = Path(tempfile.mkdtemp())
os.environ.update(BOT_DIR=str(bot), WEB_PORT="18765", NO_BROWSER="1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import webapp  # noqa: E402

(bot / "bot.py").write_text(
    "import sys, time, pathlib\n"
    "mode = sys.argv[sys.argv.index('--mode') + 1]\n"
    "pathlib.Path('logs').mkdir(exist_ok=True)\n"
    "line = sys.stdin.readline().strip()\n"
    "open(f'logs/bot_{mode}.log', 'a', encoding='utf-8').write(f'시작 {mode} stdin={line} args={sys.argv[1:]}\\n')\n"
    "while True: time.sleep(0.2)\n", "utf-8")
(bot / "journal_paper.csv").write_text("﻿time,event,price\n2026-10-01,진입,60000\n2026-10-02,청산,61000\n", "utf-8")
(bot / "config.json").write_text('{"mode": "paper", "leverage": 2, "stop_pct": 0.05}', "utf-8")
(bot / "check_signal.bat").write_text(f'"{sys.executable}" -c "print(\'신호: 상승\')"\n', "utf-8")
(bot / ".env").write_text("BYBIT_API_SECRET=secret", "utf-8")
(bot / "state_BTCUSDT.json").write_text('{"in_position": false}', "utf-8")

server = webapp.ThreadingHTTPServer(("127.0.0.1", 18765), webapp.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:18765"


def call(path, body=None, token=webapp.TOKEN, host=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode())
    req.add_header("X-Token", token)
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait_log(mode):
    for _ in range(50):
        p = bot / "logs" / f"bot_{mode}.log"
        if p.exists() and p.read_text("utf-8"):
            return p.read_text("utf-8")
        time.sleep(0.1)
    raise AssertionError(f"{mode} 로그 없음")


# 보안
assert call("/api/status", token="wrong")[0] == 403
assert call("/api/status", host="evil.example:18765")[0] == 403
assert call("/api/log?mode=../.env")[0] == 400
assert "secret" not in json.dumps(call("/api/state")[1])

# 기록·상태·신호
s, j = call("/api/journal?mode=paper")
assert j["header"] == ["time", "event", "price"] and j["rows"][0][1] == "청산", j
assert call("/api/state")[1]["states"]["state_BTCUSDT.json"] == {"in_position": False}
assert "신호: 상승" in call("/api/check", {})[1]["output"]

# 시작·정지
assert call("/api/start", {"mode": "demo", "decide_now": True}) == (200, {"ok": True})
assert "--decide-now" in wait_log("demo")
assert call("/api/status")[1]["bots"]["demo"]["running"]
assert call("/api/start", {"mode": "demo"})[0] == 400  # 중복 실행 거부
assert call("/api/start", {"mode": "live", "confirm": "live"})[0] == 400  # 정확히 LIVE
assert call("/api/start", {"mode": "live", "confirm": "LIVE"})[0] == 200
assert "stdin=LIVE" in wait_log("live")
for m in ("demo", "live"):
    assert call("/api/stop", {"mode": m})[0] == 200
    assert not call("/api/status")[1]["bots"][m]["running"]

# STOP 파일
call("/api/stopfile", {"on": True}); assert (bot / "STOP").exists()
call("/api/stopfile", {"on": False}); assert not (bot / "STOP").exists()

# 설정 검사
assert call("/api/config", {"text": "{bad"})[0] == 400
assert call("/api/config", {"text": '{"leverage": 20}'})[0] == 400
assert call("/api/config", {"text": '{"mode": "real"}'})[0] == 400
assert call("/api/config", {"text": '{"mode": "demo", "leverage": 2, "stop_pct": 0.05}'})[0] == 200
assert json.loads((bot / "config.json").read_text("utf-8"))["mode"] == "demo"
assert json.loads((bot / "config.json.bak").read_text("utf-8"))["mode"] == "paper"

# 페이지에 토큰 주입
with urllib.request.urlopen(BASE + "/") as r:
    assert webapp.TOKEN in r.read().decode()

server.shutdown()
print("모든 점검 통과")
