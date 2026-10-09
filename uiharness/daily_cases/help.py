# -*- coding: utf-8 -*-
"""遊び方（D0.5。DAILY-SPEC 13-10・16-4）。

- 上のバー左の「?」から開く。× か Esc で閉じる
- 初回だけ自動で出す（保存データの印 help）。?date=（テスト表示）では自動で出さない。
  保存できない環境では、開くたびに出る
- 初回に自動で出た遊び方を読んでいる間は、時間を数えない
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "遊び方"

TZ = "Asia/Tokyo"
LINES = {
    "ja": ["4 つの数字を順番どおりに全部使って 10 を作ります。",
           "数字のあいだに演算と括弧を置きます。",
           "使える演算：+ − × ÷ ^ !",
           "^ は累乗です（2 ^ 3 = 8）",
           "! は階乗です（3! = 6）",
           "0! は 1 です（0! = 1）",
           "毎日 0 時（端末の時刻）に新しい問題になります。"],
    "en": ["Make 10 using all four numbers in order.",
           "Add operations and parentheses between them.",
           "Operations: + − × ÷ ^ !",
           "^ is power (2 ^ 3 = 8)",
           "! is factorial (3! = 6)",
           "0! is 1 (0! = 1)",
           "A new puzzle every day at midnight, your local time."],
}
BOLD = {"ja": ["^ は累乗", "! は階乗", "0! は 1"], "en": ["^ is power", "! is factorial", "0! is 1"]}
SHOWN = "!document.getElementById('dhelpsheet').classList.contains('hide')"
ESC = "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"
RECT = ("(function(){const r=document.getElementById(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(Math.round)})()")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no = 4

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def click(el_id, wait=0.2):
        ui.ev("document.getElementById(%r).click()" % el_id)
        time.sleep(wait)

    # ══ 初めて来た人: 自動で出る ══
    ui.open(now=at(no), tz=TZ, perf=True, first=True)
    ui.check("初回: 遊び方が自動で出る", ui.ev(SHOWN), True)
    ui.check("初回: 出した時点で、保存データに印が付く", ui.saved(raw=True), {"v": 1, "days": {}, "cur": None, "help": 1})
    ui.check("見出しと、7 つの行（^・!・0! の説明と、毎日 0 時の行を含む）",
             [ui.ev("document.querySelector('#dhelpsheet h2').textContent"),
              ui.ev("[...document.querySelectorAll('#dhelpbody p')].map(e=>e.textContent)")],
             ["遊び方", LINES["ja"]])
    ui.check("太字と式（式は 2 ^ 3 = 8・3! = 6・0! = 1）",
             [ui.ev("[...document.querySelectorAll('#dhelpbody b')].map(e=>e.textContent)"),
              ui.ev("[...document.querySelectorAll('#dhelpbody code')].map(e=>e.textContent)")],
             [BOLD["ja"], ["2 ^ 3 = 8", "3! = 6", "0! = 1"]])
    ui.check("キーボードの一覧とプライバシーポリシーへのリンクは、まだ無い",
             ui.ev("document.querySelectorAll('#dhelpbody a,#dhelpbody h3').length"), 0)
    ui.check("遊び方は列いっぱいに重なり、盤を覆う",
             [ui.ev(RECT % "dhelpsheet") == ui.ev(RECT % "app"),
              ui.ev("(function(){const r=expr.getBoundingClientRect();"
                    "return !!document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2).closest('#dhelpsheet')})()")],
             [True, True])
    ui.check("行は画面の中に収まり、横にはみ出さず、式は折り返さない。中を縦に動かす必要も無い",
             ui.ev("(function(){const b=dhelpbody,a=app.getBoundingClientRect();"
                   "const ps=[...b.querySelectorAll('p')],cs=[...b.querySelectorAll('code')];"
                   "return [ps.every(p=>{const r=p.getBoundingClientRect();return r.left>=a.left&&r.right<=a.right"
                   "&&p.scrollWidth<=p.clientWidth+1}),cs.every(c=>c.getClientRects().length===1),"
                   "b.scrollHeight<=b.clientHeight+1,"
                   "ps[ps.length-1].getBoundingClientRect().bottom<=dver.getBoundingClientRect().top]})()"),
             [True, True, True, True])
    ui.check("文の大きさ・行間・明るさは本編の遊び方と同じ（13px・1.75・85%）",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#dhelpbody p'));"
                   "return [s.fontSize,Math.round(parseFloat(s.lineHeight)*100)/100,s.opacity]})()"),
             ["13px", 22.75, "0.85"])
    ui.check("式は折り返さない指定（white-space:nowrap）で、太字",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#dhelpbody code'));"
                   "return [s.whiteSpace,s.fontWeight]})()"), ["nowrap", "700"])
    # 読んでいる間は時間を数えない
    ui.tick(30000)
    ui.check("初回: 読んでいる間は時間を数えない", ui.ev("Math.round(seenNow())"), 0)
    ui.visibility("hidden")
    ui.visibility("visible")
    ui.tick(5000)
    ui.check("初回: 画面を隠して戻しても、閉じるまで数え始めない", ui.ev("Math.round(seenNow())"), 0)
    click("dhelp-close")
    ui.check("× で閉じる", ui.ev(SHOWN), False)
    ui.tick(4000)
    ui.check("閉じたところから時間を数える", ui.ev("Math.round(seenNow())"), 4000)

    # ══ 「?」から開く ══
    ui.check("「?」は上のバーの左端（統計と左右対称・同じ高さ・同じ大きさ）。絵柄は丸で囲んだ ?",
             ui.ev("(function(){const h=dhelp.getBoundingClientRect(),s=dstats.getBoundingClientRect(),"
                   "a=app.getBoundingClientRect();return [Math.round(h.left-a.left)===Math.round(a.right-s.right),"
                   "h.top===s.top,h.width===s.width,h.height===s.height,"
                   "dhelp.querySelectorAll('svg.ic circle').length,dhelp.querySelectorAll('svg.ic path').length]})()"),
             [True, True, True, True, 1, 2])
    ui.check("「?」の名前（title・aria-label）", ui.ev("[dhelp.title,dhelp.getAttribute('aria-label')]"), ["遊び方", "遊び方"])
    click("dhelp")
    ui.check("「?」を押すと出る", ui.ev(SHOWN), True)
    ui.check("閉じるボタンは統計の入口と同じ場所（右上）で、名前は「閉じる」",
             [ui.ev(RECT % "dhelp-close") == ui.ev(RECT % "dstats"),
              ui.ev("document.getElementById('dhelp-close').getAttribute('aria-label')")], [True, "閉じる"])
    ui.tick(3000)
    ui.check("「?」から開いた遊び方では、時間は止めない", ui.ev("Math.round(seenNow())"), 7000)
    ui.ev(ESC)
    ui.check("Esc で閉じる", ui.ev(SHOWN), False)
    click("dstats")
    click("dstats-close")
    click("dhelp")
    click("dstats-close")
    ui.check("統計の × は、遊び方を閉じない", ui.ev(SHOWN), True)
    ui.ev(ESC)

    # ══ 2 回目からは自動で出ない ══
    ui.open(now=at(no, 12), tz=TZ, store="keep")
    ui.check("開き直す: 自動では出ない", ui.ev(SHOWN), False)
    click("dhelp")
    ui.check("開き直した後も「?」から見られる", ui.ev(SHOWN), True)
    click("dhelp-close")
    ui.open(now=at(no + 1), tz=TZ, store="keep")
    ui.check("次の日: 自動では出ない", ui.ev(SHOWN), False)

    # ══ 解いた後・ギブアップの後も「?」から見られる ══
    ui.open(now=at(no), tz=TZ)
    ui.solve(rows[no - 1]["sol"])
    ui.check("解いた後: 「?」は見えていて、押すと出る",
             [ui.visible("dhelp"), ui.ev("(document.getElementById('dhelp').click(),%s)" % SHOWN)], [True, True])

    # ══ ?date=（テスト表示）では自動で出さない ══
    ui.open(date=day(no).isoformat(), first=True)
    ui.check("?date=: 自動では出ない。保存もしない", [ui.ev(SHOWN), ui.saved(raw=True)], [False, None])
    click("dhelp")
    ui.check("?date=: 「?」からは見られる", ui.ev(SHOWN), True)

    # ══ 保存できない環境では、開くたびに出る ══
    ui.open(now=at(no), tz=TZ, store="blocked")
    first = ui.ev(SHOWN)
    click("dhelp-close")
    ui.open(now=at(no), tz=TZ, store="blocked")
    ui.check("保存できない環境: 開くたびに自動で出る", [first, ui.ev(SHOWN)], [True, True])
    click("dhelp-close")
    ui.check("保存できない環境: 閉じれば、そのまま遊べる", ui.solve(rows[no - 1]["sol"]), "10|正解")
    ui.check_no_errors("保存できない環境で JS エラー 0")

    # ══ 問題が無い日は出さない（「?」も無い）══
    ui.open(now=at(0), tz=TZ, first=True)
    ui.check("問題が無い日: 遊び方を出さず、印も付けない",
             [ui.visible("nopuzzle"), ui.ev(SHOWN), ui.visible("dhelp"), ui.saved(raw=True)],
             [True, False, False, None])

    # ══ 英語 ══
    ui.open(now=at(no), tz=TZ, lang="en", first=True)
    ui.check("英語: 見出しと 7 つの行",
             [ui.ev("document.querySelector('#dhelpsheet h2').textContent"),
              ui.ev("[...document.querySelectorAll('#dhelpbody p')].map(e=>e.textContent)"),
              ui.ev("[...document.querySelectorAll('#dhelpbody b')].map(e=>e.textContent)"),
              ui.ev("[dhelp.title,document.getElementById('dhelp-close').getAttribute('aria-label')]")],
             ["How to play", LINES["en"], BOLD["en"], ["How to play", "Close"]])
    ui.check("英語: 行は横にはみ出さず、式は折り返さない。版の行に重ならない",
             ui.ev("(function(){const b=dhelpbody,ps=[...b.querySelectorAll('p')];"
                   "return [ps.every(p=>p.scrollWidth<=p.clientWidth+1),"
                   "[...b.querySelectorAll('code')].every(c=>c.getClientRects().length===1),"
                   "b.scrollHeight<=b.clientHeight+1]})()"), [True, True, True])
    ui.check_no_errors()
