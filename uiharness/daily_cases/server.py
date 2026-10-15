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
    # ページとサーバーで同じでなければならない値（D0.8）
    nums = lambda t: [int(x) for x in re.findall(r"[0-9]+", t)]                                       # noqa: E731
    ui.check("時間の帯の区切りは、ページ（AGG_BANDS）とサーバー（BANDS）で同じ",
             [nums(x) for x in re.findall(r"const AGG_BANDS=\[([^\]]*)\]", page)],
             [nums(x) for x in re.findall(r"^const BANDS = \[([^\]]*)\]", js, re.M)] or [None])
    ui.check("時間の上限は、ページ（AGG_T_MAX）とサーバー（T_MAX）で同じ",
             re.findall(r"const AGG_T_MAX=([0-9]+)", page), re.findall(r"^const T_MAX = ([0-9]+)", js, re.M) or [None])
    ui.check("ページの送り先（AGG_URL）は、サーバーの入口のドメインと、本体のパス",
             re.findall(r'const AGG_URL="([^"]+)"', page),
             ["https://%s%s" % (d, p) for d in re.findall(r'pattern\s*=\s*"([^"]+)"', live)
              for p in re.findall(r'path !== "(/r)" && path !== "/x"', js)])
    ui.check("D1 のつなぎ先の名前は DB（Worker の本体が読む名前と同じ）",
             [var("binding"), "env.DB." in js], [["DB"], True])
    ui.check("足すのは 1 文（ON CONFLICT … DO UPDATE SET s=s+…）。読んでから書く形にしない",
             [len(re.findall(r"ON CONFLICT\(n\) DO UPDATE SET s=s\+excluded\.s", js)),
              len(re.findall(r"INSERT OR REPLACE", js))], [1, 0])
    # D0.37 から、別の端末へ移す受け口の回数の制限だけが IP を読む（数えるためだけ。D1 には書かない。10-1）
    ui.check("サーバーは、人や端末を見分けるものを読まない（クッキー・User-Agent。IP は移す受け口の回数の制限の 1 か所だけ）",
             [re.findall(r"cookie|user-agent|request\.cf|req\.cf", js, re.I),
              re.findall(r"[^\n]*CF-Connecting-IP[^\n]*", js)],
             [[], ['    const { success } = await env.XFER_LIMIT.limit({ key: req.headers.get("CF-Connecting-IP") || "-" });']])
    # 別の端末へ移す（D0.37。10-1）。ページとサーバーで同じでなければならない値
    ui.check("移す: コードの字は、ページ（MOVE_RE）とサーバー（CODE_CHARS・CODE_RE）で同じ 31 字の 6 文字",
             [re.findall(r"const MOVE_RE=/\^\[([0-9A-Z]+)\]\{6\}\$/", page), re.findall(r'^const CODE_CHARS = "([0-9A-Z]+)"', js, re.M),
              re.findall(r"^const CODE_RE = /\^\[([0-9A-Z]+)\]\{6\}\$/", js, re.M), re.findall(r"^const CODE_LEN = ([0-9]+)", js, re.M)],
             [["23456789ABCDEFGHJKMNPQRSTUVWXYZ"]] * 3 + [["6"]])
    ui.check("移す: ページの送り先（MOVE_URL と /take）は、サーバーの入口のドメインと受け口のパス",
             [re.findall(r'const MOVE_URL="([^"]+)"', page), "MOVE_URL+\"/take\"" in page],
             [["https://%s%s" % (d, p) for d in re.findall(r'pattern\s*=\s*"([^"]+)"', live)
               for p in re.findall(r'path !== "(/x)" && path', js)], bool(re.findall(r'path !== "/x/take"', js))])
    ui.check("移す: 回数の制限は、1 つの IP から 1 分に 10 回（wrangler.toml の XFER_LIMIT）。表 xfer がある",
             [re.findall(r'^\[\[ratelimits\]\]\s*name\s*=\s*"(\w+)"\s*namespace_id\s*=\s*"\d+"\s*'
                         r'simple\s*=\s*\{\s*limit\s*=\s*(\d+)\s*,\s*period\s*=\s*(\d+)\s*\}', live, re.M),
              "env.XFER_LIMIT.limit(" in js,
              bool(re.search(r"CREATE TABLE IF NOT EXISTS xfer", dui.read(os.path.join(WORKER, "schema.sql"))))],
             [[("XFER_LIMIT", "10", "60")], True, True])
