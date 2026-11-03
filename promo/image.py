# -*- coding: utf-8 -*-
"""その日の投稿に付ける画像（1200×675 の PNG）を作る（promo/README.md）。

  python promo/image.py --no 8 --out 8.png     #8 の画像を作る（数字はページの列から読む）

- 主役は穴埋めの式「6 ? 8 ? 2 ? 3 = 10」。下に見出し「Allowed」と使える記号の段（本編の盤と同じ字・並び。まとめて中央）と、
  決まりの 1 行「Use all four digits, in order.」。上に小さく番号と名前
- 色は --paper・--dim・--gold（ダークの値）。**金は式の 10 だけ**
- 制約がある日は、使えない記号を段から消す（common.allowed_syms。型 B の文の記号の並びと同じ）。決まりの行はどの日も同じ
- **答えは載せない。** 渡すのは番号・4 つの数字・制約だけ。出来た画面の文字が決まった並びと同じことも、撮る前に確かめる
- 描くのは headless Chrome（字間と記号の字をページと同じ CSS で描ける。Actions の ubuntu-latest には入っている）
- 字は本物の Zen Kaku Gothic New。google/fonts の決まったコミットから取り、SHA-256 を確かめる（リポジトリには入れない）。
  読めなければ別の字で描かずに失敗にする
"""
import argparse
import base64
import hashlib
import html
import os
import re
import shutil
import socket
import struct
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))
import common as c          # noqa: E402

WIDTH, HEIGHT = 1200, 675
MAX_BYTES = 5 * 1024 * 1024         # X の画像の上限
RULE = "Use all four digits, in order."
HEADING = "Allowed"
EQ_MAX = 1080                         # 式の幅の上限
FONT_COMMIT = "ba225958c40ae6268a256861d80355a84b26e535"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/%s/ofl/zenkakugothicnew/ZenKakuGothicNew-%%s.ttf" % FONT_COMMIT
FONTS = {"Medium": (500, "651a3f7280b7f36262601ee76d8388a8dc4372dcc67aff025a608939a562b525"),
         "Bold": (700, "0081cedabc4921982fcd061f845a005664ac7fb642af2dd34b4007bc63ccd235")}
TIMEOUT = 30                        # 字の読み込みを待つ秒数

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(w)dpx;height:%(h)dpx;overflow:hidden}
body{background:#121213;color:#FFFFFF;font-family:"Zen Kaku Gothic New";font-weight:500;position:relative}
.head,.eq,.syms,.rule{position:absolute;left:0;right:0;display:flex;justify-content:center;white-space:nowrap}
.head{top:44px;align-items:baseline;gap:16px;font-size:36px;font-weight:700;line-height:1}
.head .no,.head .d{color:#9A9CA1}
.head .no{margin-right:10px;letter-spacing:.04em}
.head .d{font-size:24px;letter-spacing:.22em}
.eq{top:150px;align-items:center;gap:24px;font-size:140px;font-weight:700;line-height:1}
.eq .q,.eq .e{color:#9A9CA1}
.eq .g{color:#DCBD6E;margin-left:10px}
.syms{top:388px;align-items:center;gap:30px;font-size:68px;font-weight:700;line-height:1}
.syms .h{font-size:30px;font-weight:500;color:#9A9CA1;margin-right:14px}
.rule{top:544px;font-size:38px;color:#9A9CA1;letter-spacing:.04em;line-height:1}
""" % {"w": WIDTH, "h": HEIGHT}


def check_input(n, digits, rc):
    """番号・4 つの数字・制約のほかは受け取らない（答えや式が紛れ込まない）"""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise c.Fail("画像の番号が違う: %r" % (n,))
    if not isinstance(digits, str) or not re.fullmatch(r"[0-9]{4}", digits):
        raise c.Fail("画像の数字が 4 桁でない: %r" % (digits,))
    c.allowed_syms(rc)                  # 分からない制約なら Fail


def expected_text(n, digits, rc):
    """画面に出る文字の全部（空白を除いて上から順）"""
    return re.sub(r"\s", "", "#%dMake10DAILY%s=10%s%s%s" % (
        n, "?".join(digits), HEADING, c.allowed_syms(rc), RULE))


def build_html(n, digits, rc):
    check_input(n, digits, rc)
    face = "".join('@font-face{font-family:"Zen Kaku Gothic New";font-weight:%d;src:url("%s.ttf") format("truetype")}'
                   % (w, name) for name, (w, _) in FONTS.items())
    eq = '<span class="q">?</span>'.join("<span>%s</span>" % d for d in digits)
    syms = "".join('<span class="s">%s</span>' % html.escape(s) for s in c.allowed_syms(rc))
    head = '<span class="h">%s</span>' % html.escape(HEADING)
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Make10</title><style>%s%s</style></head><body>'
            '<div class="head"><span class="no">#%d</span><span>Make10</span><span class="d">DAILY</span></div>'
            '<div class="eq">%s<span class="e">=</span><span class="g">10</span></div>'
            '<div class="syms">%s%s</div><div class="rule">%s</div></body></html>'
            % (face, CSS, n, eq, head, syms, html.escape(RULE)))


def font_dir():
    return os.environ.get("PROMO_FONT_DIR") or os.path.join(tempfile.gettempdir(), "make10-promo-fonts")


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def fetch_fonts(ddir):
    """字を ddir に揃える。ある分は中身を確かめて使い、無い分は取る。どちらも SHA-256 が合わなければ止める"""
    os.makedirs(ddir, exist_ok=True)
    for name, (_, want) in FONTS.items():
        path = os.path.join(ddir, name + ".ttf")
        if os.path.exists(path) and sha256(path) == want:
            continue
        tmp = path + ".tmp"
        try:
            with urllib.request.urlopen(FONT_URL % name, timeout=60) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as e:
            raise c.Fail("字を取れない（%s）: %s" % (name, e))
        if sha256(tmp) != want:
            os.remove(tmp)
            raise c.Fail("字の SHA-256 が違う（%s）" % name)
        os.replace(tmp, path)


def png_size(b):
    """PNG の (幅, 高さ)。PNG でなければ None"""
    if len(b) < 24 or b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", b[16:24])


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def render(page_html, ddir, want_text):
    """page_html を Chrome で開いて撮る。PNG のバイト列。字が読めない・文字が違うときは Fail"""
    from uiharness import cdp
    work = tempfile.mkdtemp(prefix="make10-promo-image-")
    srv = chrome = None
    try:
        with open(os.path.join(work, "index.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        for name in FONTS:
            shutil.copy(os.path.join(ddir, name + ".ttf"), work)
        srv = cdp.serve(work, free_port())
        # Actions の ubuntu はサンドボックスが使えない
        chrome = cdp.Chrome(free_port(), os.path.join(work, "profile"),
                            args=("--no-sandbox",) if sys.platform.startswith("linux") else ())
        chrome.ws.call("Emulation.setDeviceMetricsOverride",
                       {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": False})
        chrome.goto("http://127.0.0.1:%d/index.html" % srv.server_address[1], ready="complete|undefined")
        end = time.time() + TIMEOUT
        while time.time() < end:
            st = chrome.ev("[...document.fonts].map(f=>f.status).join()+'|'+document.fonts.status")
            if st == "loaded,loaded|loaded" or "error" in st:
                break
            time.sleep(0.1)
        if st != "loaded,loaded|loaded":
            raise c.Fail("字が読めない（%s）" % st)
        got = re.sub(r"\s", "", chrome.ev("document.body.innerText"))
        width = chrome.ev("Math.ceil(Math.max(...[...document.querySelector('.eq').children].map(e=>e.getBoundingClientRect().right))"
                          "-Math.min(...[...document.querySelector('.eq').children].map(e=>e.getBoundingClientRect().left)))")
        if width > EQ_MAX:
            raise c.Fail("式の幅が %dpx（%dpx まで）" % (width, EQ_MAX))
        if got != want_text:
            raise c.Fail("画面の文字が決まった並びと違う: %r" % got)
        png = base64.b64decode(chrome.ws.call("Page.captureScreenshot", {"format": "png"})["data"])
    finally:
        if chrome:
            chrome.close()
        if srv:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(work, ignore_errors=True)
    if png_size(png) != (WIDTH, HEIGHT):
        raise c.Fail("画像の寸法が違う: %s" % (png_size(png),))
    if len(png) > MAX_BYTES:
        raise c.Fail("画像が大きすぎる: %d バイト" % len(png))
    return png


def make(n, digits, rc):
    """その日の画像（PNG のバイト列）。作れないときは Fail（理由つき）"""
    page = build_html(n, digits, rc)
    ddir = font_dir()
    try:
        fetch_fonts(ddir)
        return render(page, ddir, expected_text(n, digits, rc))
    except c.Fail:
        raise
    except Exception as e:      # Chrome が無い・起動しない・途中で切れた など
        raise c.Fail("画像を作れない: %s: %s" % (type(e).__name__, e))


def main(argv=None):
    ap = argparse.ArgumentParser(description="その日の投稿に付ける画像を作る")
    ap.add_argument("--no", type=int, required=True, help="問題番号（数字はページの列から読む）")
    ap.add_argument("--out", required=True, help="書き出す PNG のパス")
    a = ap.parse_args(argv)
    try:
        _, rows = c.load_page()
        if not 1 <= a.no <= len(rows):
            raise c.Fail("#%d は列に無い" % a.no)
        png = make(a.no, rows[a.no - 1]["digits"], rows[a.no - 1]["rc"])
    except c.Fail as e:
        print("失敗: %s" % e)
        return 1
    with open(a.out, "wb") as f:
        f.write(png)
    print("%s（#%d %s。%d バイト）" % (a.out, a.no, rows[a.no - 1]["digits"], len(png)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
