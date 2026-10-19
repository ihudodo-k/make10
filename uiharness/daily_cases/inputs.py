# -*- coding: utf-8 -*-
"""外から入ってくる値（公開前の安全の点検。D0.46〜。DAILY-SPEC 11 章）。

- 保存（localStorage）から読んだ記録と途中の分は、データ移行で受け取るときと同じ確かめに通す。
  null の日・__proto__・形の違う値は捨て、正しい日の記録は残す。統計とカレンダーが開ける（D0.46）
- 保存した記録と受け取った記録の解いた式（e）は、盤を組んで 10 になる式でなければ式だけ捨てる（「解いた」は残す）。
  時間は 86,400 秒までに詰める（D0.47）
- 集計の返事の数は 0〜10 億の整数だけを使う。大きすぎる数で NaN% や Infinity% を出さない（D0.48）
"""
import datetime
import json
import time

from uiharness import daily_ui as dui

NAME = "外から入ってくる値"

TZ = "Asia/Tokyo"
XSS = '<img src=x onerror="window.__X=(window.__X||0)+1">'


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    no = 8
    sol = lambda n: rows[n - 1]["sol"]                                # noqa: E731
    solved = lambda n, t=40, h=0, sh=0: {"r": "s", "t": t, "h": h, "sh": sh, "e": sol(n), "sent": 1}   # noqa: E731

    # ══ 保存から読んだ記録（D0.46）══
    raw = ('{"v":1,"days":{"1":%s,"2":null,"3":5,"4":{"r":"s","t":%s,"h":%s},"x5":%s,"__proto__":{"r":"s","t":1,"h":0},'
           '"6":{"r":"g","t":null,"h":1,"sh":0},"7":[1,2]},'
           '"cur":{"no":%d,"start":"x","h":"9","sh":"<b>"},"set":{"easy":0,"tap":0,"dark":0,"lang":"auto"}}'
           % (json.dumps(solved(1)), json.dumps(XSS), json.dumps(XSS), json.dumps(solved(1)), no))
    ui.open(now=at(no), tz=TZ, store="keep")
    ui.ev("localStorage.clear();localStorage.setItem(%s,%s)" % (json.dumps(dui.SAVE_KEY), json.dumps(raw)))
    ui.open(now=at(no), tz=TZ, store="keep")
    ui.check("保存の形の違う日（null・数字・HTML の時間とヒント・番号が x5・__proto__・配列）は捨て、正しい #1 と #6 は残す",
             ui.ev("JSON.stringify(DATA.days)"),
             json.dumps({"1": {k: v for k, v in solved(1).items()}, "6": {"r": "g", "t": None, "h": 1, "sh": 0}},
                        separators=(",", ":")))
    ui.check("途中の分の形の違う値は既定に戻す（ヒントの回数と共有の回数は 0 の数）",
             ui.ev("[hintUsed,shareCount,typeof hintUsed,typeof shareCount]"), [0, 0, "number", "number"])
    ui.check("プロトタイプは汚れない", ui.ev("[({}).r,({}).t,({}).h]"), [None, None, None])
    ui.ev("dstats.click()")
    time.sleep(0.2)
    ui.check("統計が開き、解いた日数は 1（#1 だけ）", ui.ev("[popNow,$('statlist').querySelector('.stat b').textContent]"),
             ["dstatsheet", "1"])
    ui.ev("const b=document.querySelector('#dcal-grid button.s');if(b)b.click()")
    time.sleep(0.1)
    ui.check("カレンダーで解いた日を選べ、HTML として出るものは無い", ui.ev("[window.__X||0,document.querySelectorAll('img').length]"),
             [0, 0])
    ui.check_no_errors("保存から読んだ記録: JS エラー 0")

    # ══ 解いた式と時間（D0.47）══
    def plus(n):                       # その日の 4 つの数字を + でつないだ式（10 にならない日を選ぶ）
        return " + ".join(rows[n - 1]["id"])
    n_not10 = next(n for n in range(9, 40) if sum(map(int, rows[n - 1]["id"])) != 10)
    bad = {"2": XSS, "3": "9 + 9 + 9 + 9", str(n_not10): plus(n_not10), "5": "1 __proto__ 2 constructor 3 toString 4",
           "6": sol(6).replace("(", "( (", 1)}
    days = {"1": solved(1)}
    for k, e in bad.items():
        days[k] = dict(solved(int(k)), e=e)
    days["7"] = dict(solved(7), t=10 ** 12)
    days[str(no)] = dict(solved(no), e="( " * 60)
    ui.open(now=at(no), tz=TZ, store={"v": 1, "days": days, "cur": None})
    got = ui.ev("JSON.stringify(DATA.days)")
    got = json.loads(got)
    ui.check("保存した記録: 10 になる式（#1）は残し、HTML・違う数字・10 にならない・知らない記号・括弧が合わない式は、式だけ捨てる（「解いた」は残す）",
             {k: [v["r"], "e" in v] for k, v in got.items()},
             dict({"1": ["s", True], "7": ["s", True], str(no): ["s", False]}, **{k: ["s", False] for k in bad}))
    ui.check("保存した記録: 時間は 86,400 秒までに詰める（10^12 秒 → 24:00:00）", got["7"]["t"], 86400)
    ui.check("今日の式を捨てたので、盤は解答例で開き、10 になる",
             [ui.ev("$('eq').textContent"), ui.ev("exprOf()")], ["10", sol(no)])
    ui.ev("dstats.click()")
    time.sleep(0.1)
    ui.ev("const b=document.querySelector('#dcal-grid button[data-no=\"7\"]');if(b)b.click()")
    time.sleep(0.1)
    ui.check("カレンダーの #7 の時間は 24:00:00", "24:00:00" in ui.ev("$('dcal-line').textContent"), True)
    ui.check_no_errors("解いた式と時間（保存）: JS エラー 0")

    CODE = "K7P2QX"
    payload = {"v": 1, "days": {"3": dict(solved(3), e=XSS, t=10 ** 300), "4": dict(solved(4))},
               "set": dui.SET_DEFAULT}
    payload["days"]["4"].pop("sent")
    ui.open(now=at(no), tz=TZ, api={"xtake": "ok", "xstore": {CODE: payload}})
    ui.ev("dset.click();$('t-move').click();$('mv-in').value=%s;$('mv-take').click()" % json.dumps(CODE))
    time.sleep(0.3)
    got = (ui.saved(raw=True) or {}).get("days", {})
    ui.check("受け取った記録: HTML の式は捨て、時間は 86,400 秒まで。正しい #4 は式ごと入る（2 日とも「解いた」）",
             [got.get("3"), got.get("4")],
             [{"r": "s", "t": 86400, "h": 0, "sh": 0, "sent": 1}, dict(solved(4), sent=1)])
    ui.check_no_errors("解いた式と時間（受け取り）: JS エラー 0")
    ui.check("列のすべての日の、すべての解答は、10 になる式として通る（正しい式を捨てない）",
             ui.ev("(function(){const ng=[];let k=0;for(const p of DAILY_DAYS)for(const e of p.sols){k++;if(!exprOk(p.no,e))ng.push(p.no+':'+e)}"
                   "return [k>DAILY_DAYS.length,ng.slice(0,5)]})()"), [True, []])

    # ══ 集計の返事の数の上限（D0.48）══
    st = {"v": 1, "days": {str(no): solved(no, t=5)}, "cur": None}
    for lab, agg, shown in (("1e308", {"s": 10 ** 308, "g": 10 ** 308, "s0": 10 ** 308, "b": [10 ** 308] * 5}, False),
                            ("10 億 ＋ 1", {"s": 10 ** 9 + 1, "g": 0, "s0": 0, "b": [10 ** 9 + 1, 0, 0, 0, 0]}, False),
                            ("10 億ちょうど", {"s": 10 ** 9, "g": 10 ** 9, "s0": 0, "b": [10 ** 9, 0, 0, 0, 0]}, True)):
        ui.open(now=at(no), tz=TZ, store=st, api={"mode": "ok", "agg": agg})
        time.sleep(0.4)
        txt = ui.ev("$('aggbox').textContent")
        ui.check("集計の返事が %s: みんなの結果を%s・NaN と Infinity が出ない" % (lab, "出す" if shown else "出さない"),
                 [ui.ev("!!aggData"), "NaN" in txt or "Infinity" in txt, ui.ev("/NaN|Infinity/.test(shareTextOf(PUZZLE,dayRecord(),aggData))")],
                 [shown, False, False])
    ui.check_no_errors("集計の返事の数の上限: JS エラー 0")
