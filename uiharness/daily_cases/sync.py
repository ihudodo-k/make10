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

# 1 文字も変えずに複製するもの（DAILY-SPEC 18-3）。D0.4 の時点
REQUIRED_JS = """STR_CORE LANGS LANG_URL LANG PLURAL pickLang t applyI18n OPOF conOf MODE solved
gd R add ml isInt fct pwr TOKEN_METRICS COMPACT_MQ ZONE_BASE ZONE_MIN MET applyMetrics tokensWidth
GLYPH NEST TRAY S $ T canPut insSeq livePositions put dropTok match parse ev same deadParens segValues
curExprScale MIN_SCALE applyScale scaleFor fit zoneCalc devSnap layoutZones closeSet afterInsert afterRemove
captureCloseSet showZones hideZones DEV_CATCH DEV_SWAP buzz lastHot ghost gmove startDrag nearest nearZone
nearSwap tgt onMove onUp clearAll DEV_DEFAULT btnOf btnOff HINT_ROW HINT_GLYPH HINT_TEXT hintExprW
hintExprScale SHARE_BTN NEXT_BTN pretty ICON_HCLOSE ICON_SHARE toastT""".split()
REQUIRED_JS_ANON = [
    '@document.body.appendChild(ghost);',
    '@$("tray").addEventListener("pointerdown",e=>{',
    '@$("expr").addEventListener("pointerdown",e=>{',
    '@document.addEventListener("click",e=>{',
    '@$("clear").onclick=()=>clearAll();',
]
MEDIA = "@media (max-height:700px) || "
REQUIRED_CSS = [
    ":root", 'body[data-theme="ai"]', "*", "html,body", "body", "#bg", "@keyframes sweep", "#bg.flash",
    "#app", ".bottom", "button", "button:active", ".hide", ".ic", ".top", ".iconbtn", ".iconbtn:active",
    ".top .info", ".readout", ".eq", ".eq.idle", ".eq.hit", ".eq.miss", ".eq.ban", ".eq.part",
    ".sub", ".sub.warn", ".sub.ok", ".field", ".field.trash", ".field .trashmsg", ".field.trash .trashmsg",
    ".exprwrap", ".expr", ".num", "@keyframes pop", ".num.pop", ".tok", ".tok.op", ".tok.fac",
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
                     "#dinfo span", "#dgiveup", "#gubox .gurow", "#gubox .gutext", "#gubox button",
                     "#gubox button:active", "#play.dplay", "#play.done .bottom",
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
                     "#aggbox.tight .ar", "#aggbox.tight .ac b", "#aggbox.tight .ac span,#aggbox.tight .bar span"]))
