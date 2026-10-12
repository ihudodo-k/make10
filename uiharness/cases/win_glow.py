# -*- coding: utf-8 -*-
"""正解したとき、数字は動かず、左から順に一瞬ほのかに光る（8.3。GAME-SPEC 8 章・DESIGN.md 4 章）。

8.2 までは、数字が 13px 上がって戻る動き（.num.pop）を、左から 0.07 秒ずつずらして行っていた。位置が大きく動くのをやめ、
数字は動かさずに影だけを光らせる（.num.shine）。光の強さと長さは、段階 2 で演算子が光る .tok.shine と同じ値。
あわせて、行き過ぎて戻る曲線 --ease を消した（動きの曲線は「減速して止まる」だけ）。

描画のたび（requestAnimationFrame）に数字の位置と影を記録して、
- 正解の後、数字の位置が上下にも左右にも動かないこと
- 光が左から順に付くこと（間隔は約 0.07 秒）。終わったら消えること
- 動きを減らす設定（prefers-reduced-motion）では、何も動かず、光らないこと
を見る。
"""
import json
import os
import re
import time

NAME = "正解の光（数字は動かない）"

# 最後の 1 手の手前まで置く（ここでは正解にならない）
PREP = r"""(function(expr){
  const steps=[];let p=0;
  for(const tk of expr.split(' ')){let x=tk,fac=0;while(x.endsWith('!')){fac++;x=x.slice(0,-1)}
    if(/^[0-9]$/.test(x))p++;
    else if(x==='('){steps.push(['lp',p]);p++}else if(x===')'){steps.push(['rp',p]);p++}else if(x!==''){steps.push([x,p]);p++}
    for(let k=0;k<fac;k++){steps.push(['!',p]);p++}}
  clearAll();for(const s of steps.slice(0,-1))put(s[0],s[1]);render();
  window.__last=steps[steps.length-1];return steps.length})"""
# 最後の 1 手を置いて、描画のたびに、数字の位置・影・transform と、演算子の影を記録する
FIRE = r"""(function(){
  put(__last[0],__last[1]);render();
  const t0=performance.now();window.__gl={on:true,f:[]};
  (function loop(){if(!__gl.on)return;
    const r=e=>{const b=e.getBoundingClientRect(),c=getComputedStyle(e);
      return [Math.round(b.left*100)/100,Math.round(b.top*100)/100,c.textShadow!=='none',c.transform,c.animationName]};
    __gl.f.push([performance.now()-t0,[...document.querySelectorAll('#expr .num')].map(r),
      [...document.querySelectorAll('#expr .tok.op,#expr .tok.fac')].map(e=>getComputedStyle(e).textShadow!=='none'),
      document.getAnimations().length]);
    requestAnimationFrame(loop)})();
  return curExprScale})()"""
STOP = "(function(){__gl.on=false;return __gl.f})()"
# CSS の決まりを、スタイルシートから読む（計算後の値ではなく、書いてある規則）
RULES = r"""(function(){const out={kf:{},ease:getComputedStyle(document.documentElement).getPropertyValue('--ease').trim()};
  for(const sh of document.styleSheets){let rs;try{rs=sh.cssRules}catch(e){continue}
    for(const r of rs)if(r.type===CSSRule.KEYFRAMES_RULE)out.kf[r.name]=[...r.cssRules].map(k=>[k.keyText,k.style.textShadow,k.style.transform])}
  const probe=(cls,tag)=>{const e=document.createElement('div');e.className=cls;document.getElementById('expr').appendChild(e);
    const c=getComputedStyle(e),v=[c.animationName,c.animationDuration,c.animationTimingFunction,c.animationIterationCount];e.remove();return v};
  out.num=probe('num shine');out.tok=probe('tok op shine');return out})()"""


def analyze(frames, n_num):
    """記録から、(位置が動いた数字, 数字ごとに影が付いた最初の時刻, transform が none でないコマの数, 影が付いたコマの数) を返す"""
    after = [f for f in frames if f[0] >= 60 and len(f[1]) == n_num]      # 置いた直後の組み直しが済んでから
    moved = []
    for i in range(n_num):
        xs = {f[1][i][0] for f in after}
        ys = {f[1][i][1] for f in after}
        if len(xs) > 1 or len(ys) > 1:
            moved.append((i, sorted(xs), sorted(ys)))
    first = []
    for i in range(n_num):
        ts = [f[0] for f in after if f[1][i][2]]
        first.append(round(ts[0]) if ts else None)
    not_none = sum(1 for f in after for x in f[1] if x[3] != "none")
    lit = sum(1 for f in after for x in f[1] if x[2])
    return moved, first, not_none, lit, after


def run(ui):
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "index.html"),
               encoding="utf-8").read()
    picks = [(1, "COURSE[0]"),
             (2, "ALL().find(p=>p.d>=9&&p.d<=13&&p.rc==='N'&&p.sol.length<=13&&!p.sol.includes('('))"),
             (3, "ALL().find(p=>p.d>=14&&p.rc==='N'&&p.sol.length<=17)")]

    def start(pick):
        ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
        ui.ev('MODE="free";loadPuzzle(%s);go("play")' % pick)
        sol = ui.ev("cur.sol")
        ui.ev(PREP + "(%s)" % json.dumps(sol))
        time.sleep(0.5)
        return sol

    def solve_and_record(wait=1.25):
        scale = ui.ev(FIRE)
        time.sleep(wait)
        return scale, ui.ev(STOP)

    # ══ CSS の決まり ══
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.click("m-course")
    r = ui.ev(RULES)
    ng = r["kf"].get("numglow", [])                 # 規則が無ければ空（下の項目が落ちる）
    ui.check("数字の光の規則: 影だけを変える（位置は変えない）。山の影は、演算子の光（glow）の山と同じ値",
             [[k[0] for k in ng], [k[2] for k in ng],
              [k[1] for k in ng if k[0] == "50%"] == [k[1] for k in r["kf"].get("glow", []) if k[0] == "50%"],
              ([k[1] for k in ng if k[0] == "50%"] or [""])[0] not in ("", "none")],
             [["0%, 100%", "50%"], ["", ""], True, True])
    ui.check("数字の光の長さ・曲線・回数は、演算子の光（.tok.shine）と同じ（0.5 秒・1 回）",
             [r["num"][0], r["num"][1:], r["tok"][0]], ["numglow", r["tok"][1:], "glow"])
    ui.check("跳ねる動き（pop）の規則は無い。行き過ぎて戻る曲線 --ease も無い",
             ["pop" in r["kf"], r["ease"], "var(--ease)" in src, "--ease:" in src], [False, "", False, False])
    curves = [tuple(float(x) for x in m.groups()) for m in
              re.finditer(r"cubic-bezier\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)", src[:src.index("</style>")])]
    ui.check("CSS の曲線は、どれも行き過ぎない（cubic-bezier の y が 0〜1 の中。1 つ以上ある）",
             [len(curves) >= 1, [c for c in curves if not (0 <= c[1] <= 1 and 0 <= c[3] <= 1)]], [True, []])

    # ══ 段階 1〜3: 数字は動かず、左から順に光る ══
    for lv, pick in picks:
        sol = start(pick)
        n_num = 4
        scale, frames = solve_and_record()
        moved, first, not_none, lit, after = analyze(frames, n_num)
        pre = "段階 %d（%s）: " % (lv, sol)
        ui.check(pre + "正解になり、演出の段階は %d。式は縮めていない（位置を素直に比べられる）" % lv,
                 [ui.ev("$('eq').textContent+'|'+$('sub').textContent"), ui.ev("hitLv"), scale, len(after) >= 40],
                 [ui.solved_text(), lv, 1, True])
        ui.check(pre + "正解の後、数字の位置は上下にも左右にも動かない（transform も付かない）", [moved, not_none], [[], 0])
        got = [x for x in first if x is not None]
        ui.check(pre + "数字は 4 つとも光り、左から順に付く", [len(got), got == sorted(got), len(set(got)) >= 3], [n_num, True, True])
        gaps = [b - a for a, b in zip(first, first[1:])] if len(got) == n_num else []
        ui.check(pre + "光り始めは置いてから約 0.26 秒後。隣との間隔は約 0.07 秒（描画の刻みぶんの幅を見る）",
                 [200 <= (first[0] or 0) <= 340, len(gaps) == n_num - 1 and all(30 <= g <= 115 for g in gaps), 150 <= sum(gaps) <= 270],
                 [True, True, True])
        ui.check(pre + "光は 0.5 秒で消える（1.2 秒後には、影も、動いているアニメーションも無い）",
                 [any(x[2] for x in after[-1][1]), after[-1][3], ui.ev("document.querySelectorAll('#expr .num.shine').length")],
                 [False, 0, n_num])
        ops = [f[2] for f in after]
        n_ops = len(ops[-1])
        lit_ops = [any(f[i] for f in ops if len(f) == n_ops) for i in range(n_ops)]
        ui.check(pre + "演算子が光るのは段階 2 から（今までどおり）", lit_ops, [lv >= 2] * n_ops)
    ui.check_no_errors("JS エラー 0")

    # ══ 動きを減らす設定: 何も動かず、光らない ══
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        for lv, pick in (picks[0], picks[2]):
            sol = start(pick)
            scale, frames = solve_and_record()
            moved, first, not_none, lit, after = analyze(frames, 4)
            pre = "動きを減らす設定・段階 %d: " % lv
            ui.check(pre + "正解になる（金の「10」と「正解」は出る）",
                     [ui.ev("$('eq').textContent+'|'+$('sub').textContent"), ui.ev("getComputedStyle($('eq')).color"), ui.ev("hitLv")],
                     ["10|正解", "rgb(227, 193, 111)", lv])
            ui.check(pre + "数字は動かず、1 コマも光らない。演算子も光らない。動いているアニメーションは 0",
                     [moved, not_none, lit, sum(1 for f in after for x in f[2] if x), max(f[3] for f in after)], [[], 0, 0, 0, 0])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors("動きを減らす設定: JS エラー 0")
