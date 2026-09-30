# -*- coding: utf-8 -*-
"""docs/ を同じ Wi-Fi のスマホに配る（実機で確かめるためのサーバー）。

    python serve_lan.py          # またはエクスプローラーで serve_lan.bat をダブルクリック

- 起動すると、スマホで開く URL（http://この PC の LAN の IP:8000/）を表示する
- 配信は検証ハーネスと同じ uiharness/cdp.py の _QuietHandler を使う。
  キャッシュを無効にし（Cache-Control: no-store）、条件付き要求にも毎回 200 で返すので、
  docs/index.html を直したらスマホで再読み込みするだけで新しい版になる
  （5.4 追補 3 で、古い版を 304 で読み続けた問題を塞いだのと同じ仕組み）
- 止めるときはこのウィンドウで Ctrl+C
- http なので navigator.clipboard と navigator.share は動かない（コピーは選択状態になるだけ）
- Windows のファイアウォールで python.exe の受信を「プライベート」ネットワークに許可しておくこと
"""
import functools
import http.server
import os
import socket
import sys

PORT = 8000
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")

sys.path.insert(0, HERE)
from uiharness.cdp import _QuietHandler          # noqa: E402


class _Server(http.server.ThreadingHTTPServer):
    # 標準の HTTPServer は allow_reuse_address=1 で、Windows ではこれがあると
    # **使用中のポートにも黙ってもう 1 つ開けてしまう**（どちらに繋がるか分からなくなる）。
    # 外したうえで、Windows では占有を明示して、使用中なら確実に失敗させる
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def lan_ip():
    """外へ出るときに使うネットワークの IPv4。UDP の connect は宛先を決めるだけで、
    パケットは送らない（インターネットに繋がっていなくてもルーター宛ての経路があれば取れる）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 80))             # 文書用の予約アドレス。実際には送らない
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main():
    # 出力をファイルやパイプへ向けたときもため込まず 1 行ずつ出す（URL がすぐ見えるように）
    sys.stdout.reconfigure(line_buffering=True)
    if not os.path.isfile(os.path.join(DOCS, "index.html")):
        print("docs/index.html が見つかりません: " + DOCS)
        return 1
    try:
        srv = _Server(("0.0.0.0", PORT), functools.partial(_QuietHandler, directory=DOCS))
    except OSError as e:
        print("ポート %d が使用中のため起動できません。" % PORT)
        print("すでに serve_lan が動いていないか確かめてください（動いていればそのウィンドウの URL が使えます）。")
        print("止めるにはそのウィンドウで Ctrl+C、見つからなければ PowerShell で:")
        print("  Get-NetTCPConnection -LocalPort %d -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess }" % PORT)
        print("（詳細: %s）" % e)
        return 1
    ip = lan_ip()
    print("Make10 の docs/ を配っています（キャッシュ無効）。")
    if ip:
        print("スマホで開く URL: http://%s:%d/" % (ip, PORT))
    else:
        print("LAN の IP アドレスが分かりませんでした。PowerShell の ipconfig で IPv4 アドレスを調べ、")
        print("http://（その IP）:%d/ を開いてください。" % PORT)
    print("この PC で開く URL: http://127.0.0.1:%d/" % PORT)
    print("スマホは同じルーターの Wi-Fi につないでください。")
    print("止めるには、このウィンドウで Ctrl+C を押してください。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n止めました。")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
