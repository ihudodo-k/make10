# -*- coding: utf-8 -*-
"""ライトモード（D0.30。DAILY-SPEC 15 章）。

- 端末の設定（prefers-color-scheme）が明るい表示のときだけ、色の変数が白（案 A 白と墨）になる。暗い表示は黒と白のまま
- 切り替えのボタンは持たない。開いている間に端末の設定が変わっても、読み直さずに替わる
- 地との比: 主な文字 7 以上・副次の字・金・赤 4.5 以上・無効 2 以上・カレンダーの点 3 以上で副次色より沈む
- ポップアップの幕は地の色を 50%
- どの画面（盤・3 つのポップアップ・ギブアップの確認・解いた後・問題が無い日）でも、見えている文字は地との比が 2 以上で、
  黒と白の色（直に書いた色の取り残し）を使っている要素が無い
"""
import datetime

from uiharness import daily_ui as dui

NAME = "ライトモード"

TZ = "Asia/Tokyo"
VARS = ["--ink", "--panel", "--edge", "--paper", "--dim", "--slate", "--coral", "--gold"]
LIGHT = {"--ink": "rgb(255, 255, 255)", "--panel": "rgb(255, 255, 255)", "--edge": "rgb(211, 214, 218)",
         "--paper": "rgb(26, 26, 27)", "--dim": "rgb(107, 111, 118)", "--slate": "rgb(163, 167, 173)",
         "--coral": "rgb(200, 55, 45)", "--gold": "rgb(143, 102, 0)"}
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
        "for(const v of vs){p.style.color='var('+v+')';o[v]=getComputedStyle(p).color}p.remove();return o})(%s)")
# 地との比（変数ごと）と、カレンダーの点
RATIOS = ("(function(vs){" + LIB + "const p=document.createElement('i');document.body.appendChild(p);const ink=__ink(),o={};"
          "for(const v of vs){p.style.color='var('+v+')';o[v]=Math.round(__ratio(__rgba(getComputedStyle(p).color),ink)*100)/100}p.remove();"
          "const d=document.createElement('i');dcal.appendChild(d);d.style.color='var(--calDot)';"
          "o.calDot=Math.round(__ratio(__rgba(getComputedStyle(d).color),ink)*100)/100;d.remove();return o})(%s)")
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
        # ══ 暗い表示（既定）: 黒と白のまま ══
        ui.open(now=at(no), tz=TZ)
        ui.check("暗い表示: 色の変数は黒と白", ui.ev(COLS % VARS), DARK)
        ui.check("暗い表示: 幕の濃さは 78%", ui.ev("getComputedStyle(document.documentElement).getPropertyValue('--popDim').trim()"), "78%")

        # ══ 開いたまま明るい表示に替える: 読み直さずに替わる ══
        ui.ev("window.__same=1")
        ui.media("light")
        ui.check("開いたまま明るい表示に替えると、読み直さずに白になる",
                 [ui.ev("window.__same"), ui.ev(COLS % VARS)], [1, LIGHT])
        ui.media()
        ui.check("暗い表示に戻すと、黒と白に戻る", ui.ev(COLS % VARS), DARK)

        # ══ 明るい表示で開く ══
        ui.media("light")
        ui.open(now=at(no), tz=TZ)
        ui.check("明るい表示: 色の変数は白（案 A 白と墨）", ui.ev(COLS % VARS), LIGHT)
        ui.check("明るい表示: 地（body）は白", ui.ev("getComputedStyle(document.body).backgroundColor"), "rgb(255, 255, 255)")
        ui.check("明るい表示: 幕の濃さは 50%", ui.ev("getComputedStyle(document.documentElement).getPropertyValue('--popDim').trim()"), "50%")
        r = ui.ev(RATIOS % VARS)
        ui.check("明るい表示: 地との比（字 7 以上・副次・金・赤 4.5 以上・無効 2 以上・点 3 以上で副次色より沈む・線 1.3 以上）",
                 [r["--paper"] >= 7, r["--dim"] >= 4.5, r["--gold"] >= 4.5, r["--coral"] >= 4.5, r["--slate"] >= 2,
                  3 <= r["calDot"] < r["--dim"], r["--edge"] >= 1.3], [True] * 7)
        ui.check("明るい表示: 切り替えのボタンは無い（設定の行は今までどおり）",
                 ui.ev("[...document.querySelectorAll('#dsetbody .toggle')].map(e=>e.id).some(i=>/theme|light|dark/i.test(i))"), False)
        scan("盤")

        for sid, btn, close, title in (("dstatsheet", "dstats", "dstats-close", "統計"),
                                       ("dhelpsheet", "dhelp", "dhelp-close", "遊び方"),
                                       ("dsetsheet", "dset", "dset-close", "設定")):
            ui.ev("document.getElementById(%r).click()" % btn)
            ui.check("%s: 幕は地の色の 50%%" % title,
                     ui.ev("(function(){" + LIB + "const c=__rgba(getComputedStyle(%s).backgroundColor);"
                           "return [Math.round(c[0]),Math.round(c[1]),Math.round(c[2]),Math.round(c[3]*100)/100]})()" % sid),
                     [255, 255, 255, 0.5])
            scan(title)
            ui.ev("document.getElementById(%r).click()" % close)
        ui.ev("dgiveup.click()")
        scan("ギブアップの確認")
        ui.ev("document.getElementById('gu-no').click()")

        ui.solve(row["sol"], wait=0.9)
        ui.check("解いた後: 「10」は白の金", ui.ev("getComputedStyle(eq).color"), "rgb(143, 102, 0)")
        scan("解いた後")

        # ══ 問題が無い日 ══
        ui.open()
        ui.check("問題が無い日: 地は白", ui.ev("getComputedStyle(document.body).backgroundColor"), "rgb(255, 255, 255)")
        scan("問題が無い日")
    finally:
        ui.media()
    ui.check_no_errors()
