# -*- coding: utf-8 -*-
"""カレンダー（D0.11。DAILY-SPEC 13-8）。統計の画面の、4 つの数字の下。

- 日の見分け（解いた・ギブアップ・遊ばなかった・今日・問題が無い日）を、クラスと、見えている形と色で見る
- 月の移動の端（起点日の月・今月）
- 月曜始まりで、日付が正しい列に入ること・問題番号が合っていること（月末・年をまたぐ月・うるう年・夏時間の地域）。
  期待値は Python の datetime で別に出す（ページの関数は使わない）
- 日付を押したときの 1 行・両方の言語・はみ出し・低い画面での縦の動き・?date=
"""
import calendar as pycal
import datetime
import re
import time

from uiharness import daily_ui as dui
from uiharness.daily_cases import lang as L

NAME = "カレンダー"

TZ = "Asia/Tokyo"
PAPER, DIM, EDGE, SLATE, INK = ("rgb(244, 241, 232)", "rgb(143, 163, 196)", "rgb(36, 52, 79)", "rgb(85, 104, 138)",
                                "rgb(10, 18, 32)")
GOLD, CORAL = "rgb(227, 193, 111)", "rgb(255, 122, 92)"
# 出ている月の、日ごとの [日, 列（左から 0〜6）, 段, 問題番号（ボタンでなければ null）, クラス]
GRID = ("(()=>{const g=document.getElementById('dcal-grid'),cs=[...g.querySelectorAll('.dc')];"
        "const xs=[...g.querySelectorAll('.dw')].map(e=>Math.round(e.getBoundingClientRect().left+e.getBoundingClientRect().width/2));"
        "const ys=[...new Set(cs.map(e=>Math.round(e.getBoundingClientRect().top)))].sort((a,b)=>a-b);"
        "return cs.map(e=>{const r=e.getBoundingClientRect(),x=Math.round(r.left+r.width/2);"
        "return [+e.textContent,xs.findIndex(v=>Math.abs(v-x)<=1),ys.indexOf(Math.round(r.top)),"
        "e.dataset.no?+e.dataset.no:null,[...e.classList].filter(c=>c!=='dc'&&c!=='sel').sort().join(' '),e.tagName]})})()")
HEAD = ("[document.getElementById('dcal-title').textContent,document.getElementById('dcal-prev').disabled,"
        "document.getElementById('dcal-next').disabled,[...document.querySelectorAll('#dcal-grid .dw')].map(e=>e.textContent).join(' ')]")
LINE = "document.getElementById('dcal-line').textContent"


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no_of = lambda d: (d - start).days + 1                          # noqa: E731

    def at(d, hour=10, tz_hours=9):
        tz = datetime.timezone(datetime.timedelta(hours=tz_hours))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def click(sel, wait=0.15):
        ui.ev("document.querySelector(%r).click()" % sel)
        time.sleep(wait)

    def records(today):
        """#1〜今日の前日の記録。遊ばなかった日・ギブアップの日・解いた日を混ぜる"""
        out = {}
        for n in range(1, today):
            if n % 7 in (3, 6) or n in (10, 11, 30):
                continue
            out[str(n)] = ({"r": "g", "t": None, "h": n % 3, "sh": 1} if n % 5 == 0
                           else {"r": "s", "t": 40 + n * 7, "h": n % 3, "sh": 1, "e": rows[n - 1]["sol"]})
        return out

    def want_grid(y, m, today, days):
        """その月の期待値（GRID と同じ形）。列は Python の曜日（月曜 = 0）、段は月曜始まりの週"""
        out = []
        lead = datetime.date(y, m, 1).weekday()
        for d in range(1, pycal.monthrange(y, m)[1] + 1):
            dt = datetime.date(y, m, d)
            n = no_of(dt)
            if n < 1 or n > today or n > len(rows):
                out.append([d, dt.weekday(), (lead + d - 1) // 7, None, "x", "SPAN"])
                continue
            r = days.get(str(n))
            st = "s" if r and r["r"] == "s" else "g" if r and r["r"] == "g" else "t" if n == today else "n"
            out.append([d, dt.weekday(), (lead + d - 1) // 7, n, " ".join(sorted([st] + (["today"] if n == today else []))), "BUTTON"])
        return out

    today = 45                                           # 2099-02-18（水）
    days = records(today)
    store = {"v": 1, "cur": None, "days": days}
    T = day(today)

    # ══ 開いたときは今月。4 つの数字の下 ══
    ui.open(now=at(T), tz=TZ, store=store)
    click("#dstats", 0.3)
    ui.check("開いたときは今月。今月より後へは行けない。曜日の見出しは月曜始まり",
             ui.ev(HEAD), ["%d年%d月" % (T.year, T.month), False, True, "月 火 水 木 金 土 日"])
    ui.check("カレンダーは、4 つの数字の下・版の行の上。4 つの数字はそのまま",
             ui.ev("(()=>{const r=e=>e.getBoundingClientRect(),c=r(dcal),s=r(statlist);"
                   "return [c.top>=s.bottom,c.bottom<=r(dver).top,document.querySelectorAll('#statlist .stat').length]})()"),
             [True, True, 4])

    # ══ 日の見分けと、日付が正しい列に入ること（今月）══
    g = ui.ev(GRID)
    ui.check("今月: 日・列（月曜始まり）・段・問題番号・見分けが、別に出した期待値と同じ", g, want_grid(T.year, T.month, today, days))
    ui.check("今月に、解いた・ギブアップ・遊ばなかった・今日・まだ来ていない日が全部ある（空振りしていない）",
             sorted({c[4] for c in g}), ["g", "n", "s", "t today", "x"])
    ui.check("見た目: 解いた日は塗りつぶした丸（--paper の地・地の色の数字）",
             ui.ev("(()=>{const i=document.querySelector('#dcal-grid .dc.s i'),s=getComputedStyle(i);"
                   "return [s.backgroundColor,s.color,s.borderRadius,s.borderTopWidth,Math.round(i.getBoundingClientRect().width)===Math.round(i.getBoundingClientRect().height)]})()"),
             [PAPER, INK, "50%", "0px", True])
    ui.check("見た目: ギブアップの日は輪だけの丸（--dim の線・塗りなし）",
             ui.ev("(()=>{const s=getComputedStyle(document.querySelector('#dcal-grid .dc.g i'));"
                   "return [s.backgroundColor,s.borderTopColor,s.borderTopStyle,parseFloat(s.borderTopWidth)>=1,s.borderRadius,s.color]})()"),
             ["rgba(0, 0, 0, 0)", DIM, "solid", True, "50%", DIM])      # 線は 1.5px。1 倍の密度の画面では 1px に丸まる
    # 点の色（D0.12）は、副次色を地の色に 55% 混ぜた色。期待値はここで別に計算する（ページの変数は読まない）
    rgb = lambda c: [int(v) for v in re.findall(r"\d+", c)[:3]]                       # noqa: E731
    mix = [(d * 0.55 + k * 0.45) / 255 for d, k in zip(rgb(DIM), rgb(INK))]

    def lum(c):
        f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4      # noqa: E731
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])

    ratio = lambda c: (lum(c) + 0.05) / (lum([v / 255 for v in rgb(INK)]) + 0.05)      # noqa: E731  地との明るさの比
    d = ui.ev("(()=>{const e=document.querySelector('#dcal-grid .dc.n'),a=getComputedStyle(e,'::after'),i=getComputedStyle(e.querySelector('i'));"
              "const r=e.getBoundingClientRect();"
              "return [a.content,a.width,a.height,a.backgroundColor,i.backgroundColor,i.borderTopWidth,"
              "getComputedStyle(document.querySelector('#dcal-legend i.n')).backgroundColor,"
              "getComputedStyle(document.querySelector('#dcal-legend i.n')).width]})()")
    got = [float(v) for v in re.findall(r"[\d.]+", d[3].split("srgb")[-1])[:3]] if "srgb" in d[3] else [v / 255 for v in rgb(d[3])]
    ui.check("見た目: 遊ばなかった日は、数字の下の小さな点（5px）。丸は無い。凡例の点も同じ色と大きさ",
             [d[0], d[1], d[2], d[4], d[5], d[6] == d[3], d[7]], ['""', "5px", "5px", "rgba(0, 0, 0, 0)", "0px", True, "5px"])
    ui.check("点の色は、副次色を地の色に 55% 混ぜた色（別に計算した値と同じ）",
             [round(a - b, 3) for a, b in zip(got, mix)], [0, 0, 0])
    ui.check("点は見える濃さ（地との比が 3 以上）で、輪（副次色）と塗った丸（--paper）よりは沈む",
             [ratio(got) >= 3, ratio(got) < ratio([v / 255 for v in rgb(DIM)]) / 2, ratio(got) < ratio([v / 255 for v in rgb(PAPER)]) / 4],
             [True, True, True])
    ui.check("点の色は、まだ来ていない日の数字（無効の色）とも、線（--edge）とも違う",
             [d[3] != SLATE, d[3] != EDGE, ui.ev("getComputedStyle(document.querySelector('#dcal-grid .dc.x'),'::after').content")],
             [True, True, "none"])
    # 統計のシートの様式（D0.12）: 左右の端・名前の字の大きさ・数字の大きさ
    low = ui.viewport != "normal"
    ui.check("統計: 見出し・4 つの数字・カレンダーの左端がそろう（15px）。名前の字は 11.5px でそろう",
             ui.ev("(()=>{const cs=e=>getComputedStyle(e),q=s=>document.querySelector(s),L=e=>Math.round(e.getBoundingClientRect().left*10)/10;"
                   "const x0=app.getBoundingClientRect().left;"
                   "return [L(q('#dstatsheet h2'))+parseFloat(cs(q('#dstatsheet h2')).paddingLeft)===L(q('#statlist .stat')),"
                   "L(q('#statlist .stat'))-L(dstatbody),L(dcal)-L(dstatbody),parseFloat(cs(q('#dstatsheet h2')).paddingLeft),"
                   "cs(q('.stat .sk')).fontSize,cs(q('#dcal-grid .dw')).fontSize,cs(document.getElementById('dcal-legend')).fontSize]})()"),
             [True, 15, 15, 15, "11.5px", "11.5px", "11.5px"])
    ui.check("統計: 4 つの数字は %s・段の高さ %dpx（低い画面は小さく。3 列の数字と同じ大きさ）" % (("22px", 66) if low else ("26px", 76)),
             ui.ev("[getComputedStyle(document.querySelector('.stat .sv b')).fontSize,document.querySelector('.stat').offsetHeight]"),
             ["22px", 66] if low else ["26px", 76])
    ui.check("見た目: 今日は外側に枠。点も丸も無い（まだ遊んでいない）。枠があるのは今日だけ",
             ui.ev("(()=>{const e=document.querySelector('#dcal-grid .dc.today'),s=getComputedStyle(e);"
                   "return [/inset/.test(s.boxShadow),getComputedStyle(e,'::after').content,"
                   "getComputedStyle(e.querySelector('i')).backgroundColor,document.querySelectorAll('#dcal-grid .dc.today').length,"
                   "[...document.querySelectorAll('#dcal-grid .dc:not(.today):not(.sel)')].every(x=>getComputedStyle(x).boxShadow==='none')]})()"),
             [True, "none", "rgba(0, 0, 0, 0)", 1, True])
    ui.check("見た目: まだ来ていない日は、印なし・押せない（数字は無効の色）",
             ui.ev("(()=>{const e=document.querySelector('#dcal-grid .dc.x'),s=getComputedStyle(e);"
                   "return [e.tagName,s.color,getComputedStyle(e,'::after').content,getComputedStyle(e.querySelector('i')).backgroundColor]})()"),
             ["SPAN", SLATE, "none", "rgba(0, 0, 0, 0)"])
    ui.check("カレンダーに、金も赤も使っていない",
             ui.ev("[dcal,...dcal.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e),a=getComputedStyle(e,'::after');"
                   "return [s.color,s.backgroundColor,s.borderTopColor,a.backgroundColor].some(c=>c===%r||c===%r)}).length" % (GOLD, CORAL)), 0)
    ui.check("凡例: 解いた・ギブアップ・遊ばなかった（印は日と同じ形）",
             ui.ev("[...document.querySelectorAll('#dcal-legend>span')].map(e=>[e.textContent,e.querySelector('i').className])"),
             [["解いた", "s"], ["ギブアップ", "g"], ["遊ばなかった", "n"]])

    # ══ 日付を押すと、下にその日の結果を 1 行 ══
    ui.check("開いたときは今日を選んでいる（まだ遊んでいない）",
             [ui.ev(LINE), ui.ev("[...document.querySelectorAll('#dcal-grid .dc.sel')].map(e=>e.dataset.no).join()")],
             ["#45　2月18日（水）　遊んでいません", "45"])
    r44 = days["44"]
    for n, want in ((44, "#44　2月17日（火）　%d:%02d　ヒント %d 回" % (r44["t"] // 60, r44["t"] % 60, r44["h"])),
                    (40, "#40　2月13日（金）　ギブアップ"), (38, "#38　2月11日（水）　遊んでいません")):
        click("#dcal-grid .dc[data-no='%d']" % n)
        ui.check("#%d を押す: %s" % (n, want.split("　", 2)[2]),
                 [ui.ev(LINE), ui.ev("[...document.querySelectorAll('#dcal-grid .dc.sel')].map(e=>e.dataset.no).join()"),
                  ui.ev("document.querySelector('#dcal-grid .dc[data-no=\"%d\"]').getAttribute('aria-label')" % n)],
                 [want, str(n), want])
    ui.check("選んだ日の印は下線（今日の枠・日の見分けはそのまま）。1 行は折り返さない",
             ui.ev("(()=>{const e=document.querySelector('#dcal-grid .dc.sel'),l=document.getElementById('dcal-line');"
                   "return [/inset/.test(getComputedStyle(e).boxShadow),e.classList.contains('n'),l.getClientRects().length,"
                   "l.scrollWidth<=l.clientWidth+1,Math.round(l.getBoundingClientRect().height)]})()"), [True, True, 1, True, 20])
    click("#dcal-grid .dc.x")
    ui.check("まだ来ていない日を押しても、何も変わらない", ui.ev(LINE), "#38　2月11日（水）　遊んでいません")

    # ══ 月の移動と、その端 ══
    click("#dcal-next")
    ui.check("今月で › を押しても動かない", ui.ev(HEAD)[0], "2099年2月")
    click("#dcal-prev")
    ui.check("‹ で前の月（起点日の月）。そこから前へは行けない。選んでいた日は外れ、1 行は空",
             [ui.ev(HEAD), ui.ev(LINE), ui.ev("document.querySelectorAll('#dcal-grid .dc.sel').length")],
             [["2099年1月", True, False, "月 火 水 木 金 土 日"], "", 0])
    ui.check("起点日の月: 起点日より前の日（1〜4 日）は印なし。5 日が #1 で月曜の列",
             ui.ev(GRID), want_grid(start.year, start.month, today, days))
    ui.check("起点日の月でも、1 行の高さは取ったまま（下の並びが動かない）",
             ui.ev("Math.round(document.getElementById('dcal-line').getBoundingClientRect().height)"), 20)
    click("#dcal-prev")
    ui.check("起点日の月で ‹ を押しても動かない", ui.ev(HEAD)[0], "2099年1月")
    click("#dcal-grid .dc[data-no='5']")
    ui.check("前の月の日も押せる", ui.ev(LINE), "#5　1月9日（金）　ギブアップ")
    click("#dcal-next")
    ui.check("› で今月へ戻る", ui.ev(HEAD), ["2099年2月", False, True, "月 火 水 木 金 土 日"])
    ui.check("ボタンの名前", ui.ev("['dcal-prev','dcal-next'].map(i=>document.getElementById(i).getAttribute('aria-label'))"),
             ["前の月", "次の月"])
    click("#dcal-prev")
    click("#dstats-close")
    click("#dstats", 0.3)
    ui.check("閉じて開き直すと、今月に戻る", [ui.ev(HEAD)[0], ui.ev(LINE)], ["2099年2月", "#45　2月18日（水）　遊んでいません"])
    # 集計の送り直し（17-2）が古い日に付ける「送った」の印 sent は、カレンダーとは別の仕組みなので外して比べる
    got = ui.saved()
    for r in got["days"].values():
        r.pop("sent", None)
    ui.check("カレンダーを見ても、保存データは変わらない（保存の形も変えていない）", got, store)
    ui.check_no_errors("カレンダーを操作して JS エラー 0")

    # ══ 年をまたぐ月・月末 ══
    t2 = datetime.date(2100, 1, 15)
    n2 = no_of(t2)
    ui.open(now=at(t2), tz=TZ, store={"v": 1, "cur": None, "days": records(n2)})
    click("#dstats", 0.3)
    ui.check("2100 年 1 月: 日・列・問題番号", ui.ev(GRID), want_grid(2100, 1, n2, records(n2)))
    click("#dcal-prev")
    ui.check("1 月から ‹ で前の年の 12 月（31 日まで。31 日は木曜の列）",
             [ui.ev(HEAD)[0], ui.ev(GRID) == want_grid(2099, 12, n2, records(n2)), ui.ev(GRID)[-1][:2]],
             ["2099年12月", True, [31, 3]])
    click("#dcal-next")
    ui.check("12 月から › で次の年の 1 月", ui.ev(HEAD)[0], "2100年1月")

    # ══ うるう年でない 2 月（2100 年）と、うるう年の 2 月（2104 年。列の外なので、日付の並びだけを見る）══
    t3 = datetime.date(2100, 3, 10)
    n3 = no_of(t3)
    ui.open(now=at(t3), tz=TZ, store={"v": 1, "cur": None, "days": {}})
    click("#dstats", 0.3)
    click("#dcal-prev")
    g = ui.ev(GRID)
    ui.check("2100 年 2 月は 28 日まで（100 で割れる年は、うるう年でない）",
             [ui.ev(HEAD)[0], len(g), g == want_grid(2100, 2, n3, {})], ["2100年2月", 28, True])
    ui.ev("calY=2104;calM=2;calSel=null;drawCal()")
    g = ui.ev(GRID)
    ui.check("2104 年 2 月は 29 日まで（29 日は金曜の列）", [len(g), g[-1][:2], [c[:3] for c in g] == [c[:3] for c in want_grid(2104, 2, n3, {})]],
             [29, [29, 4], True])

    # ══ 夏時間の地域（ニューヨーク。3 月に 1 時間進み、11 月に戻る）══
    for t4, tzh, what in ((datetime.date(2099, 3, 20), -4, "夏時間が始まる月（3 月 8 日）"),
                          (datetime.date(2099, 11, 20), -5, "夏時間が終わる月（11 月 1 日）")):
        n4 = no_of(t4)
        d4 = records(n4)
        ui.open(now=at(t4, 10, tzh), tz="America/New_York", store={"v": 1, "cur": None, "days": d4})
        click("#dstats", 0.3)
        ui.check("ニューヨーク・%s: 日・列・問題番号・見分けが 1 日もずれない" % what,
                 [ui.ev("DAILY_NO"), ui.ev(GRID) == want_grid(t4.year, t4.month, n4, d4)], [n4, True])

    # ══ 両方の言語のはみ出しと、英語の文 ══
    long_days = dict(days, **{"44": {"r": "s", "t": 86399, "h": 2, "sh": 1, "e": rows[43]["sol"]},
                              "43": {"r": "s", "t": 61, "h": 1, "sh": 1, "e": rows[42]["sol"]},
                              "42": {"r": "s", "t": 59, "h": 0, "sh": 1, "e": rows[41]["sol"]}})
    for lang in ("ja", "en"):
        ui.open(now=at(T), tz=TZ, lang=lang, store={"v": 1, "cur": None, "days": long_days})
        click("#dstats", 0.3)
        click("#dcal-grid .dc[data-no='44']")
        a = ui.ev(L.AUDIT)
        ui.check("%s: いちばん長い 1 行（1439:59）でも、はみ出しも折り返しも無い。統計の中身は縦に動かさずに収まる" % lang,
                 [a["over"], a["scroll"],
                  ui.ev("(()=>{const l=document.getElementById('dcal-line'),g=document.getElementById('dcal-legend'),b=dstatbody,p=app.getBoundingClientRect();"
                        "return [l.scrollWidth<=l.clientWidth+1,l.getClientRects().length,g.scrollWidth<=g.clientWidth+1,"
                        "[...dcal.querySelectorAll('*')].every(e=>{const r=e.getBoundingClientRect();return r.left>=p.left-0.5&&r.right<=p.right+0.5}),"
                        "b.scrollHeight<=b.clientHeight+1,dcal.getBoundingClientRect().bottom<=dver.getBoundingClientRect().top]})()")],
                 [[], False, [True, 1, True, True, True, True]])
        if lang == "en":
            ui.check("en: 月の名前・曜日の見出し・凡例・ボタンの名前",
                     [ui.ev(HEAD), ui.ev("[...document.querySelectorAll('#dcal-legend>span')].map(e=>e.textContent)"),
                      ui.ev("['dcal-prev','dcal-next'].map(i=>document.getElementById(i).getAttribute('aria-label'))")],
                     [["February 2099", False, True, "Mon Tue Wed Thu Fri Sat Sun"], ["Solved", "Gave up", "Missed"],
                      ["Previous month", "Next month"]])
            got = [ui.ev(LINE)]
            for n in (43, 42, 40, 38):
                click("#dcal-grid .dc[data-no='%d']" % n)
                got.append(ui.ev(LINE))
            ui.check("en: 1 行（hints は 2・1・0 で単数と複数。ギブアップ・遊んでいない）", got,
                     ["#44 · Tue, Feb 17 · 1439:59 · 2 hints", "#43 · Mon, Feb 16 · 1:01 · 1 hint", "#42 · Sun, Feb 15 · 0:59 · 0 hints",
                      "#40 · Fri, Feb 13 · Gave up", "#38 · Wed, Feb 11 · Not played"])
            ui.check("en: カレンダーに日本語の文字が無い",
                     [x for x in a["texts"] + a["labels"] if L.JP.search(x)], [])

    # ══ 低い画面: 統計の中身だけが縦に動く ══
    ui.resize(360, 460)
    try:
        ui.open(now=at(T), tz=TZ, store=store)
        click("#dstats", 0.3)
        ui.check("低い画面（360×460）: 統計の中身だけが縦に動き、いちばん下の 1 行まで届く。ページは動かない",
                 ui.ev("(()=>{const b=dstatbody;const can=b.scrollHeight>b.clientHeight+1,oy=getComputedStyle(b).overflowY;b.scrollTop=1e6;"
                       "const l=document.getElementById('dcal-line').getBoundingClientRect(),r=b.getBoundingClientRect();"
                       "return [can,oy,l.bottom<=r.bottom+0.5,r.bottom<=dver.getBoundingClientRect().top+0.5,"
                       "document.documentElement.scrollHeight<=innerHeight+1]})()"), [True, "auto", True, True, True])
    finally:
        ui.restore()

    # ══ ?date=（テスト表示）: 記録が無いので、全部「遊ばなかった日」の印 ══
    ui.open(date=T.isoformat())
    click("#dstats", 0.3)
    g = ui.ev(GRID)
    ui.check("?date=: 今日より前は全部「遊ばなかった日」、今日は枠、後ろは印なし。JS エラーなし",
             [g == want_grid(T.year, T.month, today, {}), sorted({c[4] for c in g}), ui.ev(LINE), ui.errors()],
             [True, ["n", "t today", "x"], "#45　2月18日（水）　遊んでいません", []])
    click("#dcal-prev")
    sv = ui.saved() or {}                                 # 空か、「遊び方は見た」の印だけ（前に開いた画面による）
    ui.check("?date=: 前の月へも移れる。記録は増えない", [ui.ev(HEAD)[0], sv.get("days", {}), sv.get("cur")], ["2099年1月", {}, None])
    # 解いた直後に開くと、今日が「解いた日」になる
    ui.open(now=at(T), tz=TZ, perf=True, store=store)
    ui.tick(75000)
    ui.solve(rows[today - 1]["sol"], wait=0.9)
    click("#dstats", 0.3)
    ui.check("今日を解いた後: 今日は塗りつぶした丸で、枠も付く。1 行に時間とヒントの回数",
             [ui.ev("[...document.querySelector('#dcal-grid .dc.today').classList].sort().join(' ')"), ui.ev(LINE)],
             ["dc s sel today", "#45　2月18日（水）　1:15　ヒント 0 回"])
    ui.check_no_errors()
