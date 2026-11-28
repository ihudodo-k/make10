# -*- coding: utf-8 -*-
"""フリープレイの出題（10.2。GAME-SPEC 7-5）。

- 2 割は FREE 全体・8 割は FREE9 の分け方は 9.9 までと同じ。選んだ組の中で、まだ解いていない問題から出す
  （組の中に無ければ組の全体から）。解いていない = 解いた問題の記録 seen に無い
- 挑戦モードで解いた問題（chalDone）も、両方の組の候補に入る。挑戦で解いただけなら「まだ解いていない」扱いで、
  フリープレイで解くと記録 freeChal に入り「解いた」扱いになる。挑戦の進み（chalDone）には数えない
- Math.random を差し替えて、決まった結果にして見る（__R に並べた値を順に返す。尽きたら 0.5）
"""
import json
import time

NAME = "フリープレイの出題"

STUB = "window.__R=[];Math.random=()=>__R.length?__R.shift():0.5;"
# n 回ぶん出題させて、出たコードの一覧を返す。r は組を決める 1 つ目の値（0.1 = 全体・0.5 = FREE9）
DRAW = ("((r,n)=>{const out=[];for(let i=0;i<n;i++){__R=[r,(i+0.5)/n];out.push(codeOf(nextOf('free')))}"
        "return out})(%s,%d)")
BASE = {"ci": 0, "cleared": 120, "hintStock": 50}


def draw(ui, r, n=200):
    return ui.ev(DRAW % (json.dumps(r), n))


def run(ui):
    ui.open(BASE)
    ui.ev(STUB)
    ui.ev("window.__C=p=>codeOf(p);window.__F9=FREE9.map(codeOf);window.__F=FREE.map(codeOf);"
          "window.__CH=CHAL.map(codeOf);0")
    # ── 2 割・8 割の分け方 ─────────────────────────────────
    ui.check("分け方: 1 つ目の値が 0.2 未満なら FREE 全体の組・0.2 以上なら FREE9 の組（何も解いていない端末）",
             # 組の中で選ぶ値は、FREE で難易度 9 未満の最初の問題 k を指す値にする（FREE9 の組なら必ず別の問題になる）
             ui.ev("(()=>{G.seen=[];const k=FREE.findIndex(p=>p.d<9),r2=(k+0.5)/FREE.length,j=Math.floor(r2*FREE9.length),a=[];"
                   "for(const r of [0,0.1999,0.2,0.9999]){__R=[r,r2];a.push(codeOf(nextOf('free')))}"
                   "return [a[0]===__F[k],a[1]===__F[k],a[2]===__F9[j],a[3]===__F9[j],FREE[k].d<9]})()"),
             [True, True, True, True, True])
    ui.check("分け方: 1 回の出題で Math.random を 2 回だけ読む（組を決める 1 回と、組の中で選ぶ 1 回）",
             ui.ev("(()=>{let k=0;const o=Math.random;Math.random=()=>{k++;return 0.5};nextOf('free');Math.random=o;return k})()"), 2)
    ui.check("分け方: FREE9 の組からは難易度 9 以上だけ・全体の組からは 9 未満も出る",
             ui.ev("(()=>{const a=%s,b=%s;const d=c=>byCode(c).d;return [a.every(c=>d(c)>=9),b.some(c=>d(c)<9)]})()"
                   % (DRAW % ("0.5", 300), DRAW % ("0.1", 300))), [True, True])
    # ── 解いていない問題を優先する ─────────────────────────
    ui.ev("G.seen=__F9.slice(0,-3);G.chalDone=[];G.freeChal=[];0")
    got = draw(ui, 0.5)
    ui.check("FREE9 の組: 解いていない 3 問が残っていれば、解いた問題は出さない（200 回）",
             [sorted(set(got)) == sorted(ui.ev("__F9.slice(-3)")), len(set(got))], [True, 3])
    ui.ev("G.seen=__F.filter(c=>c!==__F[0]&&c!==__F[5]);0")
    got = draw(ui, 0.1)
    ui.check("全体の組: 解いていない 2 問が残っていれば、その 2 問だけ出る（200 回）",
             sorted(set(got)), sorted(ui.ev("[__F[0],__F[5]]")))
    ui.ev("G.seen=__F.slice();0")
    a, b = draw(ui, 0.5), draw(ui, 0.1)
    ui.check("組の全部を解いた後は、組の全体から出る（FREE9 の組も全体の組も、端から端まで）",
             [ui.ev("(a=>a.every(c=>__F9.includes(c)))(%s)" % json.dumps(a)),
              ui.ev("__R=[0.5,0];codeOf(nextOf('free'))===__F9[0]"), ui.ev("__R=[0.5,1-1e-9];codeOf(nextOf('free'))===__F9[__F9.length-1]"), len(set(a)) == 200,
              ui.ev("(a=>a.every(c=>__F.includes(c)))(%s)" % json.dumps(b)), ui.ev("__R=[0.1,0];codeOf(nextOf('free'))===__F[0]")],
             [True, True, True, True, True, True])
    # ── 挑戦で解いた問題 ──────────────────────────────────
    # 挑戦で解くと seen にも入る（win()）。それでもフリープレイでは「まだ解いていない」として出る
    ui.ev("G.seen=__F.concat([__CH[0],__CH[7]]);G.chalDone=[__CH[0],__CH[7]];G.chalShown=__CH.slice(0,10);G.freeChal=[];0")
    a, b = draw(ui, 0.5), draw(ui, 0.1)
    ui.check("挑戦で解いた問題が候補に入り、未解決として出る（FREE9 の組・全体の組の両方。ほかは全部解いた端末）",
             [sorted(set(a)), sorted(set(b))], [sorted(ui.ev("[__CH[0],__CH[7]]"))] * 2)
    # 解いていない FREE9 の 50 問を残すと、候補は 50 ＋ 挑戦で解いた 2 問。どの位置も 1 回は引く
    ui.ev("G.seen=__F.filter(c=>!__F9.slice(100,150).includes(c)).concat([__CH[0],__CH[7]]);0")
    a = draw(ui, 0.5, 520) + draw(ui, 0.1, 520)
    ui.check("挑戦で解いていない挑戦の問題は出ない（出題しただけの問題も）・候補は残る 50 問と挑戦で解いた 2 問",
             ui.ev("(a=>{const s=new Set(a);return [__CH.filter(c=>s.has(c)).sort(),s.size,"
                   "a.every(c=>__F9.slice(100,150).includes(c)||c===__CH[0]||c===__CH[7])]})(%s)" % json.dumps(a)),
             [sorted(ui.ev("[__CH[0],__CH[7]]")), 52, True])
    # フリープレイで本当に解く: 記録の数え方は今のまま（累計・解いた問題・挑戦の進みとヒントの報酬は増えない。履歴と難易度別は 1 足す）
    ui.ev("G.seen=__F.concat([__CH[0],__CH[7]]);G.cleared=1200;G.hist=[];G.stats={n:0,sec:0,band:{}};G.chalRem=1;0")
    ui.ev("__R=[0.5,0.1];start('free')")
    ui.check("フリープレイで挑戦の問題が開く", [ui.ev("MODE"), ui.ev("codeOf(cur)===__CH[0]"), ui.ev("cur.d>=17")],
             ["free", True, True])
    before = ui.ev("JSON.stringify([G.seen.length,G.cleared,G.chalDone,G.chalShown,G.chalRem,G.hintStock])")
    ui.check("解く", ui.solve(), ui.solved_text())
    ui.check("フリープレイで解いた挑戦の問題は freeChal に入る",
             ui.ev("JSON.stringify(G.freeChal)==='['+JSON.stringify(__CH[0])+']'"), True)
    ui.check("解いても 解いた問題・累計・挑戦の進み・出題済み・報酬の端数・ヒントの残りは変わらない",
             ui.ev("JSON.stringify([G.seen.length,G.cleared,G.chalDone,G.chalShown,G.chalRem,G.hintStock])"), before)
    ui.check("履歴にはフリープレイの 1 件・難易度別は 17 以上に 1（今までどおり解くたびに数える）",
             ui.ev("[G.hist.length,G.hist[0].m,G.hist[0].c===__CH[0],G.stats.n,G.stats.band['17+']]"),
             [1, "free", True, 1, 1])
    a = draw(ui, 0.5)
    ui.check("フリープレイで解いた後は解いた扱い: 残る 1 問だけが出る", sorted(set(a)), ui.ev("[__CH[7]]"))
    ui.ev("G.freeChal.push(__CH[7]);0")
    a, b = draw(ui, 0.5, 400), draw(ui, 0.1, 400)
    ui.check("全部解いた後は、組の全体（挑戦で解いた問題も含む）から出る",
             [ui.ev("(a=>a.every(c=>__F9.includes(c)||c===__CH[0]||c===__CH[7]))(%s)" % json.dumps(a)),
              ui.ev("__R=[0.5,1-1e-9];codeOf(nextOf('free'))===__CH[7]"),
              ui.ev("(a=>a.every(c=>__F.includes(c)||c===__CH[0]||c===__CH[7]))(%s)" % json.dumps(b))],
             [True, True, True])
    # 「とばす」（#alt）も同じ出題を通る
    ui.ev("G.freeChal=[];__R=[0.5,0.99];$('alt').click();0")
    ui.check("フリープレイの「とばす」も同じ出題（未解決の挑戦の問題が出る）",
             ui.ev("[MODE,codeOf(cur)===__CH[7]]"), ["free", True])
    # 挑戦モードの出題は変えていない: 挑戦で解いた問題は出題済みなので出ない
    ui.ev("__R=[];G.chalShown=__CH.slice(0,10);0")
    ui.check("挑戦モードの出題は今のまま（出題済みは出ない）",
             ui.ev("(()=>{for(let i=0;i<300;i++){const p=nextOf('chal');if(__CH.slice(0,10).includes(codeOf(p)))return false}return true})()"),
             True)
    ui.check_no_errors("フリープレイの出題で JS エラー 0")

    # ── 保存データ ────────────────────────────────────────
    ch = ui.ev("__CH.slice(0,3)")
    old = dict(BASE, seen=["AAAAA"] + ch, chalDone=ch, chalShown=ch, chalRem=1,
               hist=[{"c": ch[0], "d": 18, "s": 40, "m": "chal"}], stats={"n": 1, "sec": 40, "band": {"17+": 1}},
               hints={ch[0]: 2})
    ui.open(old)
    KEYS = "JSON.stringify([G.ci,G.cleared,G.seen,G.chalDone,G.chalShown,G.chalRem,G.hist,G.stats,G.hints,G.hintStock])"
    ui.check("古い保存データ（freeChal が無い）: 空から始まり、エラーにならない",
             [ui.ev("JSON.stringify(G.freeChal)"), ui.errors()], ["[]", []])
    ui.check("古い保存データ: ほかの記録は変わらない",
             ui.ev(KEYS), json.dumps([0, 120, old["seen"], ch, ch, 1, old["hist"], old["stats"], old["hints"], 50],
                                     ensure_ascii=False, separators=(",", ":")))
    ui.ev(STUB)
    ui.ev("__R=[0.5,0];start('free')")
    ui.check("古い保存データ: 挑戦で解いた 3 問はフリープレイでは未解決として出る",
             ui.ev("(()=>{const o=G.seen;G.seen=o.concat(FREE.map(codeOf));const s=new Set();"
                   "for(let i=0;i<60;i++){__R=[0.5,i/60];s.add(codeOf(nextOf('free')))}G.seen=o;"
                   "return [...s].sort()})()"), sorted(ch))
    ui.ev("G.freeChal=[%s];save();0" % json.dumps(ch[1]))
    time.sleep(0.5)
    ui.check("保存: freeChal が書かれる",
             ui.ev("JSON.parse(localStorage.getItem('make10.progress.v4')).freeChal"), [ch[1]])
    saved = ui.ev("localStorage.getItem('make10.progress.v4')")
    ui.open(json.loads(saved))
    ui.check("読み直しても freeChal とほかの記録が同じ",
             [ui.ev("JSON.stringify(G.freeChal)"), ui.ev(KEYS)],
             [json.dumps([ch[1]]), json.dumps([0, 120, old["seen"], ch, ch, 1, old["hist"], old["stats"], old["hints"], 50],
                                              ensure_ascii=False, separators=(",", ":"))])
    ui.open(dict(BASE, freeChal="壊れた値"))
    ui.check("freeChal が配列でない保存データは空から始める", [ui.ev("JSON.stringify(G.freeChal)"), ui.errors()], ["[]", []])
    ui.check_no_errors("保存データの読み書きで JS エラー 0")
