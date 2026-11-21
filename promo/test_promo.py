# -*- coding: utf-8 -*-
"""promo/ の手元の試し（鍵なしで動く。本物の X・Cloudflare・集計のサーバーには 1 回も送らない）。

  python promo/test_promo.py              全部（ページとの照合に headless Chrome を使う）
  python promo/test_promo.py --no-chrome  Chrome を使う照合を飛ばす

見ること:
- 問題番号と 4 つの数字の出し方: ページの列と一致する（別の読み方の uiharness と、本物のページの JS の両方と）・日付の境目
- 4 つの文（版 4）: 280 字以内・答えが入らない・決まった形・#Make10 だけ・数は 4 つの数字と 10 だけ。文と画像の型の回り方
- 画像（image.py）: 1080×1350・紙の型は JPEG・全日全型で式が収まる・字に無い文字は描かない・答えが入らない
- 集計の返事の確かめ（common.agg_get。collect が使う）
- X・Cloudflare・集計は、返事のまねのサーバー（このファイルの中）で試す。X の署名は、まねのサーバーが別に計算し直して確かめる
- CSV: 同じ日を 2 回集めても重複しない。同じ日に 2 回流しても 2 回送らない
- 画像: 上げる → 付けて投稿する（PNG・JPEG の形式を中身から渡す）。作れない・上げられないときは文字だけで投稿する。media_test は投稿しない
"""
import base64
import contextlib
import datetime
import email.parser
import hashlib
import hmac
import io
import json
import os
import shutil
import sys
import re
import tempfile
import threading
import urllib.parse
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))
import common as c          # noqa: E402
import image                # noqa: E402
import post                 # noqa: E402
import collect              # noqa: E402
import report               # noqa: E402

results = []


def check(name, got, want):
    ok = got == want
    results.append(ok)
    print(("  OK  " if ok else "  NG  ") + name + ("" if ok else "\n        実測=%r\n        期待=%r" % (got, want)))


# ── 返事のまねのサーバー ──

KEYS = {"X_API_KEY": "test-consumer-key", "X_API_SECRET": "test-consumer-secret-SHOULD-NOT-LEAK",
        "X_ACCESS_TOKEN": "test-token", "X_ACCESS_SECRET": "test-token-secret-SHOULD-NOT-LEAK",
        "CF_API_TOKEN": "test-cf-token-SHOULD-NOT-LEAK", "CF_ACCOUNT_ID": "acct123"}
S = {}                       # まねのサーバーの状態（試しごとに reset() で作り直す）
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) + b"--\r\n"   # 本文の区切りに見える並びも入れる
JPG = b"\xff\xd8\xff\xe0" + bytes(range(256))


def reset():
    S.clear()
    S.update({"agg": {}, "posted": [], "post_resp": None, "tweets": {}, "followers": 100, "cf": None,
              "cf_req": [], "calls": [], "bad_auth": [], "next_id": 1000, "image": PNG, "uploads": [], "upload_resp": None,
              "metas": [], "meta_resp": None, "media_resp": None})


def parse_multipart(ctype, raw):
    """multipart の本文を {名前: (filename, Content-Type, バイト列)} にする（common.x_upload_image とは別に読む）"""
    msg = email.parser.BytesParser().parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
    return {p.get_param("name", header="content-disposition"):
            (p.get_filename(), p.get_content_type(), p.get_payload(decode=True)) for p in msg.get_payload()}


def fake_image(n, row):
    """post.make_image の代わり（Chrome も字も使わない）。S["image"] が None なら作れない日"""
    if S["image"] is None:
        raise c.Fail("まねの失敗: Chrome が無い")
    return S["image"], image.style_of(n)


def eq_widths(style, rows):
    """列の全日の、その型の式の幅（px）。1 つのページで数字だけ入れ替えて測る（image.render とは別に書いた）"""
    from uiharness import cdp
    work = tempfile.mkdtemp(prefix="make10-promo-width-")
    srv = ch = None
    try:
        with open(os.path.join(work, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(image.build_html(1, "1111", "N", style))
        shutil.copy(image.fetch_font(image.font_dir(), image.STYLES[style]["font"]), work)
        srv = cdp.serve(work, image.free_port())
        ch = cdp.Chrome(image.free_port(), os.path.join(work, "p"),
                        args=("--no-sandbox",) if sys.platform.startswith("linux") else ())
        ch.ws.call("Emulation.setDeviceMetricsOverride", {"width": image.WIDTH, "height": image.HEIGHT,
                                                          "deviceScaleFactor": 1, "mobile": False})
        ch.goto("http://127.0.0.1:%d/index.html" % srv.server_address[1], ready="complete|undefined")
        ch.ws.call("Runtime.evaluate", {"expression": "document.fonts.ready.then(()=>1)", "awaitPromise": True})
        return ch.ev("""(()=>{const ds=%s;const sp=[...document.querySelector('.eq').children];const out=[];
          for(const d of ds){[0,2,4,6].forEach((k,i)=>sp[k].textContent=d[i]);
            const r=sp.map(e=>e.getBoundingClientRect());out.push(Math.ceil(Math.max(...r.map(x=>x.right))-Math.min(...r.map(x=>x.left))))}
          return out})()""" % json.dumps([r["digits"] for r in rows]))
    finally:
        if ch:
            ch.close()
        if srv:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(work, ignore_errors=True)


def verify_oauth(method, base_url, query, header):
    """まねのサーバー側で署名を計算し直す（common.oauth_header とは別に書いた）"""
    if not header or not header.startswith("OAuth "):
        return False
    got = {}
    for part in header[6:].split(", "):
        k, v = part.split("=", 1)
        got[urllib.parse.unquote(k)] = urllib.parse.unquote(v.strip('"'))
    if got.get("oauth_consumer_key") != KEYS["X_API_KEY"] or got.get("oauth_token") != KEYS["X_ACCESS_TOKEN"]:
        return False
    sig = got.pop("oauth_signature", None)
    enc = lambda s: urllib.parse.quote(s, safe="-._~")  # noqa: E731
    allp = [(enc(k), enc(v)) for k, v in list(query) + list(got.items())]
    allp.sort()
    norm = "&".join(k + "=" + v for k, v in allp)
    base = method + "&" + enc(base_url) + "&" + enc(norm)
    key = enc(KEYS["X_API_SECRET"]) + "&" + enc(KEYS["X_ACCESS_SECRET"])
    want = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return sig == want


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, st, obj):
        b = json.dumps(obj).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def handle_any(self, method):
        u = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        body = raw.decode("utf-8", "replace")
        S["calls"].append((method, u.path))
        if u.path == "/agg/r":
            if self.headers.get("Origin") != c.ORIGIN:
                return self.send(403, {"e": "origin"})
            r = S["agg"].get(dict(query).get("n"))
            if r is None:
                return self.send(400, {"e": "range"})
            return self.send(*r)
        if u.path.startswith("/x/"):
            base_url = "http://%s%s" % (self.headers.get("Host"), u.path)
            if not verify_oauth(method, base_url, query, self.headers.get("Authorization")):
                S["bad_auth"].append(u.path)
                return self.send(401, {"title": "Unauthorized", "detail": "bad signature"})
            if u.path == "/x/2/users/me":
                return self.send(200, {"data": {"id": "1", "username": "make10app",
                                                "public_metrics": {"followers_count": S["followers"]}}})
            if u.path == "/x/2/media/upload" and method == "POST":
                S["uploads"].append(parse_multipart(self.headers.get("Content-Type"), raw))
                if S["upload_resp"]:
                    return self.send(*S["upload_resp"])
                return self.send(200, {"data": {"id": "770077", "media_key": "3_770077", "size": len(raw)}})
            if u.path == "/x/2/media/metadata" and method == "POST":
                S["metas"].append(json.loads(body))
                if S["meta_resp"]:
                    return self.send(*S["meta_resp"])
                return self.send(200, {"data": {"id": json.loads(body)["id"]}})
            if u.path == "/x/2/tweets" and method == "POST":
                S["posted"].append(json.loads(body))
                if S["media_resp"] and "media" in S["posted"][-1]:
                    return self.send(*S["media_resp"])
                if S["post_resp"]:
                    return self.send(*S["post_resp"])
                S["next_id"] += 1
                return self.send(201, {"data": {"id": str(S["next_id"]), "text": json.loads(body)["text"]}})
            if u.path == "/x/2/tweets" and method == "GET":
                ids = dict(query)["ids"].split(",")
                return self.send(200, {"data": [S["tweets"][i] for i in ids if i in S["tweets"]]})
        if u.path == "/cf":
            if self.headers.get("Authorization") != "Bearer " + KEYS["CF_API_TOKEN"]:
                return self.send(401, {"errors": [{"message": "auth"}]})
            S["cf_req"].append(json.loads(body))
            return self.send(*S["cf"])
        self.send(404, {"e": "path"})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")


@contextlib.contextmanager
def env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run(mod, *argv):
    """(終了コード, 出したもの)"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mod.main(list(argv))
    return code, buf.getvalue()


def tweet(tid, imp, likes, replies=0, reposts=0, prof=0):
    return {"id": tid, "public_metrics": {"impression_count": imp, "like_count": likes, "reply_count": replies,
                                          "retweet_count": reposts, "quote_count": 0},
            "non_public_metrics": {"impression_count": imp, "user_profile_clicks": prof}}


def main():
    no_chrome = "--no-chrome" in sys.argv
    start, rows = c.load_page()
    D = lambda n: start + datetime.timedelta(days=n - 1)  # noqa: E731  #n の日（UTC）
    at = lambda n, hm="08:30": "%sT%s:00Z" % (D(n).isoformat(), hm)  # noqa: E731

    print("■ 問題番号と数字の出し方")
    from uiharness import daily_ui as dui
    s2, r2 = dui.page_data()
    check("起点日が uiharness の読み方と同じ", start, s2)
    check("列の全行（番号・4 桁・制約・解答）が uiharness の読み方と同じ",
          [(r["no"], r["digits"], r["rc"], r["sols"]) for r in rows], [(r["no"], r["id"], r["rc"], r["sols"]) for r in r2])
    check("起点日の前日は #0・起点日は #1・その次は #2",
          [c.puzzle_no(start, D(0)), c.puzzle_no(start, D(1)), c.puzzle_no(start, D(2))], [0, 1, 2])
    check("UTC の日付で数える（00:00 と 23:59 は同じ番号・次の 00:00 で 1 つ進む）",
          [c.puzzle_no(start, c.now_utc(x).date()) for x in (at(5, "00:00"), at(5, "23:59"), at(6, "00:00"))], [5, 5, 6])
    check("列の最後の日まで出せる", post.plan(D(len(rows)))[0:2], (len(rows), rows[-1]))
    try:
        post.plan(D(len(rows) + 1))
        check("列の後の日は止める", "止まらなかった", "Fail")
    except c.Fail:
        check("列の後の日は止める", "Fail", "Fail")

    if not no_chrome:
        from uiharness import cdp
        port, debug = 8811, 9411
        srv = cdp.serve(dui.DOCS, port)
        prof = tempfile.mkdtemp(prefix="make10-promo-")
        chrome = cdp.Chrome(debug, prof)
        try:
            chrome.metrics(430, 900)
            ui = dui.UI(chrome, "http://127.0.0.1:%d/daily/index.html" % port, [], "promo", (430, 900))
            ui.case = "promo"

            def page_no(when, tz):
                ms = int(c.now_utc(when).timestamp() * 1000)
                ui.open(now=ms, tz=tz, api={"mode": "fail"})
                return ui.ev("[DAILY_NO, PUZZLE ? PUZZLE.id : null]")
            # 投稿の時刻（UTC 8:30）に、どの時間帯のページも post.py と同じ問題を出す。夏時間（10-26 はアメリカがまだ夏時間）と冬時間（11-09）
            for n in (1, 15, 250, len(rows)):
                when = at(n)
                want = post.plan(c.now_utc(when).date())
                for tz in ("Asia/Tokyo", "Pacific/Kiritimati", "Europe/London", "Europe/Berlin", "America/New_York",
                           "America/Los_Angeles"):
                    check("UTC 8:30 の #%d（%s）: %s のページが同じ問題を出す" % (n, D(n), tz),
                          page_no(when, tz), [want[0], want[1]["digits"]])
            # 境目: ハワイは UTC 8:30 にはまだ前の日（#n-1）。冬時間のロサンゼルスは UTC 7:30 にはまだ前の日（なので 8:30 にした）
            n = 15
            check("境目: ハワイは UTC 8:30 には前の日の問題（#%d）" % (n - 1),
                  page_no(at(n), "Pacific/Honolulu")[0], n - 1)
            check("境目: 冬時間のロサンゼルスは UTC 7:30 には前の日、8:30 には同じ日",
                  [page_no(at(n, "07:30"), "America/Los_Angeles")[0], page_no(at(n, "08:30"), "America/Los_Angeles")[0]],
                  [n - 1, n])
            check("境目: 東京は UTC 14:59 まで同じ日・15:00 に次の日",
                  [page_no(at(n, "14:59"), "Asia/Tokyo")[0], page_no(at(n, "15:00"), "Asia/Tokyo")[0]], [n, n + 1])
            check("ページの JS エラー 0", ui.errors(), [])
            for n in (8, 47, 32, len(rows)):       # #47 は − が使えない日・#32 は前の字で式がいちばん広い日・最後の日は番号がいちばん長い
                for st in image.ORDER:
                    data = image.make(n, rows[n - 1]["digits"], rows[n - 1]["rc"], st)
                    check("本物の画像 #%d 型 %d: 1080×1350・%s・5MB 以下" % (n, st, "JPEG" if image.STYLES[st]["jpeg"] else "PNG"),
                          [image.size(data), image.kind(data), c.image_format(data)[0], len(data) <= image.MAX_BYTES],
                          [(1080, 1350), "jpeg" if image.STYLES[st]["jpeg"] else "png",
                           "image/jpeg" if image.STYLES[st]["jpeg"] else "image/png", True])
            check("同じ入力なら同じ画像（紙の質感も揺れも決まった値）",
                  image.make(8, rows[7]["digits"], rows[7]["rc"], 1) == image.make(8, rows[7]["digits"], rows[7]["rc"], 1), True)
            check("post.make_image は番号で型を決める（#5 は型 2・JPEG）",
                  [post.make_image(5, rows[4])[1], image.kind(post.make_image(5, rows[4])[0])], [2, "jpeg"])
            for st in image.ORDER:
                ws = eq_widths(st, rows)
                i = max(range(len(rows)), key=lambda k: ws[k])
                check("列の全 %d 日で、型 %d の式が %dpx に収まる（いちばん広い日 #%d %s は %dpx）"
                      % (len(rows), st, image.EQ_MAX, rows[i]["no"], rows[i]["digits"], ws[i]), max(ws) <= image.EQ_MAX, True)
            bad_dir = tempfile.mkdtemp(prefix="make10-promo-font-")
            try:
                with open(os.path.join(bad_dir, "Caveat.ttf"), "wb") as fh:
                    fh.write(b"not a font")
                with env(PROMO_FONT_DIR=bad_dir), mock.patch.object(image, "FONT_URL", "http://127.0.0.1:9/%s/%s"):
                    try:
                        image.make(8, "6823", "N", 2)
                        check("字が取れない・中身が違うときは描かずに失敗", "描いた", "Fail")
                    except c.Fail:
                        check("字が取れない・中身が違うときは描かずに失敗", "Fail", "Fail")
            finally:
                shutil.rmtree(bad_dir, ignore_errors=True)
            check("3 つの字は、画面に出す字（数字・?・=・記号・英字・#）を全部持ち、漢字や ★ は持たない",
                  [(image.font_lacks(image.fetch_font(image.font_dir(), image.STYLES[st]["font"]),
                                     "0123456789?=+−×÷^!()UseMak#"),
                    image.font_lacks(image.fetch_font(image.font_dir(), image.STYLES[st]["font"]), "漢 ★"))
                   for st in image.ORDER], [("", "漢★")] * 3)
            with mock.patch.object(image, "FOOT", "Make10 #%d 漢"):     # 手書きの字に無い字（別の字で描かれる）
                try:
                    image.make(8, "6823", "N", 2)
                    check("字に無い文字があれば描かずに失敗", "描いた", "Fail")
                except c.Fail as e:
                    check("字に無い文字があれば描かずに失敗", ["Fail", "漢" in str(e)], ["Fail", True])
        finally:
            chrome.close()
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(prof, ignore_errors=True)
    else:
        print("  （--no-chrome: ページの JS との照合は飛ばした）")

    print("■ 4 つの文（文の版 4）")
    check("文の版は 4", post.TMPL, "4")
    check("例の形 A〜D（6 1 8 3 の日）", [post.compose("6183", t) for t in "ABCD"], [
        "Make 10 with 6, 1, 8, 3 — in this order. Can you?\n#Make10",
        "Looks easy. Is it?\n6, 1, 8, 3 → 10. Reply with your answer.\n#Make10",
        "Four digits, one target: 10.\n6, 1, 8, 3 — in this order.\n#Make10",
        "Today's digits: 6, 1, 8, 3.\nKeep the order. Make 10.\n#Make10"])
    all_txt = [(r, t, post.compose(r["digits"], t)) for r in rows for t in "ABCD"]
    check("どの文も 1〜2 行 ＋ ハッシュタグの行", sorted({x.count("\n") for _, _, x in all_txt}), [1, 2])
    check("どの文にもリンクの案内が無い", [x for _, _, x in all_txt if re.search(r"link|profile|bio|http", x, re.I)], [])
    check("ハッシュタグは #Make10 の 1 つだけ", sorted({tuple(re.findall(r"#\w+", x)) for _, _, x in all_txt}), [("#Make10",)])
    check("数は 4 つの数字と 10 だけ（根拠の無い数字・% が無い）",
          [(r["no"], t) for r, t, x in all_txt
           if "%" in x or sorted(re.findall(r"\d+", x)) != sorted(list(r["digits"]) + ["10", "10"])], [])
    check("代わりの文の形（記号の並びは画像の「Use」の行と同じ。#47 は − を抜く）",
          [post.alt_text(1, "8752", "N"), post.alt_text(47, "0553", "S0")],
          ["Make10 #1. Digits: 8, 7, 5, 2. Use all four, in order, to make 10. Use + − × ÷ ^ ! ( ).",
           "Make10 #47. Digits: 0, 5, 5, 3. Use all four, in order, to make 10. Use + × ÷ ^ ! ( )."])
    check("X の数え方: 英数字・·・— は 1、−（U+2212）と日本語は 2",
          [post.x_len("ab1"), post.x_len("·—"), post.x_len("−"), post.x_len("あ")], [3, 2, 2, 2])
    check("文の型は番号で順に回る（#1 A・#2 B・#3 C・#4 D・#5 A・#12 D）", [post.type_of(n) for n in (1, 2, 3, 4, 5, 12)],
          list("ABCDAD"))
    check("画像の型は番号で順に回る（#1 1・#2 2・#3 4・#4 1）", [image.style_of(n) for n in (1, 2, 3, 4)], [1, 2, 4, 1])
    check("文と画像の型は 12 日で全部の組み合わせ（4 × 3）が 1 回ずつ出る",
          len({(post.type_of(n), image.style_of(n)) for n in range(1, 13)}), 12)
    with env(PROMO_TYPE="d"):
        check("PROMO_TYPE を入れると、その型だけになる", [post.type_of(n) for n in (1, 2, 3)], list("DDD"))
    with env(PROMO_TYPE="E"):
        try:
            post.type_of(1)
            check("PROMO_TYPE が A〜D 以外なら止める", "止まらなかった", "Fail")
        except c.Fail:
            check("PROMO_TYPE が A〜D 以外なら止める", "Fail", "Fail")
    bad = []
    longest = 0
    for r, t, x in all_txt:
        longest = max(longest, post.x_len(x))
        if post.problems(x, r):
            bad.append((r["no"], t, post.problems(x, r)))
    check("列の全 %d 日 × 4 つの文: 280 字以内・決まった形・答えが入らない" % len(rows), bad, [])
    check("いちばん長い文でも短い（X の数え方で %d 字）" % longest, longest <= 120, True)
    r12 = rows[11]
    a12 = post.compose(r12["digits"], "A")
    check("答えが入った文は送らない", "答えが入っている" in post.problems(a12.replace("Can you?", r12["sols"][0]), r12), True)
    check("数字がその日の問題と違う文は送らない", [post.problems(post.compose("1234", t), r12) != [] for t in "ABCD"], [True] * 4)
    check("リンクの入った文は送らない", post.problems(a12 + " https://make10.app/daily/", r12) != [], True)
    check("ハッシュタグを足した文は送らない", post.problems(a12 + " #puzzle", r12) != [], True)
    check("記号の入った文は送らない", "演算の記号が入っている" in post.problems(a12.replace("Can you?", "Can you (really)?"), r12), True)

    print("■ 画像（image.py）")
    for bad in ((8, "6+23", 1), (8, "68233", 1), (0, "6823", 1), (True, "6823", 1), (8, "6823", 3), (8, "6823", 0)):
        try:
            image.check_input(bad[0], bad[1], "N", bad[2])
            check("番号・4 桁・型（1・2・4）でないものは受け取らない %r" % (bad,), "受け取った", "Fail")
        except c.Fail:
            check("番号・4 桁・型（1・2・4）でないものは受け取らない %r" % (bad,), "Fail", "Fail")
    check("型 3 は外してある（回すのは 1・2・4）", [sorted(image.STYLES), image.ORDER], [[1, 2, 4], (1, 2, 4)])
    check("紙の型（1・2）は JPEG の品質 90・型 4 は PNG", [image.STYLES[k]["jpeg"] for k in (1, 2, 4)], [90, 90, None])
    check("列の全 %d 日の制約が分かる" % len(rows), [r["rc"] for r in rows if r["rc"] not in c.RC_OP], [])
    check("決まった並びの例（#8 は制約なし・#47 は − が使えないので行から消える）",
          [image.expected_text(8, "6823", "N"), image.expected_text(47, "0553", "S0")],
          ["6?8?2?3=10Use+−×÷^!()Keeptheorder.Don'tswapthedigits.Make10#8",
           "0?5?5?3=10Use+×÷^!()Keeptheorder.Don'tswapthedigits.Make10#47"])
    check("並べ替えの禁止の 1 行がどの日の画像にもある", [r["no"] for r in rows
          if '<div class="rule">Keep the order. Don&#x27;t swap the digits.</div>' not in image.build_html(r["no"], r["digits"], r["rc"], image.style_of(r["no"]))], [])
    # 使えない記号は、ここで別に書いた対応（DATA-SPEC 8-B の A0 S0 M0 D0 P0 F0 ＝ + - * / ^ ! の禁止）から出す
    ban = {"A0": "+", "S0": "−", "M0": "×", "D0": "÷", "P0": "^", "F0": "!"}
    leak, differ = [], []
    for r in rows:
        h = image.build_html(r["no"], r["digits"], r["rc"], image.style_of(r["no"]))
        flat = image.expected_text(r["no"], r["digits"], r["rc"])
        use = re.search(r'<div class="use">(.*?)</div>', h).group(1)
        img_syms = re.findall(r"<span[^>]*>([^<]*)</span>", use)[1:]     # 先頭は「Use」
        alt_syms = post.alt_text(r["no"], r["digits"], r["rc"]).rsplit(" Use ", 1)[1].rstrip(".").split(" ")
        want = [x for x in "+−×÷^!()" if x != ban.get(r["rc"])]
        if any(x.replace(" ", "") in flat for x in r["sols"]):
            leak.append(r["no"])
        if not (img_syms == alt_syms == want):
            differ.append((r["no"], img_syms, alt_syms))
    check("列の全日: 画像の文字に解答のどれも入らない", leak, [])
    check("列の全 %d 日: 画像の記号の行と代わりの文の記号が同じで、使えない記号だけが抜ける" % len(rows), differ, [])
    check("画像の形式は頭の印から（PNG・JPEG）", [c.image_format(PNG), c.image_format(JPG)],
          [("image/png", ".png"), ("image/jpeg", ".jpg")])
    try:
        c.image_format(b"GIF89a")
        check("PNG でも JPEG でもなければ止める", "止まらなかった", "Fail")
    except c.Fail:
        check("PNG でも JPEG でもなければ止める", "Fail", "Fail")

    print("■ 集計の返事の確かめ（common.agg_get。collect.py が使う）")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    tmp = tempfile.mkdtemp(prefix="make10-promo-data-")
    post.make_image = fake_image
    try:
        with env(PROMO_X_API=base + "/x", PROMO_CF_API=base + "/cf", PROMO_AGG_API=base + "/agg", PROMO_DATA=None,
                 PROMO_TYPE=None, **{k: None for k in KEYS}):
            reset()

            def agg_fail():
                try:
                    c.agg_get(11)
                    return "通った"
                except c.Fail as e:
                    return str(e)
            S["agg"]["11"] = (200, {"n": 11, "s": 63, "g": 37, "s0": 26, "b": [0, 0, 0, 0, 0]})
            check("返事の数をそのまま返す", [c.agg_get(11)[k] for k in ("n", "s", "g", "s0")], [11, 63, 37, 26])
            S["agg"]["11"] = (500, {"e": "x"})
            check("集計が 500 なら止める", agg_fail(), "集計が HTTP 500（x）")
            S["agg"]["11"] = (200, {"n": 10, "s": 50, "g": 0, "s0": 0})
            check("返事の番号が違えば止める", agg_fail(), "集計の返事の形が違う")
            S["agg"]["11"] = (200, {"n": 11, "s": 1e308, "g": 0, "s0": 0})
            check("数が大きすぎる（1e308）返事は止める", agg_fail(), "集計の返事の形が違う")
            S["agg"].clear()
            check("range で断られたら止める", agg_fail(), "集計が HTTP 400（range）")
            with env(PROMO_AGG_API="http://127.0.0.1:9"):
                check("通信できなければ止める", agg_fail().startswith("通信できない"), True)
            check("四捨五入はページの Math.round と同じ（1 / 40 = 2.5% → 3%。Python の round なら 2%）",
                  [c.pct(1, 40), c.pct(26, 63), c.pct(63, 100)], [3, 41, 63])

            print("■ 投稿（post.py。X は返事のまね）")
            n = 3                                    # #3 は文 C・画像の型 4
            reset()
            code, out = run(post, "--dry-run", "--now", at(n), "--data", tmp)
            check("dry-run: 終了コード 0・送らない・CSV を作らない・鍵が無くても動く",
                  [code, S["posted"], os.path.exists(os.path.join(tmp, "posts.csv"))], [0, [], False])
            check("dry-run: 送る文と型を出す", ["文の型 C" in out, post.compose(rows[n - 1]["digits"], "C") in out], [True, True])
            code, out = run(post, "--now", at(n), "--data", tmp)
            check("鍵が無いと止め、足りない名前だけ出す（送らない）",
                  [code, "X_API_KEY" in out and "X_ACCESS_SECRET" in out, S["posted"]], [1, True, []])
            with env(**KEYS):
                code, out = run(post, "--now", at(n), "--data", tmp)
                check("送る: 終了コード 0・1 回だけ送る・署名が通る", [code, len(S["posted"]), S["bad_auth"]], [0, 1, []])
                check("送った文はその日の C の文", S["posted"][0]["text"], post.compose(rows[n - 1]["digits"], "C"))
                p = c.read_table(tmp, "posts.csv")
                row = p.get(D(n).isoformat(), {})
                check("posts.csv に 1 行（型・文の版・番号・数字・tweet の番号・フォロワー・c_note は空・画像の型）",
                      [len(p), row.get("type"), row.get("tmpl"), row.get("n"), row.get("digits"), row.get("tweet_id"),
                       row.get("followers"), row.get("c_note"), row.get("posted_at"), row.get("style")],
                      [1, "C", "4", str(n), rows[n - 1]["digits"], "1001", "100", "", at(n), "4"])
                check("画像を上げて付ける: 上げるのは 1 回・本文は multipart・tweet_image・PNG がそのまま届く",
                      [len(S["uploads"]), S["uploads"][0].get("media_category", (0, 0, 0))[2],
                       S["uploads"][0].get("media"), S["bad_auth"]],
                      [1, b"tweet_image", ("make10.png", "image/png", PNG), []])
                check("代わりの文を media/metadata で入れる", S["metas"], [{"id": "770077", "metadata": {"alt_text": {
                    "text": post.alt_text(n, rows[n - 1]["digits"], rows[n - 1]["rc"])}}}])
                check("投稿に media_id が付く・posts.csv の image は 1",
                      [S["posted"][0].get("media"), row.get("image")], [{"media_ids": ["770077"]}, "1"])
                order = [k[1] for k in S["calls"] if k[1].startswith("/x/2/") and k[0] == "POST"]
                check("上げる → 代わりの文 → 投稿 の順", order, ["/x/2/media/upload", "/x/2/media/metadata", "/x/2/tweets"])
                with open(os.path.join(tmp, "posts.csv"), encoding="utf-8") as fh:
                    check("CSV のファイルにも tmpl=4 が書いてある", fh.readline().split(",")[3] == "tmpl" and ",C,4," in fh.read(),
                          True)
                check("鍵の値を出さない", [v in out for v in KEYS.values() if "LEAK" in v], [False, False, False])
                code, out = run(post, "--now", at(n, "09:30"), "--data", tmp)
                check("同じ日に 2 回流しても、2 回目は送らない", [code, len(S["posted"])], [0, 1])
                # 次の日（#4 は D）。X が断ったら失敗・行を足さない
                S["post_resp"] = (403, {"title": "Forbidden", "detail": "You are not allowed to create a Tweet with duplicate content."})
                code, out = run(post, "--now", at(n + 1), "--data", tmp)
                check("X が断ったら終了コード 1・行を足さない・理由を出す",
                      [code, len(c.read_table(tmp, "posts.csv")), "duplicate content" in out], [1, 1, True])
                S["post_resp"] = None
                S["followers"] = 104
                S["agg"].clear()
                code, out = run(post, "--now", at(n + 2), "--data", tmp)     # #5 は文 A・画像の型 2
                code6, out6 = run(post, "--now", at(n + 3), "--data", tmp)   # #6 は文 B・画像の型 4
                p = c.read_table(tmp, "posts.csv")
                check("文の型と画像の型が順に回る（#3 C 4・#5 A 2・#6 B 4）",
                      [(p[D(k).isoformat()]["type"], p[D(k).isoformat()]["style"]) for k in (3, 5, 6)],
                      [("C", "4"), ("A", "2"), ("B", "4")])
                check("#6 の文は B の文", [code6, p[D(6).isoformat()]["text"]], [0, post.compose(rows[5]["digits"], "B")])
                code, out = run(post, "--now", "%sT08:30:00Z" % (start - datetime.timedelta(days=1)), "--data", tmp)
                # 送ったのは #3・#4（断られた画像付き）・#4（文字だけの送り直し。これも断られた）・#5・#6
                check("起点日より前の日は送らずに 0 で終わる", [code, len(S["posted"])], [0, 5])

                print("■ 画像が付かない日（post.py。X は返事のまね）")
                tmp2 = os.path.join(tmp, "画像")
                img = lambda k: c.read_table(tmp2, "posts.csv")[D(k).isoformat()]  # noqa: E731

                def one(k, **kw):
                    """#k を送る。(終了コード, 出したもの, 送った本文の並び)"""
                    S.update(posted=[], uploads=[], metas=[], **kw)
                    code, out = run(post, "--now", at(k), "--data", tmp2)
                    S.update(image=PNG, upload_resp=None, meta_resp=None, media_resp=None, post_resp=None)
                    return code, out, S["posted"]
                code, out, sent = one(7, image=None)
                check("画像を作れない日: 文字だけで送る・終了コード 0・理由を出す・image は 0・style は空・上げない",
                      [code, len(sent), "media" in sent[0], "Chrome が無い" in out, img(7)["image"], img(7)["style"], S["uploads"]],
                      [0, 1, False, True, "0", "", []])
                code, out, sent = one(8, upload_resp=(403, {"title": "Forbidden", "detail": "not permitted to upload"}))
                check("上げるのを断られた日: 文字だけで送る・終了コード 0・理由を出す・image は 0・代わりの文を送らない",
                      [code, len(sent), "media" in sent[0], "not permitted to upload" in out, img(8)["image"], S["metas"]],
                      [0, 1, False, True, "0", []])
                code, out, sent = one(9, upload_resp=(200, {"data": {"media_key": "x"}}))
                check("返事に media_id が無い日も文字だけ", [code, len(sent), "media" in sent[0], img(9)["image"]], [0, 1, False, "0"])
                code, out, sent = one(10, meta_resp=(500, {"title": "oops"}))
                check("代わりの文だけ入らない日: 画像は付ける・ログに出す・image は 1",
                      [code, sent[0].get("media"), "代わりの文が入らない" in out, img(10)["image"]],
                      [0, {"media_ids": ["770077"]}, True, "1"])
                code, out, sent = one(11, media_resp=(400, {"title": "Invalid Request", "detail": "media id invalid"}))
                check("画像付きが 4xx の日: 文字だけで 1 回送り直す・image は 0・tweet の番号が残る",
                      [code, [("media" in b) for b in sent], "media id invalid" in out, img(11)["image"], bool(img(11)["tweet_id"])],
                      [0, [True, False], True, "0", True])
                code, out, sent = one(12, media_resp=(503, {"title": "Service Unavailable"}))
                check("画像付きが 5xx の日: 送り直さない（出ているかもしれない）・終了コード 1・行を足さない",
                      [code, len(sent), D(12).isoformat() in c.read_table(tmp2, "posts.csv")], [1, 1, False])
                code, out, sent = one(13, media_resp=(403, {"title": "Forbidden"}), post_resp=(403, {"title": "Forbidden"}))
                check("文字だけの送り直しも断られたら終了コード 1・行を足さない・3 回目は送らない",
                      [code, len(sent), D(13).isoformat() in c.read_table(tmp2, "posts.csv")], [1, 2, False])
                code, out, sent = one(16, image=JPG)
                check("JPEG の日: image/jpeg・make10.jpg で上げて付ける・style はその日の画像の型",
                      [code, S["uploads"][0].get("media"), sent[0].get("media"), img(16)["image"], img(16)["style"]],
                      [0, ("make10.jpg", "image/jpeg", JPG), {"media_ids": ["770077"]}, "1", str(image.style_of(16))])
                code, out, sent = one(17, image=b"GIF89a" + bytes(10))
                check("形式が分からない画像は上げずに文字だけで送る",
                      [code, S["uploads"], "media" in sent[0], "形式が分からない" in out, img(17)["image"]], [0, [], False, True, "0"])

                print("■ media_test（post.py --media-test）")
                before = len(c.read_table(tmp2, "posts.csv"))
                S.update(posted=[], uploads=[], metas=[])
                idir = os.path.join(tmp, "出力")
                code, out = run(post, "--media-test", "--now", at(14), "--data", tmp2, "--image-dir", idir)
                check("上げて代わりの文を入れるだけ: 投稿しない・CSV に書かない・media_id と状態を出す",
                      [code, len(S["uploads"]), len(S["metas"]), S["posted"], len(c.read_table(tmp2, "posts.csv")),
                       "media_id: 770077" in out, "HTTP 200" in out], [0, 1, 1, [], before, True, True])
                with open(os.path.join(idir, "make10-14.png"), "rb") as fh:
                    check("上げた画像を書き出す", fh.read(), PNG)
                S.update(upload_resp=(403, {"title": "Forbidden", "detail": "oauth1 not permitted"}))
                code, out = run(post, "--media-test", "--now", at(14), "--data", tmp2)
                check("断られたら終了コード 1・返事を出す・投稿しない", [code, "oauth1 not permitted" in out, S["posted"]], [1, True, []])
                S.update(upload_resp=None, meta_resp=(403, {"detail": "no alt"}))
                code, out = run(post, "--media-test", "--now", at(14), "--data", tmp2)
                check("代わりの文が断られても終了コード 1", [code, "no alt" in out], [1, True])
                S.update(meta_resp=None)
                check("鍵の値を出さない", [v in out for v in KEYS.values() if "LEAK" in v], [False, False, False])
                S.update(uploads=[])
                code, out = run(post, "--dry-run", "--now", at(14), "--data", tmp2, "--image-dir", idir)
                check("dry-run: 画像を書き出す・上げない", [code, "make10-14.png" in out, S["uploads"]], [0, True, []])
                S.update(image=None)
                code, out = run(post, "--dry-run", "--now", at(15), "--data", tmp2, "--image-dir", idir)
                check("dry-run で画像を作れなくても文は出す・終了コード 0", [code, "画像を作れない" in out, "#15" in out], [0, True, True])
                S.update(image=PNG)

            print("■ 集める（collect.py。X・Cloudflare・集計は返事のまね）")
            cf_rows = lambda day, v: [  # noqa: E731
                {"count": v * 2, "sum": {"visits": v}, "dimensions": {"date": day, "refererHost": ""}},
                {"count": 3, "sum": {"visits": 3}, "dimensions": {"date": day, "refererHost": "t.co"}},
                {"count": 2, "sum": {"visits": 2}, "dimensions": {"date": day, "refererHost": "x.com"}},
                {"count": 1, "sum": {"visits": 1}, "dimensions": {"date": day, "refererHost": "www.google.com"}}]
            S["cf"] = (200, {"data": {"viewer": {"accounts": [{"rumPageloadEventsAdaptiveGroups":
                                                                cf_rows(D(5).isoformat(), 10) + cf_rows(D(6).isoformat(), 20)}]}}})
            ids = {k: p[D(k).isoformat()]["tweet_id"] for k in (3, 5, 6)}
            S["tweets"] = {ids[3]: tweet(ids[3], 900, 9, 1, 2, 5), ids[5]: tweet(ids[5], 500, 5), ids[6]: tweet(ids[6], 300, 3)}
            S["agg"][str(6)] = (200, {"n": 6, "s": 70, "g": 30, "s0": 50, "b": [0, 0, 0, 0, 0]})
            with env(**KEYS):
                now7 = at(7, "08:00")                    # #6 の投稿から 23.5 時間・#5 から 47.5 時間
                code, out = run(collect, "--now", now7, "--data", tmp)
                check("集める: 終了コード 0・署名が通る", [code, S["bad_auth"]], [0, []])
                p = c.read_table(tmp, "posts.csv")
                r6, r5 = p[D(6).isoformat()], p[D(5).isoformat()]
                check("23.5 時間の投稿は、24 時間の値と最新の値の両方に入る",
                      [r6["m24_impressions"], r6["m24_likes"], r6["last_impressions"], r6["m24_at"]], ["300", "3", "300", now7])
                check("47.5 時間の投稿は最新の値だけ（24 時間の値は空のまま）",
                      [r5["m24_impressions"], r5["last_impressions"]], ["", "500"])
                check("4 日前（#3）の投稿も、7 日の内なので読む（プロフィールのクリックも）",
                      [p[D(3).isoformat()]["last_impressions"], p[D(3).isoformat()]["last_profile_clicks"]], ["900", "5"])
                v = c.read_table(tmp, "visits.csv")
                check("訪問: 昨日までの 7 日ぶん・日ごとの訪問と t.co・x.com",
                      [len(v), {k: (v[D(k).isoformat()]["visits"], v[D(k).isoformat()]["from_tco"],
                                    v[D(k).isoformat()]["from_x"]) for k in (5, 6)}],
                      [7, {5: ("16", "3", "2"), 6: ("26", "3", "2")}])
                f = S["cf_req"][-1]["variables"]["f"]["AND"]
                check("Cloudflare への問い合わせ: UTC の日付で 7 日・make10.app の /daily/", f[:3],
                      [{"date_geq": D(0).isoformat()}, {"date_leq": D(6).isoformat()}, {"requestHost": "make10.app"}])
                a = c.read_table(tmp, "agg.csv")
                check("集計: 昨日（UTC）の問題 #6 の s・g・s0・遊んだ人", [list(a), a["6"]["s"], a["6"]["g"], a["6"]["players"]],
                      [["6"], "70", "30", "100"])
                sizes = [len(c.read_table(tmp, t)) for t in ("posts.csv", "visits.csv", "agg.csv")]
                S["tweets"][ids[6]] = tweet(ids[6], 450, 4)
                code, out = run(collect, "--now", at(7, "09:00"), "--data", tmp)
                check("同じ日を 2 回集めても、3 つの表の行は増えない",
                      [code, [len(c.read_table(tmp, t)) for t in ("posts.csv", "visits.csv", "agg.csv")]], [0, sizes])
                p = c.read_table(tmp, "posts.csv")
                check("2 回目は最新の値だけ変わり、24 時間の値は最初のまま",
                      [p[D(6).isoformat()]["m24_impressions"], p[D(6).isoformat()]["last_impressions"]], ["300", "450"])
                with open(os.path.join(tmp, "visits.csv"), encoding="utf-8") as fh:
                    check("CSV の中に同じ日付の行が無い", len(fh.read().splitlines()), 8)
                S["cf"] = (200, {"data": None, "errors": [{"message": "not authorized for that account"}]})
                code, out = run(collect, "--now", at(7, "10:00"), "--data", tmp)
                check("Cloudflare が断ったら終了コード 1。X と集計は書いてある",
                      [code, "not authorized" in out, "失敗（Cloudflare）" in out, "失敗（X）" in out], [1, True, True, False])
                check("鍵の値を出さない", [v in out for v in KEYS.values() if "LEAK" in v], [False, False, False])
            code, out = run(collect, "--now", at(7, "10:00"), "--data", tmp)
            check("鍵が無いと終了コード 1（集計だけは集める）", [code, "失敗（X）" in out, "失敗（集計）" in out], [1, True, False])
            outside = [k for k in S["calls"] if not k[1].startswith(("/x/", "/agg/", "/cf"))]
            check("まねのサーバーの外へ送っていない（本物の URL を使っていない）", outside, [])

            print("■ まとめ（report.py）")
            code, out = run(report, "--data", tmp)
            lines = out.splitlines()
            row = lambda t: next((ln for ln in lines if ln.startswith("| %s | " % t)), "")  # noqa: E731
            check("型ごとの行がある（A・B・C。D は無い）", [bool(row(t)) for t in "ABCD"], [True, True, True, False])
            # B: #6 だけ。24 時間の値は #6（表示 300・反応 3）→ 1,000 回あたり 10.0
            check("B: 投稿 1・24 時間の値がある日 1・表示 300・反応 10.0 / 1,000",
                  row("B").split(" | ")[1:5], ["1", "1", "300", "10.0"])
            check("勝ち負けを決める言葉が無い（「勝ち負けは決めない」の断り書きのほか）",
                  [w in out.replace("勝ち負けは決めない", "") for w in ("勝", "負け", "おすすめ", "最良")], [False] * 4)
            check("曜日の内訳と日ごとの表がある", ["## 曜日の内訳" in out, "## 日ごと" in out], [True, True])
            check("日ごとの表に、フォロワーの増減（#5 は 100 → 104 で +4）", any(
                ln.startswith("| %s |" % D(5)) and "| +4 |" in ln for ln in lines), True)
            sty = out.split("## 画像の型")[1].split("\n## ")[0]
            srow = lambda t: next((ln for ln in sty.splitlines() if ln.startswith("| %s | " % t)), "")  # noqa: E731
            # 画像の型: #3 は 4・#5 は 2・#6 は 4。24 時間の値は #6 だけ（表示 300・反応 3）
            check("画像の型ごとの行（2・4。1 は無い）", [bool(srow("1")), bool(srow("2")), bool(srow("4"))], [False, True, True])
            check("画像 4: 投稿 2・24 時間の値がある日 1・表示 300・反応 10.0 / 1,000",
                  srow("4").split(" | ")[1:5], ["2", "1", "300", "10.0"])
            check("文の型 × 画像の型の表（版 4 の B は画像 4 に 1 本・表示 300）",
                  next((ln for ln in sty.splitlines() if ln.startswith("| 4 | B | ")), ""), "| 4 | B | 0 / — | 1 / 300 |")
            check("日ごとの表に画像の型の列（#5 は 2）",
                  any(ln.startswith("| %s | " % D(5)) and " | 4 | A | 2 | " in ln for ln in lines), True)
            code, out = run(report, "--data", os.path.join(tmp, "空"))
            check("まだ何も無いときも出せる", [code, "まだ投稿が無い" in out], [0, True])
            # tmpl の列ができる前の posts.csv（#1・#2）に、版 2 の行が足された形
            old = os.path.join(tmp, "旧")
            os.makedirs(old)
            head = [f for f in c.POSTS if f != "tmpl"]
            with open(os.path.join(old, "posts.csv"), "w", encoding="utf-8", newline="") as fh:
                fh.write(",".join(head) + "\n")
                for k, t, imp in ((1, "A", 100), (2, "B", 200)):
                    r = {f: "" for f in head}
                    r.update({"date": D(k).isoformat(), "n": str(k), "type": t, "digits": rows[k - 1]["digits"],
                              "tweet_id": str(k), "m24_at": "x", "m24_impressions": str(imp), "m24_likes": "1",
                              "m24_replies": "0", "m24_reposts": "0"})
                    fh.write(",".join(r[f] for f in head) + "\n")
            p = c.read_table(old, "posts.csv")
            check("tmpl の列が無い古い行（#1・#2）は版 1 として読む", [p[D(k).isoformat()]["tmpl"] for k in (1, 2)], ["1", "1"])
            p[D(4).isoformat()] = {f: "" for f in c.POSTS}
            p[D(4).isoformat()].update({"date": D(4).isoformat(), "n": "4", "type": "A", "tmpl": "2", "tweet_id": "4",
                                        "m24_at": "x", "m24_impressions": "900", "m24_likes": "9", "m24_replies": "0",
                                        "m24_reposts": "0"})
            c.write_table(old, "posts.csv", p)
            check("書き戻すと、古い行にも tmpl=1 が入る", [r["tmpl"] for _, r in sorted(c.read_table(old, "posts.csv").items())],
                  ["1", "1", "2"])
            code, out = run(report, "--data", old)
            check("style の列が無い古い行は、画像の型のまとめに入らない・日ごとの表は「—」",
                  ["まだ画像の型の記録が無い" in out, any(ln.startswith("| %s | " % D(1)) and " | 1 | A | — | " in ln
                                                for ln in out.splitlines())], [True, True])
            sec = {v: out.split("## 文の版 %s" % v)[1].split("\n## ")[0] for v in ("1", "2")}
            arow = lambda v: next((ln for ln in sec[v].splitlines() if ln.startswith("| A | ")), "")  # noqa: E731
            check("まとめは版ごとに分かれ、新しい版が上", [code, out.index("## 文の版 2") < out.index("## 文の版 1")], [0, True])
            check("版 2 の A は #4 だけ（表示 900）・版 1 の A は #1 だけ（表示 100）。混ざらない",
                  [arow("2").split(" | ")[1:4], arow("1").split(" | ")[1:4]], [["1", "1", "900"], ["1", "1", "100"]])
            check("版 2 に B は無い（B は版 1 の #2 だけ）",
                  ["| B | " in sec["2"].split("### ")[0], "| B | " in sec["1"].split("### ")[0]], [False, True])
            check("日ごとの表に文の版の列", [any(ln.startswith("| %s | " % D(k)) and " | %s | %s | " % (v, t) in ln
                                         for ln in out.splitlines()) for k, v, t in ((1, "1", "A"), (4, "2", "A"))],
                  [True, True])
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)

    ok = sum(results)
    print("\n合計 %d / %d 項目  %s" % (ok, len(results), "すべて通った" if ok == len(results) else "落ちた項目がある"))
    return 0 if ok == len(results) else 1


def oauth_vector():
    """署名を、外の例 2 つで確かめる"""
    hdr = c.oauth_header("GET", "http://photos.example.net/photos", {"file": "vacation.jpg", "size": "original"},
                         ("dpf43f3p2l4k3l03", "kd94hf93k423kf44", "nnch734d00sl2jdk", "pfkkdhi9sl3r4s00"),
                         nonce="kllo9940pd9333jh", timestamp=1191242096)
    sig = urllib.parse.unquote(hdr.split('oauth_signature="')[1].split('"')[0])
    check("OAuth 1.0a の署名が、OAuth の仕様の例（photos.example.net）と同じ値", sig, "tR3+Ty81lMeYAr/Fid0kMTYa/WM=")
    # X の説明書の「署名のもとの文字列」の例。その文字列を直に hmac に通した値と、oauth_header の値が同じ
    # （＝もとの文字列の組み立て方〔符号化・並べ方・本文の値の入れ方〕が説明書と同じ）
    keys = ("xvz1evFS4wEEPTGEFPHBog", "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
            "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS6weJAEb", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE")
    hdr = c.oauth_header("POST", "https://api.twitter.com/1.1/statuses/update.json",
                         {"status": "Hello Ladies + Gentlemen, a signed OAuth request!", "include_entities": "true"},
                         keys, nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", timestamp=1318622958)
    sig = urllib.parse.unquote(hdr.split('oauth_signature="')[1].split('"')[0])
    base = ("POST&https%3A%2F%2Fapi.twitter.com%2F1.1%2Fstatuses%2Fupdate.json&include_entities%3Dtrue%26"
            "oauth_consumer_key%3Dxvz1evFS4wEEPTGEFPHBog%26oauth_nonce%3DkYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg%26"
            "oauth_signature_method%3DHMAC-SHA1%26oauth_timestamp%3D1318622958%26"
            "oauth_token%3D370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS6weJAEb%26oauth_version%3D1.0%26"
            "status%3DHello%2520Ladies%2520%252B%2520Gentlemen%252C%2520a%2520signed%2520OAuth%2520request%2521")
    want = base64.b64encode(hmac.new((keys[1] + "&" + keys[3]).encode(), base.encode(), hashlib.sha1).digest()).decode()
    check("署名のもとの文字列が、X の説明書の例と同じ", sig, want)


if __name__ == "__main__":
    print("■ X の署名")
    oauth_vector()
    sys.exit(main())
