# -*- coding: utf-8 -*-
"""起動と 5 画面の巡回。左上＝戻る／右上＝設定の出し分け（GAME-SPEC 5-0）も見る。"""

import time

NAME = "起動と画面の巡回"


def run(ui):
    ui.open()                                   # 保存データ無しで起動
    ui.check_no_errors("起動で JS エラーが出ない")
    ui.check("ホームで始まる", ui.ev("SCR"), "home")
    ui.check("本編の件数がホームに出る", ui.text("cnum"), "0 / 1000 問")
    ui.check("進捗 0%", ui.text("cpct"), "0.0")
    ui.check("ホームに NaN / undefined が出ない",
             ui.ev("/NaN|undefined/.test($('home').textContent)"), False)
    # ── 左上・右上の出し分け ───────────────────────────────
    ui.check("ホーム: 左上の戻るは出ない", ui.visible("navback"), False)
    ui.check("ホーム: 右上の三本線が出る", ui.visible("gear"), True)
    ui.click("gear")
    ui.check("設定が開く", ui.ev("SCR"), "settings")
    ui.check("設定: 左上に戻るが出る", ui.visible("navback"), True)
    ui.check("設定: 右上は空", ui.visible("gear"), False)
    ui.check("バージョン表示", ui.text("appver"),
             "バージョン " + ui.ev("APP_VERSION") + "（試作）")
    # ── 設定 → 遊び方 → 戻る → 統計 → 戻る → 戻る ─────────
    ui.ev("go('help')")
    ui.check("遊び方が開く", ui.ev("SCR"), "help")
    ui.check("遊び方: 左上に戻るが出る", ui.visible("navback"), True)
    ui.click("navback")
    ui.check("遊び方から戻ると設定", ui.ev("SCR"), "settings")
    ui.ev("go('stats')")
    ui.check("統計が開く", ui.ev("SCR"), "stats")
    ui.check("統計に NaN が出ない",
             ui.ev("/NaN/.test($('stats').textContent)"), False)
    ui.check("履歴が空なら案内が出る",
             ui.ev("$('stathist').textContent.indexOf('まだありません')>=0"), True)
    ui.click("navback")
    ui.check("統計から戻ると設定", ui.ev("SCR"), "settings")
    ui.click("navback")
    ui.check("設定から戻るとホーム", ui.ev("SCR"), "home")
    # ── 問題画面のナビ ────────────────────────────────────
    ui.ev("start('course')")
    ui.check("本編が始まる", ui.ev("SCR"), "play")
    ui.check("問題画面: 左上の戻るは出ない", ui.visible("navback"), False)
    ui.check("問題画面: 右上の三本線（#gear）は出ない", ui.visible("gear"), False)
    ui.check("問題画面: ヘッダの #back が出る", ui.visible("back"), True)
    ui.check("問題画面: ヘッダの #menu が出る", ui.visible("menu"), True)
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    # 6.5: 何も置いていないときの案内文「演算子を式の中へ」は出さない（#eq も #sub も空）
    ui.check("問題画面: 読み出し行は空（案内文を出さない）",
             [ui.text("eq"), ui.text("sub")], ["", ""])
    ui.check("問題画面: 「演算子を式の中へ」がどこにも見えない",
             ui.ev("$('play').innerText.includes('演算子を式の中へ')"), False)
    ui.check("トレイの見出しは今のまま", ui.text("trayhead"), "つまんで式の中へ")
    ui.ev("G.easy=true; render()")
    ui.check("途中の値を表示する設定でも #sub に案内文を出さない", ui.text("sub"), "")
    ui.ev("G.easy=false; render()")
    # 設定へ出入りしても問題が保たれる（3.1 の回帰）
    code = ui.ev("codeOf(cur)")
    ui.click("menu")
    ui.check("問題画面から設定へ", ui.ev("SCR"), "settings")
    ui.click("navback")
    ui.check("設定から戻ると問題画面", ui.ev("SCR"), "play")
    ui.check("問題が変わっていない", ui.ev("codeOf(cur)"), code)
    ui.check("問題画面はスクロールしない（戻った後）", ui.scrolls(), False)
    ui.click("back")
    ui.check("#back でホームへ", ui.ev("SCR"), "home")
    ui.check_no_errors("巡回のあとも JS エラー 0")
    home_total(ui)


# ホームの主役の数字のかたまり（7.4。7.3 までは本編カード）と各行の位置・大きさ
# （累計点数を消してもレイアウトが崩れない）
HOME_RECTS = ("(()=>{const r=q=>document.querySelector(q).getBoundingClientRect(),"
              "f=v=>Math.round(v*10)/10,c=r('#ctot');"
              "return ['#home .hero','#cnum','#m-course','#m-chal','#m-free'].map(q=>{const b=r(q);"
              "return [b.left,b.top,b.width,b.height].map(f).join()}).concat([[c.top,c.height].map(f).join()])"
              ".join('|')})()")


def home_total(ui):
    """ホームの累計（6.6）: 累計点数は出さない。クリア数は残す。
    点数の記録（G.best）は保存データに残る（あとで表示を戻せるように）"""
    ui.open({"ci": 0, "cleared": 0})
    off = ui.ev(HOME_RECTS)
    code = ui.ev("codeOf(COURSE[0])")
    ui.open({"ci": 0, "cleared": 5, "scoreOn": True, "best": {code: 1234}})
    ui.check("ホームの累計はクリア数だけ（点数表示オンでも）", ui.text("ctot"), "累計 5 問")
    ui.check("ホームに累計点数が出ない",
             ui.ev(r"/\d[\d,]* 点/.test($('home').innerText)"), False)
    ui.check("累計は 1 行のまま・主役の数字のかたまりとモードの行の位置と大きさが点数表示オフと同じ",
             ui.ev(HOME_RECTS), off)
    ui.check("ホームはスクロールしない（横）",
             ui.ev("$('home').scrollWidth<=$('home').clientWidth"), True)
    ui.check("点数の記録は残っている（G.best）", ui.ev("G.best[%r]" % code), 1234)
    ui.check("累計点数の計算も残っている（totalScore）", ui.ev("totalScore()"), 1234)
    # 解くと点数は今までどおり記録され、保存データにも入る
    ui.ev("start('course'); loadPuzzle(COURSE[1])")
    ui.solve()
    code2 = ui.ev("codeOf(cur)")
    ui.ev("go('home')")
    ui.check("解いた問題の点数も記録される", ui.ev("G.best[%r]>0" % code2), True)
    ui.check("保存データ（localStorage）に点数が残っている",
             ui.ev("(()=>{const b=JSON.parse(localStorage.getItem(%r)).best;"
                   "return [b[%r],b[%r]>0]})()" % ("make10.progress.v4", code, code2)),
             [1234, True])
    ui.check("解いたあともホームの累計はクリア数だけ", ui.text("ctot"), "累計 6 問")
    ui.check_no_errors("ホームの累計で JS エラー 0")
    stats_scores(ui)


# 統計画面: [上の 6 項目の名前, 6 項目の高さ, 履歴の各行の高さ, 履歴の右端の文字]
# 上の 6 項目は 7.4 で「名前 …… 値」の行 .kv から、2 列 × 3 段の .stat（大きい数字＋小さい名前）になった
STATS_ROWS = ("(()=>{const f=v=>Math.round(v*10)/10,"
              "kv=[...$('statlist').querySelectorAll('.stat')],h=[...$('stathist').querySelectorAll('.toggle')];"
              "return [kv.map(e=>e.querySelector('.sk').textContent),kv.map(e=>f(e.getBoundingClientRect().height)),"
              "h.map(e=>f(e.getBoundingClientRect().height)),h.map(e=>e.children.length>1?e.lastElementChild.textContent:'')]})()")


def stats_scores(ui):
    """統計画面（6.6。GAME-SPEC 9-2）: 星・累計スコア・履歴の「N 点」を出さない
    （点数を出すのは点数表示オンの正解カードだけ）。
    点数と星の記録（best / hist の p・st）は保存データに残る"""
    code = ui.ev("codeOf(COURSE[0])")
    code2 = ui.ev("codeOf(COURSE[1])")
    hist = [{"c": code, "d": 3, "s": 12, "m": "course", "p": 75, "st": 3},
            {"c": code2, "d": 4, "s": 40, "m": "course", "p": 60, "st": 1}]
    base = {"ci": 2, "cleared": 2, "best": {code: 75, code2: 60}, "hist": hist,
            "stats": {"n": 2, "sec": 52, "best": 12, "band": {"3-8": 2}}}
    ui.open(dict(base, scoreOn=False))
    ui.ev("go('stats')")
    off = ui.ev(STATS_ROWS)
    ui.open(dict(base, scoreOn=True))
    ui.ev("go('stats')")
    on = ui.ev(STATS_ROWS)
    ui.check("統計: 一覧に「累計スコア」の行が無い（点数表示オンでも）",
             "累計スコア" in on[0] or "累計スコア" in ui.ev("$('stats').innerText"), False)
    ui.check("統計: 上の項目は点数表示オフと同じ 6 つ", [on[0], len(on[0])], [off[0], 6])
    ui.check("統計: 上の 6 項目の高さが点数表示オフと同じ", on[1], off[1])
    ui.check("統計: 画面のどこにも星（★☆）が無い", ui.ev("/[★☆]/.test($('stats').innerText)"), False)
    ui.check("統計: 履歴の右端に何も出さない（子は左の 1 つだけ）", on[3], ["", ""])
    ui.check("統計: 履歴のどこにも点数（「N 点」）が出ない",
             ui.ev(r"/\d+ 点/.test($('stathist').innerText)"), False)
    ui.check("統計: 履歴の左の並び（番号・難易度・秒）は今までどおり",
             ui.ev("[...$('stathist').querySelectorAll('.toggle')].map(e=>e.textContent)"),
             [ui.ev("COURSE[0].id") + "　難易度 3・12秒", ui.ev("COURSE[1].id") + "　難易度 4・40秒"])
    ui.check("統計: 履歴の各行が横にはみ出さない",
             ui.ev("[...$('stathist').querySelectorAll('.toggle')].every(e=>e.scrollWidth<=e.clientWidth)"),
             True)
    ui.check("統計: 履歴の行の高さが点数表示オフと同じ", on[2], off[2])
    ui.check("統計: 横にはみ出さない",
             ui.ev("$('stats').scrollWidth<=$('stats').clientWidth"), True)
    ui.check("統計: 点数・星の記録は G に残っている",
             ui.ev("[G.best[%r],G.hist[0].p,G.hist[0].st,G.hist[1].st,totalScore()]" % code),
             [75, 75, 3, 1, 135])
    # 問題を解いても点数と星は今までどおり記録され、保存データに入る
    ui.ev("start('course'); loadPuzzle(COURSE[2])")
    ui.solve()
    ui.ev("go('stats')")
    ui.check("統計: 解いたあとも星は出ない", ui.ev("/[★☆]/.test($('stats').innerText)"), False)
    ui.check("統計: 保存データ（localStorage）に点数と星が残っている",
             ui.ev("(()=>{const s=JSON.parse(localStorage.getItem(%r)),h=s.hist[0];"
                   "return [s.best[%r],h.p>0,[1,2,3].includes(h.st),s.hist.length]})()"
                   % ("make10.progress.v4", code)),
             [75, True, True, 3])
    ui.check_no_errors("統計画面で JS エラー 0")
    home_layout(ui)
    stats_grid(ui)


# テーマ変数を解決した色
V = ("(n=>{const e=document.createElement('i');e.style.color='var('+n+')';"
     "document.body.appendChild(e);const c=getComputedStyle(e).color;e.remove();return c})")
NONE = "rgba(0, 0, 0, 0)"
# ホームのモード 3 行: [幅, 高さ, 画面の中央か, › が行の右端にあるか, 地, 下の線の色が --edge か, アイコンが無いか]
MODE_ROWS = ("(()=>{const f=v=>Math.round(v*10)/10;return ['m-course','m-free','m-chal'].map(id=>{const e=$(id),"
             "r=e.getBoundingClientRect(),c=getComputedStyle(e),ch=e.querySelector('.chev').getBoundingClientRect();"
             "return [f(r.width),f(r.height),Math.abs((r.left+r.right)/2-innerWidth/2)<0.6,"
             "r.right-ch.right>=0&&r.right-ch.right<=6,c.backgroundColor,c.borderBottomColor===%s('--edge'),"
             "!e.querySelector('.ic,.mi')]})})()" % V)
# はみ出し: [ホームが横にあふれない, 縦にもあふれない（スクロールしない）, 画面の幅を超える要素の数]
HOME_FIT = ("(()=>{const h=$('home');return [h.scrollWidth<=h.clientWidth,h.scrollHeight<=h.clientHeight,"
            "[...h.querySelectorAll('*')].filter(e=>{const r=e.getBoundingClientRect();"
            "return r.width>0&&(r.left<-0.5||r.right>innerWidth+0.5)}).length]})()")


def home_layout(ui):
    """ホームの組み立て（7.4。GAME-SPEC 7 章。Figma「13 余白（改）」の 02b）。
    囲まない・進んだ問題数が主役・モードは細い線で区切った 3 行。大きさは仕様の値を直に書く"""
    N = ui.viewport == "normal"
    hero_px, line_w, row_w, row_h = (104, 180, 264, 64) if N else (80, 150, 228, 52)
    ui.open({"ci": 137, "cleared": 162})
    ui.check("ホーム: 題名は小さく中央（15px）",
             ui.ev("(()=>{const t=document.querySelector('#home .title'),c=getComputedStyle(t),r=document.createRange();"
                   "r.selectNodeContents(t);const b=r.getBoundingClientRect();"
                   "return [c.fontSize,Math.abs((b.left+b.right-15*0.14)/2-innerWidth/2)<1]})()"), ["15px", True])
    ui.check("ホーム: 主役は進んだ問題数（大きい数字）・その下に分母",
             [ui.text("chero"), ui.text("cden"), ui.text("cnum"),
              ui.ev("getComputedStyle($('chero')).fontSize"),
              ui.ev("$('cden').getBoundingClientRect().top>=$('chero').getBoundingClientRect().bottom-1")],
             ["137", " / 1000 問", "137 / 1000 問", "%dpx" % hero_px, True])
    ui.check("ホーム: いちばん大きい字は主役の数字（数字が主役）",
             ui.ev("(()=>{let m=0,id='';for(const e of $('home').querySelectorAll('*')){if(!e.offsetWidth||e.children.length&&e.id!=='chero')continue;"
                   "const f=parseFloat(getComputedStyle(e).fontSize);if(f>m){m=f;id=e.id}}return id})()"), "chero")
    time.sleep(0.6)                          # 線の幅の遷移（.bar i の width .4s）が終わるのを待つ
    ui.check("ホーム: 進捗は細い線（幅と高さ）・画面の中央・進んだぶんだけ金",
             ui.ev("(()=>{const b=document.querySelector('.hero .bar').getBoundingClientRect(),i=$('cbar').getBoundingClientRect();"
                   "return [Math.round(b.width),Math.round(b.height),Math.abs((b.left+b.right)/2-innerWidth/2)<0.6,"
                   "Math.round(i.width/b.width*1000)/10,getComputedStyle($('cbar')).backgroundColor===%s('--gold')]})()" % V),
             [line_w, 2, True, 13.7, True])
    ui.check("ホーム: その下に「本編 N%　累計 N 問」", ui.ev("$('cpct').parentElement.textContent"), "本編 13.7%　累計 162 問")
    ui.check("ホーム: カード・アイコンは無い（鍵・星・トロフィーの定義も消した）",
             ui.ev("[!!document.querySelector('#home .card'),!!document.querySelector('#home .mi,#home .ic'),"
                   "typeof ICON_LOCK,typeof ICON_STAR,typeof ICON_TROPHY]"),
             [False, False, "undefined", "undefined", "undefined"])
    row = [row_w, row_h, True, True, NONE, True, True]
    ui.check("ホーム: モード 3 行は同じ幅と高さ・中央・右端に ›・面なし・下に細い線・アイコンなし",
             ui.ev(MODE_ROWS), [row, row, row])
    ui.check("ホーム: 3 行の上にも線が 1 本（行の幅と同じ）・行は上から本編・フリープレイ・挑戦",
             ui.ev("(()=>{const m=document.querySelector('.modes'),c=getComputedStyle(m);"
                   "return [c.borderTopWidth,c.borderTopColor===%s('--edge'),Math.round(m.getBoundingClientRect().width),"
                   "[...m.querySelectorAll('.mt')].map(e=>e.textContent)]})()" % V),
             ["1px", True, row_w, ["本編", "フリープレイ", "挑戦"]])
    ui.check("ホーム: 挑戦の値は名前の下の小さい字（副次色）・ほかの行には値を出さない",
             ui.ev("(()=>{const v=$('m-chal-v'),t=$('m-chal').querySelector('.mt'),c=getComputedStyle(v);"
                   "return [v.textContent,v.getBoundingClientRect().top>=t.getBoundingClientRect().bottom-1,c.fontSize,"
                   "c.color===%s('--dim'),document.querySelectorAll('#m-course .mv,#m-free .mv').length]})()" % V),
             ["0 / %d" % ui.ev("CHAL.length"), True, "11.5px", True, 0])
    ui.check("ホーム: 共有コードの欄は下線だけ・「ひらく」は文字だけ（面と枠なし）",
             ui.ev("(()=>{const i=getComputedStyle($('codein')),b=getComputedStyle($('codego')),s=getComputedStyle(document.querySelector('.share'));"
                   "return [i.backgroundColor,i.borderTopWidth,i.borderBottomWidth,b.backgroundColor,b.borderTopWidth,"
                   "s.borderBottomWidth,s.borderBottomColor===%s('--edge'),$('codego').textContent]})()" % V),
             [NONE, "0px", "0px", NONE, "0px", "1px", True, "ひらく"])
    ui.check("ホーム: はみ出さない（横・縦）・画面の幅を超える要素が無い", ui.ev(HOME_FIT), [True, True, 0])
    # ロック中（クリア 100 問未満）: 薄くせず、無効の色
    ui.open({"ci": 0, "cleared": 0})
    ui.check("ホーム（0 問）: 主役は 0・金の線は出さない",
             [ui.text("chero"), ui.text("cnum"), ui.ev("$('cbar').getBoundingClientRect().width")], ["0", "0 / 1000 問", 0])
    ui.check("ホーム: ロック中の挑戦は薄くしない（不透明度 1）・名前と › は無効の色・値は副次色",
             ui.ev("(()=>{const e=$('m-chal'),t=getComputedStyle(e.querySelector('.mt')),c=getComputedStyle(e.querySelector('.chev')),"
                   "v=getComputedStyle($('m-chal-v'));return [e.classList.contains('lock'),getComputedStyle(e).opacity,"
                   "t.color===%s('--slate'),c.color===%s('--slate'),$('m-chal-v').textContent,v.color===%s('--dim')]})()" % (V, V, V)),
             [True, "1", True, True, "あと 100 問", True])
    ui.check("ホーム: ロック中でも行の大きさ・位置は同じ形", ui.ev(MODE_ROWS), [row, row, row])
    ui.click("m-chal")
    ui.check("ホーム: ロック中の挑戦は押しても始まらない", ui.ev("SCR"), "home")
    ui.check("ホーム（0 問）: はみ出さない", ui.ev(HOME_FIT), [True, True, 0])
    # 全部解いた後（4 桁の 1000・挑戦も全問クリア）
    ui.open({"ci": 1000, "cleared": 1040})
    ui.ev("G.chalDone=CHAL.map(codeOf);G.chalShown=G.chalDone.slice();renderHome()")
    time.sleep(0.6)
    ui.check("ホーム（全部解いた後）: 主役は 1000・線は端まで金・挑戦は「全問クリア」",
             [ui.text("chero"), ui.text("cnum"), ui.text("cpct"),
              ui.ev("Math.round($('cbar').getBoundingClientRect().width)"), ui.text("m-chal-v"),
              ui.ev("$('m-chal').classList.contains('lock')")],
             ["1000", "1000 / 1000 問", "100.0", line_w, "全問クリア", False])
    ui.check("ホーム（全部解いた後）: 4 桁でも数字が 1 行で画面に収まる・はみ出さない",
             [ui.ev("(()=>{const r=document.createRange();r.selectNodeContents($('chero'));const b=r.getBoundingClientRect();"
                    "return b.left>=12&&b.right<=innerWidth-12&&b.height<%d})()" % (hero_px * 1.5)), ui.ev(HOME_FIT)],
             [True, [True, True, 0]])
    ui.check("ホーム（全部解いた後）: 行の形は同じ", ui.ev(MODE_ROWS), [row, row, row])
    ui.click("m-course")
    ui.check("ホーム: 本編の行を押すと問題画面へ", ui.ev("SCR"), "play")
    ui.check_no_errors("ホームの組み立てで JS エラー 0")


# 統計の上の 6 項目: [名前, 数字, 単位] と位置 [左, 上]
STAT_ITEMS = ("(()=>{const f=v=>Math.round(v*10)/10;return [...$('statlist').querySelectorAll('.stat')].map(e=>{"
              "const b=e.querySelector('.sv b'),n=e.querySelector('.sv .none'),u=e.querySelector('.sv .su'),r=e.getBoundingClientRect();"
              "return [e.querySelector('.sk').textContent,b?b.textContent:(n?n.textContent:null),u?u.textContent:'',f(r.left),f(r.top)]})})()")


def stats_grid(ui):
    """統計の上の 6 項目（7.4。GAME-SPEC 9-2）。2 列 × 3 段の「大きい数字＋小さい名前」。
    記録が無いときは数字の場所に「—」を副次色で出す（文言は足さない）"""
    N = ui.viewport == "normal"
    num_px, pitch = (26, 76) if N else (22, 66)
    code = ui.ev("codeOf(COURSE[0])")
    ui.open({"ci": 137, "cleared": 162, "hintStock": 87, "seen": [code],
             "stats": {"n": 162, "sec": 6480, "best": 9, "band": {"3-8": 61, "9-13": 78, "14-16": 15, "17+": 8}}})
    ui.ev("go('stats')")
    it = ui.ev(STAT_ITEMS)
    chal = "0 / %d" % ui.ev("CHAL.length")
    ui.check("統計: 上の 6 項目の名前・数字・単位",
             [x[:3] for x in it],
             [["解いた問題（ユニーク）", "1", "問"], ["本編の進み", "137 / 1000", "問"],
              ["平均でかかった時間", "40", "秒"], ["いちばん速かった", "9", "秒"],
              ["挑戦モードの進み", chal, "問"], ["ヒントの残り", "87", "回"]])
    ui.check("統計: 2 列 × 3 段（左の列・右の列の左端がそれぞれ揃い、段の間隔が一定）",
             [it[0][3] == it[2][3] == it[4][3], it[1][3] == it[3][3] == it[5][3], it[1][3] > it[0][3],
              it[0][4] == it[1][4], it[2][4] == it[3][4], it[4][4] == it[5][4],
              round(it[2][4] - it[0][4], 1), round(it[4][4] - it[2][4], 1)],
             [True, True, True, True, True, True, pitch, pitch])
    ui.check("統計: 数字は大きく・単位は小さい副次色・名前は小さい副次色で数字の下",
             ui.ev("(()=>{const e=$('statlist').querySelector('.stat'),b=e.querySelector('.sv b'),u=e.querySelector('.su'),k=e.querySelector('.sk'),"
                   "cb=getComputedStyle(b),cu=getComputedStyle(u),ck=getComputedStyle(k);"
                   "return [cb.fontSize,cb.color===%s('--paper'),cu.fontSize,cu.color===%s('--dim'),ck.fontSize,ck.color===%s('--dim'),"
                   "k.getBoundingClientRect().top>=b.getBoundingClientRect().bottom-1]})()" % (V, V, V)),
             ["%dpx" % num_px, True, "12px", True, "11.5px", True, True])
    ui.check("統計: 左の列の左端は下の節の行の文字と揃う・面と枠は見えない・節の見出しは 12px",
             ui.ev("(()=>{const r=document.createRange();r.selectNodeContents($('statlist').querySelector('.sv b'));"
                   "const a=r.getBoundingClientRect().left;r.selectNodeContents(document.querySelector('#statbars .row span'));"
                   "const g=getComputedStyle($('statlist'));"
                   "return [Math.abs(a-r.getBoundingClientRect().left)<0.6,g.backgroundColor,g.borderTopColor,"
                   "getComputedStyle(document.querySelector('#stats h3')).fontSize]})()"), [True, NONE, NONE, "12px"])
    FIT = ("(()=>{const s=$('stats'),cells=[...$('statlist').querySelectorAll('.stat')];"
           "return [s.scrollWidth<=s.clientWidth,cells.every(e=>e.scrollWidth<=e.clientWidth),"
           "cells.every(e=>{const sv=e.querySelector('.sv').getBoundingClientRect(),c=e.getBoundingClientRect();"
           "const last=e.querySelector('.sv').lastElementChild.getBoundingClientRect();return last.right<=c.right+0.5&&sv.height<%d}),"
           "cells.every(e=>e.querySelector('.sk').getBoundingClientRect().height<20)]})()" % (num_px * 2))
    ui.check("統計: はみ出し・折り返しが無い（画面・各項目・数字と単位・名前）", ui.ev(FIT), [True, True, True, True])
    # いちばん長い値（本編 1000 / 1000・挑戦 全問・ヒント 4 桁）でも収まる
    ui.ev("G.ci=1000;G.chalDone=CHAL.map(codeOf);G.hintStock=9999;G.seen=[...INDEX.values()].map(codeOf);renderStats()")
    ui.check("統計: いちばん長い値（1000 / 1000・挑戦の全問・5 桁の問題数）でもはみ出し・折り返しが無い",
             [ui.ev(FIT), ui.ev("$('statlist').querySelector('.sv b').textContent.length")], [[True, True, True, True], 5])
    # 記録が無いとき
    ui.open({"ci": 0, "cleared": 0})
    ui.ev("go('stats')")
    it0 = ui.ev(STAT_ITEMS)
    ui.check("統計（記録なし）: 時間の 2 項目は数字の場所に「—」・単位を出さない・ほかは 0 と初期値",
             [x[:3] for x in it0],
             [["解いた問題（ユニーク）", "0", "問"], ["本編の進み", "0 / 1000", "問"],
              ["平均でかかった時間", "—", ""], ["いちばん速かった", "—", ""],
              ["挑戦モードの進み", chal, "問"], ["ヒントの残り", str(ui.ev("HINT_START")), "回"]])
    ui.check("統計（記録なし）: 「—」は副次色・数字と同じ大きさ・位置は記録があるときと同じ",
             [ui.ev("(()=>{const n=[...$('statlist').querySelectorAll('.none')];return [n.length,"
                    "n.every(e=>getComputedStyle(e).color===%s('--dim')),getComputedStyle(n[0]).fontSize]})()" % V),
              [x[3:] for x in it0] == [x[3:] for x in it]],
             [[2, True, "%dpx" % num_px], True])
    ui.check("統計（記録なし）: 文言は足していない（上の節の文字は名前・数字・単位・「—」だけ）",
             ui.ev(r"$('statlist').innerText.replace(/\s+/g,'')"),
             "0問解いた問題（ユニーク）0/1000問本編の進み—平均でかかった時間—いちばん速かった%s問挑戦モードの進み%s回ヒントの残り"
             % (chal.replace(" ", ""), ui.ev("HINT_START")))
    ui.check_no_errors("統計の 2 列で JS エラー 0")
