# -*- coding: utf-8 -*-
"""画面の文の辞書（7.5・GAME-SPEC 13 章）。

画面に出る文は辞書（STR_CORE / STR_APP）に入れ、HTML と JS には直書きしない。
ここで見るのは 3 つ:
  1. HTML と JS に、プレイヤー向けの日本語の直書きが残っていないこと
     （開発者パネルなど、辞書に入れないものは下の一覧で除外する）
  2. 辞書のすべてのキーがどこかで使われていること・使われているキーがすべて辞書にあること
  3. 画面を巡っても、辞書に無いキーを引いた警告や、置き換えの印 {名前} の残りが出ないこと

1 と 2 の「使われているキー」は **ソースを読んで**数える（アプリの t() を通さない）。
辞書のキーの一覧だけはページから取る（辞書そのものが正なので）。
"""
import os
import re

NAME = "画面の文の辞書"

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "docs", "index.html")
JA = re.compile("[぀-ヿ㐀-鿿！-｠々〆]")
KEY = re.compile(r'"([a-z]+\.[a-z0-9_]+)"')

# 辞書に入れないもの（7.5 の決定）。足す・外すときは GAME-SPEC 13 章も直す
EXCLUDE_HTML_IDS = ["dv-open-row",   # 設定画面の中の、開発者パネルの入口
                    "devpanel",      # 開発者パネル
                    "banner"]        # 広告バナーの仮の文
EXCLUDE_JS_CTX = ["STR_CORE", "STR_APP",          # 辞書そのもの
                  # 開発者パネル
                  "THEMES", "applyDevPos", "renderDevPanel", "fillDigitInk", "ago",
                  "renderDevMeasured", "devVarInput", "#dv-min.onclick", "#dv-copy.onclick"]
EXCLUDE_JS_LINE = "console."                      # console の文
# キーを文字列で書かずに t() を呼んでよい所（applyI18n が属性の値で引く 1 か所だけ）
ALLOW_NONLITERAL = ["e.getAttribute"]
ATTRS = ["data-i18n", "data-i18n-html", "data-i18n-label", "data-i18n-ph", "data-i18n-pre"]


def _strip_js_comments(lines):
    """行ごとに、コメントを落とした文字列を返す（文字列の中の // は残す）"""
    out = []
    inblock = False
    for l in lines:
        s = ""
        j = 0
        while j < len(l):
            if inblock:
                e = l.find("*/", j)
                if e < 0:
                    j = len(l)
                    break
                inblock = False
                j = e + 2
                continue
            c = l[j]
            if c in "\"'`":
                e = j + 1
                while e < len(l) and l[e] != c:
                    if l[e] == "\\":
                        e += 1
                    e += 1
                s += l[j:e + 1]
                j = e + 1
                continue
            if l.startswith("//", j):
                break
            if l.startswith("/*", j):
                inblock = True
                j += 2
                continue
            s += c
            j += 1
        out.append(s)
    return out


def scan_source(path=HTML):
    """ソースから (直書きの日本語の一覧, 使われているキーの集合, キーを文字列で書いていない t() の引数,
    t() の呼び出しごとの (キー, 渡している名前, 行))。HTML の属性で引くキーは名前を渡さない呼び出しとして数える"""
    with open(path, encoding="utf-8") as f:
        L = f.read().split("\n")
    n = len(L)
    i_style1 = next(i for i, l in enumerate(L) if l.strip() == "</style>")
    i_script = next(i for i, l in enumerate(L) if l.strip() == "<script>")
    i_blob0 = next(i for i, l in enumerate(L) if l.startswith("const BLOB=`"))
    i_blob1 = next(i for i in range(i_blob0 + 1, n) if L[i].endswith("`;"))
    left = []
    used = set()
    calls = []
    # ── HTML（コメントを落とし、除外する要素の中は見ない）
    body = "\n".join(L[i_style1 + 1:i_script])
    body = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), body, flags=re.S)
    skip_depth = 0
    for k, l in enumerate(body.split("\n")):
        ln = i_style1 + 2 + k
        opens = len(re.findall(r"<div\b", l))
        closes = len(re.findall(r"</div>", l))
        if skip_depth == 0 and any('id="%s"' % x in l for x in EXCLUDE_HTML_IDS):
            skip_depth = opens - closes
            continue
        if skip_depth > 0:
            skip_depth += opens - closes
            continue
        for a in ATTRS:
            for m in re.finditer(r'\b%s="([^"]*)"' % re.escape(a), l):
                used.add(m.group(1))
                calls.append((m.group(1), [], ln))
        if JA.search(l):
            left.append("HTML %d: %s" % (ln, l.strip()[:60]))
    # ── JS（コメントを落とし、辞書・開発者パネル・console は見ない）
    idx = [i for i in range(i_script + 1, n) if not (i_blob0 <= i <= i_blob1)]
    stripped = _strip_js_comments([L[i] for i in idx])
    ctx = ""
    nonlit = []
    for i, s in zip(idx, stripped):
        m = re.match(r'^(?:async )?function (\w+)|^\$\("([\w-]+)"\)\.(on\w+|addEventListener)|^(?:const|let) (\w+)\s*=', L[i])
        if m:
            ctx = m.group(1) or (m.group(2) and "#" + m.group(2) + "." + m.group(3)) or m.group(4)
        if ctx in ("STR_CORE", "STR_APP"):
            continue
        for cm in re.finditer(r"(?<![\w.$])t\(([^(){}]*)", s):
            keys = KEY.findall(cm.group(1))
            if keys:
                used.update(keys)
                # 渡している名前（{名前:値} の左側）を拾う。t("key") だけなら空
                names = set()
                rest = s[cm.end():]
                if rest.startswith("{"):
                    depth = 0
                    part = ""
                    for ch in rest[1:]:
                        if ch in "([{":
                            depth += 1
                        elif ch in ")]}":
                            if depth == 0:
                                break
                            depth -= 1
                        if ch == "," and depth == 0:
                            names.add(part.split(":")[0].strip())
                            part = ""
                        else:
                            part += ch
                    if part.strip():
                        names.add(part.split(":")[0].strip())
                for k in keys:
                    calls.append((k, sorted(names), i + 1))
            elif not s.startswith("function t("):
                nonlit.append(cm.group(1).strip())
        if JA.search(s) and ctx not in EXCLUDE_JS_CTX and EXCLUDE_JS_LINE not in s:
            left.append("JS %d (%s): %s" % (i + 1, ctx, s.strip()[:60]))
    return left, used, nonlit, calls


def run(ui):
    left, used, nonlit, calls = scan_source()
    ui.check("HTML と JS に、プレイヤー向けの日本語の直書きが残っていない", left, [])
    ui.check("キーを文字列で書かない t() は applyI18n の 1 か所だけ", nonlit, ALLOW_NONLITERAL)

    ui.open()
    core = set(ui.ev("Object.keys(STR_CORE.ja)"))
    app = set(ui.ev("Object.keys(STR_APP.ja)"))
    ui.check("辞書が空でない（共通の塊・本編だけの塊）", [len(core) > 0, len(app) > 0], [True, True])
    ui.check("共通の塊と本編の塊に同じキーが無い", sorted(core & app), [])
    ui.check("キーは「場所.中身」の形",
             sorted(k for k in core | app if not re.match(r"^[a-z]+\.[a-z0-9_]+$", k)), [])
    ui.check("使われているキーがすべて辞書にある", sorted(used - (core | app)), [])
    ui.check("辞書のすべてのキーがどこかで使われている", sorted((core | app) - used), [])
    ui.check("文が空のキーが無い・複数形の文は other を持つ", ui.ev(
        """(()=>{const bad=[];for(const d of [STR_CORE.ja,STR_APP.ja])for(const [k,v] of Object.entries(d)){
             if(typeof v==='string'){if(!v)bad.push(k)}
             else if(!v||typeof v.other!=='string'||!v.other)bad.push(k)}
           return bad})()"""), [])
    ui.check("_html で終わるキーだけがタグを含む", ui.ev(
        """(()=>{const bad=[];for(const d of [STR_CORE.ja,STR_APP.ja])for(const [k,v] of Object.entries(d)){
             const s=typeof v==='string'?v:Object.values(v).join('');
             if(/<[a-z]/.test(s)!==/_html$/.test(k))bad.push(k)}
           return bad})()"""), [])

    # 置き換えの印 {名前} と、呼ぶ側が渡す名前が合っていること（1 つでも違えば印が文字のまま出る）
    marks = ui.ev("""(()=>{const o={};for(const [k,v] of Object.entries(STR)){
        const s=typeof v==='string'?v:Object.values(v).join(' ');
        o[k]=[...new Set((s.match(/\{(\w+)\}/g)||[]).map(x=>x.slice(1,-1)))].sort()}return o})()""")
    plural = set(ui.ev("Object.keys(STR).filter(k=>typeof STR[k]==='object')"))
    ui.check("複数形の文を引く所は、必ず n を渡している",
             ["%s（%d 行目）" % (k, ln) for k, names, ln in calls if k in plural and "n" not in names], [])
    ui.check("置き換えの印の名前が、呼ぶ側の渡す名前と合っている",
             ["%s（%d 行目）: 辞書 %s / 呼ぶ側 %s" % (k, ln, marks.get(k), names)
              for k, names, ln in calls
              # 複数形の文は、選ぶためだけに n を渡してよい（文に {n} が無くても）
              if k in marks and marks[k] != [x for x in names if not (x == "n" and k in plural and "n" not in marks[k])]], [])

    # ── t() の動き
    ui.check("置き換えの印 {名前} が入る", ui.ev('t("read.banned",{op:"×"})'), "× は使えません")
    ui.check("複数形の文は n で選ぶ（日本語は 1 通り）",
             ui.ev('[t("home.total",{n:1}),t("home.total",{n:2}),t("unit.puzzle",{n:1})]'),
             ["累計 1 問", "累計 2 問", "問"])
    ui.check("辞書に無いキーはキーそのものが返る", ui.ev('t("no.such_key")'), "no.such_key")

    # ── 画面を巡っても、無いキーの警告や {名前} の残りが出ない
    ui.ev("""window.__WARN=[];(function(){const o=console.warn;
      console.warn=function(){__WARN.push([].join.call(arguments,' '));o.apply(console,arguments)}})();
      window.__LEFT=[];window.__look=function(w){
        const tx=document.body.innerText+' '+[...document.querySelectorAll('[title],[aria-label],[placeholder]')]
          .map(e=>(e.title||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.placeholder||'')).join(' ');
        const m=(tx.match(/\\{[a-z]+\\}/g)||[]).concat(Object.keys(STR).filter(k=>tx.includes(k)));
        if(m.length)__LEFT.push(w+': '+m.join(','))};1""")
    ui.check("流し込む印（data-i18n…）を持つ要素はすべて中身が入っている", ui.ev(
        """[...document.querySelectorAll('[data-i18n],[data-i18n-html],[data-i18n-label],[data-i18n-ph],[data-i18n-pre]')]
           .filter(e=>!((e.textContent||'').trim()||e.title||e.placeholder)).map(e=>e.id||e.tagName)"""), [])
    ui.ev('__look("home")')
    ui.click("gear"); ui.ev('__look("settings")')
    ui.click("go-help"); ui.ev('__look("help")')
    ui.ev('go("stats");__look("stats")')
    ui.ev('go("home")')
    ui.click("m-course"); ui.ev('__look("play")')
    for i in range(3):
        ui.click("hint"); ui.ev('__look("hint%d")' % (i + 1))
    ui.ev('G.scoreOn=true')
    ui.solve(); ui.ev('__look("win")')
    ui.ev('go("stats");__look("stats2")')
    ui.check("画面を巡っても、置き換えの印やキーが文字のまま出ない", ui.ev("__LEFT"), [])
    ui.check("画面を巡っても、辞書に無いキーを引いた警告が出ない", ui.ev("__WARN"), [])
    ui.check_no_errors()
