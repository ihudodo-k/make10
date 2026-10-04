# -*- coding: utf-8 -*-
"""ヒント 3 で全解答を送る（6.9。GAME-SPEC 5-4・DATA-SPEC 8-B）。

1. **一覧の突き合わせ（全 puzzle）** ―― ゲームの `solsOf()` が出す一覧を、
   ハーネス側で BLOB だけから独立に組んだ一覧（uiharness/sols.py。ゲームのコードも
   make10.py も使わない）と、本数・順・式の文字列まで突き合わせる。
   あわせて、全部の式がゲームの計算（parse → ev）で 10 になること、
   式の文字列を読み直した木が形から直接組んだ木と同じこと（CLAUDE.md
   「表示文字列は元の木に戻せること」）を見る。make10.db は読まない
2. **操作** ―― タップで次へ・最後の次は 1 本目・位置の記憶（‹ › と開閉）・
   問題の切り替えと再起動で 1 本目・1 本だけの puzzle・振動の回数・消費しないこと・
   k が変わっても行が動かないこと。開発者パネルの表示ア（k/N 式）とイ（3 / 3 式）の両方で回す

判定は箱の中に見えている文字（.hlv / .hbin）で取る。
"""
import json
import time

from uiharness import sols

NAME = "ヒント 3 の全解答"

VIB = ("window.__VIB=[];Object.defineProperty(navigator,'vibrate',"
       "{value:x=>{__VIB.push(x);return true},configurable:true})")

# 箱に見えているもの: [段階表示, 本文]。閉じていれば ["閉", ""]
SEEN = ("(function(){const b=$('hintbox');if(!b.classList.contains('show'))return ['閉',''];"
        "return [b.querySelector('.hlv').textContent,b.querySelector('.hbin').textContent]})()")

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
    """行の中の位置: [段階表示の左, 段階表示の幅, 本文の枠の左, 本文の枠の幅, ‹ › × の左, 箱の高さ]"""
    return ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),"
        "r=x=>Math.round(x*100)/100,hl=b.querySelector('.hlv'),hb=b.querySelector('.hbody');"
        "return [r(R(hl).left),r(R(hl).width),r(R(hb).left),r(R(hb).width),"
        "[...b.querySelectorAll('.hbtn')].map(e=>r(R(e).left)),r(R(b).height)]})()")


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

    # ── 2. 操作。表示ア（k/N 式・既定）とイ（3 / 3 式）の両方で ──────
    many = ("8842", "N")       # 本編 1 問目。N が 2 桁（9 → 10 で桁が増える）
    one = next((p[1], p[2]) for p in puzzles if len(lists[(p[1], p[2])]) == 1)
    L = [sols.pretty(s) for s in lists[many]]
    n = len(L)
    ui.check("確認に使う問題: 2 本以上（%s）は 10 本以上・1 本だけ（%s）は 1 本" % (many[0], one[0]),
             [n >= 10, len(lists[one])], [True, 1])
    for mode, label in ((0, "ア"), (1, "イ")):
        tag = "[%s] " % label

        def lv(k):                     # k 本目を見ているときに見える段階表示
            return "%d/%d" % (k, n) if mode == 0 else "3 / 3"

        ui.open({"ci": 0, "cleared": 120, "hintStock": 50,
                 "devVars": {"hintSolMode": mode}})
        ui.ev(VIB)
        ui.ev("start('course')")
        load(ui, *many)
        ui.click("hint")
        ui.click("hint")
        ui.check(tag + "段階 2 は 1 本目（解答例）から作る", seen(ui),
                 ["2 / 3", "形：" + ui.ev("pretty(cur.sol).replace(/ [−+×÷^] /g,' ? ')")])
        ui.click("hint")
        ui.check(tag + "段階 3: 1 本目・「解答例：」は出さない", seen(ui), [lv(1), L[0]])
        ui.check(tag + "k/N の印（.hlv.cnt）は表示アだけ",
                 ui.ev("$('hintbox').querySelector('.hlv').classList.contains('cnt')"), mode == 0)
        ui.check(tag + "本文はボタン扱い（role・tabindex）",
                 ui.ev("[$('hint-sol').getAttribute('role'),$('hint-sol').tabIndex]"), ["button", 0])
        stock = ui.ev("G.hintStock")
        ui.check(tag + "3 段階ぶん消費している", stock, 47)
        ui.ev("save()")
        time.sleep(0.2)
        before = ui.ev("[G.hintStock,JSON.stringify(G.hints),hintMax,localStorage.getItem(SAVE_KEY)]")
        g0 = geom(ui)
        ui.ev("__VIB.length=0")
        shown, gs, fit = [], [], []
        for _ in range(n):             # n 回タップ: 2 本目 … n 本目 → 1 本目
            tap(ui)
            shown.append(seen(ui))
            gs.append(geom(ui))
            fit.append(fits(ui))
        ui.check(tag + "タップで次の解答へ。最後の次は 1 本目に戻る", shown,
                 [[lv(k), L[k - 1]] for k in list(range(2, n + 1)) + [1]])
        ui.check(tag + "タップ 1 回につき振動 1 回（ボタンと同じ長さ）",
                 ui.ev("__VIB.splice(0)"), [ui.ev("DEV_DEFAULT.vibBtn")] * n)
        ui.check(tag + "k が変わっても段階表示・本文の枠・‹ › × が動かない（9 → 10 を含む）",
                 [g for g in gs if g != g0], [])
        ui.check(tag + "どの解答も 1 行に収まり、箱の高さは 58px のまま", fit, [True] * n)
        ui.ev("save()")
        time.sleep(0.2)
        ui.check(tag + "送っても残数・到達段階・減点の段階・保存データが変わらない",
                 ui.ev("[G.hintStock,JSON.stringify(G.hints),hintMax,localStorage.getItem(SAVE_KEY)]"),
                 before)
        ui.check(tag + "保存データに解答の位置のキーは無い",
                 sorted(k for k in json.loads(before[3]) if "hint" in k.lower()),
                 ["hintStock", "hints"])
        # 位置の記憶
        tap(ui)
        tap(ui)
        ui.check(tag + "3 本目まで送った", seen(ui), [lv(3), L[2]])
        ui.click("hint-prev")
        ui.check(tag + "‹ で 2 へ（段階 2 は 1 本目のまま）", seen(ui)[0], "2 / 3")
        ui.click("hint-next")
        ui.check(tag + "› で 3 に戻ると見ていた 3 本目のまま", seen(ui), [lv(3), L[2]])
        ui.click("hint-close")
        ui.click("hint")
        ui.check(tag + "閉じて開き直しても 3 本目のまま", seen(ui), [lv(3), L[2]])
        ui.click("menu")
        ui.click("navback")
        ui.check(tag + "設定へ行って戻っても 3 本目のまま", seen(ui), [lv(3), L[2]])
        ui.ev("$('hint-sol').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
        ui.check(tag + "Enter でも次へ", seen(ui), [lv(4), L[3]])
        ui.check(tag + "残数はここまで変わらない", ui.ev("G.hintStock"), stock)
        # 1 本だけの puzzle
        load(ui, *one)
        open3(ui)
        s1 = sols.pretty(lists[one][0])
        ui.check(tag + "1 本だけの問題は 6.8 と同じ「3 / 3 解答例：式」", seen(ui), ["3 / 3", "解答例：" + s1])
        ui.check(tag + "1 本だけの問題の本文はボタンではない",
                 ui.ev("[!!$('hint-sol'),$('hintbox').querySelector('.hbody').getAttribute('role')]"),
                 [False, None])
        ui.ev("__VIB.length=0")
        ui.ev("$('hintbox').querySelector('.hbin').click();$('hintbox').querySelector('.hbody').click()")
        ui.check(tag + "1 本だけの問題は押しても何も起きず、振動もしない",
                 [seen(ui), ui.ev("__VIB.splice(0)")], [["3 / 3", "解答例：" + s1], []])
        # 問題を切り替えて戻ると 1 本目
        load(ui, *many)
        ui.click("hint")
        ui.check(tag + "問題を切り替えて戻ると 1 本目（到達済みの 3 が無料で出る）",
                 [seen(ui), ui.ev("G.hintStock")], [[lv(1), L[0]], stock - 3])
        tap(ui)
        ui.ev("save()")
        time.sleep(0.3)
        save = ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY))")
        ui.open(save)
        ui.ev(VIB)
        ui.ev("start('course')")
        load(ui, *many)
        ui.click("hint")
        ui.check(tag + "再起動すると 1 本目（位置は保存しない）", seen(ui), [lv(1), L[0]])
        ui.check(tag + "再起動しても表示の切り替えは残る（devVars）",
                 ui.ev("G.devVars.hintSolMode"), mode)
        # 振動オフ
        ui.ev("G.vib=false;__VIB.length=0")
        tap(ui)
        ui.check(tag + "振動オフではタップしても振動しない",
                 [seen(ui), ui.ev("__VIB.splice(0)")], [[lv(2), L[1]], []])
        ui.ev("G.vib=true")
        # 制約付きの問題でも同じ（禁止の記号を含む解は出ない）
        con = next((p[1], p[2]) for p in puzzles
                   if p[2] != "N" and len(lists[(p[1], p[2])]) >= 3)
        load(ui, *con)
        open3(ui)
        got = [seen(ui)[1]]
        for _ in range(len(lists[con]) - 1):
            tap(ui)
            got.append(seen(ui)[1])
        ui.check(tag + "制約付きの問題（%s %s）: 送って見える式が一覧どおり" % con,
                 got, [sols.pretty(s) for s in lists[con]])
        ui.check(tag + "制約付きの問題: 禁止の記号を含む式は 1 本も出ない",
                 [s for s in lists[con] if sols.BAN[con[1]] in s], [])
        ui.check_no_errors(tag + "JS エラー 0")

    # ── 3. 開発者パネルの切り替え ────────────────────────────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50, "dev": True,
             "devVars": {"dur": 300, "tenScale": 1.8}})     # 6.8 までの保存データ（キーが無い）
    ui.check("古い保存データでも切り替えのキーは既定（ア＝0）で補われる",
             ui.ev("[G.devVars.hintSolMode,DEV_DEFAULT.hintSolMode]"), [0, 0])
    ui.ev("start('course')")
    load(ui, *many)
    open3(ui)
    ui.ev("$('hint-sol').click()")
    ui.ev("G.dev=true;devPanelShow(true)")
    ui.check("パネル: 既定はア", ui.text("dv-hintSolMode"), "ア：k/N 式")
    ui.check("ア: 2 本目を表示中", seen(ui), ["2/%d" % n, L[1]])
    ui.check("ア: k は本文と同じ色・太さ 700、/N は段階表示の色・地の文の太さ（色は増やさない）", ui.ev(
        "(function(){const h=$('hintbox').querySelector('.hlv'),b=h.querySelector('b'),"
        "c=$('hintbox').querySelector('code'),cs=getComputedStyle;"
        "return [cs(b).color===cs(c).color,cs(b).fontWeight,cs(h).color===cs(b).color,"
        "cs(h).fontWeight===cs(document.body).fontWeight]})()"),
        [True, "700", False, True])
    ui.click("dv-hintSolMode")
    ui.check("パネル: 押すとイになる", ui.text("dv-hintSolMode"), "イ：3 / 3 式")
    ui.check("開いているヒントがその場でイに変わる（位置はそのまま）", seen(ui), ["3 / 3", L[1]])
    time.sleep(0.2)
    ui.check("切り替えは保存される",
             ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY)).devVars.hintSolMode"), 1)
    ui.click("dv-reset")
    ui.check("「既定値に戻す」でアに戻り、ヒントも描き直される",
             [ui.text("dv-hintSolMode"), seen(ui)], ["ア：k/N 式", ["2/%d" % n, L[1]]])
    ui.ev("devPanelShow(false)")
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors()
