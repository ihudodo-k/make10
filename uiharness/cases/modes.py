# -*- coding: utf-8 -*-
"""3 モードの出題と件数（GAME-SPEC 5-3・7）。"""

NAME = "3 モードの出題と件数"


def run(ui):
    ui.open({"ci": 0, "cleared": 120, "hintStock": 50})
    # ── 件数 ──────────────────────────────────────────────
    # 件数そのものは DATA-SPEC 8-B の値を固定で見る（BLOB が意図せず変わったら赤くする）。
    # 画面の「N / 全問」は下で CHAL.length / COURSE.length から組む
    ui.check("COURSE の件数", ui.ev("COURSE.length"), 1000)
    ui.check("CHAL の件数", ui.ev("CHAL.length"), 1450)
    ui.check("FREE の件数", ui.ev("FREE.length"), 15342)
    ui.check("合計", ui.ev("COURSE.length+FREE.length+CHAL.length"), 17792)
    ui.check("コードの索引も同じ数", ui.ev("INDEX.size"), 17792)
    ui.check("CHAL は全部 d>=17", ui.ev("CHAL.every(p=>p.d>=17)"), True)
    ui.check("COURSE・FREE は全部 d<=16",
             ui.ev("COURSE.concat(FREE).every(p=>p.d<=16)"), True)
    nchal = ui.ev("CHAL.length")
    # ── 本編 ──────────────────────────────────────────────
    ui.ev("start('course')")
    ui.check("本編の問題番号", ui.text("pmode"), "本編 1/1000")
    ui.check("本編の 1 問目は COURSE[0]",
             ui.ev("codeOf(cur)===codeOf(COURSE[0])"), True)
    ui.check("コード欄が埋まっている", ui.ev("$('pcode').textContent.length>0"), True)
    ui.check("問題番号が実際に見えている", ui.visible("pmode"), True)
    ui.check("本編はスクロールしない", ui.scrolls(), False)
    # ── フリー ────────────────────────────────────────────
    ui.ev("go('home'); start('free')")
    ui.check("フリーは問題番号を出さない", ui.text("pmode"), "")
    ui.check("フリーの問題は BLOB にある", ui.ev("!!byCode(codeOf(cur))"), True)
    # ── 挑戦 ──────────────────────────────────────────────
    ui.ev("go('home'); start('chal')")
    ui.check("挑戦の問題番号", ui.text("pmode"), "挑戦 1/%d" % nchal)
    ui.check("挑戦の問題は d>=17", ui.ev("cur.d>=17"), True)
    # 出題済みは二度と出ない（4.5 の chalShown）。40 回連続で確かめる
    ui.ev("""
      window.__dup=(function(){
        const seen=new Set([codeOf(cur)]); let dup=0;
        for(let i=0;i<40;i++){
          const n=nextOf('chal'); if(!n)break;
          loadPuzzle(n);
          const c=codeOf(cur); if(seen.has(c))dup++; seen.add(c);
        }
        return {dup,size:seen.size};
      })()""")
    ui.check("挑戦を 40 問続けて出しても重複しない", ui.ev("__dup.dup"), 0)
    ui.check("41 問が出題済みに積まれる", ui.ev("G.chalShown.length"), 41)
    ui.check("残りは 全問 − 出題済み",
             ui.ev("CHAL.length-G.chalShown.length"), nchal - 41)
    ui.check("挑戦の問題番号は出題数で進む", ui.text("pmode"), "挑戦 41/%d" % nchal)
    ui.check_no_errors("3 モードを回しても JS エラー 0")
