# -*- coding: utf-8 -*-
"""ヒント 3 の全解答（6.9 でデータ、7.0 で見せ方を作り直し。GAME-SPEC 5-4・DATA-SPEC 8-B）。

1. **一覧の突き合わせ（全 puzzle）** ―― ゲームの `solsOf()` が出す一覧を、
   ハーネス側で BLOB だけから独立に組んだ一覧（uiharness/sols.py。ゲームのコードも
   make10.py も使わない）と、本数・順・式の文字列まで突き合わせる。
   あわせて、全部の式がゲームの計算（parse → ev）で 10 になること、
   式の文字列を読み直した木が形から直接組んだ木と同じこと（CLAUDE.md
   「表示文字列は元の木に戻せること」）を見る。make10.db は読まない
2. **見せ方 0＝シート（既定）** ―― 段階 3 の行は 6.8 と同じ「3 / 3 解答例：式」。式をタップすると
   一覧のシートが開く（本数・順・1 本目の印・閉じ方 4 通り・シートの中だけスクロール）
3. **見せ方 1＝2 段** ―― 「3 / 3 式」の下に小さく「解答例 k / N」。式をタップすると次へ
   （ループ・位置の記憶・k が変わっても文字が動かない・箱の高さ 58px）
4. どちらも: 1 本だけの puzzle は押しても何も起きない・振動はボタンと同じ・消費しない・
   開発者パネルの切り替え・6.9 のア・イ（hintSolMode）が残っていないこと

判定は箱とシートに見えている文字で取る。
"""
import json
import time

from uiharness import sols

NAME = "ヒント 3 の全解答"

VIB = ("window.__VIB=[];Object.defineProperty(navigator,'vibrate',"
       "{value:x=>{__VIB.push(x);return true},configurable:true})")

# 箱に見えているもの: [段階表示, 本文, 下の段]。閉じていれば ["閉", "", ""]。下の段は 2 段のときだけ
SEEN = ("(function(){const b=$('hintbox');if(!b.classList.contains('show'))return ['閉','',''];"
        "const s=b.querySelector('.hsub');"
        "return [b.querySelector('.hlv').textContent,b.querySelector('.hbin').textContent,"
        "s?s.textContent:'']})()")

# シートに見えているもの: [開いているか, 見出し, [[番号, 式, 右端の印]…]]
SHEET = ("(function(){const o=!$('solsheet').classList.contains('hide')&&$('solsheet').offsetHeight>0;"
         "return [o,$('soltitle').textContent,[...$('sollist').children].map(r=>"
         "[r.querySelector('.sn').textContent,r.querySelector('code').textContent,"
         "(r.querySelector('.small')||{textContent:''}).textContent])]})()")

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

    # ── 2. 見せ方 0 ＝ シート（既定） ───────────────────────
    tag = "[シート] "
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50})
    ui.ev(VIB)
    btn = ui.ev("DEV_DEFAULT.vibBtn")
    ui.check(tag + "既定の見せ方はシート（0）", ui.ev("(G.devVars||DEV_DEFAULT).hintSolView"), 0)
    ui.ev("start('course')")
    load(ui, *one)
    place0 = ui.ev(PLACE)
    open3(ui)
    box1 = box(ui)
    mid1 = mid(ui)
    ui.check(tag + "1 本だけの問題: 式は行の中央", abs(mid1) < 1.5, True)
    ui.check(tag + "1 本だけの問題は 6.8 と同じ「3 / 3 解答例：式」", seen(ui), ["3 / 3", "解答例：" + s1, ""])
    ui.check(tag + "1 本だけの問題の本文はボタンではなく、押せる印（下線）も無い", ui.ev(
        "[!!$('hint-sol'),$('hintbox').querySelector('.hbody').getAttribute('role'),"
        "getComputedStyle($('hintbox').querySelector('code')).textDecorationLine]"),
        [False, None, "none"])
    ui.ev("__VIB.length=0")
    ui.ev("$('hintbox').querySelector('.hbin').click();$('hintbox').querySelector('.hbody').click()")
    ui.check(tag + "1 本だけの問題は押しても何も起きず、振動もしない",
             [seen(ui), ui.ev(SHEET)[0], ui.ev("__VIB.splice(0)")],
             [["3 / 3", "解答例：" + s1, ""], False, []])
    load(ui, *many)
    ui.click("hint")
    ui.click("hint")
    ui.check(tag + "段階 2 は 1 本目（解答例）から作る", seen(ui),
             ["2 / 3", "形：" + ui.ev("pretty(cur.sol).replace(/ [−+×÷^] /g,' ? ')"), ""])
    ui.click("hint")
    ui.check(tag + "段階 3 の行は 6.8 と同じ「3 / 3 解答例：式（1 本目）」", seen(ui),
             ["3 / 3", "解答例：" + L[0], ""])
    ui.check(tag + "本文はボタン扱い（role・tabindex）",
             ui.ev("[$('hint-sol').getAttribute('role'),$('hint-sol').tabIndex]"), ["button", 0])
    ui.check(tag + "押せる印: 式に点線の下線（コード欄と同じ線）", ui.ev(
        "(function(){const c=getComputedStyle($('hintbox').querySelector('code')),"
        "d=getComputedStyle($('pcodev'));"
        "return [c.textDecorationLine,c.textDecorationStyle,"
        "c.textDecorationStyle===d.textDecorationStyle&&c.textDecorationThickness===d.textDecorationThickness"
        "&&c.textUnderlineOffset===d.textUnderlineOffset]})()"), ["underline", "dotted", True])
    ui.check(tag + "箱の位置・大きさ・‹ 3 / 3 › × の位置が 1 本だけの問題と同じ（印は幅を使わない）",
             box(ui), box1)
    ui.check(tag + "箱の高さは 58px・1 行に収まる", [box(ui)[3], fits(ui)], [58, True])
    ui.check(tag + "式の上下の位置が 1 本だけの問題と同じ（行の中央）", mid(ui), mid1)
    ui.check(tag + "ヒントを開いても式・トレイ・.foot は動かない", ui.ev(PLACE), place0)
    before = state(ui)
    ui.check(tag + "3 段階ぶん消費している（2 問で 6）", ui.ev("G.hintStock"), 44)
    ui.ev("__VIB.length=0")
    tap(ui)
    sh = ui.ev(SHEET)
    ui.check(tag + "式をタップするとシートが開く", sh[0], True)
    ui.check(tag + "見出しに本数", sh[1], "解答%d 本" % n)
    ui.check(tag + "一覧は solsOf() の順に全部（番号・式）",
             [[r[0], r[1]] for r in sh[2]], [[str(i + 1), e] for i, e in enumerate(L)])
    ui.check(tag + "1 本目にだけ「解答例」の印", [r[2] for r in sh[2]], ["解答例"] + [""] * (n - 1))
    ui.check(tag + "開くタップで振動 1 回（ボタンと同じ長さ）", ui.ev("__VIB.splice(0)"), [btn])
    ui.check(tag + "シートを開いてもヒントの箱はそのまま", seen(ui), ["3 / 3", "解答例：" + L[0], ""])
    ui.check(tag + "シートを開いても式・トレイ・.foot は動かない", ui.ev(PLACE), place0)
    ui.check(tag + "行はリスト画面の様式（高さ 48px 以上・padding 14px・面は .group・1 行に収まる）", ui.ev(
        "(function(){const rows=[...$('sollist').children],c=getComputedStyle(rows[0]);"
        "return [rows.every(r=>r.getBoundingClientRect().height>=48&&r.scrollWidth<=r.clientWidth"
        "&&r.querySelector('code').getBoundingClientRect().height<=24),c.paddingLeft,"
        "$('sollist').classList.contains('group'),getComputedStyle($('soltitle')).fontSize,"
        "getComputedStyle($('soltitle')).fontWeight]})()"), [True, "14px", True, "17px", "700"])
    ui.check(tag + "シートは画面の中に収まり、広告バナーに重ならない", ui.ev(
        "(function(){const p=document.querySelector('.solpanel').getBoundingClientRect(),"
        "b=$('banner').getBoundingClientRect();"
        "return [p.top>=0,p.bottom<=b.top+0.5,p.left>=0,p.right<=innerWidth]})()"),
        [True, True, True, True])
    ui.check(tag + "開いても消費も減点も無く、保存データも変わらない", state(ui), before)
    # 閉じ方
    ui.ev("__VIB.length=0")
    ui.ev("$('sollist').children[1].click();$('soltitle').click()")
    ui.check(tag + "シートの中を押しても閉じず、振動もしない",
             [ui.ev(SHEET)[0], ui.ev("__VIB.splice(0)")], [True, []])
    ui.click("solclose")
    ui.check(tag + "× で閉じる（ボタンなので振動 1 回）。ヒントの箱はそのまま",
             [ui.ev(SHEET)[0], ui.ev("__VIB.splice(0)"), seen(ui)],
             [False, [btn], ["3 / 3", "解答例：" + L[0], ""]])
    tap(ui)
    ui.ev("__VIB.length=0")
    ui.ev("$('solsheet').click()")
    ui.check(tag + "シートの外側のタップで閉じる（ボタンではないので振動しない）。箱はそのまま",
             [ui.ev(SHEET)[0], ui.ev("__VIB.splice(0)"), seen(ui)],
             [False, [], ["3 / 3", "解答例：" + L[0], ""]])
    tap(ui)
    ui.ev("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    ui.check(tag + "Esc で閉じる", ui.ev(SHEET)[0], False)
    tap(ui)
    ui.ev("goBack()")
    ui.check(tag + "戻るは、まずシートを閉じる（問題画面のまま）",
             [ui.ev(SHEET)[0], ui.ev("SCR"), seen(ui)[0]], [False, "play", "3 / 3"])
    ui.ev("$('hint-sol').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    ui.check(tag + "Enter でも開く", ui.ev(SHEET)[0], True)
    ui.click("solclose")
    tap(ui)
    ui.click("solclose")
    tap(ui)
    ui.check(tag + "何度開いても一覧は同じ（行が増えない）", len(ui.ev(SHEET)[2]), n)
    ui.ev("go('settings')")
    ui.check(tag + "画面を切り替えるとシートは閉じる", ui.ev(SHEET)[0], False)
    ui.ev("goBack()")
    tap(ui)
    load(ui, *one)
    ui.check(tag + "問題を切り替えるとシートは閉じる", ui.ev(SHEET)[0], False)
    ui.check(tag + "ここまで残数は変わらない", ui.ev("G.hintStock"), 44)
    # いちばん本数の多い問題: シートの中だけがスクロールする
    load(ui, *big)
    open3(ui)
    tap(ui)
    sh = ui.ev(SHEET)
    ui.check(tag + "最多の問題（%s・%d 本）: 見出しと行の数" % (big[0], len(lists[big])),
             [sh[1], len(sh[2])], ["解答%d 本" % len(lists[big]), len(lists[big])])
    ui.check(tag + "最多の問題: 式の並びが一覧どおり",
             [r[1] for r in sh[2]] == [sols.pretty(s) for s in lists[big]], True)
    ui.check(tag + "最多の問題: シートの中だけが縦にスクロールし、問題画面はスクロールしない", ui.ev(
        "(function(){const b=$('solbody');b.scrollTop=99999;const end=b.scrollTop;"
        "const last=$('sollist').lastElementChild.getBoundingClientRect(),"
        "p=b.getBoundingClientRect();b.scrollTop=0;"
        "return [b.scrollHeight>b.clientHeight,end>0,last.bottom<=p.bottom+0.5,"
        "document.documentElement.scrollHeight>innerHeight+1,scrollY]})()"),
        [True, True, True, False, 0])
    ui.check(tag + "最多の問題: 番号の列は 3 桁ぶんの同じ幅で、式の左端がそろう", ui.ev(
        "(function(){const xs=[...$('sollist').querySelectorAll('code')].map(e=>"
        "Math.round(e.getBoundingClientRect().left*100)/100);return new Set(xs).size})()"), 1)
    ui.click("solclose")
    # 制約付き・振動オフ
    load(ui, *con)
    open3(ui)
    tap(ui)
    ui.check(tag + "制約付きの問題（%s %s）: シートの式が一覧どおり" % con,
             [r[1] for r in ui.ev(SHEET)[2]], [sols.pretty(s) for s in lists[con]])
    ui.check(tag + "制約付きの問題: 禁止の記号を含む式は 1 本も出ない",
             [s for s in lists[con] if sols.BAN[con[1]] in s], [])
    ui.click("solclose")
    ui.ev("G.vib=false;__VIB.length=0")
    tap(ui)
    ui.check(tag + "振動オフでは開いても振動しない", [ui.ev(SHEET)[0], ui.ev("__VIB.splice(0)")], [True, []])
    ui.ev("G.vib=true")
    ui.click("solclose")
    ui.check(tag + "問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors(tag + "JS エラー 0")

    # ── 3. 見せ方 1 ＝ 2 段 ────────────────────────────────
    tag = "[2 段] "

    def sub(k):
        return "解答例 %d / %d" % (k, n)

    ui.open({"ci": 0, "cleared": 120, "hintStock": 50, "devVars": {"hintSolView": 1}})
    ui.ev(VIB)
    ui.ev("start('course')")
    load(ui, *one)
    open3(ui)
    ui.check(tag + "1 本だけの問題: 「3 / 3 式」の下に「解答例」だけ", seen(ui), ["3 / 3", s1, "解答例"])
    ui.check(tag + "1 本だけの問題の箱の位置・大きさ・‹ 3 / 3 › × の位置がシートのときと同じ", box(ui), box1)
    ui.check(tag + "1 本だけの問題の本文はボタンではない",
             ui.ev("[!!$('hint-sol'),$('hintbox').querySelector('.hbody').getAttribute('role')]"),
             [False, None])
    ui.ev("__VIB.length=0")
    ui.ev("$('hintbox').querySelector('.hbin').click();$('hintbox').querySelector('.hbody').click()")
    ui.check(tag + "1 本だけの問題は押しても何も起きず、振動もしない",
             [seen(ui), ui.ev("__VIB.splice(0)")], [["3 / 3", s1, "解答例"], []])
    load(ui, *many)
    ui.click("hint")
    ui.click("hint")
    ui.check(tag + "段階 2 は 1 本目（解答例）から作る（下の段は無い）", seen(ui),
             ["2 / 3", "形：" + ui.ev("pretty(cur.sol).replace(/ [−+×÷^] /g,' ? ')"), ""])
    ui.click("hint")
    ui.check(tag + "段階 3: 「3 / 3 式」の下に「解答例 1 / N」。1 段目に「解答例：」は出さない",
             seen(ui), ["3 / 3", L[0], sub(1)])
    ui.check(tag + "箱の位置・大きさ・‹ 3 / 3 › × の位置が 6.8 の形（1 本だけの問題）と同じ", box(ui), box1)
    ui.check(tag + "式の上下の位置が 6.8 の形と同じ（行の中央）", mid(ui), mid1)
    ui.check(tag + "ヒントを開いても式・トレイ・.foot は動かない", ui.ev(PLACE), place0)
    ui.check(tag + "下の段は小さく（11.5px・--dim）、式の下・行の中に収まり、式は行の中央のまま", ui.ev(
        "(function(){const b=$('hintbox'),R=e=>e.getBoundingClientRect(),s=b.querySelector('.hsub'),"
        "c=b.querySelector('code'),row=b.querySelector('.hintrow'),cs=getComputedStyle(s);"
        "return [cs.fontSize,cs.color===getComputedStyle(b.querySelector('.hlv')).color,"
        "R(s).top>=R(b.querySelector('.hbin')).bottom-0.01,R(s).bottom<=R(row).bottom+0.01,"
        "Math.abs((R(c).top+R(c).bottom)/2-(R(row).top+R(row).bottom)/2)<1.5]})()"),
        ["11.5px", True, True, True, True])
    ui.check(tag + "本文はボタン扱い（role・tabindex）",
             ui.ev("[$('hint-sol').getAttribute('role'),$('hint-sol').tabIndex]"), ["button", 0])
    before = state(ui)
    g0 = geom(ui)
    ui.ev("__VIB.length=0")
    shown, gs, fit = [], [], []
    for _ in range(n):             # n 回タップ: 2 本目 … n 本目 → 1 本目
        tap(ui)
        shown.append(seen(ui))
        gs.append(geom(ui))
        fit.append(fits(ui))
    ui.check(tag + "タップで次の解答へ。最後の次は 1 本目に戻る", shown,
             [["3 / 3", L[k - 1], sub(k)] for k in list(range(2, n + 1)) + [1]])
    ui.check(tag + "タップ 1 回につき振動 1 回（ボタンと同じ長さ）", ui.ev("__VIB.splice(0)"), [btn] * n)
    ui.check(tag + "k が変わっても段階表示・本文の枠・‹ › ×・下の段の k の箱が動かない（9 → 10 を含む）",
             [g for g in gs if g != g0], [])
    ui.check(tag + "どの解答も 1 行に収まり、箱の高さは 58px のまま", fit, [True] * n)
    ui.check(tag + "シートは開かない", ui.ev(SHEET)[0], False)
    ui.check(tag + "送っても残数・到達段階・減点の段階・保存データが変わらない", state(ui), before)
    ui.check(tag + "保存データに解答の位置のキーは無い",
             sorted(k for k in json.loads(before[3]) if "hint" in k.lower()), ["hintStock", "hints"])
    # 位置の記憶
    tap(ui)
    tap(ui)
    ui.check(tag + "3 本目まで送った", seen(ui), ["3 / 3", L[2], sub(3)])
    ui.click("hint-prev")
    ui.check(tag + "‹ で 2 へ（段階 2 は 1 本目のまま）", seen(ui)[0], "2 / 3")
    ui.click("hint-next")
    ui.check(tag + "› で 3 に戻ると見ていた 3 本目のまま", seen(ui), ["3 / 3", L[2], sub(3)])
    ui.click("hint-close")
    ui.click("hint")
    ui.check(tag + "閉じて開き直しても 3 本目のまま", seen(ui), ["3 / 3", L[2], sub(3)])
    ui.click("menu")
    ui.click("navback")
    ui.check(tag + "設定へ行って戻っても 3 本目のまま", seen(ui), ["3 / 3", L[2], sub(3)])
    ui.ev("$('hint-sol').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    ui.check(tag + "Enter でも次へ", seen(ui), ["3 / 3", L[3], sub(4)])
    stock = ui.ev("G.hintStock")
    load(ui, *one)
    load(ui, *many)
    ui.click("hint")
    ui.check(tag + "問題を切り替えて戻ると 1 本目（到達済みの 3 が無料で出る）",
             [seen(ui), ui.ev("G.hintStock")], [["3 / 3", L[0], sub(1)], stock])
    tap(ui)
    ui.ev("save()")
    time.sleep(0.3)
    save = ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY))")
    ui.open(save)
    ui.ev(VIB)
    ui.ev("start('course')")
    load(ui, *many)
    ui.click("hint")
    ui.check(tag + "再起動すると 1 本目（位置は保存しない）", seen(ui), ["3 / 3", L[0], sub(1)])
    ui.check(tag + "再起動しても見せ方の切り替えは残る（devVars）", ui.ev("G.devVars.hintSolView"), 1)
    ui.ev("G.vib=false;__VIB.length=0")
    tap(ui)
    ui.check(tag + "振動オフではタップしても振動しない",
             [seen(ui), ui.ev("__VIB.splice(0)")], [["3 / 3", L[1], sub(2)], []])
    ui.ev("G.vib=true")
    load(ui, *con)
    open3(ui)
    got = [seen(ui)[1]]
    for _ in range(len(lists[con]) - 1):
        tap(ui)
        got.append(seen(ui)[1])
    ui.check(tag + "制約付きの問題（%s %s）: 送って見える式が一覧どおり" % con,
             got, [sols.pretty(s) for s in lists[con]])
    load(ui, *big)
    open3(ui)
    g0 = geom(ui)
    ui.ev("for(let i=0;i<99;i++)$('hint-sol').click()")
    ui.check(tag + "最多の問題（3 桁）: 100 本目でも下の段の k の箱と枠が動かない・1 行に収まる",
             [seen(ui)[2], geom(ui) == g0, fits(ui)],
             ["解答例 100 / %d" % len(lists[big]), True, True])
    ui.check(tag + "問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors(tag + "JS エラー 0")

    # ── 4. 開発者パネルの切り替えと、6.9 のア・イの後始末 ────────────
    # 6.9 の保存データ（ア・イのキー hintSolMode と、節の開閉 hint3 が残っている）
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50, "dev": True,
             "devVars": {"dur": 300, "tenScale": 1.8, "hintSolMode": 1},
             "devSecs": {"hint3": 1}})
    ui.check("6.9 の保存データ（hintSolMode 入り）でも起動し、そのキーは読まれない",
             ui.ev("['hintSolMode' in G.devVars,'hintSolMode' in DEV_DEFAULT,G.devVars.hintSolView,"
                   "G.devVars.tenScale]"), [False, False, 0, 1.8])
    ui.check("6.9 のア・イの名残が無い（ボタン・CSS 変数・定数）", ui.ev(
        "[!!$('dv-hintSolMode'),getComputedStyle(document.documentElement).getPropertyValue('--hintCntW'),"
        "'cntW' in HINT_ROW]"), [False, "", False])
    ui.ev("start('course')")
    load(ui, *many)
    open3(ui)
    ui.check("ア・イの番号（.hlv.cnt）は出ない",
             ui.ev("$('hintbox').querySelector('.hlv').className"), "hlv")
    ui.ev("G.dev=true;devPanelShow(true)")
    ui.check("パネル: 節の名前", ui.ev(
        "$('devbody').querySelector('h3[data-sec=hint3]').textContent.replace(/^[▾▸]/,'')"),
        "ヒント 3 の全解答（仮・実機で決める）")
    ui.check("パネル: 既定はシート", ui.text("dv-hintSolView"), "シート")
    tap(ui)
    ui.check("シートを開いた", ui.ev(SHEET)[0], True)
    ui.click("dv-hintSolView")
    ui.check("パネル: 押すと 2 段になり、開いていたシートは閉じ、ヒントがその場で 2 段に変わる",
             [ui.text("dv-hintSolView"), ui.ev(SHEET)[0], seen(ui)],
             ["2 段", False, ["3 / 3", L[0], sub(1)]])
    time.sleep(0.2)
    ui.check("切り替えは保存される",
             ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY)).devVars.hintSolView"), 1)
    ui.check("保存データに hintSolMode は残らない",
             ui.ev("'hintSolMode' in JSON.parse(localStorage.getItem(SAVE_KEY)).devVars"), False)
    tap(ui)
    ui.click("dv-reset")
    ui.check("「既定値に戻す」でシートに戻り、ヒントも描き直される",
             [ui.text("dv-hintSolView"), seen(ui)], ["シート", ["3 / 3", "解答例：" + L[0], ""]])
    ui.ev("devPanelShow(false)")
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    ui.check_no_errors()
