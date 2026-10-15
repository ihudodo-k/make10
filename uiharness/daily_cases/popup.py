# -*- coding: utf-8 -*-
"""ポップアップ（D0.26。DAILY-SPEC 13-12）。統計・遊び方・設定の 3 つ。

- 盤の上に重ねるカード（面 --panel と細い線 --edge。影なし）。幕が画面いっぱいに掛かり、後ろの盤は押せない
- 閉じ方は、外側を押す・×・Esc。開いている間、キーボードの移動（Tab）はカードの中に留まる
- カードは中身の高さ。画面より高ければ、見出しと × は残して、カードの中だけが縦に動く
- 動きは、減速して止まる曲線だけ・opacity と transform だけ。動きを減らす設定では動かない

押す・キーを打つのは、CDP の本物の入力（Input.dispatchMouseEvent・dispatchKeyEvent）で行う
（ページの関数を直に呼ぶと、幕が押す所を覆っていることや、Tab の既定の動きを確かめられない）。
"""
import datetime
import re
import time

from uiharness import daily_ui as dui

NAME = "ポップアップ"

TZ = "Asia/Tokyo"
POP_DIM, POP_BLUR = "78%", "none"          # 後ろの見え方（ページの :root の --popDim・--popBlur と同じ値）
SHEETS = (("dstatsheet", "dstats", "dstats-close", "統計"), ("dhelpsheet", "dhelp", "dhelp-close", "遊び方"),
          ("dsetsheet", "dset", "dset-close", "設定"))
# 開いているか（閉じる動きの途中は、もう閉じている扱い）
OPEN = "[...document.querySelectorAll('.dsheet')].filter(s=>!s.classList.contains('hide')&&!s.classList.contains('closing')).map(s=>s.id)"
RECT = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(v=>Math.round(v*10)/10)})()")
CENTER = ("(function(){const r=document.querySelector(%r).getBoundingClientRect();"
          "return [Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)]})()")
# 色を、計算後の形（rgb(…)）にそろえて読む
COLOR = ("(function(v){const e=document.createElement('i');e.style.color=v;document.body.appendChild(e);"
         "const c=getComputedStyle(e).color;e.remove();return c})(%r)")
INSIDE = "!!(document.activeElement&&document.activeElement.closest('#%s .dcard'))"
BEHIND = "[...app.children,dhead].filter(e=>!e.classList.contains('dsheet')).map(e=>!!e.inert)"


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

    def key(name, code, shift=False):
        for kind in ("rawKeyDown", "keyUp"):
            ui.c.ws.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": name, "windowsVirtualKeyCode": code,
                                                    "modifiers": 8 if shift else 0})

    def click(el_id, wait=0.1):
        ui.ev("document.getElementById(%r).click()" % el_id)
        time.sleep(wait)

    days = {str(n): {"r": "s", "t": 40 + n * 7, "h": n % 3, "sh": 1, "e": rows[n - 1]["sol"], "sent": 1} for n in range(20, no)}
    store = {"v": 1, "cur": None, "days": days}

    # ══ 形: 幕とカード ══
    ui.open(now=at(no), tz=TZ, store=store)
    ui.check("開く前: 3 つとも隠れていて、後ろは inert でない", [ui.ev(OPEN), any(ui.ev(BEHIND)), ui.ev("document.body.classList.contains('pop')")],
             [[], False, False])
    panel, edge = ui.ev(COLOR % "var(--panel)"), ui.ev(COLOR % "var(--edge)")
    for sid, btn, close, title in SHEETS:
        click(btn)
        card = "#%s .dcard" % sid
        ui.check("%s: 入口を押すと、その 1 つだけが開く" % title, ui.ev(OPEN), [sid])
        ui.check("%s: 幕は画面いっぱい（position:fixed）" % title,
                 [ui.ev(RECT % ("#" + sid)), ui.ev("getComputedStyle(%s).position" % sid)], [[0, 0, W, H], "fixed"])
        ui.check("%s: カードは dialog で、名前は見出し（aria-modal・aria-labelledby）" % title,
                 ui.ev("(function(){const c=document.querySelector(%r);return [c.getAttribute('role'),c.getAttribute('aria-modal'),"
                       "document.getElementById(c.getAttribute('aria-labelledby')).textContent]})()" % card), ["dialog", "true", title])
        look = ui.ev("(function(){const s=getComputedStyle(document.querySelector(%r));"
                     "return [s.backgroundColor,s.borderTopWidth,s.borderTopStyle,s.borderTopColor,s.borderTopLeftRadius,s.boxShadow]})()" % card)
        ui.check("%s: カードは面 --panel と細い線 --edge（1px）。角丸 16px・影なし" % title, look, [panel, "1px", "solid", edge, "16px", "none"])
        x, y, w, h = ui.ev(RECT % card)
        ui.check("%s: カードの幅は「画面の幅 − 左右 12px」（上限 400px）で、左右の中央" % title,
                 [w, abs(x - (W - w) / 2) <= 0.5], [min(400, W - 24), True])
        ui.check("%s: カードは上下の中央で、上下 24px の空きの中に収まる" % title,
                 [abs(y - (H - y - h)) <= 1, y >= 24, y + h <= H - 24], [True, True, True])
        ui.check("%s: 見出しと × は、カードの上の帯（× は右上）" % title,
                 ui.ev("(function(){const c=document.querySelector(%r).getBoundingClientRect(),h=document.querySelector('#%s h2').getBoundingClientRect(),"
                       "b=document.getElementById(%r).getBoundingClientRect();"
                       "return [Math.round(c.right-b.right),Math.round(b.top-c.top),b.top<=h.top&&h.bottom<=b.bottom,h.left>c.left]})()" % (card, sid, close)),
                 [7, 7, True, True])
        ui.check("%s: ページそのものは動かない（縦にも横にもスクロールが出ない）" % title, ui.scrolls(), False)
        click(close)
        ui.check("%s: × で閉じる" % title, ui.ev(OPEN), [])

    # ══ 後ろの見え方（変数 2 つで決まる）══
    click("dset")
    back = ui.ev("(function(){const r=getComputedStyle(document.documentElement),s=getComputedStyle(dsetsheet);"
                 "return {dim:r.getPropertyValue('--popDim').trim(),blur:r.getPropertyValue('--popBlur').trim(),bg:s.backgroundColor,"
                 "bf:s.backdropFilter||s.webkitBackdropFilter}})()")
    alpha = lambda c: round(float(re.findall(r"[0-9.]+", c)[-1]) * 100)          # noqa: E731  計算後の色の、最後の数（不透明度）
    ui.check("後ろの見え方: 幕は地の色 --ink を --popDim（%s）で重ねる。ぼかしは --popBlur（%s）" % (POP_DIM, POP_BLUR),
             [back["dim"], back["blur"], alpha(back["bg"]), back["bf"]], [POP_DIM, POP_BLUR, int(POP_DIM.rstrip("%")), POP_BLUR])
    ui.check("幕の色は、地の色 --ink から作っている（直値でない）",
             back["bg"], ui.ev(COLOR % ("color-mix(in srgb,var(--ink) %s,transparent)" % POP_DIM)))
    ui.ev("document.documentElement.style.setProperty('--popDim','40%');document.documentElement.style.setProperty('--popBlur','blur(5px)')")
    ui.check("2 つの変数を変えるだけで、濃さとぼかしが切り替わる",
             [alpha(ui.ev("getComputedStyle(dsetsheet).backgroundColor")), ui.ev("getComputedStyle(dsetsheet).backdropFilter")],
             [40, "blur(5px)"])
    ui.ev("document.documentElement.style.removeProperty('--popDim');document.documentElement.style.removeProperty('--popBlur')")

    # ══ 後ろの盤は押せない ══
    ui.check("開いている間、後ろ（列の中身と、広い画面の見出し）は、どれも inert。body に pop", [all(ui.ev(BEHIND)), ui.ev("document.body.classList.contains('pop')")], [True, True])
    spots = {"トレイの記号": "#tray .chip", "式の数字": "#expr .num", "統計の入口": "#dstats", "ヒント": "#hint", "ギブアップ": "#dgiveup"}
    hit = {k: ui.ev("(function(){const r=document.querySelector(%r).getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,"
                    "e=document.elementFromPoint(x,y);return e?(e.closest('.dsheet')||{}).id||e.id||e.className:null})()" % v) for k, v in spots.items()}
    ui.check("後ろの物（トレイ・式・入口・ヒント・ギブアップ）の場所を指しても、当たるのは幕かカード", hit, {k: "dsetsheet" for k in spots})
    before = ui.ev("JSON.stringify(S.toks)")
    cx, cy = ui.ev(CENTER % "#tray .chip")
    press(cx, cy)
    ui.check("トレイの記号の場所を本当に押す: 記号は選ばれず・盤も変わらず、ポップアップが閉じるだけ（外側を押した）",
             [ui.ev("held"), ui.ev("JSON.stringify(S.toks)") == before, ui.ev(OPEN)], [None, True, []])
    ui.check("閉じたら、後ろの inert が外れる（もう押せる）", [any(ui.ev(BEHIND)), ui.ev("document.body.classList.contains('pop')")], [False, False])
    click("dset")
    sx, sy = ui.ev(CENTER % "#dstats")
    press(sx, sy)
    ui.check("設定を開いたまま、統計の入口の場所を押す: 統計は開かず、設定が閉じるだけ", ui.ev(OPEN), [])
    click("dhelp")
    gx, gy = ui.ev(CENTER % "#dgiveup")
    if ui.ev("!document.elementFromPoint(%d,%d).closest('.dcard')" % (gx, gy)):
        press(gx, gy)
        ui.check("遊び方を開いたまま、ギブアップの場所を押す: 確かめの箱は出ず、遊び方が閉じるだけ",
                 ui.ev(OPEN), [])
    else:
        click("dhelp-close")

    # ══ 閉じ方: 外側・×・Esc ══
    for sid, btn, close, title in SHEETS:
        click(btn)
        x, y, w, h = ui.ev(RECT % ("#%s .dcard" % sid))
        press(x + w / 2, y + 22)                                   # カードの中（見出しの帯）
        ui.check("%s: カードの中を押しても閉じない" % title, ui.ev(OPEN), [sid])
        mouse("mousePressed", x + w / 2, y + 22)                   # カードの中で押し始めて、外で離す
        mouse("mouseReleased", x + w / 2, max(2, y - 12))
        time.sleep(0.15)
        ui.check("%s: カードの中で押し始めて外で離しても閉じない" % title, ui.ev(OPEN), [sid])
        press(x + w / 2, max(2, y - 12))                           # カードのすぐ上（幕）
        ui.check("%s: 外側（幕）を押すと閉じる" % title, ui.ev(OPEN), [])
        click(btn)
        key("Escape", 27)
        time.sleep(0.1)
        ui.check("%s: Esc で閉じる" % title, ui.ev(OPEN), [])
        click(btn)
        bx, by = ui.ev(CENTER % ("#" + close))
        press(bx, by)
        ui.check("%s: × を本当に押して閉じる" % title, ui.ev(OPEN), [])
    key("Escape", 27)
    ui.check("閉じている間の Esc は、何も起こさない（JS エラーも無い）", [ui.ev(OPEN), ui.errors()], [[], []])
    ui.ev("popShow('dstatsheet');popShow('dhelpsheet')")
    ui.check("同時に開くのは 1 つ（続けて開くと、前のものは閉じる）", ui.ev(OPEN), ["dhelpsheet"])
    ui.ev("popHide()")

    # ══ キーボードの移動は、カードの中に留まる ══
    for sid, btn, close, title in SHEETS:
        ui.ev("document.getElementById(%r).focus();document.getElementById(%r).click()" % (btn, btn))
        time.sleep(0.1)
        n = ui.ev("[...document.querySelectorAll('#%s .dcard button,#%s .dcard a[href]')].filter(x=>!x.disabled&&x.getClientRects().length).length" % (sid, sid))
        ui.check("%s: 開いた時、フォーカスはカードに移る（× にも入口にも残らない）" % title,
                 ui.ev("document.activeElement===document.querySelector('#%s .dcard')" % sid), True)
        seen, inside = [], []
        for _ in range(n + 3):
            key("Tab", 9)
            seen.append(ui.ev("document.activeElement.id||document.activeElement.className||document.activeElement.tagName"))
            inside.append(ui.ev(INSIDE % sid))
        ui.check("%s: Tab を「押せる物の数 + 3」回（%d 回）打っても、フォーカスはカードの中。最初は ×、ひと回りして × に戻る" % (title, n + 3),
                 [all(inside), seen[0], seen[n]], [True, close, close])
        back_in = []
        for _ in range(n + 3):
            key("Tab", 9, shift=True)
            back_in.append(ui.ev(INSIDE % sid))
        ui.check("%s: Shift+Tab でも、カードの中を逆に巡る" % title, all(back_in), True)
        # inert が効かないブラウザーのまね: 後ろの inert を外しても、Tab は端で折り返してカードの中に留まる
        ui.ev("[...app.children,dhead].forEach(e=>{e.inert=false})")
        ui.ev("document.querySelector('#%s .dcard').focus()" % sid)
        loop = []
        for _ in range(n + 2):
            key("Tab", 9)
            loop.append(ui.ev(INSIDE % sid))
        key("Tab", 9, shift=True)
        key("Tab", 9, shift=True)
        loop.append(ui.ev(INSIDE % sid))
        ui.check("%s: 後ろの inert を外しても（古いブラウザーのまね）、Tab はカードの中で折り返す" % title, all(loop), True)
        key("Escape", 27)
        time.sleep(0.1)
        ui.check("%s: 閉じたら、フォーカスは開く前の所（入口のボタン）に戻る" % title, [ui.ev(OPEN), ui.ev("document.activeElement.id")], [[], btn])

    # ══ カードの中だけが縦に動く ══
    # 収まらないのは、幅 360 の遊び方だけ（360×640 と、D0.27 で行が増えた 360×690。見出しと × を残して、中身が動く）
    # 開いた後にフォントが届いて行が折り返すので、届くのを待ってから見る（届いた時に薄れを決め直すことも、これで見る）
    for lang in ("ja", "en"):
        ui.open(now=at(no), tz=TZ, store=store, lang=lang)
        for sid, btn, close, title in SHEETS:
            click(btn)
            for _ in range(30):
                if ui.ev("document.fonts.status") == "loaded":
                    break
                time.sleep(0.1)
            time.sleep(0.1)
            body = "document.querySelector('#%s .dcard').lastElementChild" % sid
            m = ui.ev("(function(){const b=%s;return [b.scrollHeight>b.clientHeight+1,b.classList.contains('more'),getComputedStyle(b).overflowY]})()" % body)
            want = sid == "dhelpsheet" and W <= 360
            ui.check("%s %s: カードの中が縦に動くのは、幅 360 の遊び方だけ（動くときだけ、下の端を薄くする。フォントが届いた後も）" % (lang, title), m, [want, want, "auto"])
            if m[0]:
                head0, first0 = ui.ev(RECT % ("#%s h2" % sid)), ui.ev(RECT % ("#%s .dcard>:last-child>:first-child" % sid))
                card0 = ui.ev(RECT % ("#%s .dcard" % sid))
                step = min(20, ui.ev("(b=>b.scrollHeight-b.clientHeight)(%s)" % body))   # 360×690 は 6〜9px しか動かない
                ui.ev("%s.scrollTop=%d" % (body, step))
                time.sleep(0.1)
                ui.check("%s %s: 中身を送る（20px か、送れるだけ）: 見出しと × とカードは動かず、中身だけが上がる" % (lang, title),
                         [ui.ev(RECT % ("#%s h2" % sid)), ui.ev(RECT % ("#%s .dcard" % sid)),
                          round(first0[1] - ui.ev(RECT % ("#%s .dcard>:last-child>:first-child" % sid))[1])], [head0, card0, step])
                ui.ev("%s.scrollTop=1e6" % body)
                time.sleep(0.1)
                ui.check("%s %s: いちばん下まで送ると、下の端の薄れが消え、最後の行（リンク）がカードの中に見える" % (lang, title),
                         ui.ev("(function(){const b=%s,c=b.parentNode.getBoundingClientRect(),l=b.lastElementChild.getBoundingClientRect();"
                               "return [b.classList.contains('more'),l.bottom<=c.bottom&&l.top>=c.top,Math.round(b.scrollTop+b.clientHeight)===b.scrollHeight]})()" % body),
                         [False, True, True])
                ui.check("%s %s: 中身を送っても、ページは動かない" % (lang, title), [ui.scrolls(), ui.ev("scrollY")], [False, 0])
                click(close)
                click(btn)
                ui.check("%s %s: 開き直すと、いちばん上から" % (lang, title), ui.ev("%s.scrollTop" % body), 0)
            click(close)
    ui.check_no_errors("形・閉じ方・キーボード・中の動き: JS エラー 0")

    # ══ 広い画面: 幕は見出し（Make10 DAILY）にも掛かる ══
    ui.resize(1440, 900)
    try:
        ui.open(now=at(no), tz=TZ, store=store)
        click("dstats")
        ui.check("広い画面: 幕は画面いっぱいで、上の見出しにも掛かる。カードは幅 400px で中央",
                 [ui.ev(RECT % "#dstatsheet"), ui.ev("(function(){const r=dhead.getBoundingClientRect();"
                                                     "return (document.elementFromPoint(r.left+r.width/2,r.top+r.height/2).closest('.dsheet')||{}).id})()"),
                  ui.ev(RECT % "#dstatsheet .dcard")[2], ui.ev(RECT % "#dstatsheet .dcard")[0]], [[0, 0, 1440, 900], "dstatsheet", 400, 520])
        click("dstats-close")
        ui.check("広い画面: 閉じると、見出しは元の重なり（列より手前）に戻る",
                 [ui.ev("getComputedStyle(app).zIndex"), ui.ev("getComputedStyle(dhead).zIndex")], ["1", "2"])
    finally:
        ui.restore()

    # ══ 動き: 減速して止まる曲線・opacity と transform だけ ══
    ANIM = ("document.getAnimations().filter(a=>/^pop/.test(a.animationName||'')).map(a=>[a.animationName,a.effect.getTiming().duration,"
            "getComputedStyle(a.effect.target).animationTimingFunction,[...new Set(a.effect.getKeyframes().flatMap(k=>Object.keys(k)))]"
            ".filter(p=>!['offset','computedOffset','easing','composite'].includes(p)).sort().join(' ')]).sort()")
    EASE = "cubic-bezier(0.22, 0.72, 0.3, 1)"
    ui.open(now=at(no), tz=TZ, store=store, motion=True)
    ui.check("曲線の変数は、減速して止まる --zoneEase（行き過ぎない: 4 つの数がどれも 0〜1）",
             ui.ev("getComputedStyle(document.documentElement).getPropertyValue('--zoneEase').trim()"), "cubic-bezier(.22,.72,.3,1)")
    for sid, btn, close, title in SHEETS:
        ui.ev("document.getElementById(%r).click()" % btn)
        ui.check("%s 開く動き: 幕は薄れて出る・カードは少し上がりながら出る（0.24 秒・減速して止まる曲線・opacity と transform だけ）" % title,
                 ui.ev(ANIM), [["popfade", 240, EASE, "opacity"], ["popin", 240, EASE, "opacity transform"]])
        time.sleep(0.4)
        ui.check("%s 開く動きが終わると、カードは定位置（ずれが残らない）" % title,
                 ui.ev("(function(){const s=getComputedStyle(document.querySelector('#%s .dcard'));return [s.opacity,s.transform.replace('matrix(1, 0, 0, 1, 0, 0)','none')]})()" % sid),
                 ["1", "none"])
        ui.ev("document.getElementById(%r).click()" % close)
        ui.check("%s 閉じる動き: 0.16 秒・同じ曲線・opacity と transform だけ。閉じ始めたら、もう押せない" % title,
                 [ui.ev(ANIM), ui.ev("[%s.classList.contains('closing'),getComputedStyle(%s).pointerEvents,popNow]" % (sid, sid))],
                 [[["popfadeout", 160, EASE, "opacity"], ["popout", 160, EASE, "opacity transform"]], [True, "none", None]])
        time.sleep(0.4)
        ui.check("%s 閉じる動きが終わると、隠れる（display:none）" % title,
                 ui.ev("[%s.classList.contains('hide'),%s.classList.contains('closing'),getComputedStyle(%s).display]" % (sid, sid, sid)), [True, False, "none"])
    ui.ev("dset.click();popHide();dset.click()")
    time.sleep(0.4)
    ui.check("閉じる動きの途中で開き直しても、開いたまま残る（途中の閉じる処理が、後から隠さない）", ui.ev(OPEN), ["dsetsheet"])
    ui.ev("popHide()")
    time.sleep(0.3)
    ui.check("動きに、レイアウトを起こす性質（幅・高さ・位置）の遷移やアニメーションが無い",
             ui.ev("(function(){const bad=[];for(const sh of document.styleSheets){let rs=[];try{rs=sh.cssRules}catch(e){}for(const r of rs){"
                   "if(r.type===CSSRule.KEYFRAMES_RULE&&/^pop/.test(r.name))for(const k of r.cssRules)for(const p of k.style)if(p!=='opacity'&&p!=='transform')bad.push(r.name+':'+p)}}"
                   "for(const e of document.querySelectorAll('.dsheet,.dcard')){const t=getComputedStyle(e).transitionDuration;if(t!=='0s')bad.push('transition '+t)}return bad})()"), [])

    # ══ 動きを減らす設定: 動かずに出て、動かずに消える ══
    ui.media(reduce=True)
    try:
        ui.open(now=at(no), tz=TZ, store=store, motion=True)
        for sid, btn, close, title in SHEETS:
            got = ui.ev("(function(){document.getElementById(%r).click();const c=document.querySelector('#%s .dcard'),s=getComputedStyle(c);"
                        "const a=[document.getAnimations().filter(x=>/^pop/.test(x.animationName||'')).length,s.opacity,s.transform,getComputedStyle(%s).opacity];"
                        "document.getElementById(%r).click();"
                        "return a.concat([%s.classList.contains('hide'),%s.classList.contains('closing')])})()" % (btn, sid, sid, close, sid, sid))
            ui.check("動きを減らす設定 %s: 押したその場で、動かずに出ている。× を押したその場で、消えている" % title, got, [0, "1", "none", "1", True, False])
    finally:
        ui.media()
    ui.check_no_errors()
