# -*- coding: utf-8 -*-
"""promo/ の共通部分（X への毎日の投稿と、反応の記録。promo/README.md）。標準ライブラリだけ。

- ページの問題の列を読む（docs/daily/index.html に埋め込まれた起点日と列。ページの JS は通さない）
- 問題番号は UTC の日付から数える（サーバーの dayNo と同じ。ページは端末の日付なので、日本の 17:30 に
  日本・ヨーロッパ・アメリカ本土のどこでも同じ番号になる。ハワイは前の日のまま。README）
- HTTP（鍵をログに出さない）・X の OAuth 1.0a の署名（hmac）・CSV（キーで 1 行ずつ。重複しない）

送り先の URL は環境変数で差し替えられる（手元の試し test_promo.py が、返事のまねのサーバーへ向ける）。
"""
import base64
import csv
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE = os.path.join(ROOT, "docs", "daily", "index.html")
ORIGIN = "https://make10.app"          # 集計のサーバーは、この Origin の要求だけに答える
AGG_MIN = 30                           # 件数（解いた ＋ ギブアップ）がこれより少ない間は数を出さない（ページの AGG_MIN）
AGG_N_MAX = 10 ** 9                    # 集計の数の上限（ページの AGG_N_MAX）
UTC = datetime.timezone.utc

X_KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


class Fail(Exception):
    """続けられない失敗。メッセージに鍵を入れない"""


def api(name):
    """送り先。既定は本物。PROMO_X_API などで差し替える（読むのは呼んだ時点）"""
    return os.environ.get("PROMO_" + name, {
        "X_API": "https://api.x.com",
        "CF_API": "https://api.cloudflare.com/client/v4/graphql",
        "AGG_API": "https://api.make10.app",
    }[name]).rstrip("/")


def data_dir(arg=None):
    return arg or os.environ.get("PROMO_DATA") or os.path.join(HERE, "data")


def now_utc(arg=None):
    """今の時刻（UTC）。arg（"2026-10-26T08:30:00Z" の形）を渡すとその時刻にする（試しのため）"""
    if arg:
        return datetime.datetime.fromisoformat(arg.replace("Z", "+00:00")).astimezone(UTC)
    return datetime.datetime.now(UTC)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── ページの問題の列 ──

def load_page(path=None):
    """(起点日 date, 行のリスト)。行は {"no", "digits", "rc", "sols"}。起点日と列はページのソースの文字列から読む"""
    with open(path or PAGE, encoding="utf-8") as f:
        html = f.read()
    m = re.findall(r'const DAILY_START="(\d{4}-\d{2}-\d{2})";', html)
    d = re.findall(r"const DAILY=`([^`]*)`", html)
    if len(m) != 1 or len(d) != 1:
        raise Fail("ページに起点日（DAILY_START）か問題の列（DAILY）が 1 つだけ見つからない")
    start = datetime.date.fromisoformat(m[0])
    rows = []
    for i, ln in enumerate(d[0].replace("\r\n", "\n").split("\n")):
        f = ln.split(",", 4)
        if len(f) != 5 or not re.fullmatch(r"\d{4}", f[1]) or f[0] != str(i + 1):
            raise Fail("問題の列の %d 行目の形が違う" % (i + 1))
        rows.append({"no": i + 1, "digits": f[1], "rc": f[2], "sols": f[4].split(";")})
    return start, rows


def puzzle_no(start, day):
    """その日（UTC の日付）の問題番号。起点日が #1。起点日より前は 0 以下"""
    return (day - start).days + 1


# ── 集計（みんなの結果） ──

def pct(x, y):
    """x / y を % にして四捨五入（ページの Math.round(x*100/y) と同じ。0 以上の整数だけ）"""
    return (200 * x + y) // (2 * y)


def agg_get(n):
    """GET /r?n= の返事 {"n","s","g","s0"}。取れないときは Fail（理由つき）"""
    st, j, _ = request("GET", "%s/r?n=%d" % (api("AGG_API"), n), headers={"Origin": ORIGIN})
    if st != 200:
        raise Fail("集計が HTTP %s（%s）" % (st, (j or {}).get("e", "")))
    ok = isinstance(j, dict) and j.get("n") == n and all(
        isinstance(j.get(k), int) and not isinstance(j.get(k), bool) and 0 <= j[k] <= AGG_N_MAX
        for k in ("s", "g", "s0")) and j["s0"] <= j["s"]
    if not ok:
        raise Fail("集計の返事の形が違う")
    return j


# ── HTTP ──

def request(method, url, headers=None, body=None, timeout=30):
    """(状態, JSON か None, 本文)。HTTP のエラーも返す。通信できないときは Fail。ヘッダー（鍵）は出さない"""
    data = None
    h = {"User-Agent": "make10-promo"}
    h.update(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            st, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, text = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise Fail("通信できない: %s %s（%s）" % (method, url.split("?")[0], getattr(e, "reason", e)))
    try:
        j = json.loads(text) if text else None
    except ValueError:
        j = None
    return st, j, text


# ── X（OAuth 1.0a のユーザーの鍵） ──

def q(s):
    """RFC 3986 の百分率符号化（OAuth 1.0a の決まり。英数字と - . _ ~ だけそのまま）"""
    return urllib.parse.quote(str(s), safe="~")


def oauth_header(method, url, params, keys, nonce=None, timestamp=None):
    """Authorization ヘッダーの値。params は署名に入れる問い合わせの値（JSON の本文は入れない）。
    keys は (API キー, その秘密, アクセストークン, その秘密)"""
    ck, cs, tk, ts = keys
    oa = {
        "oauth_consumer_key": ck,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": tk,
        "oauth_version": "1.0",
    }
    pairs = sorted((q(k), q(v)) for k, v in list(params.items()) + list(oa.items()))
    u = urllib.parse.urlsplit(url)
    base_url = "%s://%s%s" % (u.scheme.lower(), u.netloc.lower(), u.path)
    base = "&".join([method.upper(), q(base_url), q("&".join("%s=%s" % p for p in pairs))])
    key = "%s&%s" % (q(cs), q(ts))
    oa["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join('%s="%s"' % (q(k), q(v)) for k, v in sorted(oa.items()))


def x_keys():
    """環境変数の 4 つの鍵。足りなければ、足りない名前だけを出して止める（値は出さない）"""
    missing = [k for k in X_KEYS if not os.environ.get(k)]
    if missing:
        raise Fail("X の鍵が無い: " + "・".join(missing))
    return tuple(os.environ[k] for k in X_KEYS)


def x_call(method, path, keys, query=None, body=None):
    """X の API v2 を呼ぶ。(状態, JSON, 本文)"""
    url = api("X_API") + path
    query = query or {}
    full = url + ("?" + "&".join("%s=%s" % (q(k), q(v)) for k, v in query.items()) if query else "")
    auth = oauth_header(method, url, query, keys)
    return request(method, full, headers={"Authorization": auth}, body=body)


def x_error(st, j, text):
    """X が断ったときの短い説明（本文の頭だけ。鍵は本文に入らない）"""
    msg = ""
    if isinstance(j, dict):
        msg = j.get("detail") or j.get("title") or ""
        if not msg and j.get("errors"):
            msg = "; ".join(str(e.get("message") or e.get("detail") or e) for e in j["errors"][:3])
    return "HTTP %s %s" % (st, (msg or text or "")[:300])


# ── CSV（キーで 1 行。同じキーは上書きするので、2 回集めても重複しない） ──

POSTS = ("date", "n", "type", "tmpl", "digits", "text", "c_note", "tweet_id", "posted_at", "followers",
         "m24_at", "m24_impressions", "m24_likes", "m24_replies", "m24_reposts", "m24_quotes", "m24_profile_clicks",
         "last_at", "last_impressions", "last_likes", "last_replies", "last_reposts", "last_quotes", "last_profile_clicks")
VISITS = ("date", "visits", "pageviews", "from_tco", "from_x", "collected_at")
AGG = ("n", "date", "s", "g", "s0", "players", "collected_at")
TABLES = {"posts.csv": (POSTS, "date"), "visits.csv": (VISITS, "date"), "agg.csv": (AGG, "n")}


def read_table(ddir, name):
    """{キー: 行}。ファイルが無ければ空"""
    fields, key = TABLES[name]
    path = os.path.join(ddir, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        rows = {r[key]: {k: r.get(k) or "" for k in fields} for r in csv.DictReader(f)}
    if name == "posts.csv":
        for r in rows.values():
            r["tmpl"] = r["tmpl"] or "1"   # 文の版の列（tmpl）ができる前の行（#1・#2）は版 1
    return rows


def write_table(ddir, name, rows):
    """キーの順（n は数の順）に書く。書きかけで壊さないよう、別の名前に書いてから置き換える"""
    fields, key = TABLES[name]
    os.makedirs(ddir, exist_ok=True)
    path = os.path.join(ddir, name)
    order = sorted(rows, key=(lambda k: int(k)) if key == "n" else None)
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for k in order:
            w.writerow({f2: rows[k].get(f2, "") for f2 in fields})
    os.replace(path + ".tmp", path)
