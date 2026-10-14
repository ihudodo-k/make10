# -*- coding: utf-8 -*-
"""ギブアップの確認（D0.28。DAILY-SPEC 13-3・13-12）。

- 統計・遊び方・設定と同じポップアップ（幕とカード）で出す。閉じ方（外側・Esc は「いいえ」と同じ）と、
  キーボードの移動をカードの中に留める処理も同じ
- カードは式の下（丸ボタンとトレイのあたり）に出し、式と重ならない
- 開いている間も、問題の所（制約の行・読み出し行・式）は幕の上に出ていて、明るさが変わらない
- 形と位置は、この画面の大きさで見る。360×640 の回では、390×844 と 1440×900 でも見る

押す・キーを打つのは、CDP の本物の入力で行う（幕が押す所を覆っていることを確かめるため。ケース popup と同じ）。
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "ギブアップの確認"

TZ = "Asia/Tokyo"
SID = "dgusheet"
OPEN = "[...document.querySelectorAll('.dsheet')].filter(s=>!s.classList.contains('hide')&&!s.classList.contains('closing')).map(s=>s.id)"
RECT = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(v=>Math.round(v*10)/10)})()")
CENTER = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
          "return [Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)]})()")
COLOR = ("(function(v){const e=document.createElement('i');e.style.color=v;document.body.appendChild(e);"
         "const c=getComputedStyle(e).color;e.remove();return c})(%r)")
INSIDE = "!!(document.activeElement&&document.activeElement.closest('#dgusheet .dcard'))"
BEHIND = "[...app.children,dhead].filter(e=>!e.classList.contains('dsheet')).map(e=>!!e.inert)"
GU = "document.body.classList.contains('gu')"
# 式が見えているか: 数字の色・不透明度（祖先まで掛け合わせる）と、重なりの順（数字が幕より手前か）。
# 重なりの順は、押せなくしてある（inert・pointer-events:none）のを一時だけ外して elementsFromPoint で読み、すぐ戻す
LOOK = r"""(function(){
  const nums=[...document.querySelectorAll('#expr .num')],sheet=document.getElementById('dgusheet');
  const lifted=[banline,document.querySelector('.readout'),field];
  const op=e=>{let k=1;for(let x=e;x&&x.nodeType===1;x=x.parentElement)k*=+getComputedStyle(x).opacity;return k};
  play.inert=false;lifted.forEach(e=>e.style.pointerEvents='auto');
  const front=nums.map(n=>{const r=n.getBoundingClientRect(),l=document.elementsFromPoint(r.left+r.width/2,r.top+r.height/2);
    const a=l.findIndex(e=>e===n||n.contains(e)),b=l.indexOf(sheet);return a>=0&&b>=0&&a<b});
  const ro=document.querySelector('.readout'),r0=ro.getBoundingClientRect(),l0=document.elementsFromPoint(r0.left+r0.width/2,r0.top+r0.height/2);
  const eqFront=l0.indexOf(ro)>=0&&l0.indexOf(ro)<l0.indexOf(sheet)&&document.getElementById('eq').textContent!=='';
  const low=[...document.querySelectorAll('#tray .chip,#hint,#clear')];low.forEach(e=>e.style.pointerEvents='auto');
  const behind=low.every(e=>{const r=e.getBoundingClientRect(),l=document.elementsFromPoint(r.left+r.width/2,r.top+r.height/2);
    const a=l.indexOf(e),b=l.indexOf(sheet);return b>=0&&(a<0||a>b)});
  low.forEach(e=>e.style.pointerEvents='');
  lifted.forEach(e=>e.style.pointerEvents='');play.inert=true;
  return {n:nums.length,front:front.every(Boolean),eqFront,color:[...new Set(nums.map(n=>getComputedStyle(n).color))],
          op:Math.min(...nums.map(op)),stillInert:play.inert,behind}})()"""


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no = 45
    W, H = ui.size

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def mouse(kind, x, y):
        ui.c.ws.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1})

    def press(x, y, wait=0.15):
        mouse("mousePressed", x, y)
        mouse("mouseReleased", x, y)
        time.sleep(wait)

    def press_el(sel, wait=0.15):
        press(*ui.ev(CENTER % sel), wait=wait)

    def key(name, code, shift=False):
        for kind in ("rawKeyDown", "keyUp"):
            ui.c.ws.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": name, "windowsVirtualKeyCode": code,
                                                    "modifiers": 8 if shift else 0})

    def layout(tag, w, h):
        """開いている確認の、形と位置（この画面の大きさで）"""
        x, y, cw, ch = ui.ev(RECT % "#dgusheet .dcard")
        e = ui.ev(RECT % "#expr")
        foot, tray = ui.ev(RECT % ".foot"), ui.ev(RECT % "#tray")
        gap = ui.ev("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--guGap'))")
        ui.check("%s: カードの幅は「画面の幅 − 左右 12px」（上限 400px）で、左右の中央" % tag,
                 [cw, abs(x - (w - cw) / 2) <= 0.5], [min(400, w - 24), True])
        ui.check("%s: カードは式の下（式の下端から %dpx 以上空く）で、式と重ならない" % (tag, gap),
                 [y >= e[1] + e[3] + gap - 0.5, y >= e[1] + e[3]], [True, True])
        ui.check("%s: カードは丸ボタンとトレイのあたり（丸ボタンの上端からトレイの下端までの間に掛かる）" % tag,
                 [y < tray[1] + tray[3], y + ch > foot[1]], [True, True])
        ui.check("%s: カードは画面に収まり（下に 24px 以上空く）、ページは動かない" % tag,
                 [y + ch <= h - 24 + 0.5, ui.scrolls()], [True, False])
        ui.check("%s: カードは縮められていない（中身の高さのまま。ボタンはカードの中）" % tag,
                 ui.ev("(function(){const c=document.querySelector('#dgusheet .dcard'),r=c.getBoundingClientRect();"
                       "return [c.scrollHeight<=c.clientHeight+1,[...c.querySelectorAll('button')].every(b=>b.getBoundingClientRect().bottom<=r.bottom-1)]})()"),
                 [True, True])
        look = ui.ev(LOOK)
        ui.check("%s: 開いている間も、式の数字と読み出し行は幕より手前（明るさは --paper・不透明度 1 のまま）" % tag,
                 [look["n"], look["front"], look["eqFront"], look["color"], look["op"], look["stillInert"]],
                 [4, True, True, [paper], 1, True])
        ui.check("%s: 幕より手前に出すのは問題の所（制約の行・読み出し行・式）だけ。トレイと丸ボタンの場所を指すと、幕かカードに当たる" % tag,
                 [ui.ev("[banline,document.querySelector('.readout'),field].map(e=>getComputedStyle(e).zIndex)"),
                  ui.ev("[...document.querySelectorAll('#tray .chip,#hint,#clear')].every(c=>{const r=c.getBoundingClientRect();"
                        "return !!document.elementFromPoint(r.left+r.width/2,r.top+r.height/2).closest('#dgusheet')})")],
                 [["61", "61", "61"], True])
        ui.check("%s: トレイと丸ボタンは幕の後ろ（重なりの順で見る）" % tag, look["behind"], True)

    store = None
    ui.open(now=at(no), tz=TZ, store=store)
    ui.ev("placeExpr(cur.id.split('').join(' + '));render()")    # 4 + 5 + 4 + 9 = 22（読み出し行に値が出る。10 ではない）
    ui.check("（前提）読み出し行に値が出ていて、まだ解けていない", [ui.text("eq"), ui.ev("playing()")], ["22", True])
    paper = ui.ev(COLOR % "var(--paper)")
    panel, edge = ui.ev(COLOR % "var(--panel)"), ui.ev(COLOR % "var(--edge)")
    ui.check("開く前: 確認は隠れていて、問題の所も幕の上に出していない", [ui.ev(OPEN), ui.ev(GU), ui.visible(SID)], [[], False, False])

    # ══ 開く: ヒントの箱は閉じる。幕とカード ══
    ui.ev("hint.click()")
    time.sleep(0.1)
    ui.check("（前提）ヒントの知らせの箱が出ている", ui.ev("hintShown"), "lock")
    ui.ev("dgiveup.focus()")
    press_el("#dgiveup")
    ui.check("入口を押すと、確認だけが開き、ヒントの箱は閉じる", [ui.ev(OPEN), ui.ev("hintShown")], [[SID], None])
    ui.check("幕は画面いっぱい（position:fixed）で、後ろは inert。body に pop と gu",
             [ui.ev(RECT % "#dgusheet"), ui.ev("getComputedStyle(dgusheet).position"), all(ui.ev(BEHIND)),
              ui.ev("document.body.classList.contains('pop')"), ui.ev(GU)],
             [[0, 0, W, H], "fixed", True, True, True])
    ui.check("カードは alertdialog で、名前は問いの文（aria-modal・aria-labelledby）",
             ui.ev("(function(){const c=document.querySelector('#dgusheet .dcard');return [c.getAttribute('role'),c.getAttribute('aria-modal'),"
                   "document.getElementById(c.getAttribute('aria-labelledby')).textContent]})()"), ["alertdialog", "true", "ギブアップしますか？"])
    ui.check("中身は問いの文と、ボタン 2 つ（はい・いいえ）。見出しと × は無い",
             [ui.ev("[...document.querySelectorAll('#dgusheet .dcard p,#dgusheet .dcard button')].map(e=>e.textContent)"),
              ui.ev("document.querySelectorAll('#dgusheet h2').length")], [["ギブアップしますか？", "はい", "いいえ"], 0])
    look = ui.ev("(function(){const s=getComputedStyle(document.querySelector('#dgusheet .dcard'));"
                 "return [s.backgroundColor,s.borderTopWidth,s.borderTopStyle,s.borderTopColor,s.borderTopLeftRadius,s.boxShadow]})()")
    ui.check("カードは、ほかのポップアップと同じ面 --panel と細い線 --edge（1px）。角丸 16px・影なし",
             look, [panel, "1px", "solid", edge, "16px", "none"])
    ui.check("幕は、ほかのポップアップと同じ色（地の色を --popDim で重ねる）",
             ui.ev("getComputedStyle(dgusheet).backgroundColor"), ui.ev("getComputedStyle(dhelpsheet).backgroundColor"))
    ui.check("問いの文とボタンは 1 行で、カードからはみ出さない。金も赤も使わない",
             ui.ev("(function(){const c=document.querySelector('#dgusheet .dcard').getBoundingClientRect(),"
                   "es=[...document.querySelectorAll('#gu-text,#dgusheet button')];"
                   "return [es.every(e=>{const r=e.getBoundingClientRect(),lh=parseFloat(getComputedStyle(e).lineHeight)||r.height;"
                   "return r.left>=c.left&&r.right<=c.right&&e.scrollWidth<=e.clientWidth+1&&e.getClientRects().length===1}),"
                   "[...new Set(es.map(e=>getComputedStyle(e).color))]]})()"), [True, [paper]])
    layout("%d×%d" % (W, H), W, H)

    # ══ 閉じ方: いいえ・Esc・外側・式の場所。カードの中では閉じない ══
    toks = ui.ev("JSON.stringify(S.toks)")
    press_el("#gu-no")
    ui.check("「いいえ」で閉じ、そのまま解ける（記録は残らない）。後ろの inert が外れ、問題の所も元の重なりに戻る",
             [ui.ev(OPEN), ui.ev("playing()"), ui.ev("dayRecord()"), any(ui.ev(BEHIND)), ui.ev(GU),
              ui.ev("getComputedStyle(field).zIndex")], [[], True, None, False, False, "auto"])
    ui.check("閉じたら、フォーカスは入口（旗）に戻る", ui.ev("document.activeElement.id"), "dgiveup")
    press_el("#dgiveup")
    key("Escape", 27)
    time.sleep(0.1)
    ui.check("Esc で閉じる（「いいえ」と同じ。記録は残らない）", [ui.ev(OPEN), ui.ev("dayRecord()"), ui.ev(GU)], [[], None, False])
    press_el("#dgiveup")
    x, y, cw, ch = ui.ev(RECT % "#dgusheet .dcard")
    press(x + cw / 2, y + 12)
    ui.check("カードの中（問いの文の上）を押しても閉じない", ui.ev(OPEN), [SID])
    mouse("mousePressed", x + cw / 2, y + 12)
    mouse("mouseReleased", x + cw / 2, 6)
    time.sleep(0.15)
    ui.check("カードの中で押し始めて外で離しても閉じない", ui.ev(OPEN), [SID])
    press(W / 2, 6)
    ui.check("外側（画面の上の端の幕）を押すと閉じる（「いいえ」と同じ）", [ui.ev(OPEN), ui.ev("dayRecord()")], [[], None])
    press_el("#dgiveup")
    press_el("#expr .num")
    ui.check("式の数字の場所を押しても、式には何も起きず、外側を押したのと同じに閉じる",
             [ui.ev(OPEN), ui.ev("JSON.stringify(S.toks)") == toks, ui.ev("held"), ui.ev("dayRecord()")], [[], True, None, None])
    # トレイとヒントの丸ボタンは、カードの下に入ることがある。カードに掛からない物を選んで押す
    UNDER = ("(function(){const c=document.querySelector('#dgusheet .dcard').getBoundingClientRect();"
             "return [...document.querySelectorAll(%r)].map(e=>e.getBoundingClientRect())"
             ".map(r=>[Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)])"
             ".filter(([x,y])=>x<c.left||x>c.right||y<c.top||y>c.bottom)})()")
    press_el("#dgiveup")
    free = ui.ev(UNDER % "#tray .chip,#hint,#clear")
    ui.check("（前提）カードに掛からないトレイの記号か丸ボタンがある", len(free) > 0, True)
    for fx, fy in free[:1]:
        press(fx, fy)
        ui.check("カードに掛からないトレイ・丸ボタンの場所を押しても、記号は選ばれず・ヒントも出ず、閉じるだけ",
                 [ui.ev(OPEN), ui.ev("held"), ui.ev("hintShown"), ui.ev("JSON.stringify(S.toks)") == toks], [[], None, None, True])

    # ══ キーボードの移動は、カードの中に留まる ══
    ui.ev("dgiveup.focus();dgiveup.click()")
    time.sleep(0.1)
    ui.check("開いた時、フォーカスはカードに移る", ui.ev("document.activeElement===document.querySelector('#dgusheet .dcard')"), True)
    seen, inside = [], []
    for _ in range(5):
        key("Tab", 9)
        seen.append(ui.ev("document.activeElement.id"))
        inside.append(ui.ev(INSIDE))
    ui.check("Tab を 5 回打っても、フォーカスはカードの中で「はい」「いいえ」を巡る", [all(inside), seen],
             [True, ["gu-yes", "gu-no", "gu-yes", "gu-no", "gu-yes"]])
    back = []
    for _ in range(4):
        key("Tab", 9, shift=True)
        back.append(ui.ev("document.activeElement.id"))
    ui.check("Shift+Tab でも、カードの中を逆に巡る", back, ["gu-no", "gu-yes", "gu-no", "gu-yes"])
    ui.ev("[...app.children,dhead].forEach(e=>{e.inert=false})")
    ui.ev("document.querySelector('#dgusheet .dcard').focus()")
    loop = []
    for _ in range(4):
        key("Tab", 9)
        loop.append(ui.ev(INSIDE))
    ui.check("後ろの inert を外しても（古いブラウザーのまね）、Tab はカードの中で折り返す", all(loop), True)
    key("Escape", 27)
    time.sleep(0.1)
    ui.check("Esc で閉じたら、フォーカスは入口に戻る", [ui.ev(OPEN), ui.ev("document.activeElement.id")], [[], "dgiveup"])
    ui.check_no_errors("開く・閉じる・キーボード: JS エラー 0")

    # ══ はい: ギブアップになる ══
    ui.tick(20000)
    press_el("#dgiveup")
    press_el("#gu-yes", wait=0.5)
    ui.check("「はい」でギブアップになる（「10」の場所に「ギブアップ」・記録は g）。確認は閉じ、後ろは押せる形に戻る",
             [ui.text("eq"), (ui.saved() or {}).get("days", {}).get(str(no), {}).get("r"), ui.ev(OPEN), any(ui.ev(BEHIND)),
              ui.ev(GU), ui.ev("document.body.classList.contains('pop')")],
             ["ギブアップ", "g", [], False, False, False])
    ui.check("ギブアップの後は、入口（旗）が無く、確認も出せない",
             [ui.visible("dgiveup"), ui.ev("(dgiveup.click(),%s)" % OPEN)], [False, []])
    ui.check_no_errors("はい: JS エラー 0")

    # ══ 英語 ══
    ui.open(now=at(no), tz=TZ, store=store, lang="en")
    press_el("#dgiveup")
    ui.check("英語: 問いの文とボタン（Give up? · Yes · No）。どれも 1 行でカードに収まる",
             [ui.ev("[...document.querySelectorAll('#dgusheet .dcard p,#dgusheet .dcard button')].map(e=>e.textContent)"),
              ui.ev("(function(){const c=document.querySelector('#dgusheet .dcard').getBoundingClientRect();"
                    "return [...document.querySelectorAll('#gu-text,#dgusheet button')].every(e=>{const r=e.getBoundingClientRect();"
                    "return r.left>=c.left&&r.right<=c.right&&e.getClientRects().length===1})})()")],
             [["Give up?", "Yes", "No"], True])
    press_el("#gu-no")

    # ══ ほかの画面の大きさ（360×640 の回で、390×844 と 1440×900 も見る。640×360 は横に倒したスマホ ――
    #    式とトレイの間に収まらず、画面の下端に合わせて置く場合）══
    if (W, H) == (360, 640):
        for w, h in ((390, 844), (1440, 900), (640, 360)):
            ui.resize(w, h)
            try:
                ui.open(now=at(no), tz=TZ, store=store)
                ui.ev("placeExpr(cur.id.split('').join(' + '));render()")
                press_el("#dgiveup")
                ui.check("%d×%d: 確認だけが開く" % (w, h), ui.ev(OPEN), [SID])
                layout("%d×%d" % (w, h), w, h)
                if w > 430:
                    ui.check("%d×%d: 幕は上の見出し（Make10 DAILY）にも掛かる" % (w, h),
                             ui.ev("(function(){const r=dhead.getBoundingClientRect();"
                                   "return (document.elementFromPoint(r.left+r.width/2,r.top+r.height/2).closest('.dsheet')||{}).id})()"), SID)
                press_el("#gu-no")
            finally:
                ui.restore()
        # 開いたまま画面の大きさが変わったら、置き直す（式の下のまま）
        ui.open(now=at(no), tz=TZ, store=store)
        press_el("#dgiveup")
        ui.resize(390, 844)
        try:
            time.sleep(0.3)
            e = ui.ev(RECT % "#expr")
            y = ui.ev(RECT % "#dgusheet .dcard")[1]
            ui.check("開いたまま画面が 390×844 に変わっても、カードは式の下に置き直される",
                     [ui.ev(OPEN), y >= e[1] + e[3] + 16 - 0.5, ui.ev(RECT % "#dgusheet")[2:]], [[SID], True, [390, 844]])
        finally:
            ui.restore()

    # ══ 動き: ほかのポップアップと同じ。閉じる動きの間も、式は幕の上のまま ══
    ANIM = ("document.getAnimations().filter(a=>/^pop/.test(a.animationName||'')).map(a=>[a.animationName,a.effect.getTiming().duration]).sort()")
    ui.open(now=at(no), tz=TZ, store=store, motion=True)
    ui.ev("dgiveup.click()")
    ui.check("開く動き: 幕は薄れて出る・カードは少し上がりながら出る（0.24 秒）", ui.ev(ANIM), [["popfade", 240], ["popin", 240]])
    time.sleep(0.4)
    ui.ev("document.getElementById('gu-no').click()")
    ui.check("閉じる動き（0.16 秒）の間も、式は幕の上のまま（途中で暗くならない）",
             [ui.ev(ANIM), ui.ev(GU), ui.ev("dgusheet.classList.contains('closing')")], [[["popfadeout", 160], ["popout", 160]], True, True])
    time.sleep(0.4)
    ui.check("閉じる動きが終わると、隠れて、式も元の重なりに戻る", [ui.ev("dgusheet.classList.contains('hide')"), ui.ev(GU)], [True, False])
    ui.ev("dgiveup.click();document.getElementById('gu-no').click();dgiveup.click()")
    time.sleep(0.4)
    ui.check("閉じる動きの途中で開き直しても、開いたまま・式は幕の上のまま", [ui.ev(OPEN), ui.ev(GU)], [[SID], True])
    ui.ev("document.getElementById('gu-no').click()")
    time.sleep(0.4)

    # ══ 動きを減らす設定: 動かずに出て、動かずに消える ══
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        ui.open(now=at(no), tz=TZ, store=store, motion=True)
        got = ui.ev("(function(){dgiveup.click();const c=document.querySelector('#dgusheet .dcard'),s=getComputedStyle(c);"
                    "const a=[document.getAnimations().filter(x=>/^pop/.test(x.animationName||'')).length,s.opacity,s.transform,getComputedStyle(dgusheet).opacity];"
                    "document.getElementById('gu-no').click();"
                    "return a.concat([dgusheet.classList.contains('hide'),dgusheet.classList.contains('closing'),document.body.classList.contains('gu')])})()")
        ui.check("動きを減らす設定: 押したその場で、動かずに出ている。「いいえ」を押したその場で消え、式も元に戻る",
                 got, [0, "1", "none", "1", True, False, False])
        ui.ev("dgiveup.click()")
        ui.ev("document.getElementById('gu-yes').click()")
        time.sleep(0.4)
        ui.check("動きを減らす設定: 「はい」でギブアップになる", [ui.text("eq"), ui.ev(OPEN), ui.ev(GU)], ["ギブアップ", [], False])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors()
