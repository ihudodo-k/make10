# -*- coding: utf-8 -*-
"""名前「Make10 DAILY」（D0.17。DAILY-SPEC 13-2・14-1）。

- スマホ（と、低い広い画面）: 上のバーの中央を 2 行にする。上の行に名前、下の行に問題番号と日付。
  上のバーの高さは変えない。盤・トレイ・ほかのボタンの位置は 1px も動かない
- パソコン（幅 720px 以上・高さ 768px 以上）: 画面の上に、幅いっぱいの見出し（高さ 60px・下に細い線）。
  列は見出しの下の残りの高さの中で、上下の中央。このときは、列の中の名前は出さない
- 金は使わない（白と副次色だけ）。押せない。読み上げには見出し（h1）として読ませる。画面に出ている h1 は、いつも 1 つ
- 「問題がありません」の画面にも名前を出す
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "名前（Make10 DAILY）"

TZ = "Asia/Tokyo"
GOLD = "rgb(227, 193, 111)"
AGG = {"s": 412, "g": 96, "s0": 268, "b": [38, 121, 147, 82, 24]}
PEND = {"s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}
RECT = ("(function(){const e=document.querySelector(%r);if(!e)return null;const r=e.getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(v=>Math.round(v*100)/100)})()")
# 見えている h1（名前）。[入っている場所, 文字]
H1 = ("[...document.querySelectorAll('h1')].filter(e=>e.getClientRects().length>0)"
      ".map(e=>[e.id||(e.closest('#dhead')?'dhead':e.closest('#dmid')?'dmid':'?'),e.textContent])")
# 名前の行を消しても動かないはずの部品の、位置と大きさ（中央の日付の行そのものは、1 行になれば中央へ動くので入れない）
PARTS = ["#play .top", "#dhelp", "#dset", "#dstats", "#share", "#dgiveup", "#banline", ".readout", "#eq", "#sub", "#field",
         "#exprwrap", "#expr", ".overlays", "#clear", "#hint", ".foot", "#tray", "#dfoot", "#dver",
         "#result", ".rcols", "#rshare", "#solbox", "#aggbox", "#applink"]
DUMP = ("(function(sels){const q=e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height].map(v=>Math.round(v*100)/100)};"
        "const o={};for(const s of sels){const e=document.querySelector(s);o[s]=e?q(e):null}"
        "o.chips=[...document.querySelectorAll('#tray .chip')].map(q);o.toks=[...document.querySelectorAll('#expr .num,#expr .tok')].map(q);"
        "o.scale=curExprScale;o.scrolly=app.classList.contains('scrolly');return o})(%s)")
# 名前の行を消して（display:none）、画面を組み直す
HIDE = ("document.querySelectorAll('#dmid .dbrand,#nobrand').forEach(e=>e.style.display='none');"
        "window.dispatchEvent(new Event('resize'))")
SHOW = ("document.querySelectorAll('#dmid .dbrand,#nobrand').forEach(e=>e.style.display='');"
        "window.dispatchEvent(new Event('resize'))")
STYLE = ("(function(){const c=s=>{const e=document.querySelector(s),x=getComputedStyle(e);"
         "return [x.color,x.fontWeight,parseFloat(x.fontSize),parseFloat(x.letterSpacing)>0]};"
         "const p=document.createElement('i');document.body.appendChild(p);const col=v=>{p.style.color=v;return getComputedStyle(p).color};"
         "const r={b:c(%r+' b'),s:c(%r+' span'),paper:col('var(--paper)'),dim:col('var(--dim)'),gold:col('var(--gold)')};p.remove();return r})()")
FITS = ("[app.classList.contains('scrolly'),!aggbox.classList.contains('hide'),"
        "document.getElementById('result').getBoundingClientRect().bottom<=dver.getBoundingClientRect().top+0.5]")


def run(ui):
    import json
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    w, h = ui.size

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def dump():
        time.sleep(0.45)
        return ui.ev(DUMP % json.dumps(PARTS))

    def moved(a, b):
        return sorted(k for k in a if a[k] != b[k])

    # ══ スマホ: 上のバーの中央が 2 行（名前・問題番号と日付）══
    for lang in ("ja", "en"):
        ui.open(now=at(1), tz=TZ, lang=lang, perf=True, api={"mode": "ok", "agg": AGG})
        pre = "%s: " % lang
        ui.check(pre + "名前は「Make10」と「DAILY」（訳さない）。画面に出ている見出し（h1）は、上のバーの 1 つだけ",
                 [ui.ev("[...document.querySelectorAll('#dmid .dbrand>*')].map(e=>e.tagName+':'+e.textContent)"), ui.ev(H1)],
                 [["B:Make10", "SPAN:DAILY"], [["dmid", "Make10DAILY"]]])
        ui.check(pre + "下の行は、今までどおり問題番号と日付", ui.text("dinfo"), dui.top_text(1, day(1), lang))
        top, brand, info, btn = ui.ev(RECT % "#play .top"), ui.ev(RECT % "#dmid .dbrand"), ui.ev(RECT % "#dinfo"), ui.ev(RECT % "#dhelp")
        ui.check(pre + "上のバーの高さは、ボタンの高さのまま（2 行にしても変わらない）", [top[3], btn[3] in (44, 52)], [btn[3], True])
        ui.check(pre + "名前が上・日付が下で、どちらも上のバーの中に収まる",
                 [brand[1] >= top[1], round(brand[1] + brand[3], 2) <= info[1] + 0.01, info[1] + info[3] <= top[1] + top[3] + 0.01],
                 [True, True, True])
        ink = ("(function(){const g=document.createRange();g.selectNodeContents(document.querySelector(%r));"
               "const r=g.getBoundingClientRect();return [r.left,r.right]})()")
        a, b, g = ui.ev(ink % "#dmid .dbrand"), ui.ev(ink % "#dinfo"), ui.ev(RECT % "#dset")
        ui.check(pre + "名前も日付も、画面の軸の上。歯車と「?」に重ならない",
                 [abs((a[0] + a[1]) / 2 - w / 2) < 1, abs((b[0] + b[1]) / 2 - w / 2) < 1, a[1] <= g[0], a[0] >= btn[0] + btn[2]],
                 [True, True, True, True])
        st = ui.ev(STYLE % ("#dmid .dbrand", "#dmid .dbrand"))
        ui.check(pre + "Make10 は白の太字。DAILY は副次色で、小さく、字間を広げてある",
                 [st["b"][:2], st["s"][0], st["s"][2] < st["b"][2], st["s"][3]], [[st["paper"], "700"], st["dim"], True, True])
        ui.check(pre + "名前に金は使わない（金の色が読めていることも見る）",
                 [st["gold"], st["gold"] in (st["b"][0], st["s"][0]),
                  ui.ev("[...document.querySelectorAll('.dbrand,.dbrand *,#dhead')].filter(e=>getComputedStyle(e).color===%r).length" % GOLD)],
                 [GOLD, False, 0])
        ui.check(pre + "名前は押せない（リンクでもボタンでもない。押しても何も起きない）",
                 ui.ev("(function(){const e=document.querySelector('#dmid .dbrand');const u=location.href,s=JSON.stringify(S.toks);"
                       "e.click();e.querySelector('b').click();"
                       "return [!!e.closest('a,button,[role=button]'),e.querySelectorAll('a,button').length,getComputedStyle(e).cursor,"
                       "location.href===u,JSON.stringify(S.toks)===s,[...document.querySelectorAll('.dsheet')].every(x=>x.classList.contains('hide'))]})()"),
                 [False, 0, "auto", True, True, True])
        ui.check(pre + "パソコンの見出しは出ていない", ui.visible("dhead"), False)

        # ── 名前の行を消しても、ほかの部品は 1px も動かない（問題画面）──
        with_brand = dump()
        ui.ev(HIDE)
        without = dump()
        ui.ev(SHOW)
        ui.check(pre + "問題画面: 名前の行があっても無くても、上のバー・盤・トレイ・ボタン・版の行の位置と大きさは同じ",
                 [moved(with_brand, without), with_brand["#play .top"][3], len(with_brand["chips"])], [[], btn[3], 8])
        # ── 解いた後も同じ ──
        ui.tick(45000)
        ui.solve(rows[0]["sol"], wait=1.2)
        with_brand = dump()
        ui.ev(HIDE)
        without = dump()
        ui.ev(SHOW)
        ui.check(pre + "解いた後: 名前の行があっても無くても、結果の並び・みんなの結果・導線の位置と大きさは同じ",
                 [moved(with_brand, without), with_brand["#aggbox"] is not None], [[], True])
        ui.check(pre + "どの画面でも、横にはみ出さない", ui.ev("document.documentElement.scrollWidth<=innerWidth"), True)
        ui.check_no_errors(pre + "JS エラー 0")

    # ══ ギブアップの確認・ヒントの箱・シートを開いても、名前は上のバーにあるまま ══
    ui.open(now=at(1), tz=TZ)
    ui.ev("document.getElementById('dhelp').click()")
    time.sleep(0.3)
    ui.check("遊び方を開くと、幕が画面に掛かる（名前の場所を指すと、幕かカードに当たる）",
             ui.ev("(function(){const r=document.querySelector('#dmid .dbrand').getBoundingClientRect();"
                   "return !!document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2).closest('#dhelpsheet')})()"), True)
    ui.ev("document.getElementById('dhelp-close').click()")

    # ══ 「問題がありません」の画面にも、名前を出す ══
    ui.open(now=at(0), tz=TZ)
    nb, np_ = ui.ev(RECT % "#nobrand"), ui.ev(RECT % "#nopuzzle")
    ui.check("問題が無い日: 名前が、上のバーがあるはずの場所に出る（上から 12px・ボタンの高さ・画面の軸）。見出しはこの 1 つ",
             [ui.visible("nopuzzle"), ui.visible("play"), ui.ev(H1), nb[1], nb[3] in (44, 52), abs(nb[0] + nb[2] / 2 - w / 2) < 1],
             [True, False, [["nobrand", "Make10DAILY"]], 12, True, True])
    st = ui.ev(STYLE % ("#nobrand", "#nobrand"))
    ui.check("問題が無い日: 名前の字は、上のバーの名前と同じ（白の太字と、副次色）", [st["b"][:2], st["s"][0]], [[st["paper"], "700"], st["dim"]])
    ui.ev(HIDE)
    ui.check("問題が無い日: 名前があっても無くても、「問題がありません」の位置は同じ", ui.ev(RECT % "#nopuzzle"), np_)
    ui.check_no_errors("問題が無い日: JS エラー 0")

    # ══ パソコン: 画面の上に、幅いっぱいの見出し。列はその下 ══
    try:
        for sw, sh, app in ((1440, 900, [505, 60, 430, 840]), (1366, 768, [468, 60, 430, 708]), (1920, 1080, [745, 120, 430, 900])):
            ui.resize(sw, sh)
            pre = "パソコン %d×%d: " % (sw, sh)
            ui.open(now=at(1), tz=TZ, perf=True, api={"mode": "ok", "agg": AGG})
            head = ui.ev(RECT % "#dhead")
            ui.check(pre + "見出しは画面の上・幅いっぱい・高さ 60px。見出し（h1）はこの 1 つで、列の中の名前は出さない",
                     [head, ui.ev(H1), ui.ev("getComputedStyle(document.querySelector('#dmid .dbrand')).display")],
                     [[0, 0, sw, 60], [["dhead", "Make10DAILY"]], "none"])
            ui.check(pre + "列は見出しの下。見出しと重ならず、残りの高さの中で上下の中央（高さの上限は 900px）",
                     [ui.ev(RECT % "#app"), app[1] >= 60, abs((app[1] - 60) - (sh - app[1] - app[3])) <= 1], [app, True, True])
            ui.check(pre + "列の中の真ん中は、問題番号と日付だけ（1 行）",
                     [ui.ev("document.getElementById('dmid').textContent"), ui.ev("dmid.getBoundingClientRect().height<20")],
                     ["Make10DAILY" + dui.top_text(1, day(1)), True])
            a = ui.ev("(function(){const g=document.createRange();g.selectNodeContents(document.querySelector('#dhead .dbrand'));"
                      "const r=g.getBoundingClientRect();return [(r.left+r.right)/2,r.top,r.bottom]})()")
            ui.check(pre + "見出しの名前は、画面の左右の中央で、見出しの中に収まる", [abs(a[0] - sw / 2) < 1, a[1] >= 0, a[2] <= 60], [True, True, True])
            st = ui.ev(STYLE % ("#dhead .dbrand", "#dhead .dbrand"))
            ui.check(pre + "見出しの名前は、スマホと同じ組み方で少し大きい（白の太字 17px・副次色の小さい字）。金は使わない",
                     [st["b"], st["s"][0], st["s"][2] < st["b"][2], st["s"][3], st["gold"] in (st["b"][0], st["s"][0])],
                     [[st["paper"], "700", 17, True], st["dim"], True, True, False])
            ui.check(pre + "見出しの下に、細い線が 1 本（--paper の 10%）。地は地の色",
                     ui.ev("(function(){const c=getComputedStyle(dhead),p=document.createElement('i');document.body.appendChild(p);"
                           "p.style.color='color-mix(in srgb,var(--paper) 10%,transparent)';const line=getComputedStyle(p).color;"
                           "p.style.color='var(--ink)';const ink=getComputedStyle(p).color;p.remove();"
                           "return [c.borderBottomWidth,c.borderBottomStyle,c.borderBottomColor===line,c.backgroundColor===ink,c.borderTopWidth]})()"),
                     ["1px", "solid", True, True, "0px"])
            ui.check(pre + "見出しの名前は押せない", ui.ev("[!!document.querySelector('#dhead a,#dhead button'),getComputedStyle(dhead).cursor]"), [False, "auto"])
            ui.check(pre + "問題画面が列の中に収まり、スクロールしない",
                     [ui.ev("(function(){const a=app.getBoundingClientRect();"
                            "return [...document.querySelectorAll('#play .top,#eq,#expr,#tray,#clear,#dver')]"
                            ".every(e=>{const r=e.getBoundingClientRect();"
                            "return r.left>=a.left-1&&r.right<=a.right+1&&r.top>=a.top-1&&r.bottom<=a.bottom+1})})()"), ui.scrolls()],
                     [True, False])
            # ポップアップ（D0.26）: 幕は画面いっぱいで、見出しにも掛かる（見出しの字は、幕の後ろに残る）
            for sheet, btn_id in (("dhelpsheet", "dhelp"), ("dstatsheet", "dstats"), ("dsetsheet", "dset")):
                ui.ev("document.getElementById(%r).click()" % btn_id)
                time.sleep(0.25)
                ui.check(pre + "%s を開く: 幕は画面いっぱいで、見出しにも掛かる。カードは幅 400px で、見出しの字は消さない" % sheet,
                         [ui.ev("(function(){const r=%s.getBoundingClientRect();return [r.left,r.top,r.width===innerWidth,r.height===innerHeight]})()" % sheet),
                          ui.ev("(document.elementFromPoint(innerWidth/2,30).closest('.dsheet')||{}).id"),
                          ui.ev("document.querySelector('#%s .dcard').getBoundingClientRect().width" % sheet), ui.ev(H1)],
                         [[0, 0, True, True], sheet, 400, [["dhead", "Make10DAILY"]]])
                ui.ev("document.getElementById(%r).click()" % (btn_id + "-close"))
            ui.tick(45000)
            ui.solve(rows[0]["sol"], wait=1.3)
            ui.check(pre + "解いた後の並びが、縦に動かさずに収まる（みんなの結果つき）", ui.ev(FITS), [False, True, True])
            ui.check(pre + "解いた後も、見出しと列は重ならない",
                     ui.ev("document.getElementById('play').getBoundingClientRect().top>=dhead.getBoundingClientRect().bottom"), True)
            ui.check_no_errors(pre + "JS エラー 0")
        # 問題が無い日: 見出しに名前が出るので、列の中の名前は出さない
        ui.resize(1440, 900)
        ui.open(now=at(0), tz=TZ)
        ui.check("パソコンの問題が無い日: 名前は見出しの 1 つだけ（列の中には出さない）",
                 [ui.visible("nopuzzle"), ui.ev(H1), ui.visible("nobrand")], [True, [["dhead", "Make10DAILY"]], False])

        # ══ 低い広い画面（1280×720 など）: 見出しは出さず、スマホと同じ出し方。列は今までどおり ══
        for sw, sh, app in ((1280, 720, [425, 0, 430, 720]), (1280, 767, [425, 0, 430, 767]), (900, 500, [235, 0, 430, 500]),
                            (719, 900, [144.5, 0, 430, 900])):
            ui.resize(sw, sh)
            pre = "%d×%d: " % (sw, sh)
            ui.open(now=at(1), tz=TZ, perf=True, api={"mode": "ok", "agg": AGG})
            ui.check(pre + "見出しは出さず、名前は上のバーの 1 行目。列の位置と大きさは今までどおり",
                     [ui.visible("dhead"), ui.ev(H1), ui.ev(RECT % "#app")], [False, [["dmid", "Make10DAILY"]], app])
        ui.resize(1280, 720)
        for name, agg in (("みんなの結果が数字", AGG), ("集計中", PEND), ("通信できない", None)):
            ui.open(now=at(1), tz=TZ, perf=True, api={"mode": "ok", "agg": agg} if agg else None)
            ui.tick(45000)
            ui.solve(rows[0]["sol"], wait=1.3)
            ui.check("1280×720: 解いた後の並びが、縦に動かさずに収まる（%s）" % name, ui.ev(FITS), [False, agg is not None, True])
    finally:
        ui.restore()
