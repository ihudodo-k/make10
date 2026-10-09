# -*- coding: utf-8 -*-
"""公開サイトの見守り（check_site.py と .github/workflows/site-check.yml。DAILY-SPEC 20 章）。

ここで見るのは、通信しない部分だけ ―― 公開前と公開後の切り替え・問題番号・列の残り・返事の形・証明書の残り日数の
計算と、ワークフローの設定。公開サイトに当てる確かめそのものは、`python check_site.py`（と定期実行）が行う。
Chrome は使わない。
"""
import datetime
import os
import re

import check_site as cs
from uiharness import daily_ui as dui

NAME = "公開サイトの見守り（台本の計算と、ワークフローの設定）"
STATIC = True


def run(ui):
    D = datetime.date
    start, rows = dui.page_data()
    n = len(rows)
    s = D(2026, 11, 2)                                   # 仮の起点日（月曜）

    # ── 公開前と公開後の切り替え（前後 1 日のどれかが起点日以後なら、公開後）──
    ui.check("起点日の 2 日前まで: 公開前（問題が無いことを見る）",
             [cs.plan(s, 1099, D(2026, 10, 31))[k] for k in ("mode", "nos")], ["pre", [-2, -1, 0]])
    ui.check("起点日の前日: 明日が #1 なので、公開後の形に切り替わる",
             [cs.plan(s, 1099, D(2026, 11, 1))[k] for k in ("mode", "nos", "missing")], ["post", [-1, 0, 1], []])
    ui.check("起点日: 今日は #1。残りは 156 週",
             [cs.plan(s, 1099, s)[k] for k in ("mode", "today", "missing", "weeks_left")], ["post", 1, [], 156])
    ui.check("今のページの起点日（遠い未来）では、今日は公開前",
             cs.plan(start, n, D(2026, 10, 10))["mode"], "pre")

    # ── 列の残り ──
    last = s + datetime.timedelta(days=1098)             # #1099 の日
    ui.check("列の最後の日: 明日（#1100）が列に無い。残りは 0 週",
             [cs.plan(s, 1099, last)[k] for k in ("today", "missing", "weeks_left")], [1099, [1100], 0])
    ui.check("列の最後の日の 2 日前: 前後 1 日は全部ある",
             cs.plan(s, 1099, last - datetime.timedelta(days=2))["missing"], [])
    ui.check("残りの週の数え方: 今日の後に 56 日あれば 8 週、55 日なら 7 週",
             [cs.plan(s, 1099, last - datetime.timedelta(days=d))["weeks_left"] for d in (56, 55)], [8, 7])
    ui.check("問題番号 = 起点日からの日数 + 1", [cs.day_no(s, s), cs.day_no(s, D(2026, 11, 9)), cs.day_no(s, D(2026, 11, 1))],
             [1, 8, 0])

    # ── 版・返事の形・証明書の残り日数 ──
    ui.check("版はソースの定数から読む（無ければ None）",
             [cs.versions('const APP_VERSION="7.9";', 'x\nconst DAILY_VERSION="0.10";'), cs.versions("", "<html>")],
             [("7.9", "0.10"), (None, None)])
    good = {"n": 5, "s": 3, "g": 1, "s0": 2, "b": [1, 1, 1, 0, 0]}
    ui.check("集計の返事の形: 決めた形だけを通す",
             [cs.agg_ok(good, 5), cs.agg_ok(good, 6), cs.agg_ok(dict(good, b=[1, 2]), 5), cs.agg_ok(dict(good, s=-1), 5),
              cs.agg_ok({"e": "range"}, 5), cs.agg_ok(None, 5), cs.agg_ok(dict(good, s0="2"), 5)],
             [True, False, False, False, False, False, False])
    now = datetime.datetime(2026, 10, 10, 12, tzinfo=datetime.timezone.utc)
    ui.check("証明書の残り日数（期限の文字列から）",
             [round(cs.days_left("Oct 24 12:00:00 2026 GMT", now), 3), round(cs.days_left("Oct 10 00:00:00 2026 GMT", now), 3)],
             [14.0, -0.5])
    ui.check("下限と上限の値（証明書 14 日・列 8 週・最後のコミットから 50 日）",
             [cs.CERT_MIN_DAYS, cs.COLUMN_MIN_WEEKS, cs.IDLE_MAX_DAYS, list(cs.CERT_HOSTS)],
             [14, 8, 50, ["make10.app", "api.make10.app"]])

    # ── 台本は読むだけ（集計へ POST しない）。送り先はページ・サーバーの設定と同じ ──
    src = dui.read(os.path.join(dui.ROOT, "check_site.py"))
    page = dui.read(dui.DAILY_HTML)
    ui.check("台本は、送る要求（POST・data=）を出さない",
             re.findall(r'method\s*=\s*"POST"|data\s*=|\.post\(', src), [])
    ui.check("台本の送り先と Origin は、ページの送り先・共有の URL と同じ出どころ",
             [cs.API, cs.ORIGIN, cs.SITE],
             [re.search(r'const AGG_URL="([^"]+)"', page).group(1), "https://make10.app", "https://make10.app"])

    # ── ワークフロー ──
    yml = dui.read(os.path.join(dui.ROOT, ".github", "workflows", "site-check.yml"))
    live = "\n".join(ln for ln in yml.splitlines() if not ln.lstrip().startswith("#"))
    ui.check("定期実行は 1 日 2 回（UTC 15:17 と 3:17。0 分を避ける）",
             re.findall(r'cron:\s*"([^"]+)"', live), ["17 15 * * *", "17 3 * * *"])
    ui.check("手で流す入口と、わざと落とす入力がある",
             [bool(re.search(r"^\s*workflow_dispatch:", live, re.M)), bool(re.search(r"^\s*fail:", live, re.M)),
              "inputs.fail && '--fail'" in live], [True, True, True])
    ui.check("ワークフローは読むだけ（書き込みの権限を持たず、秘密の値も使わない）",
             [re.findall(r"^\s*(\w[\w-]*):\s*write\s*$", live, re.M), re.findall(r"contents:\s*(\w+)", live),
              "secrets." in live], [[], ["read"], False])
    ui.check("流すのは check_site.py だけ（プッシュのたびには走らせない）",
             [re.findall(r"run:\s*(.+)", live), bool(re.search(r"^\s*(push|pull_request):", live, re.M))],
             [["python3 check_site.py ${{ inputs.fail && '--fail' || '' }}"], False])
