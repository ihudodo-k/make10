# -*- coding: utf-8 -*-
"""Chrome DevTools Protocol への最小クライアント（標準ライブラリだけ）。

npm に依存しないのは、このリポジトリに Node の環境が無いため。Puppeteer や
Playwright を入れると「検証を回すために別のものを入れる」手順が増え、
結局また使い捨てになる。ここでやることは
「ページを開く／JS を評価する／画面の大きさを決める」の 3 つだけなので、
WebSocket を自前で話しても 200 行に収まる。

つまずいた点を 4 つ実装に入れてある（詳しくは verify_ui.py の冒頭）:
  - Chrome の実行パスは MAKE10_CHROME で上書きできる
  - file:// ではなく 127.0.0.1 の HTTP で開く（localStorage のため）
  - 画面の大きさは読み込みより先に決める（applyMetrics() の latch を避ける）
  - キャッシュを使わない（配信は常に 200・no-store、ブラウザは setCacheDisabled）
"""
import base64
import functools
import http.server
import json
import os
import socket
import socketserver
import struct
import subprocess
import threading
import time
import urllib.request

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_chrome():
    """Chrome の実行ファイルを探す。MAKE10_CHROME が最優先。"""
    env = os.environ.get("MAKE10_CHROME")
    if env:
        if not os.path.exists(env):
            raise RuntimeError("MAKE10_CHROME のパスが存在しない: " + env)
        return env
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    raise RuntimeError(
        "Chrome が見つからない。MAKE10_CHROME に実行ファイルのパスを入れて実行する")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """常に今のファイルを 200 で返す。

    標準の send_head() は If-Modified-Since を見て、ファイルの更新時刻が
    それ以前なら**応答ヘッダを書く前に** 304 を返す。更新時刻の新しい古い版
    （worktree で配ったものなど）をブラウザが持っていると、手元の新しい版が
    304 で握りつぶされる（5.4 で 5.3 のページに 5.4 のテストを当てていた）。
    end_headers() で Cache-Control を足すだけでは 304 は止まらないので、
    条件付きの要求ヘッダそのものを消してから標準の処理に渡す。
    """

    def send_head(self):
        del self.headers["If-Modified-Since"]
        del self.headers["If-None-Match"]
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


class _QuietServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, *a):
        pass


def serve(directory, port):
    """docs/ を 127.0.0.1 で配る。file:// だと localStorage が使えないため。"""
    srv = _QuietServer(("127.0.0.1", port),
                       functools.partial(_QuietHandler, directory=directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class WS:
    """CDP 用の WebSocket クライアント（クライアント → サーバはマスク必須）。"""

    def __init__(self, url, timeout=60):
        _, _, rest = url.partition("://")
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)))
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n" % (path, hostport, key))
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("WebSocket のハンドシェイクに失敗した")
            buf += chunk
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
        self.seq = 0

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("接続が切れた")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        data = b""
        while True:
            head = self._read(2)
            fin = head[0] & 0x80
            ln = head[1] & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read(8))[0]
            data += self._read(ln)
            if fin:
                break
        return json.loads(data.decode("utf-8"))

    def send(self, method, params=None):
        self.seq += 1
        payload = json.dumps({"id": self.seq, "method": method,
                              "params": params or {}}).encode("utf-8")
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            head = struct.pack(">BB", 0x81, 0x80 | n)
        elif n < 65536:
            head = struct.pack(">BBH", 0x81, 0x80 | 126, n)
        else:
            head = struct.pack(">BBQ", 0x81, 0x80 | 127, n)
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + body)
        return self.seq

    def call(self, method, params=None):
        """返事が来るまで読む。イベントは読み捨てる。

        受信は**途中で打ち切らない**。フレームの途中で抜けると以後の受信が
        崩れて固まるので、待ち合わせは必ず evaluate のポーリングで行う。
        """
        want = self.send(method, params)
        while True:
            msg = self.recv()
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(method + ": " +
                                       json.dumps(msg["error"], ensure_ascii=False))
                return msg.get("result", {})


class Chrome:
    """headless Chrome を 1 つ立ち上げ、最初のページに繋ぐ。"""

    def __init__(self, port, profile):
        self.exe = find_chrome()
        os.makedirs(profile, exist_ok=True)
        self.proc = subprocess.Popen(
            [self.exe, "--headless=new", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-extensions",
             "--remote-debugging-port=%d" % port,
             "--user-data-dir=" + profile, "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "http://127.0.0.1:%d" % port
        for _ in range(160):
            try:
                with urllib.request.urlopen(base + "/json/version", timeout=2) as r:
                    self.version = json.load(r)["Browser"]
                break
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("Chrome が終了した（プロファイルが使用中かもしれない）")
                time.sleep(0.25)
        else:
            raise RuntimeError("Chrome が起動しない")
        with urllib.request.urlopen(base + "/json/list", timeout=5) as r:
            pages = [t for t in json.load(r) if t["type"] == "page"]
        self.ws = WS(pages[0]["webSocketDebuggerUrl"])
        self.ws.call("Runtime.enable")
        self.ws.call("Page.enable")
        # ブラウザのキャッシュを使わない。CDP のセッション（ここで繋ぐ 1 本）ごとの
        # 設定なので、セッションを作り直すならそこでも呼ぶこと
        self.ws.call("Network.enable")
        self.ws.call("Network.setCacheDisabled", {"cacheDisabled": True})

    def on_new_document(self, source):
        """読み込みのたびに先頭で走る script を仕込む（localStorage の種まき用）。"""
        return self.ws.call("Page.addScriptToEvaluateOnNewDocument",
                            {"source": source})["identifier"]

    def remove_on_new_document(self, ident):
        self.ws.call("Page.removeScriptToEvaluateOnNewDocument",
                     {"identifier": ident})

    def metrics(self, width, height):
        """画面の大きさ。**読み込みより先に**呼ぶこと（DESIGN.md 2-2）。"""
        self.ws.call("Emulation.setDeviceMetricsOverride",
                     {"width": width, "height": height,
                      "deviceScaleFactor": 1, "mobile": True})

    def goto(self, url, ready="complete|string", timeout=40):
        self.ws.call("Page.navigate", {"url": url})
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = self.ws.call("Runtime.evaluate", {
                    "expression": "document.readyState+'|'+(typeof APP_VERSION)",
                    "returnByValue": True})
                if r["result"].get("value") == ready:
                    return
            except Exception:
                pass
            time.sleep(0.2)
        raise RuntimeError("ページが読み込めない: " + url)

    def ev(self, expr):
        r = self.ws.call("Runtime.evaluate",
                         {"expression": expr, "returnByValue": True,
                          "userGesture": True})
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError("JS 例外: " + json.dumps(
                d.get("exception", d), ensure_ascii=False)[:500] + "  式: " + expr[:120])
        return r["result"].get("value")

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
