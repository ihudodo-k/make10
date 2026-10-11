# -*- coding: utf-8 -*-
"""設定（D0.13。DAILY-SPEC 13-11・10 章）。

- 上のバーの歯車（統計の左）から、設定のシートが開く。× か Esc で閉じる。作りは統計・遊び方のシートと同じ
- スイッチは 2 つ ――「途中の値を表示する」と「タップで配置する」。文は本編の設定の文と同じ
- 保存データの set に残り、開き直しても効いている。?date=（テスト表示）では保存しない（その場だけ効く）
- 切り替えたら、すぐ盤に反映する（選んでいる記号は壊れない。タップ配置をやめたときだけ放す）
- タップ配置で 1 問を最後まで解ける（本物のマウスで、記号を押して選び、置き場所を押す）。
  ヒントの箱・ギブアップ・開き直し・結果の画面も、タップ配置のまま動く
- 設定は、記録・集計・共有に載せない
"""
import datetime
import json
import re
import time

from uiharness import daily_ui as dui

NAME = "設定（途中の値・タップ配置）"

TZ = "Asia/Tokyo"
SHOWN = "!document.getElementById('dsetsheet').classList.contains('hide')"
ESC = "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"
RECT = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(x=>Math.round(x*10)/10)})()")
ON = "[...document.querySelectorAll('#dsetsheet .toggle')].map(b=>b.classList.contains('on'))"
LIVE = "document.querySelectorAll('#expr .zone.live').length"
TOKS = ("T().map(x=>x.t==='num'?String(x.v):x.t==='op'?x.v:x.t==='fac'?'!':x.t==='lp'?'(':')').join(' ')")
# 見えている文字の左右（要素の箱ではなく、中の文字そのもの）
INK = ("(function(){const r=document.createRange();r.selectNodeContents(document.querySelector(%r));"
       "const b=r.getBoundingClientRect();return [b.left,b.right]})()")
AGG = {"s": 40, "g": 10, "s0": 20, "b": [10, 10, 10, 5, 5]}


def main_text(key):
    """本編の辞書の文 [日本語, 英語]（ソースの文字列から読む。ページの JS は通さない）"""
    return re.findall(r'"%s":"([^"]*)"' % re.escape(key), dui.read(dui.MAIN_HTML))


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)


def tap(ui, sel, wait=0.45):
    """本物のマウスで、その場所を押して離す（動かさない）"""
    x, y = center(ui, sel)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseReleased", x, y)
    time.sleep(wait)


def click(ui, el_id, wait=0.2):
    ui.ev("document.getElementById(%r).click()" % el_id)
    time.sleep(wait)


def steps_of(expr):
    """解答の文字列を、タップで置く順の [(記号, 置く位置)…] にする（左から順に置く）"""
    out, p = [], 0
    for w in expr.split(" "):
        fac = 0
        while w.endswith("!"):
            fac += 1
            w = w[:-1]
        if re.fullmatch(r"[0-9]", w):
            p += 1
        elif w:
            out.append(({"(": "lp", ")": "rp"}.get(w, w), p))
            p += 1
        for _ in range(fac):
            out.append(("!", p))
            p += 1
    return out


def tap_solve(ui, expr, upto=None):
    """タップ配置で、解答を左から順に置く。upto を渡すと、その手数で止める"""
    for i, (op, p) in enumerate(steps_of(expr)):
        if upto is not None and i >= upto:
            break
        tap(ui, "#tray .chip[data-op='%s']" % op)
        tap(ui, "#expr .zone.live[data-p='%d']" % p)


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    no = 1
    row = rows[no - 1]
    w = ui.size[0]

    # ══ 上のバー: 歯車は統計の左。ほかのボタンは動かない ══
    ui.open(now=at(no), tz=TZ, perf=True)
    gear, stats, helpb = ui.ev(RECT % "#dset"), ui.ev(RECT % "#dstats"), ui.ev(RECT % "#dhelp")
    ui.check("歯車が見えていて、名前は「設定」", [ui.visible("dset"), ui.ev("dset.getAttribute('aria-label')")], [True, "設定"])
    ui.check("歯車は統計と同じ大きさ・同じ高さで、統計の左に 9px あけて並ぶ",
             [gear[2:], gear[1], round(stats[0] - (gear[0] + gear[2]), 1)], [stats[2:], stats[1], 9])
    ui.check("統計は右の端（列の端から 12px）、「?」は左の端のまま。共有は統計の真下のまま",
             [round(stats[0] + stats[2], 1), helpb[0], ui.ev(RECT % "#share")[0]], [w - 12, 12, stats[0]])
    ui.check("歯車の絵柄は、「?」・統計と同じ大きさ・同じ線の太さ・塗りなし",
             ui.ev("(function(){const f=s=>{const e=document.querySelector(s+' .ic'),c=getComputedStyle(e);"
                   "return [e.getBoundingClientRect().width,c.strokeWidth,c.fill,c.stroke].join('|')};"
                   "return f('#dset')===f('#dhelp')&&f('#dset')===f('#dstats')})()"), True)
    ui.check("歯車の絵柄は、箱の中央にある",
             ui.ev("(function(){const a=dset.getBoundingClientRect(),b=dset.querySelector('.ic').getBoundingClientRect();"
                   "return Math.abs(a.left+a.width/2-b.left-b.width/2)<.6&&Math.abs(a.top+a.height/2-b.top-b.height/2)<.6})()"), True)
    # 歯車の形（D0.15 で軽くした）: 外形の 1 本と、中の丸（線だけ）。外形の大きさは「?」の丸にそろえる
    shape = ui.ev("(function(){const s=dset.querySelector('svg'),b=s.getBBox(),h=dhelp.querySelector('svg').getBBox();"
                  "const len=e=>[...e.querySelectorAll('path,circle')].reduce((a,x)=>a+x.getTotalLength(),0);"
                  "return {kids:[...s.children].map(e=>e.tagName).join(' '),fill:[...s.children].map(e=>getComputedStyle(e).fill),"
                  "box:[b.x,b.y,b.x+b.width,b.y+b.height],help:[h.x,h.y,h.x+h.width,h.y+h.height],"
                  "len:len(s),helpLen:len(dhelp.querySelector('svg')),statsLen:len(dstats.querySelector('svg')),"
                  "teeth:(s.querySelector('path').getAttribute('d').match(/A/g)||[]).length}})()")
    ui.check("歯車の形: 外形の 1 本と中の丸。どちらも塗らない（線だけ）。歯は 6 枚",
             [shape["kids"], shape["fill"], shape["teeth"]], ["path circle", ["none", "none"], 6])
    ui.check("歯車の外形は、「?」の丸の外形（3.5〜20.5）の中に収まり、差は 0.5 以内。上下左右の中央",
             [all(abs(a - b) <= 0.5 and (a >= b if i < 2 else a <= b) for i, (a, b) in enumerate(zip(shape["box"], shape["help"]))),
              abs(shape["box"][0] + shape["box"][2] - 24) < 0.01, abs(shape["box"][1] + shape["box"][3] - 24) < 0.01],
             [True, True, True])
    # 画面に描かれた大きさでも見る（図の中の座標が同じでも、枠の取り方で大きく描けてしまうため）
    drawn = ui.ev("(function(){const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return [b.width,b.height]};"
                  "return [r('#dset svg path'),r('#dhelp svg circle')]})()")
    ui.check("画面に描かれた歯車の外形は、「?」の丸より大きくなく、差は 1.5px 以内",
             [all(g <= h + 0.01 and h - g <= 1.5 for g, h in zip(*drawn))], [True])
    ui.check("歯車の線の量は、「?」の 1.3 倍より少ない（D0.13 の 8 枚歯は 1.57 倍だった）。統計よりは多い",
             [shape["len"] < shape["helpLen"] * 1.3, shape["len"] > shape["statsLen"]], [True, True])
    # いちばん長い文字（4 桁の問題番号・2 桁の月と日）でも、歯車に重ならず、画面の軸に乗る。両方の言語
    long_no = max(n for n in range(1, len(rows) + 1) if n >= 1000 and day(n).month >= 10 and day(n).day >= 20)
    for lang in ("ja", "en"):
        ui.open(date=day(long_no).isoformat(), lang=lang)
        ink, g = ui.ev(INK % "#dinfo"), ui.ev(RECT % "#dset")
        ui.check("いちばん長い上のバーの文字（%s）: 1 行で、画面の軸に乗り、「?」と歯車に重ならない" % lang,
                 [ui.text("dinfo"), abs((ink[0] + ink[1]) / 2 - w / 2) < 1, ink[1] <= g[0], ink[0] >= 12 + g[2],
                  ui.ev("dinfo.getBoundingClientRect().height<20")],
                 [dui.top_text(long_no, day(long_no), lang), True, True, True, True])

    # ══ シート: 開く・閉じる。作りは統計・遊び方のシートと同じ ══
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.check("はじめは閉じている", ui.ev(SHOWN), False)
    click(ui, "dset")
    ui.check("歯車を押すと開く。見出しは「設定」", [ui.ev(SHOWN), ui.ev("document.querySelector('#dsetsheet h2').textContent")],
             [True, "設定"])
    sheet, close, head = ui.ev(RECT % "#dsetsheet"), ui.ev(RECT % "#dset-close"), ui.ev(RECT % "#dsetsheet h2")
    hstyle = ("(function(){const c=getComputedStyle(document.querySelector(%r));"
              "return [c.fontSize,c.fontWeight,c.color].join('|')})()")
    hs = ui.ev(hstyle % "#dsetsheet h2")
    click(ui, "dset-close")
    ui.check("× で閉じる", ui.ev(SHOWN), False)
    click(ui, "dstats")
    ui.check("シートの箱・× の位置・見出しの位置と様式は、統計のシートと同じ",
             [sheet, close, head[:2], hs],
             [ui.ev(RECT % "#dstatsheet"), ui.ev(RECT % "#dstats-close"), ui.ev(RECT % "#dstatsheet h2")[:2],
              ui.ev(hstyle % "#dstatsheet h2")])
    click(ui, "dstats-close")
    click(ui, "dhelp")
    ui.check("遊び方のシートとも同じ",
             [sheet, close, head[:2], hs],
             [ui.ev(RECT % "#dhelpsheet"), ui.ev(RECT % "#dhelp-close"), ui.ev(RECT % "#dhelpsheet h2")[:2],
              ui.ev(hstyle % "#dhelpsheet h2")])
    click(ui, "dhelp-close")
    click(ui, "dset")
    ui.ev(ESC)
    ui.check("Esc で閉じる", ui.ev(SHOWN), False)
    ui.check("× の名前は「閉じる」", ui.ev("document.getElementById('dset-close').getAttribute('aria-label')"), "閉じる")

    # ══ 中身: 2 つのスイッチ。文と見た目は本編の設定と同じ ══
    click(ui, "dset")
    want = [main_text("settings.easy"), main_text("settings.tap"), main_text("settings.title")]
    ui.check("本編の辞書に、3 つの文が日本語と英語である（照合の相手がある）", [len(x) for x in want], [2, 2, 2])
    ui.check("スイッチは 2 つ。文は本編の設定の文と同じ（途中の値を表示する・タップで配置する）",
             [ui.ev("[...document.querySelectorAll('#dsetsheet .toggle')].map(b=>b.id+':'+b.textContent)"),
              ui.ev("document.querySelector('#dsetsheet h2').textContent")],
             [["t-easy:" + want[0][0], "t-tap:" + want[1][0]], want[2][0]])
    ui.check("はじめは 2 つともオフ", ui.ev(ON), [False, False])
    ui.check("行は高さ 53px（本編のスイッチの行と同じ）・左右は列の端から 12px。スイッチは 44×25px で右端から 14px",
             ui.ev("[...document.querySelectorAll('#dsetsheet .toggle')].map(b=>{const r=b.getBoundingClientRect(),"
                   "s=b.querySelector('.sw').getBoundingClientRect();"
                   "return [r.height,r.left,innerWidth-r.right,s.width,s.height,Math.round(r.right-s.right)]})"),
             [[53, 12, 12, 44, 25, 14]] * 2)
    ui.check("行の文字は 13.5px・太字。面も枠も持たない（囲まない）",
             ui.ev("(function(){const c=getComputedStyle(document.getElementById('t-easy'));"
                   "return [c.fontSize,c.fontWeight,c.backgroundColor,c.borderTopWidth].join('|')})()"),
             "13.5px|700|rgba(0, 0, 0, 0)|0px")
    ui.check("区切りの線は、行の間に 1 本だけ（最後の行の下には引かない）",
             ui.ev("[...document.querySelectorAll('#dsetsheet .toggle')].map(b=>getComputedStyle(b,'::after').height)"),
             ["1px", "auto"])
    ui.check("シートに金も赤も無い",
             ui.ev("(function(){const cs=getComputedStyle(document.body),bad=[cs.getPropertyValue('--gold'),"
                   "cs.getPropertyValue('--coral')].map(v=>{const d=document.createElement('i');d.style.color=v;"
                   "document.body.appendChild(d);const c=getComputedStyle(d).color;d.remove();return c});"
                   "return [...document.querySelectorAll('#dsetsheet *')].filter(e=>{const c=getComputedStyle(e);"
                   "return bad.includes(c.color)||bad.includes(c.backgroundColor)}).length+'|'+bad.join('|')})()"),
             "0|rgb(227, 193, 111)|" + ui.ev("(function(){const d=document.createElement('i');d.style.color='var(--coral)';"
                                             "document.body.appendChild(d);const c=getComputedStyle(d).color;d.remove();return c})()"))
    click(ui, "dset-close")

    # ══ 途中の値を表示する ══
    ui.ev("put('+',1);render()")
    ui.check("オフ: 記号を 1 つ置いても、読み出し行は空", [ui.ev(TOKS), ui.text("eq")], ["8 + 7 5 2", ""])
    click(ui, "dset")
    click(ui, "t-easy")
    ui.check("オンにすると、その場で盤に途中の値が出る（シートを開いたまま）",
             [ui.ev(ON), ui.text("eq"), ui.ev("eq.className")], [[True, False], "15  ·  5  ·  2", "eq part"])
    ui.check("オンにしても、盤の式・手数・時間の数え方は変わらない",
             [ui.ev(TOKS), ui.ev("moves"), ui.ev("seenFrom!==null")], ["8 + 7 5 2", 0, True])
    ui.check("保存データの set に残る", ui.saved(raw=True)["set"], {"easy": 1, "tap": 0})
    ui.check("スイッチは押されている状態を名乗る（aria-pressed）",
             ui.ev("['t-easy','t-tap'].map(i=>document.getElementById(i).getAttribute('aria-pressed'))"), ["true", "false"])
    click(ui, "dset-close")
    ui.check("読み出し行は 1 行で、上のバーにも式にも重ならない",
             ui.ev("(function(){const e=eq.getBoundingClientRect(),t=document.querySelector('#play .top').getBoundingClientRect(),"
                   "x=exprwrap.getBoundingClientRect();return e.top>=t.bottom&&e.bottom<=x.top&&e.right<=innerWidth&&e.left>=0})()"), True)
    ui.open(now=at(no), tz=TZ, perf=True, store="keep")
    ui.ev("put('*',2);render()")
    ui.check("開き直しても効いている（盤は空に戻り、置けば途中の値が出る）",
             [ui.ev("G.easy"), ui.text("eq"), ui.ev("tapMode")], [True, "8  ·  35  ·  2", False])
    click(ui, "dset")
    ui.check("開き直した後のスイッチは、オン・オフ", ui.ev(ON), [True, False])
    click(ui, "t-easy")
    ui.check("オフに戻すと、その場で読み出し行が空に戻り、保存も戻る",
             [ui.text("eq"), ui.saved(raw=True)["set"]], ["", {"easy": 0, "tap": 0}])
    click(ui, "dset-close")
    ui.check_no_errors("途中の値: JS エラー 0")

    # ══ タップ配置: 切り替えと、選んでいる記号 ══
    ui.open(now=at(no), tz=TZ, perf=True)
    plus = "#tray .chip[data-op='+']"
    tap(ui, plus)
    ui.check("オフ（ドラッグ）: 記号を押して離しただけでは、選ばれない", [ui.ev("held"), ui.ev(LIVE), ui.ev(TOKS)], [None, 0, "8 7 5 2"])
    click(ui, "dset")
    click(ui, "t-tap")
    click(ui, "dset-close")
    ui.check("オンにすると保存され、盤がタップ配置になる", [ui.saved(raw=True)["set"], ui.ev("tapMode")], [{"easy": 0, "tap": 1}, True])
    tap(ui, plus)
    n_live = ui.ev("livePositions('+').size")
    ui.check("記号を押すと選ばれる: トレイの記号に下線の印・置ける場所の枠が開く（置ける場所の数だけ）",
             [ui.ev("held"), ui.ev("document.querySelector(%r).classList.contains('sel')" % plus), ui.ev(LIVE), n_live > 0],
             ["+", True, n_live, True])
    ui.check("選んでいる間、式ははみ出さない（枠のぶん縮む）",
             ui.ev("expr.getBoundingClientRect().width<=exprwrap.clientWidth+1"), True)
    # 選んだまま「途中の値」を切り替えても、選んでいる記号は壊れない
    click(ui, "dset")
    click(ui, "t-easy")
    click(ui, "dset-close")
    ui.check("選んだまま「途中の値」を切り替えても、選んでいる記号と枠はそのまま",
             [ui.ev("held"), ui.ev(LIVE), ui.ev("document.querySelector(%r).classList.contains('sel')" % plus)], ["+", n_live, True])
    tap(ui, "#expr .zone.live[data-p='1']")
    ui.check("置き場所を押すと置かれ、選択が外れて枠が閉じる。1 手。途中の値もその場で出る",
             [ui.ev(TOKS), ui.ev("held"), ui.ev(LIVE), ui.ev("moves"), ui.text("eq")], ["8 + 7 5 2", None, 0, 1, "15  ·  5  ·  2"])
    tap(ui, "#tray .chip[data-op='*']")
    tap(ui, "#expr .tok.op")
    ui.check("別の演算を選んで、置いてある演算を押すと差し替わる（1 手）", [ui.ev(TOKS), ui.ev("held"), ui.ev("moves")], ["8 * 7 5 2", None, 2])
    tap(ui, plus)
    tap(ui, plus)
    ui.check("同じ記号をもう一度押すと、選択が外れる", [ui.ev("held"), ui.ev(LIVE)], [None, 0])
    tap(ui, "#expr .tok.op")
    ui.check("何も選んでいないときに、置いてある記号を押すと外れる", ui.ev(TOKS), "8 7 5 2")
    # タップ配置をやめると、選んでいた記号を放す
    tap(ui, plus)
    click(ui, "dset")
    click(ui, "t-tap")
    click(ui, "dset-close")
    ui.check("選んだままタップ配置をやめると、選択が外れて枠が閉じる（ドラッグに戻る）",
             [ui.ev("tapMode"), ui.ev("held"), ui.ev(LIVE), ui.ev("document.querySelectorAll('#tray .chip.sel').length"),
              ui.saved(raw=True)["set"]], [False, None, 0, 0, {"easy": 1, "tap": 0}])
    x, y = center(ui, plus)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseMoved", x, y - 6)
    time.sleep(0.45)
    tx, ty = center(ui, "#expr .zone.live[data-p='1']")
    for k in range(1, 6):
        mouse(ui, "mouseMoved", x + (tx - x) * k / 5, (y - 6) + (ty - (y - 6)) * k / 5)
        time.sleep(0.03)
    mouse(ui, "mouseReleased", tx, ty)
    time.sleep(0.5)
    ui.check("やめた後は、今までどおりドラッグで置ける", ui.ev(TOKS), "8 + 7 5 2")
    ui.check_no_errors("切り替え: JS エラー 0")

    # ══ タップ配置で、1 問を最後まで解く（ヒントの箱を出したまま）══
    ui.open(now=at(no), tz=TZ, perf=True, api={"mode": "ok", "agg": AGG},
            store={"v": 1, "days": {}, "cur": None, "set": {"easy": 1, "tap": 1}})
    ui.check("保存してある設定で開く: 2 つともオン", [ui.ev("G.easy"), ui.ev("tapMode")], [True, True])
    click(ui, "hint")
    ui.check("ヒントの丸ボタン: もらう前の知らせの箱が出る", ui.ev("hintbox.classList.contains('show')"), True)
    n_steps = len(steps_of(row["sol"]))
    ui.tick(61000)
    tap_solve(ui, row["sol"], upto=n_steps - 1)
    ui.check("ヒントの箱が出ている間も、タップで置ける（箱は出たまま）",
             [ui.ev("moves"), ui.ev("hintbox.classList.contains('show')"), ui.ev("solved")], [n_steps - 1, True, False])
    op, p = steps_of(row["sol"])[-1]
    tap(ui, "#tray .chip[data-op='%s']" % op)
    tap(ui, "#expr .zone.live[data-p='%d']" % p, wait=0.9)
    ui.check("タップ配置で最後まで解ける: 「10」と「正解」、結果の画面へ移る",
             [ui.text("eq"), ui.text("sub"), ui.ev("play.classList.contains('done')"), ui.visible("result"),
              ui.ev("hintbox.classList.contains('show')"), ui.ev("held"), ui.ev(LIVE)],
             ["10", "正解", True, True, False, None, 0])
    rec = ui.saved(raw=True)
    ui.check("記録: 解いた式・時間・ヒントの回数・共有の回数だけ（設定は載らない）",
             {k: v for k, v in rec["days"][str(no)].items() if k != "sent"},
             {"r": "s", "t": 61, "h": 0, "sh": 0, "e": row["sol"]})
    ui.check("保存の設定は、記録とは別の場所（set）のまま", rec["set"], {"easy": 1, "tap": 1})
    calls = ui.api_calls()
    ui.check("集計へ送る中身は、今までの 4 つだけ（設定は送らない）",
             [len(calls), sorted(json.loads(calls[0]["body"]).keys())], [1, ["h", "n", "r", "t"]])
    ui.check("共有文に、設定のことは入らない", ui.ev("shareTextOf(PUZZLE.no,dayRecord(),streakNow())"),
             "Make10 #%d ⏱1:01 💡0 🔥1" % no)
    # 結果の画面では、切り替えても盤も並びも動かない
    before = [ui.ev(TOKS), ui.text("eq"), ui.ev(RECT % "#result"), ui.ev(RECT % "#exprwrap")]
    click(ui, "dset")
    click(ui, "t-easy")
    click(ui, "t-tap")
    click(ui, "dset-close")
    ui.check("解いた後に切り替えても、盤・「10」・結果の並びは動かない（設定だけが変わる）",
             [[ui.ev(TOKS), ui.text("eq"), ui.ev(RECT % "#result"), ui.ev(RECT % "#exprwrap")], ui.saved(raw=True)["set"]],
             [before, {"easy": 0, "tap": 0}])
    ui.check_no_errors("タップ配置で解く: JS エラー 0")

    # ══ タップ配置のまま: 開き直し（途中）と、ギブアップ ══
    ui.open(now=at(no), tz=TZ, perf=True,
            store={"v": 1, "days": {}, "cur": {"no": no, "ms": 42000, "h": 0, "sh": 0}, "set": {"easy": 0, "tap": 1}})
    ui.check("途中で開き直す: タップ配置のまま・盤は空・時間は続きから",
             [ui.ev("tapMode"), ui.ev(TOKS), ui.ev("held"), ui.ev("Math.round(seenMs)")], [True, "8 7 5 2", None, 42000])
    tap(ui, plus)
    click(ui, "dgiveup")
    ui.check("記号を選んだまま、ギブアップの入口を押すと確認が出る", [ui.ev("gubox.classList.contains('show')"), ui.ev("held")], [True, "+"])
    click(ui, "gu-yes", 0.5)
    ui.check("ギブアップ: 解答例が盤に出て、選択と枠は残らない",
             [ui.text("eq"), ui.ev(TOKS), ui.ev("held"), ui.ev(LIVE), ui.ev("play.classList.contains('done')")],
             ["ギブアップ", row["sol"], None, 0, True])
    ui.check("ギブアップの記録にも、設定は載らない",
             {k: v for k, v in ui.saved(raw=True)["days"][str(no)].items() if k != "sent"}, {"r": "g", "t": None, "h": 0, "sh": 0})
    ui.open(now=at(no), tz=TZ, perf=True, store="keep")
    ui.check("ギブアップの後に開き直す: 結果の画面・タップ配置の設定はそのまま",
             [ui.text("eq"), ui.ev("tapMode"), ui.visible("result")], ["ギブアップ", True, True])
    ui.check_no_errors("開き直しとギブアップ: JS エラー 0")

    # ══ ?date=（テスト表示）: その場だけ効き、保存しない ══
    ui.open(date=day(no).isoformat())
    click(ui, "dset")
    click(ui, "t-easy")
    click(ui, "t-tap")
    click(ui, "dset-close")
    tap(ui, plus)
    tap(ui, "#expr .zone.live[data-p='1']")
    ui.check("?date=: 切り替えは、その場で効く", [ui.ev(TOKS), ui.text("eq"), ui.ev("tapMode")], ["8 + 7 5 2", "15  ·  5  ·  2", True])
    ui.check("?date=: 保存しない（保存データは、開く前のまま）", ui.saved(), None)
    ui.open(date=day(no).isoformat(), store={"v": 1, "days": {}, "cur": None, "set": {"easy": 1, "tap": 1}})
    ui.check("?date=: 保存してある設定も読まない（2 つともオフで始まる）", [ui.ev("G.easy"), ui.ev("tapMode")], [False, False])

    # ══ 保存できない環境・形の違う保存データ ══
    ui.open(now=at(no), tz=TZ, store="blocked")
    click(ui, "dhelp-close")
    click(ui, "dset")
    click(ui, "t-tap")
    click(ui, "dset-close")
    tap(ui, plus)
    tap(ui, "#expr .zone.live[data-p='1']")
    ui.check("保存できない環境: 切り替えはその場で効き、そのまま遊べる", [ui.ev(TOKS), ui.ev("tapMode")], ["8 + 7 5 2", True])
    ui.check_no_errors("保存できない環境で JS エラー 0")
    for bad in (None, 5, "x", {"easy": "1", "tap": None}, {"tap": 1}):
        st = {"v": 1, "days": {}, "cur": None}
        if bad is not None:
            st["set"] = bad
        ui.open(now=at(no), tz=TZ, store=st)
        ui.check("保存データの set が %r: 0 か 1 に直して読む" % (bad,), [ui.ev("DATA.set"), ui.ev("G.easy"), ui.ev("tapMode")],
                 [{"easy": 1 if isinstance(bad, dict) and bad.get("easy") else 0,
                   "tap": 1 if isinstance(bad, dict) and bad.get("tap") else 0},
                  bool(isinstance(bad, dict) and bad.get("easy")), bool(isinstance(bad, dict) and bad.get("tap"))])

    # ══ 英語 ══
    ui.open(now=at(no), tz=TZ, lang="en")
    click(ui, "dset")
    ui.check("英語: 見出しと 2 つの文は、本編の英語の文と同じ。歯車と × の名前",
             [ui.ev("document.querySelector('#dsetsheet h2').textContent"),
              ui.ev("[...document.querySelectorAll('#dsetsheet .toggle')].map(b=>b.textContent)"),
              ui.ev("dset.getAttribute('aria-label')"), ui.ev("document.getElementById('dset-close').getAttribute('aria-label')")],
             [want[2][1], [want[0][1], want[1][1]], "Settings", "Close"])
    ui.check("英語: 行の文字は 1 行で、スイッチに重ならない。シートは横にはみ出さない",
             ui.ev("[...document.querySelectorAll('#dsetsheet .toggle')].every(b=>{const s=b.firstElementChild.getBoundingClientRect(),"
                   "k=b.querySelector('.sw').getBoundingClientRect();return s.height<24&&s.right<=k.left})"
                   "&&document.documentElement.scrollWidth<=innerWidth"), True)
    ui.check("英語のシートに、日本語の文字が無い",
             ui.ev("/[\\u3040-\\u30ff\\u4e00-\\u9fff]/.test(document.getElementById('dsetsheet').textContent)"), False)
    ui.check("どの画面でもスクロールなし", ui.scrolls(), False)
    ui.check_no_errors("英語: JS エラー 0")
