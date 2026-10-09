# -*- coding: utf-8 -*-
"""言語（D0.5。DAILY-SPEC 16 章）。

- 辞書: すべてのキーに両方の言語・置き換えの印が同じ・複数形の形・英語の文に全角の空白も日本語も無い・
  使われているキーと辞書のキーの過不足が無い（使われているキーは、ページのソースを読んで数える）
- 言語の決め方: `?lang=`・端末の言語・`<html lang>`・ページの題名
- 日付の形: 日本語は「#23　10月7日（水）」、英語は「#23 · Wed, Oct 7」（端末が en-GB でも並びが変わらない）
- 画面: 両方の言語で、主な状態を巡って、はみ出しと折り返しが無いこと。英語では日本語の文字が出ないこと
- 英語のヒントの文と共有文は、列の全問について、Python の側で別に組んだものと突き合わせる
"""
import datetime
import re
import time

from uiharness import daily_ui as dui

NAME = "言語（日本語と英語）"

TZ = "Asia/Tokyo"
GLYPH = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^", "!": "!"}
JP = re.compile(r"[　-ヿ㐀-鿿＀-￯]")      # かな・漢字・全角の記号と空白
MARK = re.compile(r"\{(\w+)\}")
TAG = re.compile(r"<[a-z]")

# 見えている文字と名前（aria-label / title）を集め、はみ出しと折り返しを見る
AUDIT = r"""(function(){
  const app=document.getElementById('app'), A=app.getBoundingClientRect();
  const vis=e=>{for(let x=e;x&&x.nodeType===1;x=x.parentElement){const s=getComputedStyle(x);
    if(s.display==='none'||s.visibility==='hidden')return false}return e.getClientRects().length>0};
  const out={texts:[],labels:[],over:[],wrap:[]};
  const toast=document.querySelector('#toast.show');
  for(const root of [app,toast].filter(Boolean)){
    const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    for(let n=w.nextNode();n;n=w.nextNode()){
      const s=n.nodeValue.trim(), e=n.parentElement;
      if(!s||!vis(e))continue;
      const r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();
      if(!b.width)continue;
      out.texts.push(s);
      if(e.closest('.btnlabel'))continue;                 // 読み上げ専用（1px に切ってある）
      if(b.left<A.left-0.5||b.right>A.right+0.5)out.over.push('画面の外: '+s);
      const btn=e.closest('button');
      if(btn){const q=btn.getBoundingClientRect();
        if(b.left<q.left-0.5||b.right>q.right+0.5)out.over.push('ボタンの外: '+s)}
    }
    for(const e of root.querySelectorAll('[aria-label],[title]'))
      if(vis(e))out.labels.push(e.getAttribute('aria-label')||e.getAttribute('title'));
  }
  // 中身が箱より広くなっていないこと
  for(const sel of ['#dinfo','#banline','.sub','.hintrow .hbody','.rcol','.rshare','.applink','#gubox .gutext',
                    '#toast.show','#dhelpbody','#dhelpbody p','.stat','#dver','#dtest','.dsheet h2','#nopuzzle'])
    for(const e of document.querySelectorAll(sel))
      if(vis(e)&&e.scrollWidth>e.clientWidth+1)out.over.push('箱より広い: '+sel+' '+e.textContent.trim().slice(0,30));
  // 1 行のはずの所が折り返していないこと（中の文字の上端から下端までが、いちばん大きい字の 1.9 倍以内）
  for(const sel of ['#dinfo','#banline','.sub','#hintbox .hbin','#solbox .hbin','.rcol .rn','.rcol .rv','.rshare',
                    '.applink','#gubox .gutext','#toast.show','.stat .sk','.stat .sv','#dver','#dtest','.dsheet h2',
                    '#dhelpbody code','#nopuzzle'])
    for(const e of document.querySelectorAll(sel)){
      if(!vis(e)||!e.textContent.trim())continue;
      const r=document.createRange();r.selectNodeContents(e);
      const rs=[...r.getClientRects()].filter(x=>x.width>0);if(!rs.length)continue;
      const span=Math.max(...rs.map(x=>x.bottom))-Math.min(...rs.map(x=>x.top));
      const f=Math.max(...[e,...e.querySelectorAll('*')].map(x=>parseFloat(getComputedStyle(x).fontSize)));
      if(span>f*1.9)out.wrap.push(sel+' '+e.textContent.trim().slice(0,30));
    }
  out.scroll=document.documentElement.scrollWidth>innerWidth+1;
  return out})()"""
STUB = r"""(function(clip){
  Object.defineProperty(navigator,"share",{value:undefined,configurable:true});
  Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:function(s){
    return clip?Promise.resolve():Promise.reject(new Error("no clipboard"))}}});
})(%s)"""
BOX = "(function(){const b=document.getElementById('hintbox');return b.classList.contains('show')?b.textContent:null})()"


def kinds(sol):
    out = []
    for c in sol:
        if c in "+-*/^!" and c not in out:
            out.append(c)
    return out


def hint_text_en(sol, n):
    """n 回目のヒントに見える文字（英語。16-4）。ラベル Uses と記号の間は CSS の余白なので、文字としては続く"""
    k = kinds(sol)
    if n == 1:
        return "Uses" + GLYPH[k[0]]
    paren = "with ( )" if "(" in sol else "no ( )"
    head = "Uses%s %s" % (GLYPH[k[0]], GLYPH[k[1]]) if len(k) > 1 else "No other operations"
    return head + " · " + paren


def forms(v):
    """辞書の値の文（複数形の形なら、その全部）"""
    return list(v.values()) if isinstance(v, dict) else [v]


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    iso = lambda n: day(n).isoformat()                              # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def click(el_id, wait=0.25):
        ui.ev("document.getElementById(%r).click()" % el_id)
        time.sleep(wait)

    # ══ 辞書 ══
    ui.open(date=iso(1))
    for name in ("STR_DAILY", "STR_CORE"):
        d = ui.ev("JSON.parse(JSON.stringify(%s))" % name)
        ja, en = d["ja"], d["en"]
        ui.check("%s: 日本語と英語が同じキーを持つ" % name,
                 [sorted(set(ja) - set(en)), sorted(set(en) - set(ja))], [[], []])
        both = [k for k in ja if k in en]
        ui.check("%s: 置き換えの印が、日本語と英語で同じ" % name,
                 [k for k in both if sorted(set(MARK.findall(" ".join(forms(ja[k]))))) !=
                  sorted(set(MARK.findall(" ".join(forms(en[k])))))], [])
        ui.check("%s: 複数形の文は、日本語が other、英語が one と other" % name,
                 [k for k in both if isinstance(ja[k], dict) != isinstance(en[k], dict) or
                  (isinstance(ja[k], dict) and (sorted(ja[k]) != ["other"] or sorted(en[k]) != ["one", "other"]))], [])
        ui.check("%s: 英語の文に、全角の空白も日本語の文字も無い" % name,
                 [k for k in en if any(JP.search(x) for x in forms(en[k]))], [])
        ui.check("%s: _html で終わるキーだけがタグを含む" % name,
                 [k for k in both for x in forms(ja[k]) + forms(en[k]) if bool(TAG.search(x)) != k.endswith("_html")], [])
        if name == "STR_DAILY":
            ui.check("デイリーの辞書のキーは daily. で始まる", [k for k in ja if not k.startswith("daily.")], [])
            # 使われているキーは、ソースを読んで数える（辞書の塊の外に書いてある "daily.…"）
            src = dui.read(dui.DAILY_HTML)
            a = src.index("const STR_DAILY=")
            b = src.index("}};", a)
            used = set(re.findall(r'"(daily\.[a-z0-9_]+)"', src[:a] + src[b:]))
            ui.check("使われているキーが辞書にあり、辞書のキーがすべて使われている",
                     [sorted(used - set(ja)), sorted(set(ja) - used)], [[], []])
            ui.check("英語のラベルにコロンを付けない（ヒント・全解答）",
                     [k for k in ("daily.hint_label_ops", "daily.sols_other") if re.search("[:：]", en[k])], [])
            ui.check("英語の画面の文の区切りは「 · 」（ヒントの 2 つの間・上のバー）",
                     [en["daily.hint_sep"], " · " in en["daily.top_date_html"]], [" · ", True])
            ui.check("英語の共有文の区切りはダッシュ",
                     [en["daily.share_before"], en["daily.share_giveup"], en["daily.share_after"] == ja["daily.share_after"]],
                     ["Make10 #{no} — Can you make 10?", "Make10 #{no} — Gave up", True])
            ui.check("英語のヒントの回数は単位を出さない。日数は day / days",
                     [en["daily.unit_times"], en["daily.unit_day"]],
                     [{"one": "", "other": ""}, {"one": "day", "other": "days"}])

    # ══ 言語の決め方 ══
    state = "[document.documentElement.lang,document.title,dinfo.textContent,dver.textContent.replace(/[0-9.]+$/,'')]"
    ja_want = ["ja", "Make10 デイリー", dui.top_text(3, day(3)), "デイリー "]
    en_want = ["en", "Make10 Daily", dui.top_text(3, day(3), "en"), "Daily "]
    for lang, nav, extra, want, what in [
            ("ja", "en-US", "", ja_want, "?lang=ja は、端末が英語でも日本語"),
            ("en", "ja-JP", "", en_want, "?lang=en は、端末が日本語でも英語"),
            (None, "ja-JP", "", ja_want, "端末が ja-JP なら日本語"),
            (None, "JA", "", ja_want, "端末が JA（大文字）でも日本語"),
            (None, "en-US", "", en_want, "端末が en-US なら英語"),
            (None, "en-GB", "", en_want, "端末が en-GB でも、日付の並びは同じ（Wed, Jan 7）"),
            (None, "fr-FR", "", en_want, "端末がそれ以外（fr-FR）なら英語"),
            (None, "", "", en_want, "端末の言語が空なら英語"),
            (None, "ja-JP", "&lang=xx", ja_want, "?lang= の知らない値は無視する")]:
        ui.open(date=iso(3), lang=lang, nav=nav, extra=extra)
        ui.check("言語の決め方: " + what, ui.ev(state), want)
    ui.open(date=iso(3), lang="en")
    ui.check("言語は保存しない（デイリーの保存データに言語の項目が無い）", ui.ev("'lang' in DATA"), False)

    # ══ 日付の形（7 つの曜日と、月をまたぐ日・列の最後）══
    nos = sorted(set([1, 2, 3, 4, 5, 6, 7, 28, 60, 150, 240, 331, 700, len(rows)]))
    for lang in ("ja", "en"):
        got = []
        for n in nos:
            ui.open(date=iso(n), lang=lang)
            got.append(ui.text("dinfo"))
        ui.check("日付の形（%s）: %s" % (lang, dui.top_text(nos[2], day(nos[2]), lang)),
                 got, [dui.top_text(n, day(n), lang) for n in nos])
    ui.check("確かめた日に、7 つの曜日と 4 つ以上の月が入っている",
             [len({day(n).weekday() for n in nos}), len({day(n).month for n in nos}) >= 4], [7, True])

    # ══ 英語のヒントの文と共有文（全問）══
    ui.open(date=iso(1), lang="en")
    got = ui.ev("(function(){const d=document.createElement('div');return DAILY_DAYS.map(p=>[1,2].map(n=>{"
                "d.innerHTML=hintHtml(p,n);return d.textContent}))})()")
    bad = [(r["no"], g) for r, g in zip(rows, got) if g != [hint_text_en(r["sol"], 1), hint_text_en(r["sol"], 2)]]
    ui.check("英語・全 %d 問: ヒントの文（1 回目・2 回目）が、解答例から組んだ文と同じ" % len(rows), bad[:3], [])
    texts = ui.ev("DAILY_DAYS.map(p=>[shareTextOf(p.no),"
                  "shareTextOf(p.no,{r:'s',t:102,h:2,sh:3},7),shareTextOf(p.no,{r:'g',t:null,h:1,sh:1},0)])")
    bad = []
    for r, t3 in zip(rows, texts):
        want = ["Make10 #%d — Can you make 10?" % r["no"], "Make10 #%d ⏱1:42 💡2 🔥7" % r["no"],
                "Make10 #%d — Gave up" % r["no"]]
        leak = [t for t in t3 if re.search(r"[+\-−×÷*/^!()]", t) or any(s in t for s in r["sols"])
                or r["id"] in t.replace("#%d" % r["no"], "").replace("make 10", "")]
        if t3 != want or leak:
            bad.append((r["no"], t3))
    ui.check("英語・全 %d 問: 共有文 3 種類が決まった文で、答え・4 桁・演算の記号・括弧が入らない" % len(rows), bad[:3], [])

    # ══ 両方の言語で、主な状態を巡る（はみ出し・折り返し。英語では日本語の文字が出ない）══
    con = next(r for r in rows if r["rc"] != "N")                                 # 制約がある日
    two = next(r for r in rows if len(kinds(r["sol"])) >= 2 and "(" in r["sol"] and len(r["sols"]) >= 3)
    nop = next(r for r in rows if len(kinds(r["sol"])) >= 2 and "(" not in r["sol"])
    one = next(r for r in rows if len(kinds(r["sol"])) == 1)
    longest = max(rows, key=lambda r: max(len(s) for s in r["sols"]))        # いちばん長い式を持つ日
    seen = {}

    def audit(lang, name):
        a = ui.ev(AUDIT)
        seen.setdefault(lang, []).append((name, a))
        return a

    def hint_state(lang, row, n, name):
        ui.open(date=iso(row["no"]), lang=lang)
        ui.ev("shareCount=2;" + "useHint();" * n)
        time.sleep(0.15)
        audit(lang, name)
        return ui.ev(BOX)

    for lang in ("ja", "en"):
        ui.open(date=iso(con["no"]), lang=lang)
        audit(lang, "問題画面（制約がある日）")
        ui.ev("put('lp',0);put('+',2);put('+',4);put('+',6);render()")
        audit(lang, "括弧の注意")
        ui.ev("clearAll()")
        click("hint")
        audit(lang, "ヒントをもらう前の知らせ")
        click("hint-close")
        click("dgiveup")
        audit(lang, "ギブアップの確認")
        h1 = hint_state(lang, two, 1, "ヒント 1 回目")
        h2 = hint_state(lang, two, 2, "ヒント 2 回目（括弧を使う）")
        h3 = hint_state(lang, nop, 2, "ヒント 2 回目（括弧を使わない）")
        h4 = hint_state(lang, one, 2, "ヒント 2 回目（演算が 1 種類だけ）")
        if lang == "en":
            ui.check("英語: 箱に出るヒントの文",
                     [h1, h2, h3, h4],
                     [hint_text_en(two["sol"], 1), hint_text_en(two["sol"], 2),
                      hint_text_en(nop["sol"], 2), hint_text_en(one["sol"], 2)])
            ui.open(date=iso(two["no"]), lang="en")
            ui.ev("shareCount=2;useHint();useHint()")
            ui.check("英語: 太字は、記号（<code>）と with（<b>）。ラベルと記号の間は余白 6px、with の前には余白を足さない",
                     ui.ev("(function(){const h=document.querySelector('#hintbox .hbin'),c=h.querySelector('code'),"
                           "b=h.querySelector('b');return [c.textContent,b.textContent,getComputedStyle(c).marginLeft,"
                           "getComputedStyle(c).fontWeight,getComputedStyle(b).marginLeft,getComputedStyle(b).fontWeight]})()"),
                     ["%s %s" % (GLYPH[kinds(two["sol"])[0]], GLYPH[kinds(two["sol"])[1]]), "with",
                      "6px", "700", "0px", "700"])
        else:
            ui.open(date=iso(two["no"]), lang="ja")
            ui.ev("shareCount=2;useHint()")
            ui.check("日本語: ラベルと記号の間に余白を足さない（全角の「：」が空きを持つ）",
                     ui.ev("getComputedStyle(document.querySelector('#hintbox .hbin code')).marginLeft"), "0px")
        # ギブアップの後（ほかの解き方）。いちばん長い式まで送る
        ui.open(date=iso(longest["no"]), lang=lang)
        click("dgiveup")
        click("gu-yes", 0.5)
        audit(lang, "ギブアップの後")
        # 縮小の計算が持つラベルの幅（SOL_LABEL_EM）が、実際の幅を下回らないこと（下回ると、縮め足りずにはみ出す）。
        # 今の列には、この箱で縮める日が無いので、画面のはみ出しでは拾えない。幅を直に比べる
        ui.check("%s: 全解答のラベル「%s」の見積もりの幅は、実際の幅以上（+10px まで）" % (
                     lang, "ほかの解き方：" if lang == "ja" else "Other solutions"),
                 ui.ev("(function(){const n=document.querySelector('#solbox .hbin').firstChild,r=document.createRange();"
                       "r.selectNodeContents(n);const w=r.getBoundingClientRect().width,"
                       "e=SOL_LABEL_EM.other[LANG]*HINT_ROW.font;return e>=w-0.1&&e<=w+10})()"), True)
        others = longest["sols"][1:]
        at_long = max(range(len(others)), key=lambda i: len(others[i])) if others else 0
        ui.ev("solAt=%d;drawSols()" % at_long)
        audit(lang, "ギブアップの後（いちばん長い式）")
        # 解いた後・統計・遊び方・トースト
        ui.open(date=iso(two["no"]), lang=lang)
        ui.solve(two["sol"])
        audit(lang, "解いた後")
        if lang == "en":
            ui.check("英語: 解いた後の 3 列（時間・ヒント・連続日数）と、共有ボタン・導線・全解答のラベル",
                     ui.ev("[...document.querySelectorAll('.rcol .rn')].map(e=>e.textContent)"
                           ".concat([rshare.textContent.trim(),document.querySelector('.applink').textContent.trim(),"
                           "document.querySelector('#solbox .hbin').firstChild.nodeValue,sub.textContent])"),
                     ["Time", "Hints", "Streak", "Share result", "Want more puzzles? Play Make10", "Solution", "Solved!"])
            ui.check("英語: ヒントの回数は数字だけ（単位の箱は出さず、数字は列の中央）。日数は 1 day",
                     ui.ev("(function(){const u=document.getElementById('r-hints-u'),b=document.getElementById('r-hints')"
                           ".getBoundingClientRect(),c=u.closest('.rcol').getBoundingClientRect();"
                           "return [u.textContent,getComputedStyle(u).display,"
                           "Math.abs((b.left+b.right)/2-(c.left+c.right)/2)<0.6,"
                           "document.getElementById('r-streak').textContent+' '+document.getElementById('r-streak-u').textContent]})()"),
                     ["", "none", True, "1 day"])
        ui.ev(STUB % "true")
        click("rshare", 0.35)
        audit(lang, "トースト（コピーしました）")
        ui.ev(STUB % "false")
        time.sleep(1.8)
        click("rshare", 0.35)
        audit(lang, "トースト（コピーできません）")
        time.sleep(1.8)
        click("dstats")
        audit(lang, "統計")
        click("dstats-close")
        click("dhelp")
        audit(lang, "遊び方")
        click("dhelp-close")
        ui.open(date=(start - datetime.timedelta(days=1)).isoformat(), lang=lang)
        audit(lang, "問題がありません")
        ui.check("%s: 主な状態を巡って、JS エラーも、辞書に無いキーの警告も無い" % lang, ui.errors(), [])

    for lang in ("ja", "en"):
        ui.check("%s: 巡った状態は 16" % lang, len(seen[lang]), 16)
        ui.check("%s: 文字が画面・ボタン・箱からはみ出さない" % lang,
                 [(n, a["over"]) for n, a in seen[lang] if a["over"] or a["scroll"]], [])
        ui.check("%s: 1 行のはずの所が折り返さない" % lang,
                 [(n, a["wrap"]) for n, a in seen[lang] if a["wrap"]], [])
    ui.check("en: 見えている文字とボタンの名前に、日本語の文字が無い",
             [(n, [x for x in a["texts"] + a["labels"] if JP.search(x)]) for n, a in seen["en"]
              if any(JP.search(x) for x in a["texts"] + a["labels"])], [])
    # 確かめが空振りしていないこと（集めた文字に、その状態の文が入っている）
    texts = {n: a["texts"] + a["labels"] for n, a in seen["en"]}
    ui.check("en: 集めた文字に、その状態の文が入っている",
             ["Give up?" in texts["ギブアップの確認"], "Gave up" in texts["ギブアップの後"],
              "Other solutions" in texts["ギブアップの後"], "Copied!" in texts["トースト（コピーしました）"],
              "Couldn't copy" in texts["トースト（コピーできません）"], "Max streak" in texts["統計"],
              "How to play" in texts["遊び方"], "No puzzle today" in texts["問題がありません"],
              "Share with a friend to unlock a hint" in texts["ヒントをもらう前の知らせ"],
              "Parentheses don't match" in texts["括弧の注意"],
              "Test mode (not saved)" in texts["問題画面（制約がある日）"],
              any("isn't allowed" in x for x in texts["問題画面（制約がある日）"]),
              "How to play" in texts["問題画面（制約がある日）"]],        # 「?」の名前
             [True] * 13)

    # ══ 統計の単位（英語の単数・複数）══
    rec = {"r": "s", "t": 60, "h": 0, "sh": 0, "e": rows[0]["sol"]}
    ui.open(now=at(3), tz=TZ, lang="en", store={"v": 1, "cur": None, "days": {"1": rec, "2": rec}})
    click("dstats")
    ui.check("英語: 統計の単位は 2 days（解いた日数・連続日数・最長）。平均時間は単位なし",
             ui.ev("[...document.querySelectorAll('#statlist .stat .sv')].map(e=>e.textContent)"),
             ["2days", "2days", "2days", "1:00"])
    ui.open(now=at(2), tz=TZ, lang="en", store={"v": 1, "cur": None, "days": {"1": rec}})
    click("dstats")
    ui.check("英語: 1 のときは 1 day",
             ui.ev("[...document.querySelectorAll('#statlist .stat .sv')].map(e=>e.textContent)"),
             ["1day", "1day", "1day", "1:00"])
    ui.open(now=at(2), tz=TZ, lang="en")
    click("dstats")
    ui.check("英語: 0 のときは 0 days",
             ui.ev("[...document.querySelectorAll('#statlist .stat .sv')].map(e=>e.textContent)").__getitem__(0), "0days")
    ui.check_no_errors()
