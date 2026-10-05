# -*- coding: utf-8 -*-
"""ヒント 3 の全解答（6.9 でデータ、7.1 で見せ方を「2 段」に決定。GAME-SPEC 5-4・DATA-SPEC 8-B）。

1. **一覧の突き合わせ（全 puzzle）** ―― ゲームの `solsOf()` が出す一覧を、
   ハーネス側で BLOB だけから独立に組んだ一覧（uiharness/sols.py。ゲームのコードも
   make10.py も使わない）と、本数・順・式の文字列まで突き合わせる。
   あわせて、全部の式がゲームの計算（parse → ev）で 10 になること、
   式の文字列を読み直した木が形から直接組んだ木と同じこと（CLAUDE.md
   「表示文字列は元の木に戻せること」）を見る。make10.db は読まない
2. **段階 3 の箱（2 段）と送り方** ―― 1 段目は 6.8 と同じ「3 / 3 解答例：式」、2 段目に「k/N」
   （1 本だけでも 1/1）。式をタップで次へ・ループ・位置の記憶・振動・消費しないこと・
   k が変わっても文字が動かないこと・箱の高さ 58px
3. **長い式の縮小** ―― 収まらない行だけ式の文字を縮める。率が式の幅からの計算どおりで、
   縮めても 1 行に収まり、高さと位置が変わらないこと
4. **やめたものの後始末** ―― 6.9 のア・イ（hintSolMode）と 7.0 のシート・切り替え（hintSolView）が
   残っていないこと、古い保存データに残っていても動くこと

判定は箱に見えている文字で取る。
"""
import json
import math
import time

from uiharness import sols

NAME = "ヒント 3 の全解答"

VIB = ("window.__VIB=[];Object.defineProperty(navigator,'vibrate',"
       "{value:x=>{__VIB.push(x);return true},configurable:true})")

# 箱に見えているもの: [段階表示, 本文（1 段目）, 2 段目]。閉じていれば ["閉", "", ""]。2 段目は段階 3 だけ
SEEN = ("(function(){const b=$('hintbox');if(!b.classList.contains('show'))return ['閉','',''];"
        "const s=b.querySelector('.hsub');"
        "return [b.querySelector('.hlv').textContent,b.querySelector('.hbin').textContent,"
        "s?s.textContent:'']})()")

# 式の文字ごとの幅（1em = 1000。Zen Kaku Gothic New・700）。ゲームの HINT_GLYPH とは別に持つ
# ―― 縮小率の期待値を、ゲームの関数を呼ばずに組むため（値は 7.1 の実測）
GLYPH = {"0": 502, "1": 409, "2": 449, "3": 482, "4": 494, "5": 470, "6": 496, "7": 416,
         "8": 508, "9": 479, "+": 851, "−": 851, "×": 851, "÷": 851, "^": 542, "!": 293,
         "(": 378, ")": 378, " ": 280}


def width(expr):
    """式（画面の書き方）の幅。12.5px のときの px"""
    return sum(GLYPH[c] for c in expr) * 12.5 / 1000


# 式・トレイ・.foot の上端
PLACE = ("(function(){const R=e=>e.getBoundingClientRect(),r=x=>Math.round(x*100)/100;"
         "return [r(R($('exprwrap')).top),r(R(document.querySelector('.tray')).top),"
         "r(R(document.querySelector('.foot')).top)]})()")

# 式の文字列をゲームのトークンに直して parse() に渡す（盤面と同じ読み方）。
# 形（後置記法）からは木を直接組む。2 つの木が same() で、値が 10 であること
CHECK_ALL = """
(function(){
  const tok=s=>{const out=[];
    for(const w of s.split(" ")){
      const core=w.replace(/!+$/,""), nf=w.length-core.length;
      if(core==="(")out.push({t:"lp"});
      else if(core===")")out.push({t:"rp"});
      else if(/^[0-9]$/.test(core))out.push({t:"num",v:+core});
      else out.push({t:"op",v:core});
      for(let i=0;i<nf;i++)out.push({t:"fac"});
    }
    return out};
  const tree=(cs,id)=>{const st=[];
    for(const c of cs){
      if(c>="0"&&c<="3")st.push({v:+id[+c]});
      else if(c==="!")st.push({f:st.pop()});
      else{const r=st.pop(),l=st.pop();st.push({o:c,l,r})}
    }
    return st[0]};
  let n=0,notTen=0,notSame=0,noParse=0;const bad=[];
  for(const [id,row] of DB.SOLS){
    for(const k of row){
      n++;
      const cs=DB.SHAPE[k], s=shapeDisplay(cs,id), a=parse(tok(s));
      if(!a){noParse++;if(bad.length<3)bad.push([id,s]);continue}
      const v=ev(a);
      if(!v||v.n!==10n||v.d!==1n){notTen++;if(bad.length<3)bad.push([id,s])}
      if(!same(a,tree(cs,id))){notSame++;if(bad.length<3)bad.push([id,s])}
    }
  }
  return {n,notTen,notSame,noParse,bad};
})()
"""


def seen(ui):
    return ui.ev(SEEN)


def load(ui, pid, rc):
    """指定の問題を問題画面に出す（フリーの出題として読む）"""
    ui.ev("MODE='free';loadPuzzle(INDEX.get(%s));go('play')" % json.dumps(pid + "|" + rc))


def open3(ui):
    """閉じた状態から段階 3 まで開く"""
    for _ in range(3):
        ui.click("hint")


def tap(ui):
    ui.ev("$('hint-sol').click()")
    time.sleep(0.05)


def geom(ui):
    """行の中の位置: [段階表示の左, 段階表示の幅, 本文の枠の左, 本文の枠の幅, ‹ › × の左, 箱の高さ,
    下の段の k の箱の左と幅（2 段のときだけ）]"""
    return ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),"
        "r=x=>Math.round(x*100)/100,hl=b.querySelector('.hlv'),hb=b.querySelector('.hbody'),"
        "k=b.querySelector('.hsub b');"
        "return [r(R(hl).left),r(R(hl).width),r(R(hb).left),r(R(hb).width),"
        "[...b.querySelectorAll('.hbtn')].map(e=>r(R(e).left)),r(R(b).height),"
        "k?[r(R(k).left),r(R(k).width)]:null]})()")


def box(ui):
    """箱の [左, 上, 幅, 高さ]・‹ › × の左・段階表示の左と上"""
    return ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),r=x=>Math.round(x*100)/100;"
        "return [r(R(b).left),r(R(b).top),r(R(b).width),r(R(b).height),"
        "[...b.querySelectorAll('.hbtn')].map(e=>r(R(e).left)),"
        "r(R(b.querySelector('.hlv')).left),r(R(b.querySelector('.hlv')).top)]})()")


def mid(ui):
    """式（code）の上下の中心 − 行の上下の中心。0 に近ければ行の中央にある"""
    return ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),c=R(b.querySelector('code')),"
        "w=R(b.querySelector('.hintrow'));"
        "return Math.round(((c.top+c.bottom)/2-(w.top+w.bottom)/2)*100)/100})()")


def state(ui):
    """消費・減点・保存に関わるもの。全解答を見ても変わらないこと"""
    ui.ev("save()")
    time.sleep(0.2)
    return ui.ev("[G.hintStock,JSON.stringify(G.hints),hintMax,localStorage.getItem(SAVE_KEY)]")


def fits(ui):
    """本文が 1 行に収まっている（横にあふれず、折り返さない）"""
    return ui.ev(
        "(function(){const b=$('hintbox'),hb=b.querySelector('.hbody'),hi=b.querySelector('.hbin');"
        "return hb.scrollWidth<=hb.clientWidth&&hi.getBoundingClientRect().height<=22"
        "&&b.getBoundingClientRect().height===58})()")


def run(ui):
    data = sols.load()
    lists, puzzles = data["lists"], data["puzzles"]

    # ── 1. 一覧の突き合わせ（全 puzzle） ─────────────────────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50})
    ui.check("BLOB の区分を読めている（形の数・4 桁の行の数）",
             ui.ev("[DB.SHAPE.length,DB.SOLS.size]"), [data["shapes"], data["rows"]])
    ui.check("3 区分の件数は今までどおり読めている",
             ui.ev("[COURSE.length,FREE.length,CHAL.length]"),
             [sum(1 for p in puzzles if p[0] == s) for s in ("COURSE", "FREE", "CHAL")])
    order = ui.ev("ALL().map(p=>p.id+'|'+p.rc)")
    ui.check("ゲームの問題の並びがハーネスの読んだ BLOB と同じ",
             order == [p[1] + "|" + p[2] for p in puzzles], True)
    total, bad, first_bad = 0, [], []
    for a in range(0, len(order), 2000):
        got = ui.ev("ALL().slice(%d,%d).map(p=>[solsOf(p),p.sol])" % (a, a + 2000))
        for (_sec, pid, rc, sol), (lst, gsol) in zip(puzzles[a:a + 2000], got):
            total += len(lst)
            if lst != lists[(pid, rc)]:
                bad.append(pid + "|" + rc)
            if not lst or lst[0] != sol or gsol != sol:
                first_bad.append(pid + "|" + rc)
    ui.check("全 %d puzzle: 一覧の本数・順・式が独立に組んだ一覧と一致（違う puzzle）"
             % len(puzzles), bad[:5], [])
    ui.check("全 puzzle: 1 本目が解答例（sol）と一致（違う puzzle）", first_bad[:5], [])
    ui.check("一覧の本数の合計", total, sum(len(v) for v in lists.values()))
    r = ui.ev(CHECK_ALL)
    ui.check("全解答の区分の式を全部ゲームの計算に通した（本数）", r["n"], data["entries"])
    ui.check("読めない式・10 にならない式・木が形と違う式",
             [r["noParse"], r["notTen"], r["notSame"], r["bad"]], [0, 0, 0, []])

    many = ("8842", "N")       # 本編 1 問目。N が 2 桁（9 → 10 で桁が増える）
    one = next((p[1], p[2]) for p in puzzles if len(lists[(p[1], p[2])]) == 1)
    big = max(lists, key=lambda k: len(lists[k]))          # いちばん本数の多い問題
    con = next((p[1], p[2]) for p in puzzles
               if p[2] != "N" and len(lists[(p[1], p[2])]) >= 3)
    L = [sols.pretty(s) for s in lists[many]]
    n = len(L)
    s1 = sols.pretty(lists[one][0])
    ui.check("確認に使う問題: 2 本以上（%s）は 10 本以上・1 本だけ（%s）は 1 本・最多（%s）は 100 本以上"
             % (many[0], one[0], big[0]), [n >= 10, len(lists[one]), len(lists[big]) >= 100],
             [True, 1, True])

    def row(k):                    # k 本目を見ているときに箱に見えるもの
        return ["3 / 3", "解答例：" + L[k - 1], "%d/%d" % (k, n)]

    # ── 2. 段階 3 の箱（2 段）と送り方 ───────────────────────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50})
    ui.ev(VIB)
    btn = ui.ev("DEV_DEFAULT.vibBtn")
    ui.ev("start('course')")
    load(ui, *one)
    place0 = ui.ev(PLACE)
    open3(ui)
    box1 = box(ui)
    mid1 = mid(ui)
    ui.check("1 本だけの問題: 1 段目は 6.8 と同じ「3 / 3 解答例：式」、2 段目は「1/1」",
             seen(ui), ["3 / 3", "解答例：" + s1, "1/1"])
    ui.check("1 本だけの問題: 式は行の中央", abs(mid1) < 1.5, True)
    ui.check("1 本だけの問題の本文はボタンではない",
             ui.ev("[!!$('hint-sol'),$('hintbox').querySelector('.hbody').getAttribute('role')]"),
             [False, None])
    ui.ev("__VIB.length=0")
    ui.ev("$('hintbox').querySelector('.hbin').click();$('hintbox').querySelector('.hbody').click()")
    ui.check("1 本だけの問題は押しても何も起きず、振動もしない",
             [seen(ui), ui.ev("__VIB.splice(0)")], [["3 / 3", "解答例：" + s1, "1/1"], []])
    ui.check("箱の高さは 58px", box1[3], 58)
    ui.check("ヒントを開いても式・トレイ・.foot は動かない", ui.ev(PLACE), place0)
    load(ui, *many)
    ui.click("hint")
    ui.check("段階 1 は今までどおり（2 段目は出さない）",
             [seen(ui)[0], seen(ui)[1].startswith("使う記号："), seen(ui)[2]], ["1 / 3", True, ""])
    ui.click("hint")
    ui.check("段階 2 は 1 本目（解答例）から作る（2 段目は出さない）", seen(ui),
             ["2 / 3", "形：" + ui.ev("pretty(cur.sol).replace(/ [−+×÷^] /g,' ? ')"), ""])
    ui.click("hint")
    ui.check("段階 3: 1 段目は「3 / 3 解答例：式（1 本目）」、2 段目は「1/N」", seen(ui), row(1))
    ui.check("箱の位置・大きさ・‹ 3 / 3 › × の位置が 1 本だけの問題と同じ", box(ui), box1)
    ui.check("式の上下の位置が 1 本だけの問題と同じ（行の中央）", mid(ui), mid1)
    ui.check("ヒントを開いても式・トレイ・.foot は動かない（2 本以上）", ui.ev(PLACE), place0)
    ui.check("2 段目は小さく（11.5px・段階表示と同じ色）、1 段目の下・行の中に収まる", ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),s=b.querySelector('.hsub'),"
        "row=b.querySelector('.hintrow'),cs=getComputedStyle(s);"
        "return [cs.fontSize,cs.color===getComputedStyle(b.querySelector('.hlv')).color,"
        "R(s).top>=R(b.querySelector('.hbin')).bottom-0.01,R(s).bottom<=R(row).bottom+0.01]})()"),
        ["11.5px", True, True, True])
    ui.check("本文はボタン扱い（role・tabindex）",
             ui.ev("[$('hint-sol').getAttribute('role'),$('hint-sol').tabIndex]"), ["button", 0])
    ui.check("押せる印（下線）は付けない",
             ui.ev("getComputedStyle($('hintbox').querySelector('code')).textDecorationLine"), "none")
    before = state(ui)
    ui.check("3 段階ぶん消費している（2 問で 6）", ui.ev("G.hintStock"), 44)
    g0 = geom(ui)
    ui.ev("__VIB.length=0")
    shown, gs, fit = [], [], []
    for _ in range(n):             # n 回タップ: 2 本目 … n 本目 → 1 本目
        tap(ui)
        shown.append(seen(ui))
        gs.append(geom(ui))
        fit.append(fits(ui))
    ui.check("タップで次の解答へ。最後の次は 1 本目に戻る", shown,
             [row(k) for k in list(range(2, n + 1)) + [1]])
    ui.check("タップ 1 回につき振動 1 回（ボタンと同じ長さ）", ui.ev("__VIB.splice(0)"), [btn] * n)
    ui.check("k が変わっても段階表示・本文の枠・‹ › ×・2 段目の k の箱が動かない（9 → 10 を含む）",
             [g for g in gs if g != g0], [])
    ui.check("どの解答も 1 行に収まり、箱の高さは 58px のまま", fit, [True] * n)
    ui.check("送っても残数・到達段階・減点の段階・保存データが変わらない", state(ui), before)
    ui.check("保存データに解答の位置のキーは無い",
             sorted(k for k in json.loads(before[3]) if "hint" in k.lower()), ["hintStock", "hints"])
    # 位置の記憶
    tap(ui)
    tap(ui)
    ui.check("3 本目まで送った", seen(ui), row(3))
    ui.click("hint-prev")
    ui.check("‹ で 2 へ（段階 2 は 1 本目のまま・2 段目は無い）", [seen(ui)[0], seen(ui)[2]], ["2 / 3", ""])
    ui.click("hint-next")
    ui.check("› で 3 に戻ると見ていた 3 本目のまま", seen(ui), row(3))
    ui.click("hint-close")
    ui.click("hint")
    ui.check("閉じて開き直しても 3 本目のまま", seen(ui), row(3))
    ui.click("menu")
    ui.click("navback")
    ui.check("設定へ行って戻っても 3 本目のまま", seen(ui), row(3))
    ui.ev("$('hint-sol').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    ui.check("Enter でも次へ", seen(ui), row(4))
    stock = ui.ev("G.hintStock")
    load(ui, *one)
    load(ui, *many)
    ui.click("hint")
    ui.check("問題を切り替えて戻ると 1 本目（到達済みの 3 が無料で出る）",
             [seen(ui), ui.ev("G.hintStock")], [row(1), stock])
    tap(ui)
    ui.ev("save()")
    time.sleep(0.3)
    save = ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY))")
    ui.open(save)
    ui.ev(VIB)
    ui.ev("start('course')")
    load(ui, *many)
    ui.click("hint")
    ui.check("再起動すると 1 本目（位置は保存しない）", seen(ui), row(1))
    ui.ev("G.vib=false;__VIB.length=0")
    tap(ui)
    ui.check("振動オフではタップしても振動しない", [seen(ui), ui.ev("__VIB.splice(0)")], [row(2), []])
    ui.ev("G.vib=true")
    load(ui, *con)
    open3(ui)
    got = [seen(ui)]
    for _ in range(len(lists[con]) - 1):
        tap(ui)
        got.append(seen(ui))
    ui.check("制約付きの問題（%s %s）: 送って見える式と k/N が一覧どおり" % con,
             got, [["3 / 3", "解答例：" + sols.pretty(s), "%d/%d" % (i + 1, len(lists[con]))]
                   for i, s in enumerate(lists[con])])
    ui.check("制約付きの問題: 禁止の記号を含む式は 1 本も出ない",
             [s for s in lists[con] if sols.BAN[con[1]] in s], [])
    load(ui, *big)
    open3(ui)
    g0 = geom(ui)
    ui.ev("for(let i=0;i<99;i++)$('hint-sol').click()")
    ui.check("最多の問題（%s・3 桁）: 100 本目でも 2 段目の k の箱と枠が動かない・1 行に収まる" % big[0],
             [seen(ui)[2], geom(ui) == g0, fits(ui)], ["100/%d" % len(lists[big]), True, True])

    # ── 3. 長い式の縮小（収まらない行だけ、式の文字を縮める。率は算術で決まる） ───────
    longp = max(lists, key=lambda k: max(width(sols.pretty(s)) for s in lists[k]))
    LL = [sols.pretty(s) for s in lists[longp]]
    # 最後の 6 は縮めるときに式の左右に残す余白 HINT_TEXT.slack（7.2 で 0.5 → 6。仕様の値を直に書く）
    SLACK = 6
    avail = ui.ev("Math.min(innerWidth,430)") - 24 - 6 - 3 * 32 - 4 * 2 - 23.83 - 50 - SLACK
    want = [min(100.0, math.floor(max(0.5, avail / width(s)) * 1000) / 10) for s in LL]
    load(ui, *longp)
    open3(ui)
    base = None
    got, okfit, same, gaps = [], [], [], []
    for i in range(len(LL)):
        r = ui.ev(
            "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),r=x=>Math.round(x*100)/100,"
            "c=b.querySelector('code'),hi=b.querySelector('.hbin'),s=b.querySelector('.hsub'),"
            "hb=b.querySelector('.hbody'),f=parseFloat(getComputedStyle(c).fontSize);"
            "return {pc:Math.round(f/12.5*1000)/10,gap:r(R(hb).width-R(hi).width),fit:hb.scrollWidth<=hb.clientWidth&&R(hi).width<=R(hb).width+0.01,"
            "geo:[r(R(b).height),r(R(hi).top),r(R(hi).height),r(R(s).top),r(R(s).height),"
            "getComputedStyle(hi).fontSize,getComputedStyle(b.querySelector('.hlv')).fontSize,"
            "r(R(b.querySelector('.hlv')).left),[...b.querySelectorAll('.hbtn')].map(e=>r(R(e).left))]}})()")
        got.append(r["pc"])
        okfit.append(r["fit"])
        if r["pc"] < 100:
            gaps.append(r["gap"])
        if base is None:
            base = r["geo"]
        same.append(r["geo"] == base)
        if i < len(LL) - 1:
            tap(ui)
    nshr = sum(1 for w in want if w < 100)
    ui.check("いちばん長い式を持つ問題（%s %s・%d 本）: 縮小率が式の幅からの計算どおり（縮む行 %d）"
             % (longp[0], longp[1], len(LL), nshr), got, want)
    ui.check("縮めた行も縮めない行も 1 行に収まる", okfit, [True] * len(LL))
    ui.check("縮めても箱の高さ・1 段目の高さと縦の位置・2 段目の位置・ラベルと段階表示の大きさが変わらない",
             same, [True] * len(LL))
    ui.check("縮めないのはラベルと段階表示（12.5px / 11.5px のまま）", [base[5], base[6]], ["12.5px", "11.5px"])
    ui.check("式をどの率（50.0〜99.9%）に縮めても 1 段目の高さは 20px のまま", ui.ev(
        "(function(){const b=$('hintbox'),c=b.querySelector('code'),hi=b.querySelector('.hbin'),"
        "keep=c.style.fontSize,bad=[];"
        "for(let k=500;k<1000;k++){c.style.fontSize=(k/10)+'%';"
        "const h=hi.getBoundingClientRect().height;if(Math.abs(h-20)>0.01)bad.push([k/10,h])}"
        "c.style.fontSize=keep;return bad.length})()"), 0)
    if ui.viewport == "compact":
        ui.check("幅 360px では、この問題に縮む行がある（いちばん小さい率は 80.7%）",
                 [nshr > 0, min(got)], [True, 80.7])
        # 率は 0.1% 刻みの切り捨てなので、余白は 6px ちょうどから +0.2px ほどまで（7.1 は 0.5px〜）
        ui.check("縮めた行は、式の左右に合わせて 6px 以上の余白が残る（6.0〜6.3px）",
                 [x for x in gaps if not (SLACK - 0.01 <= x <= SLACK + 0.3)], [])
    else:
        ui.check("幅 430px では、どの行も縮めない", nshr, 0)
    ui.check("ゲームの式の幅の計算が、実物の幅と 0.05px 以内で合う（縮めない行）", ui.ev(
        "(function(){hintSolAt=0;showHint();const c=$('hintbox').querySelector('code');"
        "return Math.abs(hintExprW(c.textContent)-c.getBoundingClientRect().width)<0.05"
        "||c.style.fontSize!==''})()"), True)
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors("JS エラー 0（箱と送り方・縮小）")

    # ── 4. やめたもの（6.9 のア・イ、7.0 のシートと切り替え）の後始末 ───────────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50, "dev": True,
             "devVars": {"dur": 300, "tenScale": 1.8, "hintSolMode": 1, "hintSolView": 0},
             "devSecs": {"hint3": 0, "vib": 0}})
    ui.check("古い保存データ（hintSolMode・hintSolView・節 hint3 入り）でも起動し、そのキーは読まれない",
             ui.ev("['hintSolMode' in G.devVars,'hintSolView' in G.devVars,'hintSolView' in DEV_DEFAULT,"
                   "'hint3' in (G.devSecs||{}),G.devVars.tenScale,G.devSecs.vib]"),
             [False, False, False, False, 1.8, 0])
    ui.check("シートと切り替えの名残が無い（要素・関数・CSS 変数・定数）", ui.ev(
        "[!!$('solsheet'),!!$('dv-hintSolView'),!!$('dv-hintSolMode'),typeof solSheetShow,"
        "!!$('devbody').querySelector('h3[data-sec=hint3]'),"
        "getComputedStyle(document.documentElement).getPropertyValue('--hintCntW'),'cntW' in HINT_ROW]"),
        [False, False, False, "undefined", False, "", False])
    ui.ev("start('course')")
    load(ui, *many)
    open3(ui)
    ui.check("古い保存データでも段階 3 は 2 段（hintSolView=0 のシートにはならない）", seen(ui), row(1))
    tap(ui)
    ui.check("古い保存データでもタップで次へ", seen(ui), row(2))
    ui.ev("G.dev=true;devPanelShow(true)")
    ui.click("dv-reset")
    ui.check("開発者パネルの「既定値に戻す」を押してもヒントはそのまま", seen(ui), row(2))
    ui.ev("devPanelShow(false);save()")
    time.sleep(0.2)
    ui.check("保存し直したデータに hintSolMode・hintSolView は残らない", ui.ev(
        "(function(){const d=JSON.parse(localStorage.getItem(SAVE_KEY)).devVars;"
        "return ['hintSolMode' in d,'hintSolView' in d]})()"), [False, False])
    ui.click("back")
    ui.click("gear")
    ui.click("go-help")
    ui.check("遊び方の「ヒント」に、段階 3 の式を押すとほかの解き方が見られることが書いてある",
             ui.ev("$('help').textContent.indexOf('3段階目の式を押すと、ほかの解き方も見られます。')>=0"), True)
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors()
