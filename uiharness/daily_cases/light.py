# -*- coding: utf-8 -*-
"""色 ―― 白（既定）と、設定から入れるダークモード（D0.30・D0.31。DAILY-SPEC 15 章・13-11）。

- 白が既定。端末の設定（prefers-color-scheme）は見ない（暗い表示の端末でも白で開く）
- 設定のスイッチ「ダークモード」を入れると、その場で黒と白になり、盤は描き直さない。保存して、開き直しても黒と白。
  黒と白は、描く前（head の中）に決める ―― 白が一瞬見えない
- ?date=（テスト表示）は保存を読まないので、保存がダークモードでも白で開く（スイッチはその場だけ効く）
- 白の値・地との比・幕 50%・カードの影。黒と白は幕 78%・影なし
- どの画面（盤・3 つのポップアップ・ギブアップの確認・解いた後・問題が無い日）でも、見えている文字は地との比が 2 以上で、
  黒と白の色（直に書いた色の取り残し）を使っている要素が無い
"""
import datetime
import json
import time

from uiharness import daily_ui as dui

NAME = "色（白とダークモード）"

TZ = "Asia/Tokyo"
VARS = ["--ink", "--panel", "--edge", "--paper", "--dim", "--slate", "--coral", "--gold"]
LIGHT = {"--ink": "rgb(255, 255, 255)", "--panel": "rgb(255, 255, 255)", "--edge": "rgb(211, 214, 218)",
         "--paper": "rgb(26, 26, 27)", "--dim": "rgb(107, 111, 118)", "--slate": "rgb(163, 167, 173)",
         "--coral": "rgb(200, 55, 45)", "--gold": "rgb(184, 134, 11)"}
DARK = {"--ink": "rgb(18, 18, 19)", "--panel": "rgb(18, 18, 19)", "--edge": "rgb(58, 58, 60)",
        "--paper": "rgb(255, 255, 255)", "--dim": "rgb(154, 156, 161)", "--slate": "rgb(95, 96, 100)",
        "--coral": "rgb(226, 106, 87)", "--gold": "rgb(220, 189, 110)"}
# 色の読み方（rgb()・rgba()・color(srgb …) を [r,g,b,a] に）と、地との比
LIB = ("const __rgba=s=>{let m=s.match(/^rgba?\\(([^)]+)\\)/);if(m){const v=m[1].split(/[ ,\\/]+/).filter(x=>x).map(Number);"
       "return [v[0],v[1],v[2],v.length>3?v[3]:1]}m=s.match(/^color\\(srgb ([^)]+)\\)/);if(m){const v=m[1].split(/[ \\/]+/).filter(x=>x).map(Number);"
       "return [v[0]*255,v[1]*255,v[2]*255,v.length>3?v[3]:1]}return null};"
       "const __lum=c=>{const f=x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};"
       "const __ratio=(a,b)=>{const x=__lum(a),y=__lum(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)};"
       "const __ink=()=>__rgba(getComputedStyle(document.body).backgroundColor);")
# 変数の今の値（色として読み直す）
COLS = ("(function(vs){const p=document.createElement('i');document.body.appendChild(p);const o={};"
        "for(const v of vs){p.style.color='var('+v+')';o[v]=getComputedStyle(p).color}p.remove();return o})(%s)" % json.dumps(VARS))
# 地との比（変数ごと）と、カレンダーの点
RATIOS = ("(function(vs){" + LIB + "const p=document.createElement('i');document.body.appendChild(p);const ink=__ink(),o={};"
          "for(const v of vs){p.style.color='var('+v+')';o[v]=Math.round(__ratio(__rgba(getComputedStyle(p).color),ink)*100)/100}p.remove();"
          "const d=document.createElement('i');dcal.appendChild(d);d.style.color='var(--calDot)';"
          "o.calDot=Math.round(__ratio(__rgba(getComputedStyle(d).color),ink)*100)/100;d.remove();return o})(%s)" % json.dumps(VARS))
# 見えている文字のうち、地との比が 2 に届かないもの。黒と白の色を使っている要素
SCAN = ("(function(){" + LIB + "const ink=__ink(),low=[],dark=[];"
        "const DK=['rgb(18, 18, 19)','rgb(58, 58, 60)','rgb(154, 156, 161)','rgb(95, 96, 100)','rgb(220, 189, 110)','rgb(226, 106, 87)'];"
        "const op=e=>{let a=1;for(;e&&e.nodeType===1;e=e.parentElement){const s=getComputedStyle(e);a*=+s.opacity;if(s.visibility==='hidden')return 0}return a};"
        "for(const e of document.querySelectorAll('body *')){if(!e.getClientRects().length)continue;const s=getComputedStyle(e);"
        "const name=(e.id?'#'+e.id:e.tagName.toLowerCase()+(typeof e.className==='string'&&e.className?'.'+e.className.split(' ')[0]:''));"
        "for(const k of ['color','backgroundColor','borderTopColor','borderBottomColor']){const c=s[k];if(DK.includes(c)&&(k==='color'||__rgba(c)[3]>0)"
        "&&!(k!=='color'&&parseFloat(s[k==='borderTopColor'?'borderTopWidth':k==='borderBottomColor'?'borderBottomWidth':'width'])===0))dark.push(name+' '+k+' '+c)}"
        "const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());if(!own||op(e)<0.5)continue;"
        "const c=__rgba(s.color),a=c[3],b=[c[0]*a+ink[0]*(1-a),c[1]*a+ink[1]*(1-a),c[2]*a+ink[2]*(1-a)];"
        "const r=__ratio(b,ink);if(r<2)low.push(name+' '+e.textContent.trim().slice(0,12)+' '+r.toFixed(2))}"
        "return {low,dark}})()")
POPDIM = "getComputedStyle(document.documentElement).getPropertyValue('--popDim').trim()"
IS_DARK = "document.documentElement.classList.contains('dark')"
SHADOW = "getComputedStyle(document.querySelector('#dstatsheet .dcard')).boxShadow"
SW = ("[...document.querySelectorAll('#dsetbody .toggle')].map(e=>[e.id,e.textContent.trim(),e.classList.contains('on'),"
      "e.getAttribute('aria-pressed')])")
# html に dark が初めて付いた時に、body がもうあったか（描く前＝head の中で付いたなら false）
WATCH = ("new MutationObserver((l,o)=>{if(document.documentElement.classList.contains('dark')&&!('__darkAt' in window)){"
         "window.__darkAt=document.body?'body':'head';o.disconnect()}}).observe(document,{attributes:true,subtree:true,attributeFilter:['class']});")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    no = 3
    row = rows[no - 1]

    def scan(where):
        got = ui.ev(SCAN)
        ui.check("%s: 見えている文字は、どれも地との比が 2 以上" % where, got["low"], [])
        ui.check("%s: 黒と白の色を使っている要素が無い" % where, got["dark"], [])

    try:
        # ══ 白が既定。端末の設定は見ない ══
        ui.media("dark")
        ui.open(now=at(no), tz=TZ, dark=False)
        ui.check("暗い表示の端末でも、白で開く（html に dark が無い・変数は白）", [ui.ev(IS_DARK), ui.ev(COLS)], [False, LIGHT])
        ui.media("light")
        ui.check("明るい表示の端末でも白のまま", ui.ev(COLS), LIGHT)
        ui.media()
        ui.check("白: 地（body）は白・幕の濃さ 50%", [ui.ev("getComputedStyle(document.body).backgroundColor"), ui.ev(POPDIM)],
                 ["rgb(255, 255, 255)", "50%"])
        r = ui.ev(RATIOS)
        # 金は大きい字の「10」（28px 以上の太字）にしか使わないので、大きい字の基準 3 で見る（D0.32）
        ui.check("白: 地との比（字 7 以上・副次・赤 4.5 以上・金 3 以上・無効 2 以上・点 3 以上で副次色より下・線 1.3 以上）",
                 [r["--paper"] >= 7, r["--dim"] >= 4.5, r["--gold"] >= 3, r["--coral"] >= 4.5, r["--slate"] >= 2,
                  3 <= r["calDot"] < r["--dim"], r["--edge"] >= 1.3], [True] * 7)
        ui.check("白: ポップアップのカードに影がある", ui.ev(SHADOW) != "none", True)
        scan("白の盤")

        for sid, btn, close, title in (("dstatsheet", "dstats", "dstats-close", "統計"),
                                       ("dhelpsheet", "dhelp", "dhelp-close", "遊び方"),
                                       ("dsetsheet", "dset", "dset-close", "設定")):
            ui.ev("document.getElementById(%r).click()" % btn)
            ui.check("白の%s: 幕は地の色の 50%%・カードに影" % title,
                     ui.ev("(function(){" + LIB + "const c=__rgba(getComputedStyle(%s).backgroundColor);"
                           "return [Math.round(c[0]),Math.round(c[1]),Math.round(c[2]),Math.round(c[3]*100)/100,"
                           "getComputedStyle(document.querySelector('#%s .dcard')).boxShadow!=='none']})()" % (sid, sid)),
                     [255, 255, 255, 0.5, True])
            scan("白の" + title)
            ui.ev("document.getElementById(%r).click()" % close)
        ui.ev("dgiveup.click()")
        ui.check("白のギブアップの確認: カードに影", ui.ev("getComputedStyle(document.querySelector('#dgusheet .dcard')).boxShadow") != "none", True)
        scan("白のギブアップの確認")
        ui.ev("document.getElementById('gu-no').click()")

        # ══ 設定のスイッチ ══
        ui.ev("dset.click()")
        ui.check("設定のスイッチは 3 つ（文は「〜する」を取った形・ダークモードは切れている）", ui.ev(SW),
                 [["t-easy", "途中の値を表示", False, "false"], ["t-tap", "タップで配置", False, "false"],
                  ["t-dark", "ダークモード", False, "false"]])
        ui.solve(" ".join(row["sol"].split(" ")[:3]), wait=0.3)        # 途中の式を置いておく（盤を描き直さないことを見る）
        before = ui.ev("expr.innerHTML")
        ui.ev("document.getElementById('t-dark').click()")
        time.sleep(0.5)                                               # スイッチの色の遷移（0.2 秒）が終わるのを待つ
        ui.check("ダークモードを入れると、その場で黒と白（幕 78%・影なし）・スイッチが入る・保存される",
                 [ui.ev(IS_DARK), ui.ev(COLS), ui.ev(POPDIM), ui.ev(SHADOW), ui.ev(SW)[2][2:], ui.saved(raw=True)["set"]],
                 [True, DARK, "78%", "none", [True, "true"], {"easy": 0, "tap": 0, "dark": 1}])
        ui.check("ダークモードを入れても、盤は描き直さない（置いた式がそのまま）", ui.ev("expr.innerHTML"), before)
        scan_dark = ui.ev(SCAN)
        ui.check("黒と白の設定: 見えている文字は、どれも地との比が 2 以上", scan_dark["low"], [])
        ui.ev("document.getElementById('dset-close').click()")

        # 開き直しても黒と白。描く前（head の中）に決まる
        wid = ui.c.on_new_document(WATCH)
        try:
            ui.open(now=at(no), tz=TZ, store="keep", dark=False)
            ui.check("開き直しても黒と白。dark は body より前（head の中）で付く", [ui.ev(IS_DARK), ui.ev(COLS), ui.ev("window.__darkAt")],
                     [True, DARK, "head"])
        finally:
            ui.c.remove_on_new_document(wid)
        ui.ev("dset.click()")
        ui.check("開き直した設定: ダークモードのスイッチが入っている", ui.ev(SW)[2][2:], [True, "true"])
        ui.ev("document.getElementById('t-dark').click()")
        ui.check("ダークモードを切ると白に戻り、保存も 0", [ui.ev(IS_DARK), ui.ev(COLS), ui.saved(raw=True)["set"]],
                 [False, LIGHT, {"easy": 0, "tap": 0, "dark": 0}])
        ui.ev("document.getElementById('dset-close').click()")

        # ══ ?date=（テスト表示）は保存を読まない ══
        wid = ui.c.on_new_document(WATCH)
        try:
            ui.open(date=day(no).isoformat(), store={"v": 1, "days": {}, "cur": None, "set": {"easy": 0, "tap": 0, "dark": 1}}, dark=False)
        finally:
            ui.c.remove_on_new_document(wid)
        ui.check("?date= では、保存がダークモードでも白で開く（読み込みの途中でも一度も dark が付かない）",
                 [ui.ev(IS_DARK), ui.ev(COLS), ui.ev("window.__darkAt===undefined")], [False, LIGHT, True])
        ui.ev("dset.click();document.getElementById('t-dark').click()")
        ui.check("?date= でも、スイッチはその場だけ効く", ui.ev(IS_DARK), True)
        ui.ev("document.getElementById('dset-close').click()")

        # ══ 英語 ══
        ui.open(now=at(no), tz=TZ, lang="en", dark=False)
        ui.ev("dset.click()")
        ui.check("英語の設定のスイッチ", [x[1] for x in ui.ev(SW)], ["Show intermediate values", "Tap to place", "Dark mode"])
        ui.ev("document.getElementById('dset-close').click()")

        # ══ 解いた後・問題が無い日（白）══
        ui.open(now=at(no), tz=TZ, dark=False)
        ui.solve(row["sol"], wait=0.9)
        ui.check("白の解いた後: 「10」は白の金", ui.ev("getComputedStyle(eq).color"), "rgb(184, 134, 11)")
        scan("白の解いた後")
        ui.open(dark=False)
        ui.check("問題が無い日: 地は白", ui.ev("getComputedStyle(document.body).backgroundColor"), "rgb(255, 255, 255)")
        scan("白の問題が無い日")
    finally:
        ui.media()
    ui.check_no_errors()
