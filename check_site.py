# -*- coding: utf-8 -*-
"""公開中のサイトの見守り（DAILY-SPEC 20 章）。

GitHub Actions の定期実行（.github/workflows/site-check.yml。1 日 2 回）から呼ぶ。手元でも流せる:

    python check_site.py            # 公開サイトに当てる
    python check_site.py --fail     # わざと落とす（通知の確かめ用）

確かめること
  1. https://make10.app/・/daily/・/privacy/ が 200 で返ること
  2. 公開ページの版（APP_VERSION・DAILY_VERSION）と、デイリーの起点日・列が、このリポジトリ（main）と同じこと
  3. デイリーに今日の問題があること。列の残りが 8 週を切ったら落とす
  4. 集計のサーバー https://api.make10.app/r が、決めたとおりの返事をすること
  5. make10.app と api.make10.app の証明書の期限が 14 日より多く残っていること
  6. リポジトリの最後のコミットから 50 日を超えていないこと（公開リポジトリは、60 日動きが無いと定期実行が止まる）

**公開前と公開後は、公開ページに埋め込んである起点日から、この台本が自分で切り替える。**
  公開前（起点日が未来）: 今日の問題が無いこと・API が {"e":"range"} で断ること
  公開後            : 今日の問題があること・列の残り・API が今日の番号に 200 で集計を返すこと
「今日」は UTC の日付の前後 1 日で見る（問題は端末の日付で切り替わる。定期実行は遅れることがある）。

**集計のサーバーへは読む要求（GET）しか出さない。数は足さない。**
標準ライブラリだけで動く（Chrome も npm も要らない）。1 つでも落ちたら終了コード 1。
"""
import argparse
import datetime
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

from uiharness import daily_ui as dui

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = "https://make10.app"
API = "https://api.make10.app/r"
ORIGIN = "https://make10.app"          # 集計のサーバーが受け付ける Origin（worker/wrangler.toml の ALLOW_ORIGIN）
CERT_HOSTS = ("make10.app", "api.make10.app")
CERT_MIN_DAYS = 14                     # 証明書の残りがこれを切ったら落とす
COLUMN_MIN_WEEKS = 8                   # 列の残りがこれを切ったら落とす（公開後）
IDLE_MAX_DAYS = 50                     # 最後のコミットからの日数がこれを超えたら落とす
TIMEOUT = 20


# ── 計算だけの部分（通信しない。verify_daily.py のケース monitor が確かめる）────────────────
def day_no(start, day):
    """問題番号 = 起点日（#1）からの日数 + 1"""
    return (day - start).days + 1


def plan(start, n_rows, today):
    """今日（UTC の日付）から、確かめの中身を決める。

    返すのは {"mode": "pre"|"post", "nos": 前後 1 日の問題番号, "today": 今日の番号,
             "missing": 列に無い番号, "weeks_left": 今日の後に残っている週の数}。
    公開前（pre）= 前後 1 日のどの日も起点日より前。1 日でも起点日以後なら公開後（post）"""
    nos = [day_no(start, today + datetime.timedelta(days=k)) for k in (-1, 0, 1)]
    if nos[2] < 1:
        return {"mode": "pre", "nos": nos, "today": nos[1], "missing": [], "weeks_left": None}
    live = [n for n in nos if n >= 1]
    return {"mode": "post", "nos": nos, "today": nos[1], "missing": [n for n in live if n > n_rows],
            "weeks_left": (n_rows - max(nos[1], 0)) // 7}


def versions(main_html, daily_html):
    """ソースの文字列から (APP_VERSION, DAILY_VERSION)。無ければ None"""
    a = re.search(r'const APP_VERSION="([^"]+)"', main_html or "")
    d = re.search(r'const DAILY_VERSION="([^"]+)"', daily_html or "")
    return (a.group(1) if a else None, d.group(1) if d else None)


def agg_ok(j, no):
    """集計の返事の形（DAILY-SPEC 17-2）"""
    return (isinstance(j, dict) and j.get("n") == no
            and all(isinstance(j.get(k), int) and j[k] >= 0 for k in ("s", "g", "s0"))
            and isinstance(j.get("b"), list) and len(j["b"]) == 5
            and all(isinstance(x, int) and x >= 0 for x in j["b"]))


def days_left(not_after, now):
    """証明書の期限（ssl の notAfter の文字列）までの日数"""
    end = datetime.datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), datetime.timezone.utc)
    return (end - now).total_seconds() / 86400


# ── 通信する部分 ────────────────────────────────────────────────────────────
def fetch(url, headers=None):
    """(状態, 見出し, 本文の文字列)。4xx・5xx も例外にせず返す。つながらなければ (None, {}, 理由)"""
    req = urllib.request.Request(url, headers=dict({"User-Agent": "make10-site-check", "Cache-Control": "no-cache"},
                                                   **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:                                  # noqa: BLE001  つながらない・証明書が合わない、など
        return None, {}, "%s: %s" % (type(e).__name__, e)


def cert_not_after(host):
    """その名前でつないで、証明書の期限を読む（名前と期限の確かめは ssl がする。合わなければ例外）"""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as s:
            return s.getpeercert()["notAfter"]


def last_commit_time():
    """このリポジトリの最後のコミットの時刻（UTC）。読めなければ None"""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return datetime.datetime.fromtimestamp(int(out.stdout.strip()), datetime.timezone.utc)
    except Exception:                                       # noqa: BLE001
        return None


def read_local(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8", newline="") as f:
        return f.read()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):                 # 出せない文字があっても、最後まで出し切る
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:                                   # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="公開中のサイトの見守り（DAILY-SPEC 20 章）")
    ap.add_argument("--fail", action="store_true", help="わざと落とす（通知が届くことの確かめ用）")
    # 下は、手元で「わざと期待値を変えて落ちること」を確かめるための入口。定期実行では使わない
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--api", default=API)
    ap.add_argument("--today", help="今日（UTC）の日付を YYYY-MM-DD で差し替える")
    ap.add_argument("--expect-app", help="本編の版の期待値を差し替える")
    ap.add_argument("--expect-daily", help="デイリーの版の期待値を差し替える")
    ap.add_argument("--cert-min-days", type=float, default=CERT_MIN_DAYS)
    ap.add_argument("--column-min-weeks", type=int, default=COLUMN_MIN_WEEKS)
    ap.add_argument("--idle-max-days", type=float, default=IDLE_MAX_DAYS)
    args = ap.parse_args(argv)

    now = datetime.datetime.now(datetime.timezone.utc)
    today = datetime.date.fromisoformat(args.today) if args.today else now.date()
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print("  [%s] %s%s" % ("OK" if ok else "NG", name, ("  … " + detail) if detail else ""), flush=True)

    print("公開サイトの見守り: %s  （今日は UTC の %s）" % (args.site, today.isoformat()))

    # 1. 3 つのページが 200
    pages = {}
    for path in ("/", "/daily/", "/privacy/"):
        st, _, body = fetch(args.site + path)
        pages[path] = body if st == 200 else ""
        check("%s が 200 で返る" % path, st == 200, "状態 %s%s" % (st, "" if st else "  " + body[:120]))

    # 2. 版と、デイリーの起点日・列が、このリポジトリと同じ
    local_main, local_daily = read_local("docs", "index.html"), read_local("docs", "daily", "index.html")
    want = list(versions(local_main, local_daily))
    if args.expect_app:
        want[0] = args.expect_app
    if args.expect_daily:
        want[1] = args.expect_daily
    got = versions(pages["/"], pages["/daily/"])
    check("本編の版が main と同じ", got[0] is not None and got[0] == want[0], "公開 %s ／ main %s" % (got[0], want[0]))
    check("デイリーの版が main と同じ", got[1] is not None and got[1] == want[1], "公開 %s ／ main %s" % (got[1], want[1]))
    check("プライバシーポリシーのページに題と問い合わせ先がある",
          "プライバシーポリシー" in pages["/privacy/"] and "Privacy Policy" in pages["/privacy/"]
          and "mailto:" in pages["/privacy/"])
    start = rows = None
    try:
        start, rows = dui.page_data(pages["/daily/"])
        lstart, lrows = dui.page_data(local_daily)
        same = start == lstart and [(r["no"], r["id"], r["rc"], r["sol"]) for r in rows] == \
            [(r["no"], r["id"], r["rc"], r["sol"]) for r in lrows]
        check("デイリーの起点日と列が main と同じ", same,
              "公開 %s・%d 行 ／ main %s・%d 行" % (start, len(rows), lstart, len(lrows)))
    except Exception as e:                                  # noqa: BLE001
        check("デイリーの起点日と列が読める", False, "%s: %s" % (type(e).__name__, e))

    # 3. 今日の問題（起点日から、公開前か公開後かを決める）
    p = None
    if start is not None:
        p = plan(start, len(rows), today)
        if p["mode"] == "pre":
            check("公開前: 今日（前後 1 日）は起点日より前で、問題が無い", True,
                  "起点日 %s まで %d 日" % (start, (start - today).days))
        else:
            check("公開後: 今日（前後 1 日）の問題が列にある", not p["missing"],
                  "問題番号 %s ／ 列は #%d まで%s" % ([n for n in p["nos"] if n >= 1], len(rows),
                                             "  ** 無い番号 %s" % p["missing"] if p["missing"] else ""))
            check("公開後: 列の残りが %d 週以上ある" % args.column_min_weeks, p["weeks_left"] >= args.column_min_weeks,
                  "残り %d 週（今日は #%d・列は #%d まで）。少なければ python make10.py daily --weeks で伸ばす"
                  % (p["weeks_left"], p["today"], len(rows)))

    # 4. 集計のサーバー（読むだけ。数は足さない）
    st, hd, body = fetch(args.api + "?n=1")
    check("集計: Origin を付けない要求は 403 で断る", st == 403 and '"origin"' in body, "状態 %s  %s" % (st, body[:80]))
    if p is not None:
        no = 1 if p["mode"] == "pre" else max(p["today"], 1)
        st, hd, body = fetch("%s?n=%d" % (args.api, no), {"Origin": ORIGIN})
        try:
            j = json.loads(body)
        except Exception:                                   # noqa: BLE001
            j = None
        acao = {k.lower(): v for k, v in hd.items()}.get("access-control-allow-origin")
        if p["mode"] == "pre":
            check("集計（公開前）: どの問題番号も 400・range で断る", st == 400 and j == {"e": "range"},
                  "GET ?n=%d → 状態 %s  %s" % (no, st, body[:80]))
        else:
            check("集計（公開後）: 今日の番号に 200 で、決めた形の集計を返す", st == 200 and agg_ok(j, no),
                  "GET ?n=%d → 状態 %s  %s" % (no, st, body[:120]))
        check("集計: 返事に Access-Control-Allow-Origin: %s" % ORIGIN, acao == ORIGIN, "実際 %s" % acao)

    # 5. 証明書の期限
    for host in CERT_HOSTS:
        try:
            left = days_left(cert_not_after(host), now)
            check("証明書 %s: 残り %g 日より多い" % (host, args.cert_min_days), left > args.cert_min_days,
                  "残り %.1f 日" % left)
        except Exception as e:                              # noqa: BLE001
            check("証明書 %s が読める（名前と期限が合っている）" % host, False, "%s: %s" % (type(e).__name__, e))

    # 6. 最後のコミットからの日数（60 日動きが無いと、定期実行が止まる）
    t = last_commit_time()
    if t is None:
        check("最後のコミットの時刻が読める", False, "git log が読めない")
    else:
        idle = (now - t).total_seconds() / 86400
        ok = idle <= args.idle_max_days
        check("最後のコミットから %g 日を超えていない" % args.idle_max_days, ok,
              "%.1f 日前" % idle + ("" if ok else "。60 日動きが無いと、GitHub が定期実行を止める。空のコミットを入れれば戻る"
                                  "（git commit --allow-empty -m \"見守りを続ける\" && git push）"))

    if args.fail:
        check("わざと落とす（--fail。通知が届くことの確かめ）", False)

    ng = results.count(False)
    print("合計 %d / %d 項目%s" % (len(results) - ng, len(results), "  すべて通った" if not ng else "  落ちた項目 %d" % ng))
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
