# -*- coding: utf-8 -*-
"""解いた後・ギブアップ・時間・保存・連続日数・統計（D0.3。DAILY-SPEC 7・10・13-3・13-5・13-6）。

`?date=` は保存しないので、ここでは端末の時計と時間帯を差し替えて「本物の今日」として開く。
時間は端末の時計（Date）で数える（D0.24）ので、その時計をケースから進める（`tick()`）。
60 分を過ぎたら数え直す（D0.25）。遊んでいる間の見回りは本物のタイマーなので、そこだけ実際に待つ。
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "解いた後・保存・連続日数"

GOLD = "rgb(227, 193, 111)"
DIM = "rgb(143, 163, 196)"
TZ = "Asia/Tokyo"
CLOCK_WAIT = 5.6           # 見回り（CLOCK_WATCH_MS = 5 秒おき）が 1 回は走るのを待つ秒
RECT = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.right,r.bottom].map(v=>Math.round(v*10)/10)})()")
BOARD = "T().map(x=>x.t==='num'?x.v:x.t==='op'?x.v:x.t==='fac'?'!':x.t==='lp'?'(':')').join(' ')"
# 見えているか（visibility:hidden も「見えない」に数える）
SEEN = ("(function(){const e=document.querySelector(%r);if(!e)return false;const s=getComputedStyle(e);"
        "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0})()")
COLS = ("[['r-time',null],['r-hints','r-hints-u'],['r-streak','r-streak-u']].map(([a,b])=>"
        "document.getElementById(a).textContent+(b?document.getElementById(b).textContent:''))")
STATS = ("[...document.querySelectorAll('#statlist .stat')].map(e=>"
         "e.querySelector('.sk').textContent+'='+e.querySelector('.sv').textContent)")


def flat(expr):
    """列の式の書き方（"( 3 + 1 )! / 6" の ! は前に付く）を、盤の並び（1 記号ずつ）に直す"""
    out = []
    for w in expr.split(" "):
        n = len(w) - len(w.rstrip("!"))
        out.append(w.rstrip("!"))
        out.extend("!" * n)
    return " ".join(out)


def pretty(expr):
    return expr.replace("*", "×").replace("/", "÷").replace("-", "−")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10, minute=0, offset=9):
        """問題番号 n の日の、その時間帯での時刻（UTC のミリ秒）"""
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=offset))
        return int(datetime.datetime(d.year, d.month, d.day, hour, minute, tzinfo=tz).timestamp() * 1000)

    multi = next(r for r in rows[:60] if len(r["sols"]) >= 3)        # 全解答が 3 本以上の日
    single = next(r for r in rows if len(r["sols"]) == 1)            # 全解答が 1 本だけの日
    no = multi["no"]

    # ══ 解く。時間は、最初に見た時刻からの実際の経過時間（隠している間も数える。D0.24）══
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.check("問題の画面が出た瞬間に、最初に見た時刻がその日の分として保存される", ui.saved(),
             {"v": 1, "days": {}, "cur": {"no": no, "start": at(no), "h": 0, "sh": 0}})
    ui.check("解く前: 結果の並びは出ていない。ギブアップの入口・トレイ・「全部消す」が見える",
             [ui.ev(SEEN % "#result"), ui.ev(SEEN % "#dgiveup"), ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#clear")],
             [False, True, True, True])
    ui.check("解く前: テスト表示ではない", ui.visible("dtest"), False)
    before = [ui.ev(RECT % "#exprwrap"), ui.ev(RECT % ".readout")]
    ui.tick(40000)                       # 見ている 40 秒
    ui.visibility("hidden")
    ui.tick(25000)                       # 隠れている 25 秒（これも数える）
    ui.check("隠しても、最初に見た時刻は動かない", ui.saved()["cur"], {"no": no, "start": at(no), "h": 0, "sh": 0})
    ui.visibility("visible")
    ui.check("見せ直しても、最初に見た時刻は動かない（数え直さない）",
             [ui.saved()["cur"]["start"], ui.ev("startAt")], [at(no), at(no)])
    ui.tick(37000)                       # 見ている 37 秒
    got = ui.solve(multi["sol"], wait=0.9)
    ui.check("解いた: 「10」と「正解」", got, "10|正解")
    ui.check("時間は実際の経過時間（40 + 25 + 37 秒 = 1:42。隠れていた 25 秒も数える）",
             ui.text("r-time"), "1:42")
    ui.check("3 列: 時間・ヒント 0 回・連続 1 日", ui.ev(COLS), ["1:42", "0回", "1日"])
    ui.check("3 列の名前",
             ui.ev("[...document.querySelectorAll('#result .rn')].map(e=>e.textContent)"),
             ["時間", "ヒント", "連続日数"])
    ui.check("記録: 解いた・時間 102 秒・ヒント 0・共有 0・解いた式。途中の時間は消える", ui.saved(),
             {"v": 1, "days": {str(no): {"r": "s", "t": 102, "h": 0, "sh": 0, "e": multi["sol"]}}, "cur": None})
    ui.check("トレイ・「全部消す」・ギブアップの入口が消える",
             [ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#clear"), ui.ev(SEEN % "#dgiveup")], [False, False, False])
    ui.check("式は、解く前と同じ位置（画面を切り替えない）", ui.ev(RECT % "#exprwrap"), before[0])
    # 読み出し行は式へ寄せる（D0.12）。「正解」の下端から式の上端まで、normal 40px・低い画面 32px
    want_gap = 40 if ui.viewport == "normal" else 32
    time.sleep(0.4)                                    # 寄せる動き（0.3 秒）が終わるのを待つ
    GAP = ("(()=>{const r=e=>e.getBoundingClientRect(),low=sub.textContent?sub:eq;"
           "return [Math.abs(r(exprwrap).top-r(low).bottom-%d)<1,r(eq).bottom<=r(sub).top+0.5,"
           "r(eq).top>=r(document.querySelector('.top')).bottom,"
           "getComputedStyle(document.querySelector('.readout')).transitionProperty]})()")
    ui.check("読み出し行は式へ寄る: 「正解」の下端から式まで %dpx。「10」は「正解」の上・上のバーの下。動かすのは transform" % want_gap,
             ui.ev(GAP % want_gap), [True, True, True, "transform"])       # 位置は整数に丸めて測るので、1px 未満の端数は許す
    ui.check("読み出し行の箱の大きさは変わらない（レイアウトを起こさない。下へずれただけ）",
             [ui.ev(RECT % ".readout")[0], ui.ev(RECT % ".readout")[2],
              ui.ev(RECT % ".readout")[3] - ui.ev(RECT % ".readout")[1], ui.ev(RECT % ".readout")[1] > before[1][1]],
             [before[1][0], before[1][2], before[1][3] - before[1][1], True])
    ui.check("盤に自分の式が残る", ui.ev(BOARD), flat(multi["sol"]))
    ui.check("盤は動かせない（式が操作を受けない）",
             ui.ev("getComputedStyle(document.getElementById('expr')).pointerEvents"), "none")
    # 並びと収まり
    n = len(multi["sols"])
    ui.check("全解答の箱: 「解答例：」と 1 本目、下に 1/N",
             [ui.ev("document.querySelector('#solbox .hbin').textContent"),
              ui.ev("document.querySelector('#solbox .hsub').textContent")],
             ["解答例：" + pretty(multi["sols"][0]), "1/%d" % n])
    ui.check("アプリへの導線", [ui.text("applink"), ui.ev("applink.getAttribute('href')")],
             ["もっと解きたい人はアプリで", "https://make10.app/"])
    order = ui.ev("['#exprwrap','.rcols','#rshare','#solbox','#applink','#dver'].map(s=>{"
                  "const r=document.querySelector(s).getBoundingClientRect();return [r.top,r.bottom]})")
    ui.check("上から 式 → 3 列 → 共有ボタン → 全解答 → 導線 → 版 の順で、重ならない",
             all(order[i][1] <= order[i + 1][0] + 0.5 for i in range(len(order) - 1)), True)
    gap = {"normal": 24, "compact": 16, "small": 16}[ui.viewport]
    ui.check("間隔は normal 24px・compact 16px。式と 3 列のあいだは 8px 広い",
             [round(order[1][0] - order[0][1], 1), round(order[2][0] - order[1][1], 1),
              round(order[3][0] - order[2][1], 1), round(order[4][0] - order[3][1], 1)],
             [gap + 8, gap, gap, gap])
    ui.check("共有ボタン「結果を共有」は幅 168px・丸ボタンと同じ高さで、左右の中央",
             ui.ev("(function(){const r=rshare.getBoundingClientRect(),b=dstats.getBoundingClientRect();"
                   "return [rshare.textContent,r.width,r.height-b.height,"
                   "Math.abs((r.left+r.right)/2-innerWidth/2)<0.6]})()"), ["結果を共有", 168, 0, True])
    # 低い画面用の詰めが効いていること（D0.3 は、後ろの規則に負けて効いていなかった）
    low = ui.viewport != "normal"
    ui.check("3 列の数字・導線・版の行の大きさ（normal 26px・48px・52px ／ 低い画面 22px・44px・40px）",
             ui.ev("[getComputedStyle(document.querySelector('.rcol .rv b')).fontSize,"
                   "applink.getBoundingClientRect().height,dfoot.getBoundingClientRect().height,"
                   "document.querySelector('.rcol').getBoundingClientRect().height]"),
             ["22px", 44, 40, 47] if low else ["26px", 48, 52, 53])
    ui.check("3 列は画面の幅の 3 等分（列の中央が 1/6・3/6・5/6）",
             ui.ev("[...document.querySelectorAll('.rcol')].map(e=>{const r=e.getBoundingClientRect();"
                   "return Math.round((r.left+r.right)/2/innerWidth*600)/100})"), [1, 3, 5])
    ui.check("全解答の箱は高さ 58px で、左右 12px 空く",
             ui.ev("(function(){const r=solbox.getBoundingClientRect();"
                   "return [r.height,r.left,innerWidth-r.right]})()"), [58, 12, 12])
    ui.check("スクロールしない（縦に動かせる形にもなっていない）",
             [ui.scrolls(), ui.ev("app.classList.contains('scrolly')")], [False, False])
    ui.check("金を使っているのは「10」だけ",
             ui.ev("[...document.querySelectorAll('#app *')].filter("
                   "e=>!e.closest('#dhelpsheet')&&getComputedStyle(e).color===%r).map(e=>e.id)" % GOLD), ["eq"])
    # 全解答を送る
    ui.ev("document.getElementById('sol-next').click()")
    ui.check("箱を押すと次の解答（2/N）",
             [ui.ev("document.querySelector('#solbox .hbin').textContent"),
              ui.ev("document.querySelector('#solbox .hsub').textContent")],
             ["解答例：" + pretty(multi["sols"][1]), "2/%d" % n])
    for _ in range(n - 1):
        ui.ev("document.getElementById('sol-next').click()")
    ui.check("最後の次は 1 本目に戻る",
             ui.ev("document.querySelector('#solbox .hsub').textContent"), "1/%d" % n)
    ui.check("箱を送っても、記録は変わらない", ui.saved()["days"][str(no)]["t"], 102)
    ui.check_no_errors("解いた後: JS エラー 0")

    # ══ 開き直すと結果の画面（解き直せない）══
    ui.open(now=at(no, 15), tz=TZ, perf=True, store="keep")
    ui.check("開き直す: 結果の画面が出て、トレイと「全部消す」は無い",
             [ui.ev(SEEN % "#result"), ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#clear"), ui.ev(SEEN % "#dgiveup")],
             [True, False, False, False])
    ui.check("開き直す: 「10」と「正解」、盤に自分の式、時間は記録のまま",
             [ui.text("eq"), ui.text("sub"), ui.ev(BOARD), ui.ev(COLS)],
             ["10", "正解", flat(multi["sol"]), ["1:42", "0回", "1日"]])
    ui.tick(50000)
    ui.visibility("hidden")
    ui.check("開き直した後は、時間も記録も動かない", ui.saved(),
             {"v": 1, "days": {str(no): {"r": "s", "t": 102, "h": 0, "sh": 0, "e": multi["sol"]}}, "cur": None})
    ui.check_no_errors("開き直す: JS エラー 0")
    # 解答例でない解き方で解いても、その式が残る
    other = multi["sols"][-1]
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.tick(5000)
    ui.solve(other, wait=0.9)
    ui.open(now=at(no, 20), tz=TZ, store="keep")
    ui.check("解答例でない式で解いて開き直しても、自分の式が出る", ui.ev(BOARD), flat(other))

    # ══ 解いている途中で開き直す: 時間は、保存した「最初に見た時刻」から。盤は空 ══
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.ev("put('+',1);render()")
    ui.tick(30000)
    ui.check("閉じる前に、最初に見た時刻は保存されている（閉じるときの保存に頼らない）",
             ui.saved()["cur"], {"no": no, "start": at(no), "h": 0, "sh": 0})
    ui.open(now=at(no, 10, 20), tz=TZ, perf=True, store="keep")          # 閉じていた間に、時計は 20 分進んだ
    ui.check("途中で開き直す: 盤は空に戻る（数字だけ）", ui.ev(BOARD), " ".join(multi["id"]))
    ui.check("途中で開き直す: まだ解ける", [ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#result")], [True, False])
    ui.check("途中で開き直す: 最初に見た時刻は、保存したもののまま（開き直した時刻にしない）",
             [ui.ev("startAt"), ui.saved()["cur"]["start"]], [at(no), at(no)])
    ui.tick(12000)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("途中で開き直す: 閉じていた間も数える（20 分 + 12 秒 = 20:12）",
             [ui.text("r-time"), ui.saved()["days"][str(no)]["t"]], ["20:12", 1212])
    # ══ 60 分で数え直す（D0.25）══
    cur0 = lambda t, h=0, sh=0: {"no": no, "start": t, "h": h, "sh": sh}          # noqa: E731
    MIN = 60000
    # (1) 開き直したとき: 2 回開き直して、最初に見てから 62 分。開き直した時から数え直す
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.open(now=at(no, 10, 30), tz=TZ, perf=True, store="keep")
    ui.check("30 分で開き直す: まだ置き直さない（最初に見た時刻のまま）", [ui.ev("startAt"), ui.saved()["cur"]], [at(no), cur0(at(no))])
    ui.open(now=at(no, 11, 2), tz=TZ, perf=True, store="keep")
    ui.check("62 分で開き直す: 開き直した時刻に置き直し、保存も直す",
             [ui.ev("startAt"), ui.saved()["cur"]], [at(no, 11, 2), cur0(at(no, 11, 2))])
    ui.tick(5000)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("62 分で開き直して 5 秒で解く: 0 から数え直した 0:05（1:02:05 にしない）。記録は 5 秒",
             [ui.ev(COLS), ui.saved()["days"][str(no)]["t"]], [["0:05", "0回", "1日"], 5])
    # (2) 画面に戻ってきたとき: 隠して 61 分。戻った時から数え直す。ヒントと共有の回数は残る
    ui.open(now=at(no), tz=TZ, perf=True, store={"v": 1, "days": {}, "cur": cur0(at(no), 1, 3)})
    ui.visibility("hidden")
    ui.tick(61 * MIN)
    time.sleep(CLOCK_WAIT)
    ui.check("隠れている間は、60 分を過ぎても置き直さない（見回りも何もしない）",
             [ui.ev("startAt"), ui.saved()["cur"]], [at(no), cur0(at(no), 1, 3)])
    ui.visibility("visible")
    ui.check("61 分たって画面に戻る: 戻った時刻に置き直し、保存も直す。ヒントと共有の回数は残る",
             [ui.ev("startAt"), ui.saved()["cur"], ui.ev("[hintUsed,shareCount]")],
             [at(no, 11, 1), cur0(at(no, 11, 1), 1, 3), [1, 3]])
    ui.tick(42000)
    ui.solve(multi["sol"], wait=0.9)
    rec = ui.saved()["days"][str(no)]
    ui.check("戻ってから 42 秒で解く: 0:42。記録にヒント 1 回・共有 3 回が残る",
             [ui.text("r-time"), rec["t"], rec["h"], rec["sh"]], ["0:42", 42, 1, 3])
    # (3) 遊んでいる間の見回り: 画面を見せたまま 60 分を過ぎると、見回りが置き直す
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.check("見回りの間隔と、60 分の定数", ui.ev("[CLOCK_WATCH_MS,CLOCK_MAX_MS]"), [5000, 3600000])
    ui.tick(60 * MIN - 1)
    time.sleep(CLOCK_WAIT)
    ui.check("59 分 59.999 秒: 見回りは置き直さない", [ui.ev("startAt"), ui.saved()["cur"]], [at(no), cur0(at(no))])
    ui.tick(1)
    time.sleep(CLOCK_WAIT)
    ui.check("ちょうど 60 分: 画面を見せたままでも、見回りが置き直す（保存も直す）",
             [ui.ev("startAt"), ui.saved()["cur"]], [at(no, 11), cur0(at(no, 11))])
    ui.tick(59 * MIN + 59000)
    time.sleep(CLOCK_WAIT)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("置き直してから 59 分 59 秒で解く: 59:59（記録は 60 分未満）",
             [ui.text("r-time"), ui.saved()["days"][str(no)]["t"]], ["59:59", 3599])
    kept = ui.saved()
    ui.tick(2 * 60 * MIN)
    ui.visibility("hidden")
    ui.visibility("visible")
    time.sleep(CLOCK_WAIT)
    ui.check("解いたその画面のまま 2 時間たっても、記録は動かない（戻ってきても・見回りでも）",
             [ui.saved(), ui.text("r-time")], [kept, "59:59"])
    # (4) 見回りの合間に 60 分を過ぎて解いても、記録は 60 分未満
    for extra, want in ((0, 1), (2000, 1), (-400, 3599), (-1000, 3599)):
        ui.open(now=at(no), tz=TZ, perf=True)
        ui.ev("for(let i=1;i<1e4;i++)clearInterval(i)")          # 見回りを止めて、合間を作る
        ui.tick(60 * MIN + extra)
        ui.solve(multi["sol"], wait=0.9)
        t = ui.saved()["days"][str(no)]["t"]
        ui.check("見回りの合間に、60 分%+d ミリ秒で解く: 記録は %d 秒（60 分未満）" % (extra, want),
                 [t, t < 3600, ui.text("r-time")], [want, True, dui.fmt_time(want)])
    # (5) 何度置き直しても、ヒントと共有の回数は残る。別の日・解いた後・ギブアップの後は置き直さない
    ui.open(now=at(no, 15), tz=TZ, perf=True, store={"v": 1, "days": {}, "cur": cur0(at(no), 2, 5)})
    ui.check("5 時間たって開き直す: 開き直した時刻に置き直す。ヒント 2 回・共有 5 回は残る",
             [ui.saved()["cur"], ui.ev("[hintUsed,shareCount]")], [cur0(at(no, 15), 2, 5), [2, 5]])
    done = {"v": 1, "cur": None, "days": {str(no): {"r": "s", "t": 77, "h": 0, "sh": 0, "e": multi["sol"], "sent": 1}}}
    ui.open(now=at(no), tz=TZ, perf=True, store=done)
    ui.tick(3 * 60 * MIN)
    ui.visibility("hidden")
    ui.visibility("visible")
    time.sleep(CLOCK_WAIT)
    ui.check("解いた後は、何時間たっても記録が動かない（見回りは何もしない）", ui.saved(), done)
    FIT = ("(()=>{const r=[...document.querySelectorAll('.rcol .rv')].map(e=>e.getBoundingClientRect());"
           "return r[0].right<=r[1].left&&r[0].left>=0})()")
    # 時間の表示の決まり（期待値は、ページの関数を使わずに組む）
    secs = [1, 59, 60, 61, 599, 3599, 3600, 3661, 36000, 86399, 86400, 359999, 360000]
    ui.check("時間の表示: 1 時間までは m:ss、1 時間からは h:mm:ss（24 時間を超えても時のまま）",
             ui.ev("%r.map(fmtTime)" % secs), [dui.fmt_time(s) for s in secs])
    ui.check("…その例は 0:59・59:59・1:00:00・1:01:01・23:59:59・100:00:00",
             [dui.fmt_time(s) for s in (59, 3599, 3600, 3661, 86399, 360000)],
             ["0:59", "59:59", "1:00:00", "1:01:01", "23:59:59", "100:00:00"])
    # いちばん長い表示（1 日ぶん・100 時間）でも、結果の 3 列に収まる
    for sec in (86399, 360000):
        ui.open(now=at(no, 15), tz=TZ, store={"v": 1, "cur": None, "days": {
            str(no): {"r": "s", "t": sec, "h": 2, "sh": 0, "e": multi["sol"], "sent": 1}}})
        ui.check("長い時間（%s）: 結果の 3 列に収まり、重ならず、スクロールも出ない" % dui.fmt_time(sec),
                 [ui.text("r-time"), ui.ev(FIT), ui.scrolls()], [dui.fmt_time(sec), True, False])
    # 別の日の「最初に見た時刻」は引き継がない（日付が変わったら、新しく数える）
    ui.open(now=at(no + 1), tz=TZ, perf=True, store={"v": 1, "days": {}, "cur": {"no": no, "start": at(no), "h": 1, "sh": 2}})
    ui.check("日付が変わって別の問題になったら、開いた時から新しく数える（前の日の時刻・回数は消える）",
             [ui.saved()["cur"], ui.ev("[hintUsed,shareCount]")], [{"no": no + 1, "start": at(no + 1), "h": 0, "sh": 0}, [0, 0]])
    ui.tick(8000)
    ui.solve(rows[no]["sol"], wait=0.9)
    ui.check("前の日の時間は引き継がない（0:08）", ui.text("r-time"), "0:08")
    # 端末の時計が戻された（経過時間がマイナス）ら、1 秒
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.tick(-600000)                     # 開いた後に、時計を 10 分戻す
    ui.solve(multi["sol"], wait=0.9)
    ui.check("開いた後に時計が戻された: マイナスにせず 1 秒（0:01）",
             [ui.text("r-time"), ui.saved()["days"][str(no)]["t"]], ["0:01", 1])
    ui.open(now=at(no), tz=TZ, perf=True, store={"v": 1, "days": {}, "cur": {"no": no, "start": at(no, 13), "h": 0, "sh": 0}})
    ui.tick(4000)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("保存した時刻が今より先（閉じている間に時計が戻された）: 1 秒（0:01）",
             [ui.text("r-time"), ui.saved()["days"][str(no)]["t"]], ["0:01", 1])
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("1 秒より短くても 1 秒（0:01）", [ui.text("r-time"), ui.saved()["days"][str(no)]["t"]], ["0:01", 1])
    # 保存した時刻の形が違うときは、開いた時から数える
    for bad in ("x", None, {}):
        ui.open(now=at(no), tz=TZ, perf=True, store={"v": 1, "days": {}, "cur": {"no": no, "start": bad, "h": 1, "sh": 1}})
        ui.check("最初に見た時刻が数でない（%r）: 開いた時から数える。回数は引き継ぐ" % (bad,),
                 ui.saved()["cur"], {"no": no, "start": at(no), "h": 1, "sh": 1})
    # 隠れたまま読み込まれた（裏のタブで開いた）ときは、見えた時から数える
    ui.open(now=at(no), tz=TZ, perf=True, hidden=True)
    ui.tick(50000)
    ui.check("隠れたまま読み込まれた間は、まだ数え始めない（保存もしない）", [ui.ev("startAt"), ui.saved()], [None, None])
    ui.visibility("visible")
    ui.check("初めて見えた時が、最初に見た時刻", ui.saved()["cur"], {"no": no, "start": at(no) + 50000, "h": 0, "sh": 0})
    ui.visibility("hidden")
    ui.tick(20000)
    ui.visibility("visible")
    ui.tick(7000)
    ui.solve(multi["sol"], wait=0.9)
    ui.check("そこからは、隠している間も数える（20 + 7 秒 = 0:27）", ui.text("r-time"), "0:27")
    # ギブアップは、時間を残さない（今までどおり）
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.tick(3700000)
    ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
    time.sleep(0.5)
    ui.check("ギブアップ: 1 時間たっていても、時間は「—」で、記録の時間は無い。途中の分は消える",
             [ui.text("r-time"), ui.saved()], ["—", {"v": 1, "days": {str(no): {"r": "g", "t": None, "h": 0, "sh": 0}}, "cur": None}])
    ui.check_no_errors("時間: JS エラー 0")

    # ══ ギブアップ ══
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.check("ギブアップの入口は、上のバー左の席の真下（間隔 8px・同じ大きさ）",
             ui.ev("(function(){const g=dgiveup.getBoundingClientRect(),s=dhelp"
                   ".getBoundingClientRect(),b=dstats.getBoundingClientRect();"
                   "return [g.left-s.left,g.top-s.bottom,g.width-s.width,g.height-b.height]})()"), [0, 8, 0, 0])
    ui.check("確認は、押すまで出ない", ui.ev(SEEN % "#dgusheet"), False)
    ui.ev("dgiveup.click()")
    ui.check("入口を押すと、確認がポップアップで出る（D0.28。形・位置・閉じ方はケース giveup）",
             [ui.ev(SEEN % "#dgusheet"),
              ui.ev("[...document.querySelectorAll('#dgusheet .dcard p,#dgusheet button')].map(e=>e.textContent)")],
             [True, ["ギブアップしますか？", "はい", "いいえ"]])
    ui.check("確認のカードは、式に重ならない",
             ui.ev("document.querySelector('#dgusheet .dcard').getBoundingClientRect().top>=expr.getBoundingClientRect().bottom"), True)
    ui.ev("document.getElementById('gu-no').click()")
    ui.check("「いいえ」で確認が消え、そのまま解ける",
             [ui.ev(SEEN % "#dgusheet"), ui.ev(SEEN % "#tray"), ui.saved()],
             [False, True, {"v": 1, "days": {}, "cur": {"no": no, "start": at(no), "h": 0, "sh": 0}}])       # 保存にあるのは「最初に見た時刻」だけ
    ui.tick(20000)
    ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
    ui.check("「はい」: 「10」の場所に「ギブアップ」（副次色。金は使わない）",
             [ui.text("eq"), ui.text("sub"), ui.ev("getComputedStyle(eq).color"),
              ui.ev("eq.classList.contains('hit')")], ["ギブアップ", "", DIM, False])
    ui.check("ギブアップの後: 金はどこにも無い",
             ui.ev("[...document.querySelectorAll('#app *')].filter("
                   "e=>!e.closest('#dhelpsheet')&&getComputedStyle(e).color===%r).length" % GOLD), 0)
    ui.check("ギブアップの後: 盤に解答例", ui.ev(BOARD), flat(multi["sol"]))
    ui.check("ギブアップの後: 時間は「—」（副次色）・ヒント 0 回・連続 0 日",
             [ui.ev(COLS), ui.ev("getComputedStyle(document.getElementById('r-time')).color")],
             [["—", "0回", "0日"], DIM])
    ui.check("ギブアップの後: 全解答は「ほかの解き方：」で 2 本目から",
             [ui.ev("document.querySelector('#solbox .hbin').textContent"),
              ui.ev("document.querySelector('#solbox .hsub').textContent")],
             ["ほかの解き方：" + pretty(multi["sols"][1]), "1/%d" % (n - 1)])
    ui.check("ギブアップの後: トレイ・「全部消す」・入口・確認が消える",
             [ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#clear"), ui.ev(SEEN % "#dgiveup"), ui.ev(SEEN % "#dgusheet")],
             [False, False, False, False])
    ui.check("ギブアップの記録（時間は持たない）", ui.saved(),
             {"v": 1, "days": {str(no): {"r": "g", "t": None, "h": 0, "sh": 0}}, "cur": None})
    ui.check("ギブアップの後: 並びが版の行より上に収まり、スクロールしない",
             [ui.ev("applink.getBoundingClientRect().bottom<=dver.getBoundingClientRect().top+0.5"),
              ui.scrolls()], [True, False])
    ui.check_no_errors("ギブアップ: JS エラー 0")
    ui.open(now=at(no, 18), tz=TZ, store="keep")
    ui.check("ギブアップの後に開き直す: 同じ結果の画面（解き直せない）",
             [ui.text("eq"), ui.ev(BOARD), ui.ev(COLS), ui.ev(SEEN % "#tray")],
             ["ギブアップ", flat(multi["sol"]), ["—", "0回", "0日"], False])
    # ほかの解き方が無い日は、箱を出さない
    ui.open(now=at(single["no"]), tz=TZ)
    ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
    ui.check("ほかの解き方が無い日のギブアップ: 全解答の箱を出さない",
             [ui.ev(SEEN % "#solbox"), ui.ev(SEEN % "#applink")], [False, True])
    ui.open(now=at(single["no"]), tz=TZ)
    ui.solve(single["sol"], wait=0.9)
    ui.check("全解答が 1 本だけの日に解いた: 箱は 1/1 で、押しても送れない",
             [ui.ev("document.querySelector('#solbox .hsub').textContent"),
              ui.ev("!!document.getElementById('sol-next')")], ["1/1", False])

    # ══ 低い画面では間隔を詰め、それでも収まらなければ縦に動かせるようにする（13-5）══
    FIT = ("(function(){const r=s=>document.querySelector(s).getBoundingClientRect();"
           "return [getComputedStyle(result).getPropertyValue('--resGap'),app.classList.contains('scrolly'),"
           "r('#applink').bottom<=r('#dtest').top+0.5]})()")
    for sw, sh, want in ((360, 640, ["12px", False, True]), (360, 600, ["8px", False, True]),
                         (430, 720, ["16px", False, True])):
        ui.resize(sw, sh)
        ui.open(date=day(no).isoformat())
        ui.solve(multi["sol"], wait=0.9)
        ui.check("画面 %d×%d: 間隔・縦に動かせる形か・版の行より上に収まるか" % (sw, sh), ui.ev(FIT), want)
        ui.check("画面 %d×%d: スクロールしない" % (sw, sh), ui.scrolls(), False)
    ui.resize(360, 380)
    ui.open(date=day(no).isoformat())
    ui.solve(multi["sol"], wait=0.9)
    ui.check("画面 360×380（8px でも収まらない）: 列の中を縦に動かせる形になり、導線まで動かして届く",
             ui.ev("(function(){const a=document.getElementById('app');a.scrollTop=9999;"
                   "const l=applink.getBoundingClientRect();"
                   "return [getComputedStyle(result).getPropertyValue('--resGap'),a.classList.contains('scrolly'),"
                   "a.scrollTop>0,l.bottom<=innerHeight+0.5]})()"), ["8px", True, True, True])
    # 幅がとても狭いときは、収まらない式だけ縮める（ラベルは縮めない）。いちばん長い式の日で見る
    longest = max(rows, key=lambda r: max(len(x) for x in r["sols"]))
    ui.resize(240, 690)
    ui.open(date=day(longest["no"]).isoformat())
    ui.solve(longest["sol"], wait=0.9)
    ui.check("幅 240px・いちばん長い式の日: どの解答もはみ出さず、行の高さも変わらない。長い式は縮む",
             ui.ev("(function(){let over=0,min=100;const n=PUZZLE.sols.length;for(let i=0;i<n;i++){"
                   "const b=document.querySelector('#solbox .hbody'),c=document.querySelector('#solbox code');"
                   "if(b.scrollWidth>b.clientWidth+0.5)over++;"
                   "if(Math.abs(document.querySelector('#solbox .hintrow').getBoundingClientRect().height-48)>0.5)over++;"
                   "const f=parseFloat(c.style.fontSize)||100;if(f<min)min=f;"
                   "document.getElementById('sol-next').click()}return [over,min<100,min>=50]})()"),
             [0, True, True])
    ui.restore()

    # ══ 連続日数と統計 ══
    def rec(r, t=60):
        return {"r": r, "t": t if r == "s" else None, "h": 0, "sh": 0, "e": "x"}

    def stats():
        ui.ev("dstats.click()")
        got = ui.ev(STATS)
        ui.ev("document.getElementById('dstats-close').click()")
        return got

    cases = [
        ("3 日続けて解いて、4 日目はまだ", {1: "s", 2: "s", 3: "s"}, 4, 3,
         ["解いた日数=3日", "連続日数=3日", "最長=3日", "平均時間=1:00"]),
        ("2 日目がギブアップ", {1: "s", 2: "g", 3: "s"}, 4, 1,
         ["解いた日数=2日", "連続日数=1日", "最長=1日", "平均時間=1:00"]),
        ("3 日目は遊ばなかった", {1: "s", 2: "s"}, 4, 0,
         ["解いた日数=2日", "連続日数=0日", "最長=2日", "平均時間=1:00"]),
        ("昨日がギブアップ", {1: "s", 2: "s", 3: "g"}, 4, 0,
         ["解いた日数=2日", "連続日数=0日", "最長=2日", "平均時間=1:00"]),
        ("何も遊んでいない", {}, 4, 0,
         ["解いた日数=0日", "連続日数=0日", "最長=0日", "平均時間=—"]),
    ]
    for name, days, today, streak, want in cases:
        ui.open(now=at(today), tz=TZ, store={"v": 1, "days": {str(k): rec(v) for k, v in days.items()}, "cur": None})
        ui.check("統計・%s" % name, stats(), want)
        ui.solve(rows[today - 1]["sol"], wait=0.9)
        ui.check("%s → 今日解くと連続 %d 日" % (name, streak + 1), ui.text("r-streak"), str(streak + 1))
        ui.open(now=at(today), tz=TZ, store={"v": 1, "days": {str(k): rec(v) for k, v in days.items()}, "cur": None})
        ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
        ui.check("%s → 今日ギブアップすると連続 0 日" % name, ui.text("r-streak"), "0")
    # 平均時間は解いた日だけ。最長は途切れても残る
    ui.open(now=at(9), tz=TZ, store={"v": 1, "cur": None, "days": {
        "1": rec("s", 30), "2": rec("s", 90), "3": rec("s", 120), "4": rec("g"), "6": rec("s", 200), "7": rec("s", 10)}})
    ui.check("統計: 最長は途切れても残り、平均は解いた日だけ（450 秒 ÷ 5 = 1:30）", stats(),
             ["解いた日数=5日", "連続日数=0日", "最長=3日", "平均時間=1:30"])
    # 統計の画面の開け閉め
    ui.ev("dstats.click()")
    ui.check("統計: 見出しと、盤の上に重なるカード（幕は画面いっぱい。カードは幕の中に収まる。D0.26）",
             [ui.ev(SEEN % "#dstatsheet"), ui.ev("document.querySelector('#dstatsheet h2').textContent"),
              ui.ev("(function(){const s=dstatsheet.getBoundingClientRect(),c=document.querySelector('#dstatsheet .dcard').getBoundingClientRect();"
                    "return [s.left,s.top,s.width===innerWidth,s.height===innerHeight,c.top>=24&&c.bottom<=innerHeight-24&&c.left>=12]})()")],
             [True, "統計", [0, 0, True, True, True]])
    ui.check("統計: 2 列に並ぶ（1・3 番目と 2・4 番目の左端が揃う）",
             ui.ev("(function(){const x=[...document.querySelectorAll('#statlist .stat')].map("
                   "e=>Math.round(e.getBoundingClientRect().left));return [x[0]===x[2],x[1]===x[3],x[1]>x[0]]})()"),
             [True, True, True])
    ui.ev("document.getElementById('dstats-close').click()")
    ui.check("統計: × で閉じる", ui.ev(SEEN % "#dstatsheet"), False)
    ui.ev("dstats.click();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
    ui.check("統計: Esc でも閉じる", ui.ev(SEEN % "#dstatsheet"), False)
    ui.check("統計を開いても、盤はそのまま解ける", [ui.ev(SEEN % "#tray"), ui.ev(BOARD)], [True, " ".join(rows[8]["id"])])

    # ══ 時間帯の移動 ══
    # 日本で #2 を解いた。同じ瞬間に、まだ #2 の日のハワイで開くと、結果の画面が出る（解き直せない）
    moved = {"v": 1, "cur": None, "days": {"1": rec("s"), "2": {"r": "s", "t": 60, "h": 0, "sh": 0, "e": rows[1]["sol"]}}}
    t = at(3, 0, 30)                                  # 日本の #3 の日の 0:30 ＝ ハワイは #2 の日の 5:30
    ui.open(now=t, tz="Pacific/Honolulu", store=moved)
    ui.check("西へ移動（同じ番号の日に戻る）: #2 の結果の画面が出て、解き直せない",
             [ui.text("dinfo"), ui.ev(SEEN % "#result"), ui.ev(SEEN % "#tray"), ui.text("r-streak")],
             [dui.top_text(2, day(2)), True, False, "2"])
    ui.open(now=t, tz=TZ, store=moved)
    ui.check("同じ瞬間の日本は #3 で、まだ解ける。連続は昨日までの 2 日",
             [ui.text("dinfo"), ui.ev(SEEN % "#tray"), stats()[1]], [dui.top_text(3, day(3)), True, "連続日数=2日"])
    # 日本の #2 の日の 19:30 ＝ キリバスは #3 の日の 0:30。#3 を解くと連続 3 日
    ui.open(now=at(2, 19, 30), tz="Pacific/Kiritimati", store=moved)
    ui.solve(rows[2]["sol"], wait=0.9)
    ui.check("東へ移動（次の番号の日）: #3 を解くと連続 3 日",
             [ui.text("dinfo"), ui.text("r-streak")], [dui.top_text(3, day(3)), "3"])
    ui.open(tz=None)

    # ══ ?date= は保存しない・読まない ══
    seeded = {"v": 1, "cur": None, "days": {str(no): {"r": "s", "t": 77, "h": 0, "sh": 0, "e": multi["sol"]}}}
    ui.open(date=day(no).isoformat(), store=seeded, perf=True)
    ui.check("?date=: 保存してある結果を読まない（その日をまだ解いていない形で開く）",
             [ui.visible("dtest"), ui.ev(SEEN % "#tray"), ui.ev(SEEN % "#result")], [True, True, False])
    ui.tick(9000)
    ui.visibility("hidden")
    ui.visibility("visible")
    ui.solve(multi["sols"][1], wait=0.9)
    ui.check("?date=: 解くと結果の画面は出る", [ui.ev(SEEN % "#result"), ui.text("r-time")], [True, "0:09"])
    ui.check("?date=: 保存データは 1 文字も変わらない", ui.saved(), seeded)
    ui.open(date=day(no + 1).isoformat(), store=None)
    ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
    ui.check("?date=: ギブアップしても何も保存しない", ui.saved(), None)

    # ══ 保存できない環境: 知らせずに、そのまま遊べる ══
    ui.open(now=at(no), tz=TZ, store="blocked", perf=True)
    ui.tick(15000)
    ui.visibility("hidden")
    ui.visibility("visible")
    ui.solve(multi["sol"], wait=0.9)
    ui.check("保存できない環境: 解けて、結果の画面が出る", [ui.text("eq"), ui.ev(COLS)], ["10", ["0:15", "0回", "1日"]])
    ui.check_no_errors("保存できない環境: JS エラー 0（知らせも出さない）")
    ui.open(tz=None)
