# -*- coding: utf-8 -*-
"""底が -1・0・1 の累乗（6.7・GAME-SPEC 2-5）。

底が -1・0・1 なら値は -1・0・1 にしかならないので、指数の上限（24）を掛けない。
pwr() は**ループに入る前に偶奇で返す** ―― ループのままだと指数 12!（4.8 億回）や
134 桁の指数で固まる（6.6 の pwr() は 1,000 万回で約 0.2 秒かかった）。
"""
import time

NAME = "底が -1・0・1 の累乗"

# 盤面に任意の式を置く。__solve() と同じ置き方で、解答例の代わりに引数の文字列を使う
PLACE = """
window.__place=function(s){
  const t=performance.now();
  let i=0;
  for(const ch of s.replace(/\\s+/g,'')){
    if(/[0-9]/.test(ch)){i++;}
    else if(ch==='('){put('lp',i);i++;}
    else if(ch===')'){put('rp',i);i++;}
    else if(ch==='!'){put('!',i);i++;}
    else {put(ch,i);i++;}
  }
  render();
  window.__placeMs=performance.now()-t;
  return $('eq').textContent;
};
"""


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.ev(PLACE)
    # ── pwr() そのもの（指数の大きさによらず一瞬で終わる） ────────────────
    ui.ev("""window.__pw=(function(){
      const show=v=>v===null?'null':(v.d===1n?String(v.n):v.n+'/'+v.d);
      const big=10n**133n+1n;                       // 134 桁の奇数
      const cases=[[-1n,120n],[-1n,121n],[-1n,-121n],[-1n,479001600n],[-1n,big],
                   [1n,479001600n],[1n,-big],[0n,big],[0n,0n],[0n,-5n],
                   [2n,24n],[2n,25n],[-2n,25n]];
      const t=performance.now();
      const out=cases.map(([a,e])=>show(pwr(R(a),R(e))));
      out.push(show(pwr(R(1n,2n),R(25n))));         // 分数の底は今までどおり 24 まで
      return {out,ms:performance.now()-t};
    })()""")
    ui.check("pwr: (-1)^120・(-1)^121・(-1)^-121・(-1)^12!・(-1)^(134 桁の奇数)",
             ui.ev("__pw.out.slice(0,5)"), ["1", "-1", "-1", "1", "-1"])
    ui.check("pwr: 1^12!・1^(-134 桁)・0^(134 桁)・0^0・0^-5",
             ui.ev("__pw.out.slice(5,10)"), ["1", "1", "0", "1", "null"])
    ui.check("pwr: 2^24 は計算でき、2^25・(-2)^25・(1/2)^25 は今までどおり計算できない",
             ui.ev("__pw.out.slice(10)"), [str(2 ** 24), "null", "null", "null"])
    ui.check("pwr: 14 通りが 50ms 未満で終わる", ui.ev("__pw.ms<50"), True)

    # ── 8959: ( 8 - 9 ) ^ 5! + 9 を組んで 10 になる ────────────────────
    ui.ev("go('home'); start('free')")
    code = ui.ev("(function(){for(const p of INDEX.values())"
                 "if(p.id==='8959')return codeOf(p);return null})()")
    ui.check("8959 が問題データにある", code is not None, True)
    ui.ev("loadPuzzle(byCode(%r))" % code)
    ui.check("8959 の解答例", ui.ev("cur.sol"), "( 8 - 9 ) ^ 5! + 9")
    ui.check("8959 の難易度は 15", ui.ev("cur.d"), 15)
    got = ui.ev("__place('( 8 - 9 ) ^ 5! + 9')")
    time.sleep(1.0)
    ui.check("( 8 - 9 ) ^ 5! + 9 を組むと 10", got, "10")
    ui.check("読み出し行が「10|正解」", ui.text("eq") + "|" + ui.text("sub"), ui.solved_text())
    ui.check("「計算できません」は出ない",
             "計算できません" in ui.ev("document.body.innerText"), False)

    # ── 巨大な指数でも固まらない ──────────────────────────────────────
    # 9094 は問題データに無いので、出題中の問題を写して数字と解答例だけ差し替える。
    # 9 + 0! ^ 9! ^ 4! = 9 + 1^(9!^24)。指数 9!^24 は 134 桁
    ui.ev("go('home'); start('free')")
    ui.ev("loadPuzzle(Object.assign({},cur,{id:'9094',rc:'N',sol:'9 + 0! ^ 9! ^ 4!'}))")
    t = time.time()
    got = ui.ev("__place('9 + 0! ^ 9! ^ 4!')")
    wall = time.time() - t
    time.sleep(1.0)
    ui.check("9 + 0! ^ 9! ^ 4!（指数 134 桁）を組むと 10", got, "10")
    ui.check("組み終えるまで 500ms 未満（ブラウザ内の計測）", ui.ev("__placeMs<500"), True)
    ui.check("組み終えるまで 2 秒未満（外からの計測）", wall < 2.0, True)
    # 底が 0 の大きな指数も同じ（0 ^ 7! = 0）
    ui.ev("loadPuzzle(Object.assign({},cur,{id:'0791',rc:'N',sol:'0 ^ 7! + 9 + 1'}))")
    got = ui.ev("__place('0 ^ 7! + 9 + 1')")
    ui.check("0 ^ 7! + 9 + 1 を組むと 10（底 0・指数 5040）", got, "10")
    ui.check_no_errors("累乗の確認で JS エラー 0")
