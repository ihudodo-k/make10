# -*- coding: utf-8 -*-
"""「進捗をリセット」（10.3。GAME-SPEC 9 章・9-1）。

10.2 までは、リセットが累計 cleared を 0 に戻すのに、解いた問題 seen を残していた。累計は seen に無い問題を
解いたときだけ増えるので、リセットの後にクラシックを解き直しても累計が 0 のまま増えず、挑戦が解放されなかった。
10.3 から seen も空にする。デイリーの記録（make10.daily.v1）は今までどおり消さない。
"""
import json
import time

NAME = "進捗をリセット"

DAILY = {"v": 1, "days": {"31": {"r": "s", "t": 102, "h": 0, "sh": 0, "e": "( 1 + 1 ) * 5"}}, "cur": None}
STORE = "JSON.parse(localStorage.getItem('make10.daily.v1')||'null')"
SAVED = "JSON.parse(localStorage.getItem('make10.progress.v4')||'null')"
SOLVED_STAT = ("(()=>{const k=[...$('statlist').querySelectorAll('.stat')].find(e=>e.querySelector('.sk').textContent===t('stats.solved'));"
               "return k?k.querySelector('.sv b').textContent:null})()")
# 確認の文が 1 行で、› に重ならない
CONFIRM = ("(()=>{const b=$('reset'),s=b.querySelector('span'),r=document.createRange();r.selectNodeContents(s);"
           "const q=[...r.getClientRects()];return [s.textContent,new Set(q.map(x=>Math.round(x.top))).size,"
           "q[q.length-1].right<=b.querySelector('.chev').getBoundingClientRect().left]})()")


def run(ui):
    ui.open({"ci": 0, "cleared": 0})
    course = ui.ev("COURSE.slice(0,150).map(codeOf)")
    free = ui.ev("FREE.slice(0,40).map(codeOf)")
    ch = ui.ev("CHAL.slice(0,2).map(codeOf)")
    seen = course + free + ch
    prog = {"ci": 150, "cleared": len(seen), "seen": seen, "chalDone": ch, "chalShown": ch, "freeChal": ch[:1],
            "hist": [{"c": course[0], "d": 3, "s": 20, "m": "course"}], "stats": {"n": 1, "sec": 20, "band": {"3-8": 1}},
            "hintStock": 40, "hints": {course[0]: 2}}
    # ── 確認の文 ───────────────────────────────────────────
    for lang, want in [("ja", "もう一度押すと消えます（デイリー以外）"), ("en", "Tap again to erase (except Daily)")]:
        ui.open(prog, lang=lang, daily=DAILY)
        ui.ev("go('settings')")
        ui.click("reset")
        ui.check("確認の文（%s）: デイリー以外が消えると言う・1 行で › に重ならない" % lang, ui.ev(CONFIRM), [want, 1, True])
    # ── リセット ───────────────────────────────────────────
    ui.open(prog, daily=DAILY)
    ui.ev("go('settings')")
    ui.click("reset")
    ui.click("reset")
    time.sleep(0.4)
    ui.check("リセットすると 解いた問題 seen も空になる（画面の上と保存の両方）",
             [ui.ev("[G.ci,G.cleared,G.seen.length,G.chalDone.length,G.freeChal.length,G.hist.length,G.hintStock]"),
              ui.ev("(s=>[s.ci,s.cleared,s.seen.length])(%s)" % SAVED)],
             [[0, 0, 0, 0, 0, 0, 100], [0, 0, 0]])
    ui.check("リセットしても、デイリーの記録は残る", ui.ev(STORE), DAILY)
    ui.ev("go('stats')")
    ui.check("統計の解いた問題は 0 から", ui.ev(SOLVED_STAT), "0")
    # ── 解き直す ───────────────────────────────────────────
    got = []
    for i in range(3):
        ui.ev("go('home');start('course')")
        ui.solve()
        got.append(ui.ev("[codeOf(cur)===%s,G.cleared,G.seen.length]" % json.dumps(course[i])))
        ui.ev("advance()")
    ui.check("リセットの後にクラシックを解くと、累計と解いた問題が 1 ずつ増える（前に解いた 1〜3 問目でも）",
             got, [[True, 1, 1], [True, 2, 2], [True, 3, 3]])
    ui.ev("go('home');go('stats')")
    ui.check("統計の解いた問題は 0 から数え直す", ui.ev(SOLVED_STAT), "3")
    ui.ev("go('home')")
    ui.check("ホームの累計も数え直す", ui.text("ctot"), "累計 3 問")
    # フリープレイ: 前に解いた FREE の問題も「まだ解いていない」として出る（全体の組・選ぶ位置は 0 と末尾近く）
    ui.check("フリープレイは、リセットの前に解いた問題も未解決として出す",
             ui.ev("(()=>{const o=Math.random,out=[];for(const r of [0,%d/FREE.length]){let k=0;Math.random=()=>k++?r:0.1;"
                   "out.push(codeOf(nextOf('free')))}Math.random=o;return out})()" % 5),
             [free[0], free[5]])
    ui.check("挑戦で解いた問題もリセットで消え、フリープレイには出ない",
             ui.ev("(()=>{const o=Math.random;let k=0;Math.random=()=>k++%%2?1-1e-9:0.5;const p=nextOf('free');Math.random=o;"
                   "return %s.includes(codeOf(p))})()" % json.dumps(ch)), False)
    ui.check("解き直した後も、デイリーの記録は残る", ui.ev(STORE), DAILY)
    # 挑戦の解放: 累計が増えるので、100 問解けば解放される（ここでは 96 問を足して 99 問にしてから確かめる）
    ui.ev("G.seen=G.seen.concat(FREE.slice(100,196).map(codeOf));G.cleared+=96;renderHome()")
    ui.check("リセットの後も、99 問ではロック", ui.text("m-chal-v"), "あと 1 問")
    ui.ev("start('course')")
    ui.solve()
    ui.ev("go('home')")
    ui.check("リセットの後に解いて 100 問になると、挑戦が解放される",
             [ui.ev("G.cleared"), ui.ev("$('m-chal').classList.contains('lock')")], [100, False])
    ui.check_no_errors("リセットと解き直しで JS エラー 0")
