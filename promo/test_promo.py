# -*- coding: utf-8 -*-
"""promo/ の手元の試し（鍵なしで動く。本物の X・Cloudflare・集計のサーバーには 1 回も送らない）。

  python promo/test_promo.py              全部（ページとの照合に headless Chrome を使う）
  python promo/test_promo.py --no-chrome  Chrome を使う照合を飛ばす

見ること:
- 問題番号と 4 つの数字の出し方: ページの列と一致する（別の読み方の uiharness と、本物のページの JS の両方と）・日付の境目
- 3 つの型の文: 280 字以内・答えが入らない・決まった形。C の数字の作り方（ページと同じ四捨五入）と、集計が足りない・取れないときの形
- X・Cloudflare・集計は、返事のまねのサーバー（このファイルの中）で試す。X の署名は、まねのサーバーが別に計算し直して確かめる
- CSV: 同じ日を 2 回集めても重複しない。同じ日に 2 回流しても 2 回送らない
"""
import base64
import contextlib
import datetime
import hashlib
import hmac
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))
import common as c          # noqa: E402
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


def reset():
    S.clear()
    S.update({"agg": {}, "posted": [], "post_resp": None, "tweets": {}, "followers": 100, "cf": None,
              "cf_req": [], "calls": [], "bad_auth": [], "next_id": 1000})


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
        body = self.rfile.read(n).decode() if n else ""
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
            if u.path == "/x/2/tweets" and method == "POST":
                S["posted"].append(json.loads(body))
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
        finally:
            chrome.close()
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(prof, ignore_errors=True)
    else:
        print("  （--no-chrome: ページの JS との照合は飛ばした）")

    print("■ 3 つの型の文")
    check("文の版は 2", post.TMPL, "2")
    check("例の形 A", post.compose(12, "6183", "A"),
          "Make10 Daily #12\nToday's numbers: 6 · 1 · 8 · 3\nUse all four, in order, to make 10.\n"
          "Play free — link in profile.\n#Make10 #DailyPuzzle #MathPuzzle")
    check("例の形 B", post.compose(12, "6183", "B"),
          "Can you make 10 from 6 · 1 · 8 · 3?\nKeep the order. + − × ÷ ^ ! ( ) allowed.\n"
          "Make10 Daily #12 — link in profile.\n#Make10 #DailyPuzzle #BrainTeaser")
    check("例の形 C", post.compose(12, "6183", "C", "Yesterday's puzzle: 63% solved, 41% with no hints."),
          "Make10 Daily #12: 6 · 1 · 8 · 3\nYesterday's puzzle: 63% solved, 41% with no hints.\n"
          "Your turn — make 10. Link in profile.\n#Make10 #DailyPuzzle #MathPuzzle")
    check("C で昨日の行が無いとき（2 行目を除く）", post.compose(12, "6183", "C", ""),
          "Make10 Daily #12: 6 · 1 · 8 · 3\nYour turn — make 10. Link in profile.\n#Make10 #DailyPuzzle #MathPuzzle")
    check("X の数え方: 英数字・·・— は 1、−（U+2212）と日本語は 2",
          [post.x_len("ab1"), post.x_len("·—"), post.x_len("−"), post.x_len("あ")], [3, 2, 2, 2])
    check("型は番号で順に回る（#1 A・#2 B・#3 C・#4 A・#12 C）", [post.type_of(n) for n in (1, 2, 3, 4, 12)],
          list("ABCAC"))
    with env(PROMO_TYPE="b"):
        check("PROMO_TYPE を入れると、その型だけになる", [post.type_of(n) for n in (1, 2, 3)], list("BBB"))
    with env(PROMO_TYPE="D"):
        try:
            post.type_of(1)
            check("PROMO_TYPE が A・B・C 以外なら止める", "止まらなかった", "Fail")
        except c.Fail:
            check("PROMO_TYPE が A・B・C 以外なら止める", "Fail", "Fail")
    worst = "Yesterday's puzzle: 100% solved, 100% with no hints."
    bad = []
    longest = 0
    for r in rows:
        for t in "ABC":
            for line in (("", worst) if t == "C" else ("",)):
                txt = post.compose(r["no"], r["digits"], t, line)
                longest = max(longest, post.x_len(txt))
                if post.problems(txt, r):
                    bad.append((r["no"], t, post.problems(txt, r)))
    check("列の全 %d 日 × 3 つの型（C は昨日の行の有り無し）: 280 字以内・決まった形・答えが入らない" % len(rows), bad, [])
    check("いちばん長い文でも 280 字より十分短い（X の数え方で %d 字）" % longest, longest <= 200, True)
    r12 = rows[11]
    a12 = post.compose(12, r12["digits"], "A")
    check("答えが入った文は送らない", "答えが入っている" in post.problems(
        a12.replace("Use all four, in order, to make 10.", r12["sols"][0]), r12), True)
    check("番号と数字がその日の問題と違う文は送らない",
          [post.problems(post.compose(12, "1234", t), r12) != [] for t in "ABC"] +
          [post.problems(post.compose(13, r12["digits"], t), r12) != [] for t in "ABC"], [True] * 6)
    check("リンクの入った文は送らない", post.problems(a12 + " https://make10.app/daily/", r12) != [], True)
    check("B の決まりの行の外に記号があれば送らない", "演算の記号が入っている" in post.problems(
        post.compose(12, r12["digits"], "B").replace("link in profile", "link (profile)"), r12), True)
    check("C の昨日の行が決まった形でなければ送らない",
          post.problems(post.compose(12, r12["digits"], "C", "Yesterday's puzzle: everyone solved it."), r12) != [], True)

    print("■ C の数字（みんなの結果）")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    tmp = tempfile.mkdtemp(prefix="make10-promo-data-")
    try:
        with env(PROMO_X_API=base + "/x", PROMO_CF_API=base + "/cf", PROMO_AGG_API=base + "/agg", PROMO_DATA=None,
                 PROMO_TYPE=None, **{k: None for k in KEYS}):
            reset()
            S["agg"]["11"] = (200, {"n": 11, "s": 63, "g": 37, "s0": 26, "b": [0, 0, 0, 0, 0]})
            check("63 / 100 解いた・ヒントなし 26 / 63（41.3%）", post.c_line(12)[0],
                  "Yesterday's puzzle: 63% solved, 41% with no hints.")
            S["agg"]["11"] = (200, {"n": 11, "s": 1, "g": 39, "s0": 1, "b": [0, 0, 0, 0, 0]})
            check("四捨五入はページの Math.round と同じ（1 / 40 = 2.5% → 3%。Python の round なら 2%）", post.c_line(12)[0],
                  "Yesterday's puzzle: 3% solved, 100% with no hints.")
            S["agg"]["11"] = (200, {"n": 11, "s": 20, "g": 9, "s0": 3, "b": [0, 0, 0, 0, 0]})
            check("29 件（30 件未満）なら昨日の行を出さず、記録にそう残す", post.c_line(12), ("", "30 件未満（29 件）"))
            S["agg"]["11"] = (200, {"n": 11, "s": 20, "g": 10, "s0": 3, "b": [0, 0, 0, 0, 0]})
            check("30 件ちょうどなら出す", post.c_line(12)[0], "Yesterday's puzzle: 67% solved, 15% with no hints.")
            S["agg"]["11"] = (200, {"n": 11, "s": 0, "g": 30, "s0": 0, "b": [0, 0, 0, 0, 0]})
            check("解いた人が 0 なら「ヒントなし」は付けない", post.c_line(12)[0], "Yesterday's puzzle: 0% solved.")
            S["agg"]["11"] = (500, {"e": "x"})
            check("集計が 500 なら出さない", post.c_line(12)[0], "")
            S["agg"]["11"] = (200, {"n": 10, "s": 50, "g": 0, "s0": 0})
            check("返事の番号が違えば出さない", post.c_line(12), ("", "取れない（集計の返事の形が違う）"))
            S["agg"]["11"] = (200, {"n": 11, "s": 1e308, "g": 0, "s0": 0})
            check("数が大きすぎる（1e308）返事は出さない", post.c_line(12)[0], "")
            S["agg"].clear()
            check("range で断られたら出さない", post.c_line(12), ("", "取れない（集計が HTTP 400（range））"))
            check("#1 には昨日が無い（集計へ問い合わせない）", [post.c_line(1), S["calls"][-1:]],
                  [("", "昨日の問題が無い"), [("GET", "/agg/r")]])
            with env(PROMO_AGG_API="http://127.0.0.1:9"):
                check("通信できなければ出さない", post.c_line(12)[0], "")

            print("■ 投稿（post.py。X は返事のまね）")
            n = 3                                    # #3 は C
            reset()
            S["agg"][str(n - 1)] = (200, {"n": n - 1, "s": 40, "g": 10, "s0": 30, "b": [0, 0, 0, 0, 0]})
            code, out = run(post, "--dry-run", "--now", at(n), "--data", tmp)
            check("dry-run: 終了コード 0・送らない・CSV を作らない・鍵が無くても動く",
                  [code, S["posted"], os.path.exists(os.path.join(tmp, "posts.csv"))], [0, [], False])
            check("dry-run: 送る文と型を出す", ["型 C" in out, post.compose(n, rows[n - 1]["digits"], "C",
                                                 "Yesterday's puzzle: 80% solved, 75% with no hints.") in out], [True, True])
            code, out = run(post, "--now", at(n), "--data", tmp)
            check("鍵が無いと止め、足りない名前だけ出す（送らない）",
                  [code, "X_API_KEY" in out and "X_ACCESS_SECRET" in out, S["posted"]], [1, True, []])
            with env(**KEYS):
                code, out = run(post, "--now", at(n), "--data", tmp)
                check("送る: 終了コード 0・1 回だけ送る・署名が通る", [code, len(S["posted"]), S["bad_auth"]], [0, 1, []])
                check("送った文はその日の C の文", S["posted"][0]["text"],
                      post.compose(n, rows[n - 1]["digits"], "C", "Yesterday's puzzle: 80% solved, 75% with no hints."))
                p = c.read_table(tmp, "posts.csv")
                row = p.get(D(n).isoformat(), {})
                check("posts.csv に 1 行（型・文の版・番号・数字・tweet の番号・フォロワー・C の記録）",
                      [len(p), row.get("type"), row.get("tmpl"), row.get("n"), row.get("digits"), row.get("tweet_id"),
                       row.get("followers"), row.get("c_note"), row.get("posted_at")],
                      [1, "C", "2", str(n), rows[n - 1]["digits"], "1001", "100", "出した（s=40 g=10 s0=30）", at(n)])
                with open(os.path.join(tmp, "posts.csv"), encoding="utf-8") as fh:
                    check("CSV のファイルにも tmpl=2 が書いてある", fh.readline().split(",")[3] == "tmpl" and ",C,2," in fh.read(),
                          True)
                check("鍵の値を出さない", [v in out for v in KEYS.values() if "LEAK" in v], [False, False, False])
                code, out = run(post, "--now", at(n, "09:30"), "--data", tmp)
                check("同じ日に 2 回流しても、2 回目は送らない", [code, len(S["posted"])], [0, 1])
                # 次の日（#4 は A）。X が断ったら失敗・行を足さない
                S["post_resp"] = (403, {"title": "Forbidden", "detail": "You are not allowed to create a Tweet with duplicate content."})
                code, out = run(post, "--now", at(n + 1), "--data", tmp)
                check("X が断ったら終了コード 1・行を足さない・理由を出す",
                      [code, len(c.read_table(tmp, "posts.csv")), "duplicate content" in out], [1, 1, True])
                S["post_resp"] = None
                S["followers"] = 104
                S["agg"].clear()
                code, out = run(post, "--now", at(n + 2), "--data", tmp)     # #5 は B
                code6, out6 = run(post, "--now", at(n + 3), "--data", tmp)   # #6 は C。集計が取れない
                p = c.read_table(tmp, "posts.csv")
                check("型が順に回る（#3 C・#5 B・#6 C）", [p[D(k).isoformat()]["type"] for k in (3, 5, 6)], ["C", "B", "C"])
                check("C で集計が取れない日は昨日の行なしで送り、記録にそう残す",
                      [code6, p[D(6).isoformat()]["text"], p[D(6).isoformat()]["c_note"]],
                      [0, post.compose(6, rows[5]["digits"], "C", ""), "取れない（集計が HTTP 400（range））"])
                code, out = run(post, "--now", "%sT08:30:00Z" % (start - datetime.timedelta(days=1)), "--data", tmp)
                check("起点日より前の日は送らずに 0 で終わる", [code, len(S["posted"])], [0, 4])

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
            check("型ごとの行がある（B・C）", [bool(row("B")), bool(row("C")), bool(row("A"))], [True, True, False])
            # C: #3 と #6。24 時間の値は #6 だけ（表示 300・反応 3）→ 1,000 回あたり 10.0
            check("C: 投稿 2・24 時間の値がある日 1・表示 300・反応 10.0 / 1,000",
                  row("C").split(" | ")[1:5], ["2", "1", "300", "10.0"])
            check("勝ち負けを決める言葉が無い（「勝ち負けは決めない」の断り書きのほか）",
                  [w in out.replace("勝ち負けは決めない", "") for w in ("勝", "負け", "おすすめ", "最良")], [False] * 4)
            check("曜日の内訳と日ごとの表がある", ["## 曜日の内訳" in out, "## 日ごと" in out], [True, True])
            check("日ごとの表に、フォロワーの増減（#5 は 100 → 104 で +4）", any(
                ln.startswith("| %s |" % D(5)) and "| +4 |" in ln for ln in lines), True)
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
