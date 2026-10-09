# -*- coding: utf-8 -*-
"""起動と画面（D0.2）。問題画面・「問題がありません」・テスト表示・版・パソコンの列の中央配置。

判定は見えている値で取る。期待値の起点日と列は、ページのソースから読む（`daily_ui.page_data()`）。
"""
import datetime

from uiharness import daily_ui as dui

NAME = "起動と画面"

RECT = ("(function(){const r=document.getElementById(%r).getBoundingClientRect();"
        "return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)]})()")


def run(ui):
    start, rows = dui.page_data()
    w, h = ui.size
    iso = lambda d: d.isoformat()                      # noqa: E731
    last = start + datetime.timedelta(days=len(rows) - 1)

    # ── #1 の日を ?date= で開く ──
    ui.open(date=iso(start))
    ui.check("問題画面が見えている", [ui.visible("play"), ui.visible("nopuzzle")], [True, False])
    ui.check("上のバー: 問題番号・日付・曜日", ui.text("dinfo"), dui.top_text(1, start))
    ui.check("ページの題名", ui.ev("document.title"), "Make10 デイリー")
    ui.check("<html lang> は日本語", ui.ev("document.documentElement.lang"), "ja")
    ui.check("版が画面のいちばん下に見えている",
             [ui.visible("dver"), ui.text("dver")], [True, "デイリー " + ui.ev("DAILY_VERSION")])
    ui.check("?date= のときは「テスト表示（記録しません）」",
             [ui.visible("dtest"), ui.text("dtest")], [True, "テスト表示（記録しません）"])
    ui.check("盤に 4 つの数字が並ぶ",
             ui.ev("[...document.querySelectorAll('#expr .num')].map(e=>e.textContent).join('')"),
             rows[0]["id"])
    ui.check("トレイの記号は 8 つ",
             ui.ev("[...document.querySelectorAll('#tray .chip')].map(e=>e.dataset.op).join(' ')"),
             "+ - * / ^ ! lp rp")
    ui.check("読み出し行は空", [ui.text("eq"), ui.text("sub")], ["", ""])
    ui.check("縦にも横にもスクロールしない", ui.scrolls(), False)
    ui.check("版の行は、トレイより下で、画面の中",
             ui.ev("(function(){const t=tray.getBoundingClientRect(),v=dver.getBoundingClientRect();"
                   "return v.top>=t.bottom&&v.bottom<=innerHeight})()"), True)
    # 列ははみ出しを切り落とすので、スクロールだけでは「押し出されて見えない」を拾えない。位置でも見る
    ui.check("上のバー・式・「全部消す」・トレイが、上から順に、重ならずに画面の中にある",
             ui.ev("(function(){const r=s=>document.querySelector(s).getBoundingClientRect();"
                   "const a=[r('#play .top'),r('#field'),r('#clear'),r('#tray'),r('#dfoot')];"
                   "return a.every((x,i)=>x.height>0&&x.top>=0&&x.bottom<=innerHeight+0.5"
                   "&&(i===0||x.top>=a[i-1].bottom-0.5))})()"), True)
    ui.check("上のバーの文字は画面の左右の中央",
             ui.ev("(function(){const r=dinfo.getBoundingClientRect(),a=app.getBoundingClientRect();"
                   "return Math.abs((r.left+r.right)/2-(a.left+a.right)/2)<1})()"), True)
    ui.check("見えているボタンは、遊び方・統計・共有・ギブアップ・全部消す・ヒント",
             ui.ev("[...document.querySelectorAll('button')].filter(b=>b.offsetHeight>0"
                   "&&getComputedStyle(b).visibility!=='hidden').map(b=>b.id).join(' ')"),
             "dhelp dstats share dgiveup clear hint")
    ui.check("ボタンの名前",
             ui.ev("[dhelp,dstats,share,dgiveup,hint].map(b=>b.getAttribute('aria-label')).join(' ')"),
             "遊び方 統計 共有 ギブアップ ヒント")
    ui.check("「全部消す」の名前", ui.ev("clear.getAttribute('aria-label')"), "全部消す")
    ui.check("画面に、辞書の印やキーがそのまま出ていない",
             ui.ev("/\\{\\w+\\}|daily\\.|read\\.|btn\\./.test(document.body.innerText)"), False)
    # 列の幅と高さ。スマホの画面では、列＝画面
    ui.check("列（#app）は画面いっぱい", ui.ev(RECT % "app"), [0, 0, w, h])
    ui.check_no_errors()

    # ── 「全部消す」 ──
    ui.solve(rows[0]["sol"])
    n_before = ui.ev("T().length")
    ui.ev("clear.click()")
    ui.check("「全部消す」で記号が消え、数字だけになる",
             [n_before > 4, ui.ev("T().length"), ui.ev("T().every(x=>x.t==='num')")], [True, 4, True])

    # ── 最後の日・その次の日・起点日の前の日 ──
    ui.open(date=iso(last))
    ui.check("列の最後の日は問題が出る",
             [ui.visible("play"), ui.text("dinfo")], [True, dui.top_text(len(rows), last)])
    for name, day in (("列の終わりの次の日", last + datetime.timedelta(days=1)),
                      ("起点日の前の日", start - datetime.timedelta(days=1))):
        ui.open(date=iso(day))
        ui.check("%s: 「問題がありません」" % name,
                 [ui.visible("play"), ui.visible("nopuzzle"), ui.text("nopuzzle")],
                 [False, True, "問題がありません"])
        ui.check("%s: テスト表示と版は出る" % name,
                 [ui.visible("dtest"), ui.visible("dver")], [True, True])
        ui.check("%s: スクロールしない" % name, ui.scrolls(), False)
        ui.check_no_errors("%s: JS エラー 0" % name)

    # ── ?date= なし（今日）。起点日は遠い未来なので「問題がありません」。テスト表示は出ない ──
    today = datetime.date.today()
    ui.open()
    want_play = start <= today <= last
    ui.check("?date= なし: 今日が列の外なら「問題がありません」",
             [ui.visible("play"), ui.visible("nopuzzle")], [want_play, not want_play])
    ui.check("?date= なし: テスト表示は出ない", ui.visible("dtest"), False)
    ui.check_no_errors("?date= なし: JS エラー 0")

    # ── ?date= の形が違う・無い日付は無視して、今日として扱う ──
    for bad in ("2099-02-30", "2099-1-5", "abc", "20990105"):
        ui.open(date=bad)
        ui.check("?date=%s は無視（テスト表示にならない）" % bad,
                 [ui.visible("dtest"), ui.visible("play")], [False, want_play])

    # ── パソコン: 列は幅 430・高さ最大 900 で、画面の上下左右の中央（DAILY-SPEC 14-1）──
    for sw, sh, want in ((1440, 900, [505, 0, 430, 900]), (1280, 720, [425, 0, 430, 720]),
                         (1440, 1100, [505, 100, 430, 900])):
        ui.resize(sw, sh)
        ui.open(date=iso(start))
        ui.check("パソコン %d×%d: 列の位置と大きさ" % (sw, sh), ui.ev(RECT % "app"), want)
        ui.check("パソコン %d×%d: 問題画面が列の中に収まる" % (sw, sh),
                 ui.ev("(function(){const a=app.getBoundingClientRect();"
                       "return [...document.querySelectorAll('#play .top,#eq,#expr,#tray,#clear,#dver')]"
                       ".every(e=>{const r=e.getBoundingClientRect();"
                       "return r.left>=a.left-1&&r.right<=a.right+1&&r.top>=a.top-1&&r.bottom<=a.bottom+1})})()"),
                 True)
        ui.check("パソコン %d×%d: スクロールしない" % (sw, sh), ui.scrolls(), False)
    ui.restore()
