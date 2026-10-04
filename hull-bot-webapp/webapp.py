"""Hull Suite 봇 웹 콘솔.

봇 폴더(bot.py가 있는 곳)에 webapp.py, webapp.html을 두고 `python webapp.py` 실행.
파이썬 표준 라이브러리만 사용. 이 PC 안(127.0.0.1)에서만 접속됩니다.
"""
import csv
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
BOT_DIR = Path(os.environ.get("BOT_DIR", HERE))
PORT = int(os.environ.get("WEB_PORT", 8765))
MODES = ("paper", "demo", "testnet", "live")
TOKEN = secrets.token_urlsafe(24)  # 실행할 때마다 새로 만듦. 다른 사이트가 이 콘솔에 주문을 보내지 못하게 함
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}

# ponytail: 실행 중인 봇은 메모리에만 기록. 웹 콘솔을 끄면 여기서 시작한 봇도 함께 멈추고,
# 콘솔 창을 X로 닫는 등 비정상 종료 시 봇이 추적 없이 남을 수 있음 (화면의 '마지막 로그' 시각으로 확인).
procs = {}  # mode -> {"p": Popen, "started": epoch}
lock = threading.Lock()


def decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp949", "replace")  # 한글 윈도우 콘솔 출력


def tail(path, n=300):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 300_000))
            return decode(f.read()).splitlines()[-n:]
    except FileNotFoundError:
        return []


def read_json(path):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        return {"_읽기오류": str(e)}


def mtime(path):
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def journal(mode, limit=500):
    path = BOT_DIR / f"journal_{mode}.csv"
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            rows = list(csv.reader(f))
    except FileNotFoundError:
        return {"header": [], "rows": []}
    if not rows:
        return {"header": [], "rows": []}
    return {"header": rows[0], "rows": rows[1:][-limit:][::-1]}  # 최신이 위


def status():
    bots = {}
    for m in MODES:
        e = procs.get(m)
        running = bool(e) and e["p"].poll() is None
        bots[m] = {
            "running": running,
            "pid": e["p"].pid if running else None,
            "started": e["started"] if e else None,
            "exit_code": e["p"].returncode if e and not running else None,
            "last_log": mtime(BOT_DIR / "logs" / f"bot_{m}.log"),
        }
    return {
        "bots": bots,
        "stop_file": (BOT_DIR / "STOP").exists(),
        "bot_dir": str(BOT_DIR),
        "bot_found": (BOT_DIR / "bot.py").exists(),
        "env_found": (BOT_DIR / ".env").exists(),
        "now": time.time(),
    }


def start(mode, decide_now=False, confirm=""):
    if mode == "live" and confirm != "LIVE":
        raise ValueError("실계정은 LIVE를 정확히 입력해야 시작합니다.")
    with lock:
        e = procs.get(mode)
        if e and e["p"].poll() is None:
            raise ValueError(f"{mode} 봇이 이미 실행 중입니다.")
        if not (BOT_DIR / "bot.py").exists():
            raise ValueError(f"{BOT_DIR}에 bot.py가 없습니다.")
        (BOT_DIR / "logs").mkdir(exist_ok=True)
        cmd = [sys.executable, "bot.py", "--mode", mode] + (["--decide-now"] if decide_now else [])
        with open(BOT_DIR / "logs" / f"console_{mode}.log", "ab") as out:
            out.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} 웹 콘솔에서 시작: {' '.join(cmd[1:])} =====\n".encode())
            out.flush()
            p = subprocess.Popen(
                cmd, cwd=BOT_DIR, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT, env=CHILD_ENV,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        try:
            # run_live.bat처럼 확인 문구를 요구하는 경우를 대비해 LIVE를 넘김(요구하지 않으면 무시됨)
            if mode == "live":
                p.stdin.write(b"LIVE\n")
            p.stdin.close()
        except OSError:
            pass
        procs[mode] = {"p": p, "started": time.time()}


def stop(mode):
    e = procs.get(mode)
    if not e or e["p"].poll() is not None:
        return
    p = e["p"]
    # Ctrl+C와 같은 효과. 보유 포지션과 거래소 손절 주문은 그대로 남음
    p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        p.wait(15)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def set_stop_file(on):
    path = BOT_DIR / "STOP"
    if on:
        path.touch()
    else:
        path.unlink(missing_ok=True)


def check_signal():
    bat = BOT_DIR / "check_signal.bat"
    if not bat.exists():
        raise ValueError("check_signal.bat이 없습니다.")
    cmd = ["cmd", "/c", bat.name] if os.name == "nt" else ["sh", bat.name]
    # 배치 끝의 pause가 있어도 멈추지 않도록 엔터를 넣어 줌
    r = subprocess.run(cmd, cwd=BOT_DIR, input=b"\r\n", capture_output=True, timeout=180, env=CHILD_ENV)
    return decode(r.stdout + r.stderr)


def save_config(text):
    try:
        cfg = json.loads(text)
    except ValueError as e:
        raise ValueError(f"JSON 형식 오류: {e}")
    if not isinstance(cfg, dict):
        raise ValueError("설정은 { } 객체여야 합니다.")
    lev = cfg.get("leverage", 2)
    if isinstance(lev, bool) or not isinstance(lev, (int, float)) or not 0 < lev <= 10:
        raise ValueError("leverage는 0 초과 10 이하여야 합니다.")
    sp = cfg.get("stop_pct", 0.05)
    if isinstance(sp, bool) or not isinstance(sp, (int, float)) or not 0 < sp < 1:
        raise ValueError("stop_pct는 0과 1 사이여야 합니다 (예: 0.05).")
    if cfg.get("mode", "paper") not in MODES:
        raise ValueError(f"mode는 {', '.join(MODES)} 중 하나여야 합니다.")
    path = BOT_DIR / "config.json"
    if path.exists():
        shutil.copy2(path, BOT_DIR / "config.json.bak")
    tmp = BOT_DIR / "config.json.tmp"
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", "utf-8")
    os.replace(tmp, path)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def guard(self):
        # Host 검사: DNS 리바인딩 차단. 토큰 헤더: 다른 웹사이트의 요청 차단
        if self.headers.get("Host") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            self.reply(403, {"error": "허용되지 않은 주소"})
            return False
        if self.path.startswith("/api/") and not secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN):
            self.reply(403, {"error": "토큰 불일치 — 페이지를 새로고침하세요"})
            return False
        return True

    def mode(self, value):
        if value not in MODES:  # 파일 경로에 들어가므로 반드시 검사 (.env 등 노출 방지)
            raise ValueError("알 수 없는 모드")
        return value

    def do_GET(self):
        if not self.guard():
            return
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                html = (HERE / "webapp.html").read_text("utf-8").replace("__TOKEN__", TOKEN)
                return self.reply(200, html.encode(), "text/html; charset=utf-8")
            if u.path == "/api/status":
                return self.reply(200, status())
            if u.path == "/api/journal":
                return self.reply(200, journal(self.mode(q.get("mode", "paper"))))
            if u.path == "/api/log":
                m = self.mode(q.get("mode", "paper"))
                kind = "console" if q.get("kind") == "console" else "bot"
                return self.reply(200, {"lines": tail(BOT_DIR / "logs" / f"{kind}_{m}.log")})
            if u.path == "/api/state":
                states = {p.name: read_json(p) for p in sorted(BOT_DIR.glob("state_*.json"))}
                return self.reply(200, {"states": states, "paper_account": read_json(BOT_DIR / "paper_account.json")})
            if u.path == "/api/config":
                p = BOT_DIR / "config.json"
                return self.reply(200, {"text": p.read_text("utf-8") if p.exists() else "{}"})
            self.reply(404, {"error": "없음"})
        except (ValueError, OSError) as e:
            self.reply(400, {"error": str(e)})

    def do_POST(self):
        if not self.guard():
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            p = self.path
            if p == "/api/start":
                start(self.mode(body.get("mode")), bool(body.get("decide_now")), body.get("confirm", ""))
            elif p == "/api/stop":
                stop(self.mode(body.get("mode")))
            elif p == "/api/stopfile":
                set_stop_file(bool(body.get("on")))
            elif p == "/api/check":
                return self.reply(200, {"output": check_signal()})
            elif p == "/api/config":
                save_config(body.get("text", ""))
            else:
                return self.reply(404, {"error": "없음"})
            self.reply(200, {"ok": True})
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            self.reply(400, {"error": str(e)})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"웹 콘솔: {url}  (봇 폴더: {BOT_DIR})\n끄려면 Ctrl+C — 여기서 시작한 봇도 함께 멈춥니다.")
    if not os.environ.get("NO_BROWSER"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for m in MODES:
            stop(m)
        server.server_close()


if __name__ == "__main__":
    main()
