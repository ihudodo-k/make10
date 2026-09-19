# -*- coding: utf-8 -*-
"""クリアの確定と挑戦モードの報酬（GAME-SPEC 3-1・7-2・7-3）。

5.4 で chalDone / seen / cleared を advance()（つぎへ）から win()（正解した瞬間）へ
移した。「正解して『つぎへ』を押さずホームへ戻る」でも、記録・報酬・クリア数が
そろって確定することを見る。二重計上しないことも同じだけ大事。
"""

NAME = "クリアの確定と挑戦の報酬"

SNAP = ("({chalDone:G.chalDone.length,chalShown:G.chalShown.length,chalRem:G.chalRem,"
        "hint:G.hintStock,seen:G.seen.length,cleared:G.cleared,statsN:G.stats.n,"
        "hist:G.hist.length,ci:G.ci})")


def run(ui):
    ui.open({"ci": 0, "cleared": 120, "hintStock": 10, "chalRem": 0})

    # ── 挑戦: 正解 → 「つぎへ」を押さずホーム ───────────────
    ui.ev("start('chal')")
    ui.check("挑戦の 1 問目を解く", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("1問目: クリア数が増える", s["chalDone"], 1)
    ui.check("1問目: seen が増える", s["seen"], 1)
    ui.check("1問目: cleared が増える", s["cleared"], 121)
    ui.check("1問目: 記録も残る", [s["statsN"], s["hist"]], [1, 1])
    ui.check("1問目: 報酬の端数は 1", s["chalRem"], 1)
    ui.check("1問目: まだヒントは増えない", s["hint"], 10)
    ui.ev("go('home')")
    s = ui.ev(SNAP)
    ui.check("つぎへを押さずホームへ戻ってもクリア数は戻らない", s["chalDone"], 1)
    ui.check("ホームの挑戦の表示も増える", ui.text("m-chal-v"),
             "1 / %d" % ui.ev("CHAL.length"))

    ui.ev("start('chal')")
    ui.check("挑戦の 2 問目を解く", ui.solve(1.4), "10|正解")
    s = ui.ev(SNAP)
    ui.check("2問目: クリア数 2", s["chalDone"], 2)
    ui.check("2問目: 2 問ごとの報酬でヒントが 1 個増える", s["hint"], 11)
    ui.check("2問目: 端数は 0 に戻る", s["chalRem"], 0)
    ui.check("2問目: 知らせるトースト",
             ui.ev("__TOASTS.filter(t=>t.indexOf('ヒントを 1 個')>=0).length"), 1)
    ui.ev("go('home')")

    # ── 「つぎへ」を押しても二重に数えない ────────────────
    ui.ev("start('chal')")
    ui.check("挑戦の 3 問目を解く", ui.solve(), "10|正解")
    before = ui.ev(SNAP)
    ui.check("3問目: 正解した時点でクリア数 3", before["chalDone"], 3)
    ui.click("wnext")
    after = ui.ev(SNAP)
    ui.check("つぎへ: クリア数は二重に増えない",
             after["chalDone"] - before["chalDone"], 0)
    ui.check("つぎへ: seen も二重に増えない", after["seen"] - before["seen"], 0)
    ui.check("つぎへ: cleared も二重に増えない",
             after["cleared"] - before["cleared"], 0)
    ui.check("つぎへ: 報酬の端数も動かない",
             after["chalRem"] - before["chalRem"], 0)   # 3 問目ぶんの 1 が残ったまま
    ui.check("つぎへ: 端数は 3 問目の 1 のまま", after["chalRem"], 1)
    ui.check("つぎへ: 次の問題が出る", after["chalShown"] - before["chalShown"], 1)
    ui.check("つぎへ: 2 回目以降は無視する",
             (ui.click("wnext"), ui.ev("G.chalDone.length"))[1], 3)

    # ── 本編: 位置（ci）は「つぎへ」でだけ進む ──────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    ui.ev("start('course')")
    ui.check("本編の 1 問目を解く", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("本編: 正解でクリア数が増える", s["cleared"], 1)
    ui.check("本編: seen も増える", s["seen"], 1)
    ui.check("本編: 位置はまだ進まない", s["ci"], 0)
    ui.ev("go('home')")
    ui.check("ホームの累計も増える", ui.text("ctot"), "累計 1 問")
    ui.check("ホームの位置は 0 のまま", ui.text("cnum"), "0 / 1000 問")
    ui.ev("start('course')")
    ui.check("同じ問題が出る", ui.ev("codeOf(cur)===codeOf(COURSE[0])"), True)
    ui.check("解き直す", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("解き直しても二重に数えない", [s["cleared"], s["seen"]], [1, 1])
    ui.click("wnext")
    s = ui.ev(SNAP)
    ui.check("つぎへで位置が進む", s["ci"], 1)
    ui.check("つぎへではクリア数は増えない", s["cleared"], 1)

    # ── フリー: 報酬は増えない ────────────────────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10, "chalRem": 1})
    ui.ev("start('free')")
    ui.check("フリーの問題を解く", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("フリー: クリア数が増える", s["cleared"], 1)
    ui.check("フリー: 挑戦のクリア数には入らない", s["chalDone"], 0)
    ui.check("フリー: 報酬は増えない（端数も動かない）",
             [s["hint"], s["chalRem"]], [10, 1])

    # ── 共有: 5.4 でクリアとして数えるようになった ────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    code = ui.ev("codeOf(CHAL[7])")
    ui.ev("$('codein').value=%r" % code)
    ui.click("codego")
    ui.check("共有コードで開く", ui.ev("SCR"), "play")
    ui.check("共有の問題を解く", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("共有: クリアとして数える（5.4 の変更）", s["cleared"], 1)
    ui.check("共有: 挑戦のクリア数には入らない", s["chalDone"], 0)

    # ── 挑戦モードの解放（CHAL_AT=100）──────────────────────
    ui.open({"ci": 0, "cleared": 99, "hintStock": 10})
    ui.check("解放条件は 100 問", ui.ev("CHAL_AT"), 100)
    ui.check("99 問ではロック", ui.text("m-chal-v"), "あと 1 問")
    ui.ev("start('free')")
    ui.check("あと 1 問を解く", ui.solve(), "10|正解")
    ui.ev("go('home')")
    ui.check("つぎへを押さなくても解放される", ui.text("m-chal-v"),
             "0 / %d" % ui.ev("CHAL.length"))
    ui.check("ロックの class が外れる",
             ui.ev("$('m-chal').classList.contains('lock')"), False)
    ui.click("m-chal")
    ui.check("挑戦モードに入れる", ui.ev("SCR"), "play")
    ui.check("挑戦の問題が出ている", ui.ev("cur.d>=17"), True)
    ui.check_no_errors("一連の流れで JS エラー 0")
