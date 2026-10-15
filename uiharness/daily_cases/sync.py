# -*- coding: utf-8 -*-
"""本編との同期の照合（DAILY-SPEC 2 章・11 章・18-3）。

デイリーは、本編の盤・辞書・CSS を 1 文字も変えずに複製している。本編を直したのにデイリーへ
反映し忘れた（またはデイリーの複製にうっかり手を入れた）ことを、ここで見つける。

- JS: デイリーの**トップレベルの文**のうち、本編に同じ名前（宣言の先頭の名前。宣言でない文は 1 行目）の
  ものがあれば、文字列が同じであること
- CSS: デイリーの規則のうち、本編に同じセレクタのものがあれば、中身が同じであること
- 手を入れたものは除外の一覧（`daily_ui.JS_EXCLUDE` / `CSS_EXCLUDE`）に載せる。一覧は DAILY-SPEC 18-3 と同じにする
- 複製するはずのもの（18-3 の一覧）が、そろっていること（名前を変えて照合から外れていないこと）

ソースの文字列だけを比べる（Chrome は使わない）。画面の大きさに依らないので 1 回だけ回る。
"""
from uiharness import daily_ui as dui

NAME = "本編との同期の照合"
STATIC = True

# 1 文字も変えずに複製するもの（DAILY-SPEC 18-3）。D0.13 で JS に足したものは無い（設定はデイリーだけの文）
REQUIRED_JS = """STR_CORE LANGS LANG_URL LANG PLURAL pickLang t applyI18n OPOF conOf MODE solved
gd R add ml isInt fct pwr TOKEN_METRICS COMPACT_MQ ZONE_BASE ZONE_MIN MET applyMetrics tokensWidth
GLYPH NEST TRAY S $ T canPut insSeq livePositions put dropTok match parse ev same deadParens segValues
curExprScale MIN_SCALE applyScale scaleFor fit zoneCalc devSnap layoutZones closeSet afterInsert afterRemove
captureCloseSet showZones hideZones DEV_CATCH DEV_SWAP buzz lastHot ghost gmove startDrag nearest nearZone
nearSwap tgt onMove onUp clearAll DEV_DEFAULT btnOf btnOff HINT_ROW HINT_GLYPH HINT_TEXT hintExprW
hintExprScale SHARE_BTN NEXT_BTN pretty ICON_HCLOSE ICON_SHARE toastT dropFacRun pressedBtn pressOff
RULE_GAP ruleLine""".split()
REQUIRED_JS_ANON = [
    '@document.body.appendChild(ghost);',
    '@$("tray").addEventListener("pointerdown",e=>{',
    '@$("expr").addEventListener("pointerdown",e=>{',
    '@document.addEventListener("click",e=>{',
    '@$("clear").onclick=()=>clearAll();',
    # D0.10: 押した瞬間の手応え
    '@document.addEventListener("pointerdown",e=>{',
    '@document.addEventListener("pointerup",pressOff,true);',
    '@document.addEventListener("pointercancel",pressOff,true);',
]
MEDIA = "@media (max-height:700px) || "
WIDE = "@media (min-width:720px) and (min-height:768px) || "      # パソコンの見出し（D0.17。デイリーだけ）
REQUIRED_CSS = [
    ":root", 'body[data-theme="ai"]', "*", "html,body", "body", "#bg", "@keyframes sweep", "#bg.flash",
    "#app", ".bottom", "button", "button:active", ".hide", ".ic", ".top", ".iconbtn", ".iconbtn:active",
    ".top .info", ".readout", ".eq", ".eq.idle", ".eq.hit", ".eq.miss", ".eq.ban", ".eq.part",
    ".sub", ".sub.warn", ".sub.ok", ".field", ".field.trash", ".field .trashmsg", ".field.trash .trashmsg",
    ".exprwrap", ".expr", ".num", ".ruleline", ".ruleline.on", "@keyframes ruledraw", "@keyframes rulefade", ".tok", ".tok.op", ".tok.fac",
    ".tok.lp,.tok.rp", ".tok.lone", ".tok.dead", ".tok.lift", ".tok.swap", "@keyframes glow", ".tok.shine",
    ".zone", ".zone.snap", ".zone.live", ".zone.hot", ".tray", ".chip", ".chip:active", ".chip.sel",
    ".chip.off", ".chip .stock", "@keyframes shake", ".chip.shake", ".foot", "#ghost",
    # D0.3: 上のバーのボタン・確認と全解答の箱・統計の 2 列・導線の ›
    ".plainbtn", ".plainbtn:active", ".chev", ".top .info b", ".overlays", ".overlays>*",
    ".hintbox", ".hintbox.show", ".hintbox code", ".hintbox .hbin code", ".hintrow",
    ".hintrow .hbody", ".hintrow .hbody>.hbin", ".hintrow .hbody::-webkit-scrollbar",
    ".hintrow .hbody.two", ".hintrow .hsub", ".hintrow .hsub b", ".hintrow .hbody.tap",
    "#statlist", ".stat", ".stat .sv", ".stat .sv b,.stat .sv .none", ".stat .sv .none",
    ".stat .sv .su", ".stat .sk",
    MEDIA + ".stat", MEDIA + ".stat .sv b,.stat .sv .none",
    # D0.4: ヒントの丸ボタンの残り回数・共有ボタンの位置・箱の中のボタン・トースト
    ".btnlabel", "#share", "#hint", ".stocknum", "#hint::before", '#hint[aria-disabled="true"]',
    '#hint[aria-disabled="true"]:active', ".hintrow .hbtn", ".hintrow .hbtn .ic",
    ".hintrow .hbtn:active:not(:disabled)", ".hintrow .hbtn:disabled",
    "#toast", "#toast.show", "#toast.atfoot", "#toast.atfoot.show",
    # D0.10: 押した瞬間の手応え
    'button.pressed,[role="button"].pressed',
    # D0.13: 設定のスイッチの行（本編の設定の行）
    ".toggle", ".toggle:active", ".toggle span.sw", ".toggle span.sw::after", ".toggle.on span.sw",
    ".toggle.on span.sw::after", ".group .toggle:not(:last-child)::after",
    MEDIA + ".readout", MEDIA + ".eq", MEDIA + ".eq.idle", MEDIA + ".eq.part", MEDIA + ".chip",
    MEDIA + ".foot", MEDIA + ".top", MEDIA + ".field",
    "@media (prefers-reduced-motion:reduce) || *",
]


def compare(daily, main, exclude):
    """(同じだったもの, 違ったもの, 除外で飛ばしたもの, デイリーだけのもの)。
    daily / main は [(鍵, 文字列)…]。同じ鍵が本編に複数あるときは、そのどれかと同じならよい"""
    by = {}
    for k, text in main:
        by.setdefault(k, []).append(text)
    same, diff, skipped, own = [], [], [], []
    for k, text in daily:
        if k not in by:
            own.append(k)
        elif k in exclude:
            skipped.append(k)
        elif text in by[k]:
            same.append(k)
        else:
            diff.append(k)
    return same, diff, skipped, own


def run(ui):
    main = dui.read(dui.MAIN_HTML)
    daily = dui.read(dui.DAILY_HTML)

    # ── JS ──
    mj = [(dui.js_key(n, t), t) for n, t in dui.split_js(dui.script_of(main))]
    dj = [(dui.js_key(n, t), t) for n, t in dui.split_js(dui.script_of(daily))]
    same, diff, skipped, own = compare(dj, mj, dui.JS_EXCLUDE)
    ui.check("JS: 本編と同じ名前の文は、文字列が同じ", diff, [])
    ui.check("JS: 複製するはずの文がそろっている（18-3）",
             [k for k in REQUIRED_JS + REQUIRED_JS_ANON if k not in same], [])
    main_keys = {k for k, _ in mj}
    main_text = dict(mj)
    ui.check("JS: 除外の一覧の名前は、本編にある",
             [k for k in dui.JS_EXCLUDE if k not in main_keys], [])
    ui.check("JS: 除外の一覧に、もう本編と同じになっているものが無い",
             [k for k, t in dj if k in dui.JS_EXCLUDE and main_text.get(k) == t], [])
    # 辞書の共通の塊は、塊ごと同じ（16-2。上の照合に入っているが、名前で確かめておく）
    ui.check("JS: STR_CORE・t・pickLang・applyI18n が照合に入っている",
             [k for k in ("STR_CORE", "t", "pickLang", "applyI18n") if k not in same], [])
    ui.check("JS: 同じだった文の数が、そろえる数以上",
             len(same) >= len(REQUIRED_JS) + len(REQUIRED_JS_ANON), True)

    # ── CSS ──
    mc = dui.split_css(dui.style_of(main))
    dc = dui.split_css(dui.style_of(daily))
    same, diff, skipped, own = compare(dc, mc, dui.CSS_EXCLUDE)
    ui.check("CSS: 本編と同じセレクタの規則は、中身が同じ", diff, [])
    ui.check("CSS: 複製するはずの規則がそろっている（18-3）",
             [k for k in REQUIRED_CSS if k not in same], [])
    main_sel = {k for k, _ in mc}
    ui.check("CSS: 除外の一覧のセレクタは、本編にある",
             [k for k in dui.CSS_EXCLUDE if k not in main_sel], [])
    # デイリーだけの規則。ここが変わったら、複製した規則のセレクタを書き換えていないかを見る
    ui.check("CSS: デイリーだけの規則", sorted(own),
             sorted(["body.daily", "#app.daily", "#banline", "#nopuzzle", "#dfoot",
                     # D0.3
                     "#dinfo span", "#dgiveup", "#play.dplay", "#play.done .bottom",
                     "#play.done #expr,#play.locked #expr,#play.locked #tray", "#play.done #dgiveup",
                     ".eq.gaveup", "#result", ".rcols", ".rcol .rv", ".rcol .rv b", ".rcol .rv b.none",
                     ".rcol .rv .ru", ".rcol .rn", "#solbox", "#solbox .hintrow", ".applink",
                     ".applink:active", "#app.daily.scrolly", ".dsheet", ".dsheet .shead",
                     ".dsheet h2", MEDIA + "#dfoot", MEDIA + ".rcol .rv", MEDIA + ".rcol .rv b",
                     MEDIA + ".applink",
                     # D0.4
                     ".rshare", ".rshare:active", ".rshare .ic",
                     # D0.5
                     ".rcol .rv .ru:empty", "#dhelpbody", "#dhelpbody p", "#dhelpbody code",
                     # D0.6
                     "#dhelpbody .hlink", "#dhelpbody .hlink a",
                     # D0.8（みんなの結果）
                     "#aggbox", "#aggbox .at", "#aggbox .ap", "#aggbox .ar", "#aggbox .ac", "#aggbox .ac b",
                     "#aggbox .ac span", "#aggbox .ab", "#aggbox .bar", "#aggbox .bar i", "#aggbox .bar span",
                     "#aggbox .bar.me i", "#aggbox .bar.me span", "#aggbox.tight", "#aggbox.tight .at",
                     "#aggbox.tight .ar", "#aggbox.tight .ac b", "#aggbox.tight .ac span,#aggbox.tight .bar span",
                     # D0.11（カレンダー）
                     "#dstatbody", "#dcal", "#dcal .chead", "#dcal .chead b", "#dcal .chead button:disabled",
                     "#dcal-grid", "#dcal-grid .dw", "#dcal-grid .dc", "#dcal-grid .dc:active", "#dcal-grid .dc i",
                     "#dcal-grid .dc.s i", "#dcal-grid .dc.g i", "#dcal-grid .dc.n::after", "#dcal-grid .dc.x",
                     "#dcal-grid .dc.today", "#dcal-grid .dc.sel", "#dcal-grid .dc.today.sel",
                     "#dcal-legend", "#dcal-legend span", "#dcal-legend i", "#dcal-legend i.s", "#dcal-legend i.g",
                     "#dcal-legend i.n", "#dcal-line", "#dcal-line b",
                     # D0.12（調整の版）
                     "#dstatbody #statlist", "#play.done .readout", "#aggbox.tight.pend", "#aggbox.tight.pend .at",
                     "#aggbox.tight.pend .ap", MEDIA + "#statlist .stat",
                     MEDIA + "#statlist .stat .sv b,#statlist .stat .sv .none",
                     # D0.13（設定）
                     "#dsetbody", "#dmid",
                     # D0.16（遊び方の見本の盤。.hd1 .dn3 は、止まっている形と動きの 2 つ）
                     ".hfig", ".hstep", "#dhelpbody .hfig .hcap", ".hdemo", ".dexpr", ".dnum", ".dtok", ".dtok.op",
                     ".dtok.par", ".dslot", ".dslot>*", ".dzone", ".dhot", ".dtray", ".dchip", ".dghost", ".deq", ".dsub",
                     ".hd1 .dn0,.hd1 .dn1,.hd1 .ds1", ".hd1 .dn3", ".hd1 .dn0", ".hd1 .dn1", ".hd1 .dn2", ".hd1 .dn3",
                     ".hd1 .ds1", ".hd1 .dzone", ".hd1 .dhot", ".hd1 .ds1 .dtok", ".hd1 .dghost", ".hd1 .dpick",
                     "@keyframes hd-n0", "@keyframes hd-n1", "@keyframes hd-n2", "@keyframes hd-n3", "@keyframes hd-s1",
                     "@keyframes hd-zone", "@keyframes hd-hot", "@keyframes hd-tok", "@keyframes hd-ghost",
                     "@keyframes hd-pick", "#dhelpbody p.hico", "#dhelpbody p.hico .hi", "#dhelpbody p.hico .hi .ic",
                     # D0.17（名前。#dinfo の左の余白は、名前と日付を入れる #dmid へ移した）
                     ".dbrand", ".dbrand b", ".dbrand span", "#dhead", "#nobrand", "#nobrand.hide",
                     WIDE + "body.daily", WIDE + "#dhead", WIDE + "#dhead .dbrand", WIDE + "#dhead .dbrand span",
                     WIDE + "#app.daily", WIDE + "#dmid .dbrand,#nobrand",
                     # D0.26（ポップアップ。変数は html に置く ―― 本編から複製した :root とセレクタを分ける）
                     "html", "@keyframes popfade", "@keyframes popin", "@keyframes popfadeout", "@keyframes popout",
                     ".dcard", ".dsheet.closing", ".dsheet.closing>.dcard", "body.pop #app",
                     ".dcard>:last-child", ".dcard>.more",
                     # D0.28（ギブアップの確認をポップアップに。D0.3 の #gubox の 4 規則は消した）
                     "#dgusheet", "#dgusheet .dcard", "#gu-text", "#dgusheet .gubtns", "#dgusheet .gubtns button",
                     "#dgusheet .gubtns button:active", "body.gu #banline,body.gu .readout,body.gu #field",
                     # D0.30・D0.31（色。白が既定。本編から複製した規則は変えず、html:not(.dark) の下で上書きする）
                     "html:not(.dark)", 'html:not(.dark) body[data-theme="ai"]', "html:not(.dark) #dcal",
                     "html:not(.dark) #toast", "html:not(.dark) #ghost", "html:not(.dark) .dghost", "html:not(.dark) .dcard",
                     # D0.31（統計を 3 つ横並び）
                     "#dstatbody #statlist .stat", "#dstatbody #statlist .stat .sv"]))
