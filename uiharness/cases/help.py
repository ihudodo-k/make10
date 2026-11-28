# -*- coding: utf-8 -*-
"""遊び方（9.5。Web のデイリーの遊び方を手本に作り直した。GAME-SPEC 7-4）。

9.5 まではケース look の中にあった（9.6 で分けた。1 ファイル 1 主題）:
  - 並びと文・見本の盤 2 組（Web のデイリーと同じ部品。盤の実物と同じ見た目・同じ動き）・式・アイコン
  - 金は見本の「10」だけ・動きを減らす設定・はみ出し（日本語・英語・360×640 も）
  - 節の見出しの様式（9.7 で 13px・700・副次色）とモードの行の区切り（9.7。日本語「・・・」・英語「 — 」）
  - 題の行（9.6）: シートを下へ動かしても、題の行（＜ と 題）が上に残り、＜ が本文に重ならない。
    本文は題の行の下地の下をくぐる。同じ作りの統計のシートも見る（題の行の決まり .sheet h2 は 4 枚のシートで共通）
Web と同じ文と部品がそろっていることは verify_daily.py のケース sync が照合する。
"""
import time

NAME = "遊び方"

# テーマ変数を解決した色
V = ("(n=>{const e=document.createElement('i');e.style.color='var('+n+')';"
     "document.body.appendChild(e);const c=getComputedStyle(e).color;e.remove();return c})")


# ── 遊び方（9.5）。Web のデイリーの遊び方（DAILY-SPEC 13-10）を手本に作り直した ──
HELP_LINES = {
    "ja": [["P", "4 つの数字を順番どおりに全部使って 10 を作ります。"],
           ["H3", "計算のきまり"],
           ["P", "^ は累乗です（2 ^ 3 = 8）"], ["P", "0 ^ 0 は 1 です（0 ^ 0 = 1）"],
           ["P", "^ は右から計算します。2 ^ 3 ^ 2 は 2 ^ ( 3 ^ 2 )"], ["P", "! は階乗です（4! = 4 × 3 × 2 × 1 = 24）"],
           ["P", "0! は 1 です（0! = 1）"], ["P", "階乗は 12! まで。3!! とは書けません。( 3! )! と書きます"],
           ["P", "0 で割る式は正解になりません"],
           ["H3", "操作"],
           ["P", "置いた記号を式の外へ出すと外れます"], ["P", "置いた記号は、つまんで別の場所へ運べます"],
           ["P", "演算子は、置いてある演算子の上に重ねると差し替わります"],
           ["P", "括弧は ( と ) を別々に置きます。相手がいない括弧は赤くなります"],
           ["P", "タップで置く：設定でオンにすると、記号を押して選び、置き場所を押します。置いた記号は押すと外れます"],
           ["P", "全部消す：置いた記号をまとめて外します"],
           ["H3", "ヒント"],
           ["P", "ヒント：3 段階です。押すたびに少しずつ答えに近づきます"],
           ["P", "3段階目の式を押すと、ほかの解き方も見られます。"],
           ["P", "ヒントの数には限りがあります。挑戦モードで 2 問解くごとに 1 つ増えます"],
           ["H3", "モード"],
           ["P", "クラシック ・・・ 1000問。だんだん難しくなります"], ["P", "フリープレイ ・・・ ランダムに出題。まだ解いていない問題から出ます。挑戦モードで解いた問題も出ます"],
           ["P", "挑戦モード ・・・ 100問クリアで解放。かなりの難問です"], ["P", "デイリー ・・・ 1 日 1 問。みんなが同じ問題を解きます"],
           ["H3", "統計"],
           ["P", "クラシックの進み：1000 問のうち、解いて先へ進んだ数"],
           ["P", "挑戦モードの進み：挑戦モードで解いた問題の数。フリープレイで解いても数えません"],
           ["P", "解いた問題：解いた問題の数。同じ問題は何度解いても 1 回です"],
           ["P", "平均時間：最近解いた 30 回の、解けるまでの時間の平均。モードは分けません"],
           ["P", "難易度別クリア数：難易度ごとの解いた回数。解き直しも数えます"],
           ["P", "最近解いた問題：新しい順に 30 件。押すとその問題が開きます"],
           ["P", "ヒントの残り：使えるヒントの数。新しい段階を開くと 1 つ減ります"],
           ["P", "デイリーの結果は、ここには入りません"],
           ["H3", "デイリー"],
           ["P", "1 日 1 回だけ解けます"], ["P", "ヒント：共有でもらえます（1 日 2 回まで）"],
           ["P", "ギブアップ：解答例を見て、その日を終えます"], ["P", "統計：解いた日数・連続日数とカレンダー"],
           ["P", "毎日 0 時（端末の時刻）に新しい問題になります。"],
           ["P", "記録はクラシックとは別に数えます。クラシックのヒントは減りません"],
           ["H3", "共有コード"],
           ["P", "問題ごとにコードがあります。友達に送ると同じ問題が開きます。"],
           ["P", "共有：問題の画面の右上から、コードを送れます"],
           ["P", "問題の画面の上のコードを押すと、コピーできます"],
           ["P", "もらったコードは、ホームの欄に入れてひらくを押します"]],
    "en": [["P", "Make 10 using all four numbers in order."],
           ["H3", "Rules"],
           ["P", "^ is power (2 ^ 3 = 8)"], ["P", "0 ^ 0 is 1 (0 ^ 0 = 1)"],
           ["P", "^ is evaluated right to left. 2 ^ 3 ^ 2 means 2 ^ ( 3 ^ 2 )"],
           ["P", "! is factorial (4! = 4 × 3 × 2 × 1 = 24)"], ["P", "0! is 1 (0! = 1)"],
           ["P", "Factorials go up to 12!. You can't write 3!!; write ( 3! )!"], ["P", "Dividing by 0 never counts as correct"],
           ["H3", "Controls"],
           ["P", "Drag a placed symbol out to remove it."], ["P", "Drag a placed symbol to move it to another spot."],
           ["P", "Drop an operation on top of another to replace it."],
           ["P", "Place ( and ) separately. Unmatched parentheses turn red."],
           ["P", "Tap to place · Turn it on in Settings, tap a symbol, then tap a spot. Tap a placed symbol to remove it."],
           ["P", "Clear all · Removes every placed symbol"],
           ["H3", "Hints"],
           ["P", "Hint · 3 steps, each a little closer to the answer"],
           ["P", "In step 3, tap the expression to see other solutions."],
           ["P", "Hints are limited. You get one for every 2 Challenge puzzles you solve."],
           ["H3", "Modes"],
           ["P", "Classic — 1000 puzzles that get harder as you go"], ["P", "Free Play — random puzzles, unsolved ones first. Challenge puzzles you've solved show up too"],
           ["P", "Challenge — unlocks after 100 clears. Very tough puzzles"],
           ["P", "Daily — one puzzle a day, the same for everyone"],
           ["H3", "Stats"],
           ["P", "Classic progress · How many of the 1000 puzzles you've finished"],
           ["P", "Challenge progress · Puzzles solved in Challenge mode. Free Play solves don't count"],
           ["P", "Puzzles solved · Each puzzle counts once, however many times you solve it"],
           ["P", "Avg. time · Average time of your last 30 solves, all modes together"],
           ["P", "Clears by difficulty · Every solve by difficulty, re-solves included"],
           ["P", "Recently solved · Your last 30 solves, newest first. Tap one to open it"],
           ["P", "Hints left · Hints you can still use. Each new step uses one"],
           ["P", "Daily results are not counted here."],
           ["H3", "Daily"],
           ["P", "One try a day."], ["P", "Hint · Share to get one (up to 2 a day)"],
           ["P", "Give up · See a solution and end the day's puzzle"], ["P", "Stats · Days solved, streaks and a calendar"],
           ["P", "A new puzzle every day at midnight, your local time."],
           ["P", "Daily results are counted separately from Classic. Your Classic hints are not used."],
           ["H3", "Share codes"],
           ["P", "Every puzzle has a code. Send it to a friend to open the same puzzle."],
           ["P", "Share · Send the code from the top right of the puzzle screen"],
           ["P", "Tap the code at the top of the puzzle screen to copy it"],
           ["P", "To open a code you got, enter it on Home and tap Open"]],
}
# 見本の 2 組 [手順の番号, 図の名前, 説明]（Web と同じ文）
HELP_FIGS = {"ja": [["1", "見本: 8 7 5 2 の、8 と 7 のあいだに − を置く", "記号を数字のあいだへドラッグして置きます\n（設定でタップ配置にもできます）"],
                    ["2", "見本: ( 8 − 7 ) × 5 × 2 は、括弧の中から計算して 10。正解", "括弧の中から先に計算します。10 になれば正解です"]],
             "en": [["1", "Example: placing − between 8 and 7 in 8 7 5 2", "Drag a symbol between the numbers\n(or turn on Tap to place in Settings)"],
                    ["2", "Example: ( 8 − 7 ) × 5 × 2 is calculated from the parentheses and makes 10. Solved!",
                     "Parentheses are calculated first. Make 10 and it's solved"]]}
# 遊び方の並び: 見出し（H3）と文（P。見本の説明は .hfig の中なので入らない）
HELP_SEQ = "[...$('help').children].filter(e=>e.tagName==='P'||e.tagName==='H3').map(e=>[e.tagName,e.textContent.trim()])"
HD = "document.getAnimations().filter(a=>(a.animationName||'').startsWith('hd-'))"
# 見本の部品の見た目を、盤の実物と比べる（Web のケース help と同じ比べ方。色・太さ・線は同じ、大きさは盤の寸法 × 倍率 --dk）
HELP_LOOK = r"""(function(){
  const q=s=>document.querySelector(s), cs=e=>getComputedStyle(e), bad=[];
  const dk=parseFloat(cs(q('#help .hdemo')).getPropertyValue('--dk'));
  const same=(name,a,b,props)=>{if(!a||!b){bad.push(name+': 要素が無い');return}
    for(const p of props)if(cs(a)[p]!==cs(b)[p])bad.push(name+'.'+p+': 盤 '+cs(a)[p]+' / 見本 '+cs(b)[p])};
  const ratio=(name,a,b,props,k)=>{if(!a||!b)return;
    for(const p of props){const x=parseFloat(cs(a)[p]),y=parseFloat(cs(b)[p]);
      if(!(x>0)||Math.abs(y-x*k)>0.06)bad.push(name+'.'+p+': 盤 '+x+' × '+k+' / 見本 '+y)}};
  const d=q('#help .hd2');
  same('数字',q('#expr .num'),d.querySelector('.dnum'),['color','fontWeight','fontVariantNumeric']);
  ratio('数字',q('#expr .num'),d.querySelector('.dnum'),['fontSize','width','height','marginLeft'],dk);
  same('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['color','fontWeight']);
  ratio('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['fontSize','width','height'],dk);
  same('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['color','fontWeight']);
  ratio('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['fontSize','width','height'],dk);
  const line=['borderTopColor','borderTopStyle','borderTopWidth','backgroundColor'];
  same('枠',q('#expr .zone.live:not(.hot)'),q('#help .hd1 .dzone'),line);
  same('吸着した枠',q('#expr .zone.hot'),q('#help .hd1 .dhot'),line);
  same('トレイの記号',q('#tray .chip:not(.off)'),q('#help .hd1 .dchip'),['color','fontWeight']);
  ratio('トレイの記号',q('#tray .chip:not(.off)'),q('#help .hd1 .dchip'),['fontSize'],dk);
  same('トレイの線',q('#tray'),q('#help .hd1 .dtray'),['borderTopColor','borderTopStyle','borderTopWidth']);
  same('10',q('#eq.hit'),d.querySelector('.deq'),['color','fontWeight','fontVariantNumeric']);
  same('正解',q('#sub.ok'),d.querySelector('.dsub'),['color']);
  same('運んでいる記号',q('#ghost'),q('#help .hd1 .dghost'),['color','fontWeight']);
  ratio('運んでいる記号',q('#ghost'),q('#help .hd1 .dghost'),['fontSize'],dk);
  return {bad,dk}})()"""
# 遊び方のシートの中で、横にはみ出す要素・はみ出す段落・折り返した式・横の動き・画面全体の縦の動き
HELP_FIT = ("(()=>{const h=$('help'),hb=h.getBoundingClientRect(),bad=[];"
            "for(const e of h.querySelectorAll('*')){const r=e.getBoundingClientRect();if(!r.width)continue;"
            "if(r.left<hb.left-0.5||r.right>hb.right+0.5)bad.push(e.className||e.tagName)}"
            "for(const p of h.querySelectorAll('p'))if(p.scrollWidth>p.clientWidth+1)bad.push('p:'+p.textContent.slice(0,12));"
            "return [bad,[...h.querySelectorAll('code')].filter(c=>c.getClientRects().length!==1).map(c=>c.textContent),"
            "h.scrollWidth>h.clientWidth,document.documentElement.scrollWidth>innerWidth,"
            "document.documentElement.scrollHeight>innerHeight+1]})()")


def sheet(ui):
    """遊び方（9.5）。並び・文・見本の盤（Web と同じ部品・同じ動き・盤と同じ見た目）・アイコン・はみ出し"""
    for lang in ("ja", "en"):
        ui.open(lang=lang)
        ui.ev("go('help')")
        time.sleep(0.3)
        ui.check("遊び方（%s）: 見出しと、節の見出し・文の並び（9.5）" % lang,
                 [ui.ev("document.querySelector('#help h2').textContent"), ui.ev(HELP_SEQ)],
                 [{"ja": "遊び方", "en": "How to play"}[lang], HELP_LINES[lang]])
        ui.check("遊び方（%s）: 見本は 2 組で、最初の文のすぐ後。手順の番号・図の名前・説明（Web と同じ文）" % lang,
                 [ui.ev("[...document.querySelectorAll('#help .hfig')].map(f=>[f.querySelector('.hstep').textContent,"
                        "f.querySelector('.hdemo').getAttribute('aria-label'),f.querySelector('.hcap').textContent])"),
                  ui.ev("[1,2,3].map(i=>$('help').children[i].tagName+'.'+$('help').children[i].className).join('|')")],
                 [HELP_FIGS[lang], "P.|DIV.hfig|DIV.hfig"])
        ui.check("遊び方（%s）: 手順 1 の説明は、文の区切りで改行して、ちょうど 2 行" % lang,
                 ui.ev("(function(){const p=document.querySelector('#help .hd1').parentElement.querySelector('.hcap');"
                       "return [getComputedStyle(p).whiteSpace,Math.round(p.getBoundingClientRect().height/parseFloat(getComputedStyle(p).lineHeight))]})()"),
                 ["pre-line", 2])
        ui.check("遊び方（%s）: 見本の「正解」は辞書の文" % lang, ui.ev("document.querySelector('#help .hd2 .dsub').textContent"),
                 {"ja": "正解", "en": "Solved!"}[lang])
        # はみ出し: 今の画面と、compact のときは 360×640 も。いちばん下へ送った後も見る
        for size in ([None] if ui.viewport == "normal" else [None, (360, 640)]):
            if size:
                ui.c.metrics(*size)
            try:
                if size:
                    ui.open(lang=lang)
                    ui.ev("go('help')")
                    time.sleep(0.3)
                a = ui.ev(HELP_FIT)
                ui.ev("$('help').scrollTop=99999")
                b = ui.ev(HELP_FIT)
                ui.ev("$('help').scrollTop=0")
                ui.check("遊び方（%s%s）: 横にはみ出さない・式は折り返さない・画面は縦に動かない（シートの中だけ動く）"
                         % (lang, "・360×640" if size else ""), [a, b], [[[], [], False, False, False]] * 2)
            finally:
                if size:
                    ui.c.metrics(360, 690)
    ui.open()
    ui.ev("go('help')")
    ui.check("式（Web と同じ 4 つと、^ は右から・12! の式）",
             ui.ev("[...document.querySelectorAll('#help code')].map(e=>e.textContent)"),
             ["2 ^ 3 = 8", "0 ^ 0 = 1", "2 ^ 3 ^ 2", "2 ^ ( 3 ^ 2 )", "4! = 4 × 3 × 2 × 1 = 24", "0! = 1", "3!!", "( 3! )!"])
    ui.check("式は本文と同じ書体の太字で、折り返さない（Web と同じ）",
             ui.ev("(function(){const c=getComputedStyle(document.querySelector('#help code')),p=getComputedStyle(document.querySelector('#help p'));"
                   "return [c.whiteSpace,c.fontWeight,c.fontFamily===p.fontFamily]})()"), ["nowrap", "700", True])
    ui.check("文は 13px・行間 1.75・明るさ 85%（Web の遊び方と同じ）・段落の間は 6px",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#help p'));"
                   "return [s.fontSize,Math.round(parseFloat(s.lineHeight)*100)/100,s.opacity,s.marginBottom]})()"),
             ["13px", 22.75, "0.85", "6px"])
    ui.check("アイコン付きの行の絵柄は、本物のボタンと同じ（全部消す・ヒント・デイリーのヒント・ギブアップ・統計・共有）",
             ui.ev("[['hi-clear','clear'],['hi-hint','hint'],['hi-dhint','hint'],['hi-giveup','dgiveup'],['hi-dstats','dstats'],['hi-share','share']]"
                   ".map(([a,b])=>$(a).innerHTML===$(b).querySelector('svg').outerHTML)"), [True] * 6)
    ui.check("図の中身は読み上げから隠してある・見本は触れない（pointer-events:none）",
             ui.ev("[[...document.querySelectorAll('#help .hdemo')].every(d=>d.getAttribute('role')==='img'&&[...d.children].every(c=>c.getAttribute('aria-hidden')==='true')),"
                   "getComputedStyle(document.querySelector('#help .hdemo')).pointerEvents]"), [True, "none"])
    ui.check("見本に見えている文字（置いた後の 8 − 7 5 2 とトレイの 8 つ／10・正解・( 8 − 7 ) × 5 × 2）",
             ui.ev("[[...document.querySelectorAll('#help .hd1 .dexpr .dnum,#help .hd1 .dexpr .dtok')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd1 .dchip')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd2 .deq,#help .hd2 .dsub')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd2 .dexpr>*')].map(e=>e.textContent).join(' ')]"),
             ["8 − 7 5 2", "+ − × ÷ ^ ! ( )", "10 正解", "( 8 − 7 ) × 5 × 2"])
    ui.check("開いている間: 見本の動きは 12 個。どれも 5 秒で繰り返し、動かすのは transform と opacity だけ",
             ui.ev("(function(){const a=" + HD + ";const keys=new Set();"
                   "a.forEach(x=>x.effect.getKeyframes().forEach(k=>Object.keys(k).forEach(p=>keys.add(p))));"
                   "['offset','computedOffset','easing','composite'].forEach(p=>keys.delete(p));"
                   "return [a.length,a.every(x=>x.playState==='running'),"
                   "a.every(x=>x.effect.getTiming().duration===5000&&x.effect.getTiming().iterations===Infinity),[...keys].sort()]})()"),
             [12, True, True, ["opacity", "transform"]])
    pos = ("(function(){const c=s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]};"
           "const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
           "const g=c('#help .hd1 .dghost'),z=c('#help .hd1 .ds1');"
           "return {slot:Math.hypot(g[0]-z[0],g[1]-z[1]),ghost:o('#help .hd1 .dghost'),hot:o('#help .hd1 .dhot'),tok:o('#help .hd1 .ds1 .dtok')}})()")
    ui.ev(HD + ".forEach(a=>{a.pause();a.currentTime=2200})")
    f = ui.ev(pos)
    ui.check("動きの途中（2.2 秒）: 運ぶ記号が 8 と 7 のあいだの枠に重なり、その枠が明るい",
             [f["slot"] < 1.5, f["ghost"], f["hot"], f["tok"]], [True, 1, 1, 0])
    ui.ev("go('settings')")
    ui.check("遊び方を閉じると、見本の動きは止まる（動いているものが 0 個）", ui.ev(HD + ".length"), 0)
    # 見本の見た目は、盤の実物と同じ（盤を解いた形にして、枠を開き、1 つを吸着の見た目にしてから比べる）
    # 本編 11 問目（4205）の解答例は ( 4 - 2 + 0 ) * 5 で、括弧・演算・数字がそろう。枠の色は遷移するので、待ってから比べる
    ui.open({"ci": 10})
    ui.ev("start('course')")
    ui.solve(wait=0.8)
    ui.ev("showZones('!');document.querySelector('#expr .zone.live').classList.add('hot');ghost.style.display='block'")
    ui.ev("$('help').classList.remove('hide')")
    time.sleep(0.6)
    look = ui.ev(HELP_LOOK)
    ui.ev("$('help').classList.add('hide');ghost.style.display='none'")
    ui.check("比べる相手がある（盤に括弧と演算がある）",
             ui.ev("document.querySelectorAll('#expr .tok.lp').length>0&&document.querySelectorAll('#expr .tok.op').length>0"), True)
    ui.check("見本の数字・演算・括弧・枠・吸着した枠・トレイ・「10」・「正解」・運ぶ記号は、盤の実物と同じ見た目（大きさは × 0.55）",
             [look["bad"], look["dk"]], [[], 0.55])
    ui.check("遊び方の中で金を使っているのは、見本の「10」だけ（正解の「10」の見本。Web の遊び方と同じ）",
             ui.ev("(()=>{const g=%s('--gold');return [...document.querySelectorAll('#help *')].filter(e=>getComputedStyle(e).color===g"
                   "&&getComputedStyle(e.parentElement).color!==g).map(e=>e.className+':'+e.textContent)})()" % V), ["deq:10"])
    # 動きを減らす設定: 動かさず、置いた後の形で止まっている
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        ui.open()
        ui.ev("go('help')")
        time.sleep(0.3)
        ui.check("動きを減らす設定: 見本は動かず、置いた後の形（記号は置かれ、枠と運ぶ記号は見えない）",
                 [ui.ev(HD + ".length"),
                  ui.ev("(function(){const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
                        "return [o('#help .hd1 .ds1 .dtok'),o('#help .hd1 .dzone'),o('#help .hd1 .dhot'),o('#help .hd1 .dghost')]})()")],
                 [0, [1, 0, 0, 0]])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors("遊び方で JS エラー 0")


# ── 題の行（9.6）。9.5 までは題が本文と一緒に流れて消え、#app に固定の ＜（#navback）だけが残って本文に重なっていた ──
# 今のシートで: 題の行の上端とシートの上端の差・＜ と題の行の中心の差・題の行の下地の色が地の色か・
# ＜ の四角と題の行の帯の上の点で、＜ の次にいちばん上にあるのが題の行か（本文が見えていないか）・本文が題の行の下に入っているか
TITLE = ("(()=>{const sc=$(SCR),h=sc.querySelector('h2'),hr=h.getBoundingClientRect(),sr=sc.getBoundingClientRect(),"
         "nb=$('navback'),nr=nb.getBoundingClientRect(),bad=[];const pts=[];"
         "for(const fx of [.1,.5,.9])for(const fy of [.1,.5,.9])pts.push([nr.left+nr.width*fx,nr.top+nr.height*fy]);"
         "for(const fx of [.3,.6,.95])pts.push([hr.left+hr.width*fx,hr.top+hr.height*.5]);"
         "for(const [x,y] of pts){const top=document.elementsFromPoint(x,y).find(e=>!nb.contains(e));"
         "if(!top||!h.contains(top))bad.push(Math.round(x)+','+Math.round(y)+':'+(top?(top.id||top.tagName+'.'+top.className):'なし'))}"
         "const under=[...sc.querySelectorAll('p,h3,.stat,.toggle,.hfig')].some(e=>{const r=e.getBoundingClientRect();"
         "return r.height&&r.top<hr.bottom-1&&r.bottom>hr.top});"
         "return {top:Math.round(hr.top-sr.top),mid:Math.abs((nr.top+nr.bottom)/2-(hr.top+hr.bottom)/2)<1,"
         "bg:getComputedStyle(h).backgroundColor===%s('--ink'),bad,under,moves:sc.scrollHeight-sc.clientHeight}})()" % V)
HIST = [{"c": "1234", "d": 3, "s": 20 + i, "m": "course"} for i in range(40)]
STATS_SAVE = {"ci": 137, "cleared": 162, "stats": {"n": 40, "sec": 1580, "best": 20, "band": {"3-8": 40}}, "hist": HIST}


def title_row(ui, size):
    where = ("%d×%d" % size) if size else ui.viewport
    for lang in ("ja", "en"):
        for scr, save in (("help", None), ("stats", STATS_SAVE)):
            ui.open(save, lang=lang)
            ui.ev("go('%s')" % scr)
            time.sleep(0.3)
            got = []
            for y in ("0", "Math.round(($(SCR).scrollHeight-$(SCR).clientHeight)/2)", "99999"):
                ui.ev("$(SCR).scrollTop=" + y)
                time.sleep(0.1)
                r = ui.ev(TITLE)
                got.append([r["top"], r["mid"], r["bg"], r["bad"], r["under"] or y == "0"])
                moves = r["moves"]
            name = {"help": "遊び方", "stats": "統計（履歴 40 件）"}[scr]
            ui.check("題の行（%s・%s・%s）: シートは縦に動く（確かめる意味がある）" % (name, lang, where), moves > 100, True)
            ui.check("題の行（%s・%s・%s）: 上・途中・下まで動かしても、題の行はシートの上に残り、＜ と並ぶ。"
                     "下地は地の色で、＜ の下にも題の行の帯にも本文が見えない。本文は題の行の下をくぐる（9.6）" % (name, lang, where),
                     got, [[0, True, True, [], True]] * 3)


def stats_section(ui):
    """遊び方の統計の節（9.9）。モードの節のすぐ後。項目の名前は統計の画面と同じ文（辞書を引く）、
    文の中の数（30 件・1000 問）はコードの数え方と同じ。文が統計の画面とずれたらここで止まる"""
    for lang in ("ja", "en"):
        ui.open(lang=lang)
        ui.ev("go('help')")
        got = ui.ev("(()=>{const h=[...document.querySelectorAll('#help h3')],i=h.findIndex(e=>e.textContent===t('help.sec_stats'));"
                    "const ps=[];let e=h[i]&&h[i].nextElementSibling;while(e&&e.tagName==='P'){ps.push(e);e=e.nextElementSibling}"
                    "return [h.map(e=>e.textContent),i>0&&h[i-1].textContent===t('help.sec_modes'),"
                    "ps.slice(0,7).map(p=>(p.querySelector('b')||{}).textContent),"
                    "['stats.course','stats.chal','stats.solved','stats.avg','stats.by_level','stats.recent','stats.hints'].map(k=>t(k)),"
                    "ps.length,[AVG_RECENT,COURSE.length]]})()")
        ui.check("遊び方（%s）: 統計の節はモードの節のすぐ後・8 行（9.9）" % lang, [got[1], got[4]], [True, 8])
        ui.check("遊び方（%s）: 統計の節の各行の太字は、統計の画面の名前と同じ文（同じ並び）" % lang, got[2], got[3])
        ui.check("遊び方（%s）: 文の中の数は、平均時間と最近解いた問題の 30・クラシックの 1000（コードの AVG_RECENT・COURSE の数）" % lang,
                 got[5], [30, 1000])
    # 最近解いた問題の一覧は 30 件まで（履歴は 100 件まで持つ）
    ui.open(STATS_SAVE)
    ui.ev("go('stats')")
    ui.check("統計: 最近解いた問題の一覧は 30 件（遊び方の文と同じ）", ui.ev("$('stathist').querySelectorAll('.toggle').length"), 30)


def run(ui):
    ui.open()
    ui.ev("go('help')")
    # 9.7: 12px・500 では薄すぎて読みにくかった。副次色のまま 13px・700・字間 4%（本文より控えめなのは色。--slate は使わない）
    ui.check("遊び方: 節の見出しは 13px・700・副次色（--slate ではない）・字間 4%（9.7）",
             ui.ev("(()=>{const c=getComputedStyle(document.querySelector('#help h3'));return [c.fontSize,c.fontWeight,"
                   "c.color===%s('--dim'),c.color===%s('--slate'),Math.round(parseFloat(c.letterSpacing)/13*100)]})()" % (V, V)),
             ["13px", "700", True, False, 4])
    ui.check("遊び方: 節の見出しはどれも同じ様式（7 つ。9.9 で統計を足した）",
             ui.ev("(()=>{const h=[...document.querySelectorAll('#help h3')];return [h.length,new Set(h.map(e=>{const c=getComputedStyle(e);"
                   "return c.fontSize+c.fontWeight+c.color+c.letterSpacing})).size]})()"), [7, 1])
    stats_section(ui)
    ui.ev("go('settings')")
    ui.check("設定と統計の節見出しは 12px・500 のまま（9.7 で変えたのは遊び方だけ）",
             ui.ev("['#settings h3','#stats h3'].map(s=>{const c=getComputedStyle(document.querySelector(s));return c.fontSize+'/'+c.fontWeight})"),
             ["12px/500", "12px/500"])
    sheet(ui)
    title_row(ui, None)
    if ui.viewport == "compact":
        for size in ((360, 640), (390, 844)):
            ui.c.metrics(*size)
            try:
                title_row(ui, size)
            finally:
                ui.c.metrics(360, 690)
    ui.check_no_errors("題の行で JS エラー 0")
