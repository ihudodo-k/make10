# -*- coding: utf-8 -*-
"""テスト表示の、みんなの結果の見本（D0.15。DAILY-SPEC 11 章・17-4）。

?date=（テスト表示）は集計と通信しないので、公開前に「みんなの結果」を画面で見る方法が無かった。
?date= に agg=demo か agg=pending を付けたときだけ、解いた後・ギブアップの後に、決まった見本の数字で出す。

- 通信はしない（fetch を 1 回も呼ばない）。記録も保存もしない（テスト表示の決まりのまま）
- 自分のいる帯は、その回の自分の時間から決まる（本物の返事と同じ処理を通す）
- agg を付けない ?date= は今までどおり（出ない）。?date= が無いときは、agg を無視する
"""
import datetime
import time

from uiharness import daily_ui as dui
from uiharness.daily_cases.agg import BOX, REST

NAME = "みんなの結果の見本（テスト表示）"

TZ = "Asia/Tokyo"
DEMO = {"s": 412, "g": 96, "s0": 268, "b": [38, 121, 147, 82, 24]}       # 508 件
PEND = {"s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}                  # 29 件（30 件未満は「集計中」）
LABELS = ["<0:30", "<1:00", "<2:00", "<5:00", "5:00+"]
# fetch を呼んだ回数を数える（どこ宛てでも数える。集計の差し替えより外側に置く）
COUNT = "window.__F=0;(function(){const f=window.fetch;window.fetch=function(){__F++;return f.apply(this,arguments)}})()"
NET = ("performance.getEntriesByType('resource').map(e=>e.name)"
       ".filter(n=>/api\\.make10\\.app|cloudflareinsights/.test(n))")


def pct(x, y):
    return "%d%%" % int(x * 100 / y + 0.5)


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no = 4
    sol = rows[no - 1]["sol"]
    iso = day(no).isoformat()
    ok_other = {"mode": "ok", "agg": {"s": 90, "g": 10, "s0": 45, "b": [50, 20, 10, 5, 5]}}   # 見本とは違う数字

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def solve(sec, wait=0.9):
        ui.tick(sec * 1000)
        return ui.solve(sol, wait=wait)

    def giveup(wait=0.6):
        ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
        time.sleep(wait)

    ui.check("見本の数字のつじつま（帯の合計 = 解いた数・ヒントなし <= 解いた数・demo は 30 件以上・pending は 30 件未満）",
             [sum(DEMO["b"]) == DEMO["s"], sum(PEND["b"]) == PEND["s"], DEMO["s0"] <= DEMO["s"], PEND["s0"] <= PEND["s"],
              DEMO["s"] + DEMO["g"] >= 30, PEND["s"] + PEND["g"] < 30], [True] * 6)

    # ══ agg=demo: 解いた後に、見本の数字で出る。通信しない ══
    # 集計の返事は「見本とは違う数字で 200」にしておく ―― もし通信していれば、違う数字が出るか、要求が記録に残る
    ui.open(date=iso, extra="&agg=demo", perf=True, api=ok_other)
    ui.ev(COUNT)
    ui.check("ページの見本の数字は、決めた値", ui.ev("AGG_DEMO"), {"demo": DEMO, "pending": PEND})
    ui.check("解く前は、みんなの結果は出ない。テスト表示の文は出ている", [ui.ev(BOX), ui.visible("dtest"), ui.text("dtest")],
             [None, True, "テスト表示（記録しません）"])
    solve(45)
    box = ui.ev(BOX)
    ui.check("agg=demo で解いた後: みんなの結果が、見本の数字で出る（正解率・ヒントなし・5 つの帯）",
             [box and box["title"], box and box["pending"], box and box["nums"], box and box["names"], box and box["labels"]],
             ["みんなの結果", None, [pct(DEMO["s"], DEMO["s"] + DEMO["g"]), pct(DEMO["s0"], DEMO["s"])], ["正解率", "ヒントなし"], LABELS])
    ui.check("自分のいる帯は、その回の時間（45 秒）から決まる（<1:00 の 1 本だけ）", [box and box["me"], box and box["you"]], [[1], ["あなた"]])
    ui.check("棒の高さは、見本の数字の比（いちばん多い帯がいちばん高い）",
             box and [box["bars"].index(max(box["bars"])), box["bars"][4] < box["bars"][0] < box["bars"][3] < box["bars"][1]],
             [2, True])
    ui.check("通信は 0 回（fetch を 1 回も呼ばない・集計にも計測にも要求が出ない）",
             [ui.ev("__F"), ui.api_calls(), ui.ev(NET)], [0, [], []])
    ui.check("記録も保存もしない。テスト表示の文は出たまま。ほかの並びはそのまま",
             [ui.saved(), ui.visible("dtest"), ui.ev(REST)], [None, True, True])
    ui.check("どの画面でも、横にはみ出さない", ui.ev("document.documentElement.scrollWidth<=innerWidth"), True)
    ui.check_no_errors("agg=demo: JS エラー 0")

    # 時間が違えば、自分の帯も違う（本物と同じ処理を通している）
    for sec, band in ((10, 0), (100, 2), (400, 4)):
        ui.open(date=iso, extra="&agg=demo", perf=True)
        solve(sec)
        box = ui.ev(BOX)
        ui.check("agg=demo: %d 秒で解くと、自分の帯は %s" % (sec, LABELS[band]), box and box["me"], [band])

    # ══ agg=demo: ギブアップの後にも出る。自分の帯は無い ══
    ui.open(date=iso, extra="&agg=demo", perf=True, api=ok_other)
    ui.ev(COUNT)
    giveup()
    box = ui.ev(BOX)
    ui.check("agg=demo でギブアップの後: 見本の数字で出る。目立つ帯は無い",
             [box and box["nums"], box and box["me"], ui.text("eq")],
             [[pct(DEMO["s"], DEMO["s"] + DEMO["g"]), pct(DEMO["s0"], DEMO["s"])], [], "ギブアップ"])
    ui.check("ギブアップでも、通信は 0 回・保存もしない", [ui.ev("__F"), ui.api_calls(), ui.saved()], [0, [], None])

    # ══ agg=pending: 件数が少なくて「集計中」になる場合 ══
    ui.open(date=iso, extra="&agg=pending", perf=True, api=ok_other)
    ui.ev(COUNT)
    solve(45)
    box = ui.ev(BOX)
    ui.check("agg=pending で解いた後: 見出しと「集計中」だけ（数字も棒も出さない）",
             [box and box["title"], box and box["pending"], box and box["nums"], box and box["bars"]],
             ["みんなの結果", "集計中", [], []])
    ui.check("agg=pending でも、通信は 0 回・保存もしない", [ui.ev("__F"), ui.api_calls(), ui.saved()], [0, [], None])
    ui.check_no_errors("agg=pending: JS エラー 0")

    # ══ agg なしの ?date= は、今までどおり（出ない・通信しない）══
    for extra, name in (("", "agg なし"), ("&agg=", "agg が空"), ("&agg=1", "agg=1"), ("&agg=DEMO", "agg=DEMO（大文字）"),
                        ("&agg=toString", "agg=toString")):
        ui.open(date=iso, extra=extra, perf=True, api=ok_other)
        ui.ev(COUNT)
        solve(45)
        ui.check("?date= で %s: みんなの結果は出ない・通信もしない" % name,
                 [ui.ev(BOX), ui.ev("__F"), ui.api_calls(), ui.ev(REST)], [None, 0, [], True])

    # ══ ?date= が無いときは、agg を無視する（本物の動きのまま）══
    ui.open(now=at(no), tz=TZ, lang="ja", extra="&agg=demo", perf=True, api=ok_other)
    ui.check("?date= なしで agg=demo: テスト表示にならない・見本を持たない", [ui.visible("dtest"), ui.ev("AGG_TEST")], [False, None])
    solve(45)
    calls = ui.api_calls()
    box = ui.ev(BOX)
    ui.check("?date= なしで agg=demo: 今までどおり 1 回送り、返事の数字（見本ではない）を出す。記録も残る",
             [[c["method"] for c in calls], box and box["nums"], ui.saved()["days"][str(no)]["r"]],
             [["POST"], ["90%", "50%"], "s"])
    ui.open(now=at(no), tz=TZ, lang="ja", extra="&agg=demo", perf=True)        # 通信できない
    solve(45)
    ui.check("?date= なしで agg=demo・通信できない: みんなの結果は出ない（見本で埋めない）", ui.ev(BOX), None)
    ui.check_no_errors()
