# -*- coding: utf-8 -*-
"""集計のサーバーの設定と、ページとの突き合わせ（D0.7。DAILY-SPEC 17-3）。

ソースの文字列だけを比べ、Chrome も Node も使わない。サーバーの動き（100 件同時・断ること）は、
`worker/` の中の `npm test`（手元の D1）で確かめる。ここで見るのは、ページとサーバーで同じでなければ
ならない値が、食い違っていないこと。
"""
import os
import re

from uiharness import daily_ui as dui

NAME = "集計のサーバーの設定"
STATIC = True

WORKER = os.environ.get("MAKE10_WORKER") or os.path.join(dui.ROOT, "worker")      # 壊した複製を当てるときは MAKE10_WORKER


def run(ui):
    start, rows = dui.page_data()
    toml = dui.read(os.path.join(WORKER, "wrangler.toml"))
    js = dui.read(os.path.join(WORKER, "src", "index.js"))
    page = dui.read(dui.DAILY_HTML)

    # 設定ファイルの、コメントでない行だけを見る
    live = "\n".join(ln for ln in toml.splitlines() if not ln.lstrip().startswith("#"))
    var = lambda k: (re.findall(r'^\s*%s\s*=\s*"([^"]*)"' % re.escape(k), live, re.M) or [None])     # noqa: E731

    ui.check("サーバーの起点日は、ページの起点日と同じ（make10.py daily が両方に書く）",
             var("DAILY_START"), [start.isoformat()])
    ui.check("受け付ける Origin は https://make10.app（ページの共有の URL と同じ出どころ）",
             [var("ALLOW_ORIGIN"), re.findall(r'const DAILY_URL="(https://[^/"]+)/', page)],
             [["https://make10.app"], ["https://make10.app"]])
    ui.check("入口は api.make10.app の Custom Domain だけ（workers.dev の URL は開けない）",
             [re.findall(r'pattern\s*=\s*"([^"]+)"\s*,\s*custom_domain\s*=\s*true', live),
              re.findall(r"^\s*workers_dev\s*=\s*(\w+)", live, re.M)],
             [["api.make10.app"], ["false"]])
    ui.check("D1 のつなぎ先の名前は DB（Worker の本体が読む名前と同じ）",
             [var("binding"), "env.DB." in js], [["DB"], True])
    ui.check("足すのは 1 文（ON CONFLICT … DO UPDATE SET s=s+…）。読んでから書く形にしない",
             [len(re.findall(r"ON CONFLICT\(n\) DO UPDATE SET s=s\+excluded\.s", js)),
              len(re.findall(r"INSERT OR REPLACE", js))], [1, 0])
    ui.check("サーバーは、人や端末を見分けるものを読まない（IP・クッキー・User-Agent）",
             re.findall(r"CF-Connecting-IP|cookie|user-agent|request\.cf|req\.cf", js, re.I), [])
