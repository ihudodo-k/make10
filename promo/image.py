# -*- coding: utf-8 -*-
"""その日の投稿に付ける画像（縦長 1080×1350・4:5）を作る（promo/README.md）。紙の型は JPEG（品質 90）、無地の型は PNG。

  python promo/image.py --no 8 --out 8.jpg              #8 の画像を作る（数字はページの列から読む。型は番号で決まる）
  python promo/image.py --no 8 --style 2 --out 8.jpg    型を決めて作る（見本を作るため）
  （拡張子は形式に合わせて自分で付ける。形式は kind() で分かる）

- 中身は 4 つだけ: 大きな穴埋めの式「6 ? 8 ? 2 ? 3 = 10」・その下の小さな「Use + − × ÷ ^ ! ( )」・
  並べ替えの禁止の 1 行「Keep the order. Don't swap the digits.」（RULE）・右下の小さな「Make10 #8」
- 制約がある日は、使えない記号を「Use」の行から抜く（common.allowed_syms）
- **答えや手がかりは載せない。** 渡すのは番号・4 つの数字・制約だけ。出来た画面の文字が決まった並びと同じことも、撮る前に確かめる
- 見た目の型は 3 つ（STYLES）。問題番号で順に回す（style_of。#1 が型 1・#2 が型 2・#3 が型 4・#4 が型 1）:
    1 白い紙の質感 ＋ 青いマーカーの手書き / 2 生成りの紙の質感 ＋ 赤いペンの手書き / 4 淡い青の地 ＋ 黒の手書き
  （型 3「白地 ＋ 黒の太字」は見本の後に外した。番号は記録の型の名前なので詰めない）
- 手書きの字は「1」に上のはね（旗）があるものを選ぶ（「10」が「l0」・「Make10」が「Makel0」に読めないように）。
  記号の行の「^」と「−」は、字の大きさを上げて形がはっきり見えるようにする（STYLES の caret・minus）
- 紙の質感は SVG の feTurbulence（決まった seed）で描く。写真や他人の画像は使わない。手書きの揺れも決まった並びで、毎回同じ絵になる
- 紙の型は粒があるので PNG だと約 1.7MB になる。JPEG の品質 90 にする（STYLES の jpeg）
- 描くのは headless Chrome（Actions の ubuntu-latest には入っている）
- 字は google/fonts の決まったコミットから取り、SHA-256 を確かめる（リポジトリには入れない）。
  読めない・画面に出す字のどれかを持っていない（別の字で描かれる）ときは、描かずに失敗にする。
  持っているかは、字のファイルの cmap（字 → 字形の表）を読んで確かめる（font_lacks）
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

WIDTH, HEIGHT = 1080, 1350
MAX_BYTES = 5 * 1024 * 1024         # X の画像の上限
USE = "Use"
RULE = "Keep the order. Don't swap the digits."   # 並べ替えは禁止（並べ替えた答えの返信が来たため）
FOOT = "Make10 #%d"
EQ_MAX = 960                        # 式の幅の上限（左右に 60px ずつ残す）
TIMEOUT = 30                        # 字の読み込みを待つ秒数

# 字。名前 → (google/fonts のコミット, その中のパス, CSS の font-weight, SHA-256)
FONT_URL = "https://raw.githubusercontent.com/google/fonts/%s/%s"
HAND = "06bfe0d62a98375cb09c942fa18e68bd32cff057"
FONTS = {
    # 手書き（どれも OFL）。数字・?・+ − × ÷ ^ ! ( ) と英字を持ち、「1」に上のはねがあるものから選んだ（README）
    "CaveatBrush-Regular": (HAND, "ofl/caveatbrush/CaveatBrush-Regular.ttf", "400",
                            "e565bd7bffd895ca64f8d1cb77c816b9b38d9c010246386a07c9648592f6f282"),
    "Caveat": (HAND, "ofl/caveat/Caveat%5Bwght%5D.ttf", "400 700",
               "0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988"),
    "Itim-Regular": (HAND, "ofl/itim/Itim-Regular.ttf", "400",
                     "9164d7eb92ca717b53b07193e3445c96782222d24215151b8d2851b576b17645"),
}

# 型。地の色・紙の質感（None は無地）・字・字の色・大きさ・手書きの揺れ・インクのにじみ
STYLES = {
    # use は記号の行の字の大きさ（見本の後に 64 から 1.3 倍）。uwt はその行の太さ。caret・minus は ^ と − だけの大きさの倍率
    1: {"name": "white paper + blue marker", "bg": "#FBFAF6", "paper": "white", "font": "CaveatBrush-Regular", "wt": 400, "ink": "#1F4FC4",
        "eq": 160, "use": 84, "uwt": 400, "caret": 1.6, "minus": 1.3, "foot": 40, "rough": 2.2, "jpeg": 90},
    2: {"name": "cream paper + red pen", "bg": "#F3EAD6", "paper": "cream", "font": "Caveat", "wt": 600, "ink": "#BF2A2A",
        "eq": 158, "use": 84, "uwt": 700, "caret": 1.6, "minus": 1.3, "foot": 40, "rough": 1.6, "jpeg": 90},
    4: {"name": "light blue + black hand", "bg": "#DCEAF5", "paper": None, "font": "Itim-Regular", "wt": 400, "ink": "#1B1B1B",
        "eq": 136, "use": 84, "uwt": 400, "caret": 1.0, "minus": 1.3, "foot": 40, "rough": 1.4, "jpeg": None},
}
ORDER = (1, 2, 4)                   # 回す順

# 手書きの揺れ（度・px）。文字の位置ごとに決まった値を順に使う（乱数は使わない）
JITTER = [(-2.5, 3), (1.8, -4), (-1.2, 2), (2.4, -2), (-1.8, 5), (1.2, -3), (-2.2, 1), (2.0, 4), (-1.0, -5), (1.6, 2)]

PAPER = {
    # 細かい粒（紙の目）と、大きなむら
    # (細かさ, 重ね, seed, 濃さ, 底上げ)。影の濃さ = 濃さ × (0.5 − ノイズ) ＋ 底上げ
    "white": (("0.9", 4, 11, 0.30, 0.015), ("0.006 0.02", 3, 5, 0.12, 0.0)),
    "cream": (("0.85", 4, 13, 0.36, 0.025), ("0.005 0.018", 3, 17, 0.16, 0.0)),
}


def style_of(n):
    """その番号の画像の型（ORDER を順に）。#1 が 1・#2 が 2・#3 が 4・#4 が 1"""
    return ORDER[(n - 1) % len(ORDER)]


def check_input(n, digits, rc, style):
    """番号・4 つの数字・制約・型のほかは受け取らない（答えや式が紛れ込まない）"""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise c.Fail("画像の番号が違う: %r" % (n,))
    if not isinstance(digits, str) or not re.fullmatch(r"[0-9]{4}", digits):
        raise c.Fail("画像の数字が 4 桁でない: %r" % (digits,))
    if style not in STYLES:
        raise c.Fail("画像の型が違う: %r" % (style,))
    c.allowed_syms(rc)                  # 分からない制約なら Fail


def expected_text(n, digits, rc):
    """画面に出る文字の全部（空白を除いて上から順）"""
    return re.sub(r"\s", "", "%s=10%s%s%s%s" % ("?".join(digits), USE, c.allowed_syms(rc), RULE, FOOT % n))


def paper_svg(kind):
    """紙の質感（決まった seed の feTurbulence）。kind が None なら無地"""
    if not kind:
        return ""
    layers = []
    for i, (freq, octaves, seed, k, base) in enumerate(PAPER[kind]):
        layers.append(
            '<filter id="p%d" x="0" y="0" width="100%%" height="100%%"><feTurbulence type="fractalNoise" baseFrequency="%s" '
            'numOctaves="%d" seed="%d" stitchTiles="stitch"/><feColorMatrix type="matrix" '
            'values="0 0 0 0 0.25  0 0 0 0 0.2  0 0 0 0 0.12  %s 0 0 0 %s"/></filter>'
            '<rect width="100%%" height="100%%" filter="url(#p%d)"/>' % (i, freq, octaves, seed, -k, round(k * 0.5 + base, 4), i))
    return ('<svg class="paper" width="%d" height="%d" xmlns="http://www.w3.org/2000/svg">%s</svg>'
            % (WIDTH, HEIGHT, "".join(layers)))


def ink_filter(scale):
    """字の縁を少し揺らす（インクのにじみ）。scale が 0 なら無し"""
    if not scale:
        return ""
    return ('<svg width="0" height="0" style="position:absolute"><filter id="ink"><feTurbulence type="fractalNoise" '
            'baseFrequency="0.9" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="%s" '
            'xChannelSelector="R" yChannelSelector="G"/></filter></svg>' % scale)


def css(st, family):
    return """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(w)dpx;height:%(h)dpx;overflow:hidden}
body{background:%(bg)s;color:%(ink)s;font-family:"%(fam)s";font-weight:%(wt)s;position:relative}
.paper{position:absolute;left:0;top:0}
.ink{position:absolute;left:0;top:0;width:100%%;height:100%%;%(filter)s}
.eq,.use,.rule{position:absolute;left:0;right:0;display:flex;justify-content:center;align-items:center;white-space:nowrap;line-height:1}
.eq{top:500px;gap:%(gap)dpx;font-size:%(eq)dpx}
.use{top:800px;gap:%(ugap)dpx;font-size:%(use)dpx}
.use{font-weight:%(uwt)s}
.use .h{margin-right:%(ugap)dpx}
.use .cr{font-size:%(caret)gem;position:relative;top:.16em}
.use .mi{font-size:%(minus)gem}
.rule{top:930px;font-size:%(rule)dpx;font-weight:%(uwt)s}
.foot{position:absolute;right:64px;bottom:56px;font-size:%(foot)dpx;opacity:.62;white-space:nowrap;line-height:1}
.eq span,.use span{display:inline-block}
""" % {"w": WIDTH, "h": HEIGHT, "bg": st["bg"], "ink": st["ink"], "fam": family, "wt": st["wt"],
       "filter": "filter:url(#ink);" if st["rough"] else "", "eq": st["eq"], "use": st["use"], "uwt": st["uwt"], "caret": st["caret"], "minus": st["minus"], "foot": st["foot"],
       "rule": round(st["use"] * 0.7), "gap": st["eq"] // 6, "ugap": st["use"] // 3}


def jitter(i, k=1.0):
    r, y = JITTER[i % len(JITTER)]
    return ' style="transform:translateY(%gpx) rotate(%gdeg)"' % (y * k, r * k)


def font_of(st):
    if not st["font"]:
        raise c.Fail("手書きの字が決まっていない")
    return st["font"]


def build_html(n, digits, rc, style):
    check_input(n, digits, rc, style)
    st = STYLES[style]
    name = font_of(st)
    commit, path, weight, _ = FONTS[name]
    face = '@font-face{font-family:"F";font-weight:%s;src:url("%s.ttf") format("truetype")}' % (weight, name)
    k = 1.0
    parts = []
    for i, d in enumerate(digits):
        if i:
            parts.append('<span class="q"%s>?</span>' % jitter(2 * i - 1, k))
        parts.append('<span%s>%s</span>' % (jitter(2 * i, k), d))
    eq = "".join(parts) + '<span%s>=</span><span%s>10</span>' % (jitter(7, k), jitter(8, k * 0.6))
    cls = {"^": ' class="cr"', "−": ' class="mi"'}
    syms = "".join('<span%s%s>%s</span>' % (cls.get(s, ""), jitter(i + 3, k * 0.6), html.escape(s))
                   for i, s in enumerate(c.allowed_syms(rc)))
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Make10</title><style>%s%s</style></head><body>'
            '%s%s<div class="ink"><div class="eq">%s</div><div class="use"><span class="h">%s</span>%s</div>'
            '<div class="rule">%s</div><div class="foot">%s</div></div></body></html>'
            % (face, css(st, "F"), paper_svg(st["paper"]), ink_filter(st["rough"]), eq, html.escape(USE), syms,
               html.escape(RULE), html.escape(FOOT % n)))


def font_dir():
    return os.environ.get("PROMO_FONT_DIR") or os.path.join(tempfile.gettempdir(), "make10-promo-fonts")


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def fetch_font(ddir, name):
    """字 name を ddir に揃える。あれば中身を確かめて使い、無ければ取る。どちらも SHA-256 が合わなければ止める"""
    commit, path, _, want = FONTS[name]
    os.makedirs(ddir, exist_ok=True)
    dest = os.path.join(ddir, name + ".ttf")
    if os.path.exists(dest) and sha256(dest) == want:
        return dest
    tmp = dest + ".tmp"
    try:
        with urllib.request.urlopen(FONT_URL % (commit, path), timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as e:
        raise c.Fail("字を取れない（%s）: %s" % (name, e))
    if sha256(tmp) != want:
        os.remove(tmp)
        raise c.Fail("字の SHA-256 が違う（%s）" % name)
    os.replace(tmp, dest)
    return dest


def png_size(b):
    """PNG の (幅, 高さ)。PNG でなければ None"""
    if len(b) < 24 or b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", b[16:24])


def jpeg_size(b):
    """JPEG の (幅, 高さ)。JPEG でなければ None（印を順にたどって SOF を探す）"""
    if b[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            return None
        m = b[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        ln = struct.unpack(">H", b[i + 2:i + 4])[0]
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + ln
    return None


def kind(b):
    """画像の形式（"png" か "jpeg"）。どちらでもなければ None"""
    return "png" if png_size(b) else "jpeg" if jpeg_size(b) else None


def size(b):
    """画像の (幅, 高さ)。PNG でも JPEG でもなければ None"""
    return png_size(b) or jpeg_size(b)


MIME = {"png": "image/png", "jpeg": "image/jpeg"}
EXT = {"png": ".png", "jpeg": ".jpg"}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def font_chars(path):
    """字のファイル（TrueType）が字形を持っている字（コードポイントの集合）。cmap の形式 4 と 12 を読む。
    字形の番号が 0（.notdef）の字は持っていないとみなす。
    （ブラウザで幅を比べる確かめは、全角の字がどの後ろの字でも 1em になって見分けられないのでやめた）"""
    with open(path, "rb") as f:
        b = f.read()
    n = struct.unpack(">H", b[4:6])[0]
    tabs = {b[12 + 16 * i:16 + 16 * i]: struct.unpack(">II", b[20 + 16 * i:28 + 16 * i]) for i in range(n)}
    if b"cmap" not in tabs:
        raise c.Fail("字に cmap が無い")
    off = tabs[b"cmap"][0]
    out = set()
    for i in range(struct.unpack(">H", b[off + 2:off + 4])[0]):
        pid, eid, so = struct.unpack(">HHI", b[off + 4 + 8 * i:off + 12 + 8 * i])
        if (pid, eid) not in ((0, 3), (0, 4), (3, 1), (3, 10)):    # Unicode の表だけ
            continue
        t = off + so
        fmt = struct.unpack(">H", b[t:t + 2])[0]
        if fmt == 4:
            seg = struct.unpack(">H", b[t + 6:t + 8])[0] // 2
            ends = struct.unpack(">%dH" % seg, b[t + 14:t + 14 + 2 * seg])
            starts = struct.unpack(">%dH" % seg, b[t + 16 + 2 * seg:t + 16 + 4 * seg])
            deltas = struct.unpack(">%dh" % seg, b[t + 16 + 4 * seg:t + 16 + 6 * seg])
            ro = t + 16 + 6 * seg
            ranges = struct.unpack(">%dH" % seg, b[ro:ro + 2 * seg])
            for k in range(seg):
                for cp in range(starts[k], ends[k] + 1):
                    if cp == 0xFFFF:
                        continue
                    if ranges[k] == 0:
                        g = (cp + deltas[k]) & 0xFFFF
                    else:
                        at = ro + 2 * k + ranges[k] + 2 * (cp - starts[k])
                        g = struct.unpack(">H", b[at:at + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    if g:
                        out.add(cp)
        elif fmt == 12:
            for k in range(struct.unpack(">I", b[t + 12:t + 16])[0]):
                a, z, g0 = struct.unpack(">III", b[t + 16 + 12 * k:t + 28 + 12 * k])
                out.update(cp for cp in range(a, z + 1) if g0 + cp - a)
    return out


def font_lacks(path, text):
    """text の字（空白を除く）のうち、字のファイルが持っていないもの（並びは text の順・重ねない）"""
    have = font_chars(path)
    return "".join(dict.fromkeys(ch for ch in text if not ch.isspace() and ord(ch) not in have))


def render(page_html, font_path, want_text, jpeg=None):
    """page_html を Chrome で開いて撮る。画像のバイト列（jpeg に品質を渡すと JPEG、None なら PNG）。字が読めない・字が足りない・文字が違うときは Fail"""
    from uiharness import cdp
    work = tempfile.mkdtemp(prefix="make10-promo-image-")
    srv = chrome = None
    try:
        with open(os.path.join(work, "index.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        shutil.copy(font_path, work)
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
            if st == "loaded|loaded" or "error" in st:
                break
            time.sleep(0.1)
        if st != "loaded|loaded":
            raise c.Fail("字が読めない（%s）" % st)
        got = re.sub(r"\s", "", chrome.ev("document.body.innerText"))
        width = chrome.ev("Math.ceil(Math.max(...[...document.querySelector('.eq').children].map(e=>e.getBoundingClientRect().right))"
                          "-Math.min(...[...document.querySelector('.eq').children].map(e=>e.getBoundingClientRect().left)))")
        if width > EQ_MAX:
            raise c.Fail("式の幅が %dpx（%dpx まで）" % (width, EQ_MAX))
        if got != want_text:
            raise c.Fail("画面の文字が決まった並びと違う: %r" % got)
        shot = {"format": "jpeg", "quality": jpeg} if jpeg else {"format": "png"}
        png = base64.b64decode(chrome.ws.call("Page.captureScreenshot", shot)["data"])
    finally:
        if chrome:
            chrome.close()
        if srv:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(work, ignore_errors=True)
    if kind(png) != ("jpeg" if jpeg else "png"):
        raise c.Fail("画像の形式が違う: %s" % kind(png))
    if size(png) != (WIDTH, HEIGHT):
        raise c.Fail("画像の寸法が違う: %s" % (size(png),))
    if len(png) > MAX_BYTES:
        raise c.Fail("画像が大きすぎる: %d バイト" % len(png))
    return png


def make(n, digits, rc, style=None):
    """その日の画像（PNG か JPEG のバイト列。形式は kind()）。型を省くと番号で決まる。作れないときは Fail（理由つき）"""
    style = style_of(n) if style is None else style
    page = build_html(n, digits, rc, style)
    try:
        path = fetch_font(font_dir(), font_of(STYLES[style]))
        lacks = font_lacks(path, expected_text(n, digits, rc))
        if lacks:
            raise c.Fail("字に無い文字がある（別の字で描かれる）: %r" % lacks)
        return render(page, path, expected_text(n, digits, rc), STYLES[style]["jpeg"])
    except c.Fail:
        raise
    except Exception as e:      # Chrome が無い・起動しない・途中で切れた など
        raise c.Fail("画像を作れない: %s: %s" % (type(e).__name__, e))


def main(argv=None):
    ap = argparse.ArgumentParser(description="その日の投稿に付ける画像を作る")
    ap.add_argument("--no", type=int, required=True, help="問題番号（数字はページの列から読む）")
    ap.add_argument("--style", type=int, choices=sorted(STYLES), help="型（省くと番号で決まる）")
    ap.add_argument("--out", required=True, help="書き出すパス（紙の型は JPEG・無地の型は PNG）")
    a = ap.parse_args(argv)
    try:
        _, rows = c.load_page()
        if not 1 <= a.no <= len(rows):
            raise c.Fail("#%d は列に無い" % a.no)
        style = a.style or style_of(a.no)
        png = make(a.no, rows[a.no - 1]["digits"], rows[a.no - 1]["rc"], style)
    except c.Fail as e:
        print("失敗: %s" % e)
        return 1
    with open(a.out, "wb") as f:
        f.write(png)
    print("%s（#%d %s・型 %d・%s。%d バイト）" % (a.out, a.no, rows[a.no - 1]["digits"], style, kind(png), len(png)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
