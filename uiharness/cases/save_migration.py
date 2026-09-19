# -*- coding: utf-8 -*-
"""保存データの移行（5.3）。今の BLOB に無いコードが残っていても詰まないこと。

BLOB を組み替えると、保存データには存在しない問題のコードが残る（5.2 では
2,511 問が消えた）。消えたコードは**その場で作る** ―― 過去の BLOB を持ち込むと
検証が古いデータに縛られるので、INDEX に無い (id,rc) から codeOf() で作る。
"""
import json

NAME = "保存データの移行"

# INDEX に無い (id,rc) からコードを作る。形式は正しいが byCode() は null になる
DEAD_JS = """
(function(){const out=[];
  for(let i=0;i<10000&&out.length<6;i++){
    const id=String(i).padStart(4,'0');
    for(const rc of RCS){ if(!INDEX.has(id+'|'+rc)){ out.push(codeOf({id,rc})); break } }
  }
  return out})()
"""


def run(ui):
    ui.open()
    dead = ui.ev(DEAD_JS)
    live = ui.ev("({c12:codeOf(COURSE[12]),c20:codeOf(COURSE[20]),"
                 "chal0:codeOf(CHAL[0]),chal1:codeOf(CHAL[1])})")
    ui.check("消えたコードを 6 本用意できた", len(dead), 6)
    ui.check("消えたコードは形式としては正しい",
             ui.ev("(%s).every(s=>!!decode(s))" % json.dumps(dead)), True)
    ui.check("消えたコードは byCode() が null",
             ui.ev("(%s).every(s=>byCode(s)===null)" % json.dumps(dead)), True)

    save = {
        "ci": 12, "cleared": 120, "scoreOn": True,
        "stats": {"n": 4, "sec": 300, "best": 20, "band": {"3-8": 2, "17+": 2}},
        "hist": [{"c": dead[0], "d": 20, "s": 33, "m": "chal", "p": 55, "st": 2},
                 {"c": live["c20"], "d": 3, "s": 11, "m": "course", "p": 88, "st": 3},
                 {"c": "ZZZZZ", "d": 9, "s": 40, "m": "free", "p": 40, "st": 1}],
        "best": {dead[0]: 55, dead[1]: 60, live["c20"]: 88},
        "seen": [dead[0], dead[1], live["c20"]],
        "hints": {dead[0]: 3, dead[1]: 2, live["c20"]: 1},
        "hintStock": 50,
        "swap": {"12": dead[2], "13": live["c20"]},
        "chalDone": [dead[3], dead[4], live["chal0"]],
        "chalShown": [dead[3], dead[4], dead[5], live["chal0"], live["chal1"]],
        "chalRem": 1,
        # 5.0 で廃止したキー。読み込んでも G に入らないこと
        "held": [1, 2], "heldC": ["AAAAA"], "heldT": [], "heldF": [],
    }
    raw = json.dumps(save, ensure_ascii=False)
    ui.open(save)
    ui.check_no_errors("古い保存データで起動しても JS エラーが出ない")

    # ── 捨てるもの ────────────────────────────────────────
    ui.check("swap: 消えたコードの位置 12 は捨てる", ui.ev("'12' in G.swap"), False)
    ui.check("swap: 生きているコードの位置 13 は残す",
             ui.ev("G.swap['13']"), live["c20"])
    ui.check("chalDone: 生きている 1 件だけ", ui.ev("G.chalDone"), [live["chal0"]])
    ui.check("chalShown: 生きている 2 件だけ",
             ui.ev("G.chalShown"), [live["chal0"], live["chal1"]])
    # ── 捨てないもの ──────────────────────────────────────
    ui.check("best: 3 件とも残る", ui.ev("Object.keys(G.best).length"), 3)
    ui.check("best: 消えたコードの点数も残る",
             ui.ev("G.best[%s]" % json.dumps(dead[0])), 55)
    ui.check("hints: 消えたコードの到達段階も残る",
             ui.ev("G.hints[%s]" % json.dumps(dead[1])), 2)
    ui.check("seen: 3 件とも残る", ui.ev("G.seen.length"), 3)
    ui.check("hist: 3 件とも残る", ui.ev("G.hist.length"), 3)
    ui.check("ヒント残数は保たれる", ui.ev("G.hintStock"), 50)
    ui.check("chalRem は保たれる", ui.ev("G.chalRem"), 1)
    ui.check("5.0 で廃止した held 系は G に入らない",
             ui.ev("['held','heldC','heldT','heldF'].filter(k=>k in G)"), [])
    ui.check("読み込みでは保存 JSON を書き換えない",
             ui.ev("localStorage.getItem(%s)===%s"
                   % (json.dumps("make10.progress.v4"), json.dumps(raw))), True)
    # ── 画面 ──────────────────────────────────────────────
    ui.check("ホームの本編の件数", ui.text("cnum"), "12 / 1000 問")
    ui.check("ホームの挑戦の件数（捨てた分は数えない）",
             ui.text("m-chal-v"), "1 / %d" % ui.ev("CHAL.length"))
    # ── 消えたコードの位置で詰まない（5.3 の本命）───────────
    ui.ev("start('course')")
    ui.check("本編が始まる", ui.ev("SCR"), "play")
    ui.check("ci=12 では COURSE[12] 自身が出る",
             ui.ev("codeOf(cur)===codeOf(COURSE[12])"), True)
    ui.check("出た問題は遊べる（プレースホルダではない）",
             ui.ev("!!cur.sol&&cur.sol.indexOf('この試作には入っていない')<0"), True)
    ui.check("問題番号が出ている", ui.text("pmode"), "本編 13/1000")
    ui.check("正解の数が 0 でない", ui.ev("cur.n>0"), True)
    ui.ev("G.ci=13; loadPuzzle(nextOf('course'))")
    ui.check("生きている差し替えは効く", ui.ev("codeOf(cur)"), live["c20"])
    ui.ev("go('home'); G.ci=5000; start('course')")
    ui.check("ci が範囲外でも最後の問題で頭打ち",
             ui.ev("codeOf(cur)===codeOf(COURSE[COURSE.length-1])"), True)
    # ── 統計の履歴 ───────────────────────────────────────
    ui.ev("go('home'); go('stats')")
    ui.check("履歴は 3 行とも出る", ui.ev("$('stathist').children.length"), 3)
    ui.check("消えた問題の行も 4 桁で出る（byCodeShown）",
             ui.ev("$('stathist').children[0].textContent.slice(0,4)"),
             ui.ev("decode(%s).id" % json.dumps(dead[0])))
    ui.check("読めないコードの行は ????",
             ui.ev("$('stathist').children[2].textContent.slice(0,4)"), "????")
    ui.ev("$('stathist').children[0].click()")
    ui.check("消えた問題の行を押しても開かない", ui.ev("SCR"), "stats")
    ui.ev("$('stathist').children[1].click()")
    ui.check("生きている行は開く", ui.ev("SCR"), "play")
    ui.check("開いたのは履歴の問題", ui.ev("codeOf(cur)"), live["c20"])
    # ── 共有コード ───────────────────────────────────────
    ui.ev("go('home')")
    ui.ev("$('codein').value=%s" % json.dumps(dead[0]))
    ui.click("codego")
    ui.check("消えたコードの共有入力は弾かれる", ui.ev("SCR"), "home")
    ui.check("弾いたときの案内", ui.ev("$('codein').placeholder"),
             "コードが正しくありません")
    ui.ev("$('codein').value=%s" % json.dumps(live["chal1"]))
    ui.click("codego")
    ui.check("生きているコードの共有入力は通る", ui.ev("SCR"), "play")
    ui.check_no_errors("移行の確認のあとも JS エラー 0")
