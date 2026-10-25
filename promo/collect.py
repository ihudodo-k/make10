# -*- coding: utf-8 -*-
"""毎日の数字を集めて表に足す（promo/README.md）。GitHub Actions が UTC 8:00 に流す（投稿の 30 分前）。

  python promo/collect.py            3 つを集めて promo/data/ の CSV に書く。1 つでも取れなければ終了コード 1

1. X: 過去 7 日に post.py が送った投稿（posts.csv にある tweet_id）の、表示回数・いいね・返信・リポスト・引用・
   プロフィールのクリック（非公開の指標。ユーザーの鍵で読む）。最新の値（last_*）は毎回上書きし、
   投稿から 20〜36 時間の間に初めて集めた値を「約 24 時間の値」（m24_*）として 1 度だけ残す
2. Cloudflare Web Analytics（GraphQL の API）: make10.app/daily/ の、日ごとの訪問数と、参照元が t.co・x.com の訪問数。
   日付は UTC。昨日までの 7 日ぶん（今日は途中なので取らない）
3. みんなの結果: 昨日（UTC）の問題の s・g・s0（GET /r?n=…）。サーバーは今日の前後 1 日しか答えないので、
   集め損ねた日は後から取れない

表は日（集計は番号）で 1 行。同じ日を何度集めても、その行を上書きするので重複しない。
"""
import argparse
import datetime
import os
import sys

import common as c

X_DAYS = 7
CF_DAYS = 7
M24 = (20, 36)               # 「約 24 時間の値」として残す、投稿からの時間（時）の範囲
METRICS = ("impressions", "likes", "replies", "reposts", "quotes", "profile_clicks")
X_HOSTS = {"x.com", "mobile.x.com", "twitter.com", "mobile.twitter.com"}
CF_HOST = "make10.app"
CF_PATHS = ["/daily/", "/daily", "/daily/index.html"]
CF_QUERY = """query($tag: string!, $f: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject) {
  viewer { accounts(filter: {accountTag: $tag}) {
    rumPageloadEventsAdaptiveGroups(limit: 5000, filter: $f) {
      count
      sum { visits }
      dimensions { date refererHost }
    }
  } }
}"""


def metrics_of(t):
    pub = t.get("public_metrics") or {}
    non = t.get("non_public_metrics") or {}
    return {"impressions": non.get("impression_count", pub.get("impression_count", "")),
            "likes": pub.get("like_count", ""), "replies": pub.get("reply_count", ""),
            "reposts": pub.get("retweet_count", ""), "quotes": pub.get("quote_count", ""),
            "profile_clicks": non.get("user_profile_clicks", "")}


def collect_x(ddir, now, keys):
    posts = c.read_table(ddir, "posts.csv")
    want = {}
    for r in posts.values():
        if r["tweet_id"] and r["posted_at"]:
            age = now - c.now_utc(r["posted_at"])
            if age <= datetime.timedelta(days=X_DAYS, hours=1):
                want[r["tweet_id"]] = r
    if not want:
        print("X: 過去 %d 日の投稿が無い" % X_DAYS)
        return
    st, j, txt = c.x_call("GET", "/2/tweets", keys, query={
        "ids": ",".join(sorted(want)), "tweet.fields": "created_at,public_metrics,non_public_metrics"})
    if st != 200 or not isinstance(j, dict):
        raise c.Fail("X の指標が読めない: " + c.x_error(st, j, txt))
    got = {t["id"]: t for t in j.get("data") or []}
    for tid, r in sorted(want.items(), key=lambda kv: kv[1]["date"]):
        if tid not in got:
            print("X: %s の投稿 %s が返らない（消した？）" % (r["date"], tid))
            continue
        m = metrics_of(got[tid])
        hours = (now - c.now_utc(r["posted_at"])).total_seconds() / 3600
        for k in METRICS:
            r["last_" + k] = str(m[k])
        r["last_at"] = c.iso(now)
        if not r["m24_at"] and M24[0] <= hours <= M24[1]:
            for k in METRICS:
                r["m24_" + k] = str(m[k])
            r["m24_at"] = c.iso(now)
        print("X: %s #%s 型 %s  %.1f 時間  表示 %s・いいね %s・返信 %s・リポスト %s・プロフィール %s%s"
              % (r["date"], r["n"], r["type"], hours, m["impressions"], m["likes"], m["replies"], m["reposts"],
                 m["profile_clicks"], "（24 時間の値に残した）" if r["m24_at"] == c.iso(now) else ""))
    c.write_table(ddir, "posts.csv", posts)


def collect_cf(ddir, now):
    tok, acct = os.environ.get("CF_API_TOKEN"), os.environ.get("CF_ACCOUNT_ID")
    if not tok or not acct:
        raise c.Fail("Cloudflare の鍵が無い: " + "・".join(k for k, v in (("CF_API_TOKEN", tok), ("CF_ACCOUNT_ID", acct)) if not v))
    d1 = now.date() - datetime.timedelta(days=1)
    d0 = now.date() - datetime.timedelta(days=CF_DAYS)
    f = {"AND": [{"date_geq": d0.isoformat()}, {"date_leq": d1.isoformat()},
                 {"requestHost": CF_HOST}, {"requestPath_in": CF_PATHS}]}
    st, j, txt = c.request("POST", c.api("CF_API"), headers={"Authorization": "Bearer " + tok},
                           body={"query": CF_QUERY, "variables": {"tag": acct, "f": f}})
    if st != 200 or not isinstance(j, dict) or j.get("errors") or not (j.get("data") or {}).get("viewer"):
        msg = "; ".join(str(e.get("message", e)) for e in (j or {}).get("errors") or []) if isinstance(j, dict) else ""
        raise c.Fail("Cloudflare の数が読めない: HTTP %s %s" % (st, (msg or txt or "")[:300]))
    accts = j["data"]["viewer"].get("accounts") or []
    if not accts:
        raise c.Fail("Cloudflare: アカウント（CF_ACCOUNT_ID）が見えない。トークンの権限を確かめる")
    days = {}
    for d in range(CF_DAYS):
        k = (d0 + datetime.timedelta(days=d)).isoformat()
        days[k] = {"visits": 0, "pageviews": 0, "from_tco": 0, "from_x": 0}
    for g in accts[0].get("rumPageloadEventsAdaptiveGroups") or []:
        k = g["dimensions"]["date"]
        if k not in days:
            continue
        v = int((g.get("sum") or {}).get("visits") or 0)
        host = (g["dimensions"].get("refererHost") or "").lower()
        days[k]["visits"] += v
        days[k]["pageviews"] += int(g.get("count") or 0)
        if host == "t.co":
            days[k]["from_tco"] += v
        elif host in X_HOSTS:
            days[k]["from_x"] += v
    table = c.read_table(ddir, "visits.csv")
    for k, v in days.items():
        table[k] = {"date": k, **{a: str(b) for a, b in v.items()}, "collected_at": c.iso(now)}
    c.write_table(ddir, "visits.csv", table)
    print("Cloudflare: %s〜%s  " % (d0, d1) + "・".join(
        "%s 訪問 %d（t.co %d・x.com %d）" % (k[5:], v["visits"], v["from_tco"], v["from_x"]) for k, v in days.items()))


def collect_agg(ddir, now, page=None):
    start, _rows = c.load_page(page)
    day = now.date() - datetime.timedelta(days=1)
    n = c.puzzle_no(start, day)
    if n < 1:
        print("集計: 昨日（%s）は起点日より前" % day)
        return
    j = c.agg_get(n)
    table = c.read_table(ddir, "agg.csv")
    table[str(n)] = {"n": str(n), "date": day.isoformat(), "s": str(j["s"]), "g": str(j["g"]), "s0": str(j["s0"]),
                     "players": str(j["s"] + j["g"]), "collected_at": c.iso(now)}
    c.write_table(ddir, "agg.csv", table)
    print("集計: %s #%d  解いた %d・ギブアップ %d・ヒントなし %d" % (day, n, j["s"], j["g"], j["s0"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="毎日の数字を集めて表に足す")
    ap.add_argument("--data", help="CSV の置き場所（既定は promo/data。環境変数 PROMO_DATA でも）")
    ap.add_argument("--page", help="問題の列を読むページ（既定は docs/daily/index.html）")
    ap.add_argument("--now", help="今の時刻を決める（試しのため。2026-10-27T08:00:00Z の形）")
    a = ap.parse_args(argv)
    ddir = c.data_dir(a.data)
    now = c.now_utc(a.now)
    failed = []
    for name, run in (("X", lambda: collect_x(ddir, now, c.x_keys())),
                      ("Cloudflare", lambda: collect_cf(ddir, now)),
                      ("集計", lambda: collect_agg(ddir, now, a.page))):
        try:
            run()
        except c.Fail as e:
            print("失敗（%s）: %s" % (name, e))
            failed.append(name)
    if failed:
        print("取れなかったもの: " + "・".join(failed) + "（取れた分は書いた）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
