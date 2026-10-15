"""verify_daily.py のケースから使う道具（デイリー D0.2。DAILY-SPEC 11 章）。

本編の `uiharness/ui.py` とは別に持つ（本編の検証には触らない）。`uiharness/cdp.py` は共用する。

- ソースを「トップレベルの文」と「CSS の規則」に分ける（本編との同期の照合に使う）
- ページを開く（`?date=` `?lang=`・時間帯・端末の時計の差し替え）・見えている値を読む・判定を積む
"""
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 配る場所。MAKE10_DOCS で差し替えられる（わざと壊した複製に当てて、赤くなることを確かめるため）
DOCS = os.environ.get("MAKE10_DOCS") or os.path.join(ROOT, "docs")
MAIN_HTML = os.path.join(DOCS, "index.html")
DAILY_HTML = os.path.join(DOCS, "daily", "index.html")
READY = "complete|undefined"     # cdp.Chrome.goto() の待ち合わせ。デイリーに APP_VERSION は無い

# 本編と同じ名前だが、手を入れてあるもの（DAILY-SPEC 18-3 の除外の一覧）。
# 足す・外すときは CHANGELOG.md に書く
JS_EXCLUDE = {
    "render": "カーソルの印を足す予定（14-3）。本編のコード欄・難易度の言葉・正解の後の処理の呼び出しを外した",
    "applyLang": "本編は STR_APP を名前で書いている（16-2）。本編だけの画面の引き直しも持たない",
    "toast": "出す位置を本編の下の段の並びから決めている（D0.2 ではまだ持たない）",
    # 同じ名前の宣言だが、中身は別物（仕様で決まっている）
    "hideWin": "clearAll() が呼ぶ。デイリーには正解カードが無いので、何もしない関数を置く",
    "G": "同じ名前の小さい G（2 章）。複製した関数が読む項目だけを持つ",
    "STR": "辞書を組む行。本編は STR_APP、デイリーは STR_DAILY を重ねる（16-2）",
}
# 本編と同じセレクタだが、手を入れてある CSS の規則（DAILY-SPEC 18-3）
CSS_EXCLUDE = {}


def read(path):
    """改行を LF に揃えて読む（Git の設定で CRLF になっている作業ツリーでも同じ結果にする）"""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def script_of(html):
    """最後の <script>…</script> の中身（ページの JS）"""
    i = html.rindex("<script>") + len("<script>")
    return html[i:html.rindex("</script>")]


def style_of(html):
    i = html.index("<style>") + len("<style>")
    return html[i:html.index("</style>")]


# ── JS をトップレベルの文に分ける ─────────────────────────────────────
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")


def split_js(src):
    """JS のソースを、トップレベルの文のかたまりに分ける。[(名前, 文字列)…]。

    行の頭で「括弧の深さが 0・文字列やコメントの外」になっている行を、文の始まりとみなす
    （本編の書き方に合わせた決め方。続きの行は、字下げされているか、深さが 0 でない）。
    名前は、宣言の先頭の名前（function X / const X= / let X= / var X=）。宣言でない文は None。
    コメントだけのかたまりは捨てる。文字列・テンプレート・コメント・正規表現の中の括弧は数えない。"""
    n = len(src)
    i = 0
    depth = 0
    starts = []            # 文の始まりになりうる行頭の位置
    line_start = True
    mode = None            # None / "'" / '"' / "`" / "//" / "/*" / "re"
    tmpl = []              # テンプレートの ${ } の入れ子（そのときの depth）
    prev = ""              # 直前の、空白でない文字（正規表現かどうかの判定用）
    in_class = False
    while i < n:
        c = src[i]
        if line_start and mode is None and depth == 0 and c not in " \t\n":
            starts.append(i)
        line_start = False
        if mode is None:
            two = src[i:i + 2]
            if two == "//":
                mode = "//"; i += 2; continue
            if two == "/*":
                mode = "/*"; i += 2; continue
            if c in "'\"":
                mode = c
            elif c == "`":
                mode = "`"
            elif c == "/" and (prev == "" or prev in _REGEX_PREV):
                mode = "re"; in_class = False
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if c == "}" and tmpl and tmpl[-1] == depth:
                    tmpl.pop(); mode = "`"
            if c not in " \t\n":
                prev = c
        elif mode == "//":
            if c == "\n":
                mode = None
        elif mode == "/*":
            if src[i:i + 2] == "*/":
                mode = None; i += 2; continue
        elif mode in ("'", '"'):
            if c == "\\":
                i += 2; continue
            if c == mode or c == "\n":
                mode = None; prev = "x"
        elif mode == "`":
            if c == "\\":
                i += 2; continue
            if c == "`":
                mode = None; prev = "x"
            elif src[i:i + 2] == "${":
                tmpl.append(depth); depth += 1; mode = None; i += 2; continue
        elif mode == "re":
            if c == "\\":
                i += 2; continue
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif (c == "/" and not in_class) or c == "\n":
                mode = None; prev = "x"
        if c == "\n":
            line_start = True
        i += 1
    if depth != 0 or mode not in (None, "//"):
        raise ValueError("JS を分けられない（深さ %d・状態 %r で終わった）" % (depth, mode))
    out = []
    for k, a in enumerate(starts):
        b = starts[k + 1] if k + 1 < len(starts) else n
        text = src[a:b].rstrip()
        body = _strip_comments(text).strip()
        if not body:
            continue
        m = re.match(r"(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", body) or \
            re.match(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)", body)
        out.append((m.group(1) if m else None, _strip_trailing_comment(text)))
    return out


def _strip_comments(text):
    """文の頭に付いたコメントだけを落とす（かたまりがコメントだけかを見るため）"""
    s = text
    while True:
        s = s.lstrip()
        if s.startswith("//"):
            s = s[s.index("\n") + 1:] if "\n" in s else ""
        elif s.startswith("/*"):
            s = s[s.index("*/") + 2:] if "*/" in s else ""
        else:
            return s


def _strip_trailing_comment(text):
    """文の後ろに続く、次の文のためのコメント（行頭から始まるもの）を落とす"""
    lines = text.split("\n")
    while lines:
        last = lines[-1]
        if not last.strip():
            lines.pop(); continue
        if last.startswith("//") or (last.startswith("/*") and last.rstrip().endswith("*/")):
            lines.pop(); continue
        break
    # 複数行の /* … */ が末尾に付いている場合（行頭から始まり、文の本体より後ろ）
    text = "\n".join(lines)
    while True:
        m = re.search(r"\n/\*(?:(?!\*/).)*\*/\s*$", text, re.S)
        if not m:
            return text
        text = text[:m.start()].rstrip()


def js_key(name, text):
    """照合の鍵。宣言は名前、宣言でない文は 1 行目"""
    return name if name else "@" + text.split("\n")[0].strip()


# ── CSS を規則に分ける ────────────────────────────────────────────────
def split_css(src, prefix=""):
    """CSS を規則に分ける。[(セレクタ, 本体)…]。@media などの中は「@media … || セレクタ」。
    コメントは落とし、セレクタと本体の空白は 1 つに詰める（本体は { } の中の文字列）。"""
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    out = []
    i, n = 0, len(s)
    while i < n:
        j = s.find("{", i)
        if j < 0:
            break
        sel = " ".join(s[i:j].split())
        depth, k = 1, j + 1
        while k < n and depth:
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
            k += 1
        body = s[j + 1:k - 1]
        if sel.startswith("@media") or sel.startswith("@supports"):
            out.extend(split_css(body, prefix + sel + " || "))
        else:
            out.append((prefix + sel, " ".join(body.split())))
        i = k
    return out


# ── ページに埋め込んである起点日と列を読む ────────────────────────────
def page_data(html=None):
    """(起点日 date, 行 [{"no","id","rc","d","sol","sols"}…])。ソースの文字列から読む（ページの JS は通さない）。
    html を渡すと、その文字列から読む（公開ページの HTML を読む check_site.py が使う）。省くと手元のページ"""
    import datetime
    if html is None:
        html = read(DAILY_HTML)
    start = re.search(r'const DAILY_START="(\d{4})-(\d{2})-(\d{2})"', html)
    text = re.search(r"const DAILY=`([^`]*)`", html).group(1)
    rows = []
    for ln in text.splitlines():
        if not ln:
            continue
        f = ln.split(",")
        sols = ",".join(f[4:]).split(";")
        rows.append({"no": int(f[0]), "id": f[1], "rc": f[2], "d": int(f[3]),
                     "sol": sols[0], "sols": sols})
    return datetime.date(*map(int, start.groups())), rows


def top_text(no, day, lang="ja"):
    """上のバーの中央に出るはずの文字（DAILY-SPEC 16-3・16-4 の daily.top_date_html）"""
    if lang == "en":
        return "#%d · %s, %s %d" % (no, "Mon Tue Wed Thu Fri Sat Sun".split()[day.weekday()],
                                    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[day.month - 1],
                                    day.day)
    return "#%d　%d月%d日（%s）" % (no, day.month, day.day, "月火水木金土日"[day.weekday()])


def fmt_time(sec):
    """時間の表示（DAILY-SPEC 7 章。D0.24）。1 時間までは 1:42、1 時間からは 1:02:05。ページの関数は使わない"""
    if sec >= 3600:
        return "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
    return "%d:%02d" % (sec // 60, sec % 60)


# ── 共有の文（DAILY-SPEC 9 章。D0.21）。ページの辞書も関数も使わずに、ここで組む ──────────
SHARE_BANDS = (30, 60, 120, 300)        # 時間の帯の境目（秒。17-4）
SHARE_MIN = 30                          # 件数がこれより少ない間は「集計中」（位置を足さない）


def share_pct(kind, sec=None, agg=None):
    """共有の文に足す、みんなの中の位置（%）。足さないときは None。
    kind … "s"（解いた）/ "g"（ギブアップ）。agg … みんなの結果（s・g・b）"""
    if not agg or agg["s"] + agg["g"] < SHARE_MIN:
        return None
    if kind == "g":
        return int(agg["s"] * 100 / (agg["s"] + agg["g"]) + 0.5)
    if not agg["s"]:
        return None
    mine = sum(1 for b in SHARE_BANDS if sec >= b)
    return sum(agg["b"][mine + 1:]) * 100 // agg["s"] or None


def share_text(row, kind=None, sec=None, agg=None, lang="ja"):
    """共有の文（URL の前まで）。kind … None（解く前）/ "s" / "g" """
    ja = lang == "ja"
    lines = ["Make10 DAILY #%d" % row["no"]]
    digits = " ".join(row["id"])
    if kind is None:
        return "\n".join(lines + [digits, "この 4 つの数字で 10 を作れる？" if ja else "Can you make 10 with these four digits?"])
    pct = share_pct(kind, sec, agg)
    if kind == "s":
        # 時間は「→ 10」と同じ行（D0.23。間は半角の空白 2 つ）
        lines.append(digits + " → 10  ⏱ " + fmt_time(sec))
        if pct is not None:
            lines.append(("解いた人の %d%% より速い" if ja else "Faster than %d%% of solvers") % pct)
        lines.append("あなたは何秒？" if ja else "How fast are you?")
    else:
        lines.append(digits + " → 10")
        if ja:
            lines.append("ギブアップ…" + ("" if pct is None else "（正解率 %d%%）" % pct))
        else:
            lines.append("I gave up…" + ("" if pct is None else " (%d%% solved it)" % pct))
        lines.append("あなたは解ける？" if ja else "Can you?")
    return "\n".join(lines)


def share_leak(row, text):
    """共有の文に、入ってはいけないものが入っていれば、その名前の一覧（答え・演算の記号・解く前後の文の括弧）。
    その日の 4 つの数字（問題そのもの）は入ってよい。「（正解率 81%）」「(81% solved it)」の括弧は、決めた文の一部"""
    t = re.sub(r"（正解率 \d+%）| \(\d+% solved it\)", "", text)
    out = []
    if re.search(r"[+\-−×÷*/^!()（）]", t):
        out.append("演算の記号か括弧")
    if any(s in text or s.replace(" ", "") in text.replace(" ", "") for s in row["sols"]):
        out.append("答え")
    return out


# ── ページを開いて読む ────────────────────────────────────────────────
class Fail(Exception):
    pass


# 読み込みより先に入れる。JS エラーを集め、保存データを消し、必要なら端末の言語と時計を差し替える
SEED = r"""
window.__ERRS=[];
addEventListener("error",e=>__ERRS.push("error: "+String(e.message||e)));
addEventListener("unhandledrejection",e=>__ERRS.push("reject: "+String(e.reason)));
(function(){const o=console.error, w=console.warn;
  console.error=function(){__ERRS.push("console.error: "+[].join.call(arguments," "));o.apply(console,arguments)};
  // 辞書に無いキーを引くと t() が console.warn を出す。それも拾う
  console.warn=function(){__ERRS.push("console.warn: "+[].join.call(arguments," "));w.apply(console,arguments)};
})();
%(store)s
%(nav)s
%(clock)s
%(api)s
"""
# 集計の送り先（api.make10.app）の差し替え（D0.8）。ページの fetch を、読み込みより先に差し替える。
# **本物の集計へは 1 回も送らない**（ページの側に、送り先を切り替える入口は作らない）。
#   __API     = 出た要求の記録 [{url, method, headers, body, keys（fetch に渡した項目の名前）}…]
#   __APIMODE = 返事の決め方 {mode, agg, delay}
#     mode: "fail" 通信そのものが失敗（既定）／"ok" 200 で agg を返す（n は要求の問題番号）／"500"／
#           "range" 400 {"e":"range"}／"value" 400 {"e":"value"}／"badjson" 200 だが JSON でない／
#           "badshape" 200 だが形が違う／"hang" 返事が来ない（打ち切りを待つ）
#     xput・xtake・xcode・xs・xstore: 別の端末へ移す受け口（/x・/x/take）の返事（D0.37。下の中に説明）
API = r"""
window.__API=[];window.__APIMODE=%s;
(function(){const real=window.fetch;
  window.fetch=function(u,o){
    const url=String(u&&u.url||u);
    if(!/^https:\/\/api\.make10\.app(\/|$)/.test(url))return real.apply(this,arguments);
    o=o||{};const m=window.__APIMODE;
    let n=null;try{n=o.body?JSON.parse(o.body).n:+new URL(url).searchParams.get("n")}catch(e){}
    __API.push({url,method:o.method||"GET",headers:o.headers||{},body:o.body===undefined?null:o.body,
      keys:Object.keys(o).sort()});
    const res=(st,obj)=>new Response(typeof obj==="string"?obj:JSON.stringify(obj),
      {status:st,headers:{"Content-Type":"application/json"}});
    return new Promise((ok,ng)=>{
      if(o.signal)o.signal.addEventListener("abort",()=>ng(new DOMException("aborted","AbortError")));
      // 別の端末へ移す（D0.37。10-1）の受け口。xput は預ける返事、xtake は受け取る返事
      //   （"ok"／"fail" 通信の失敗（既定）／"busy" 429／"500"）。xcode・xs は預けたときに返すコードと秒数。
      //   受け取るときは xstore {コード: 中身} から返して消す（無ければ 404）
      const xp=new URL(url).pathname;
      if(xp==="/x"||xp==="/x/take"){
        const take=xp==="/x/take", xm=(take?m.xtake:m.xput)||"fail";
        setTimeout(()=>{
          if(xm==="busy")ok(res(429,{e:"busy"}));
          else if(xm==="500")ok(res(500,{e:"x"}));
          else if(xm!=="ok")ng(new TypeError("Failed to fetch"));
          else if(!take)ok(res(200,{c:m.xcode||"K7P2QX",s:m.xs||600}));
          else{const c=JSON.parse(o.body).c, st=m.xstore||(m.xstore={});
            if(Object.prototype.hasOwnProperty.call(st,c)){const d=st[c];delete st[c];ok(res(200,{d}))}
            else ok(res(404,{e:"code"}))}
        },m.delay||0);
        return;
      }
      setTimeout(()=>{
        if(m.mode==="ok")ok(res(200,Object.assign({n},m.agg)));
        else if(m.mode==="500")ok(res(500,{e:"x"}));
        else if(m.mode==="range")ok(res(400,{e:"range"}));
        else if(m.mode==="value")ok(res(400,{e:"value"}));
        else if(m.mode==="badjson")ok(res(200,"<html>"));
        else if(m.mode==="badshape")ok(res(200,{n,s:1}));
        else if(m.mode==="hang"){}
        else ng(new TypeError("Failed to fetch"));
      },m.delay||0)})}})();
"""
SAVE_KEY = "make10.daily.v1"          # デイリーの保存のキー（本編は make10.progress.v4）
SET_DEFAULT = {"easy": 0, "tap": 0, "dark": 0, "lang": "auto"}   # 設定の既定（D0.13。途中の値を表示しない・ドラッグで置く。dark は D0.31 で足した。白。lang は D0.36。端末に合わせる）
# ダークモードで回すための仕込み（D0.31。open(dark=True)）。読み込みの最初（html ができた時）に html へ dark を付け、
# ページの applyDark()（保存の set.dark が 0 なので classList.toggle("dark", false) を呼ぶ）には外させない。
# 外させてから付け直す形にすると、その間に白で計算された色から黒と白へ遷移が走り、測る時刻によって色が途中の値になる（D0.31 で見つけた）
DARK_SEED = ("(function(){const T=DOMTokenList.prototype.toggle;DOMTokenList.prototype.toggle=function(k,f){"
             "if(k==='dark'&&document.documentElement&&this===document.documentElement.classList)f=true;return T.call(this,k,f)};"
             "const add=()=>{const h=document.documentElement;if(!h)return false;h.classList.add('dark');return true};"
             "if(!add()){const o=new MutationObserver(()=>{if(add())o.disconnect()});o.observe(document,{childList:true})}})();")
# performance.now を、ケースから進められるものに差し替える。__perf がミリ秒。
# D0.24 から、ページは時間を端末の時計（Date）で数えるので、時間の確かめには効かない（tick() は両方を進める）
PERF = r"""
window.__perf=0;
performance.now=()=>window.__perf;
"""
# 保存できない環境（プライベートブラウズなど）のまね。読むのも書くのも例外にする
NO_STORAGE = r"""
Storage.prototype.getItem=function(){throw new Error("storage blocked")};
Storage.prototype.setItem=function(){throw new Error("storage blocked")};
"""
# 端末の時計を差し替える（Date の「今」だけ。時間帯は CDP が決める）。__now がミリ秒で、
# 自分では進まない ―― ケースが tick() で進める（戻すこともできる）。D0.24 から、ページはこの時計で時間を数える
CLOCK = r"""
(()=>{const RealDate=Date;window.__now=%(ms)s;
  class FakeDate extends RealDate{
    constructor(...a){if(a.length)super(...a);else super(window.__now)}
    static now(){return window.__now}}
  window.Date=FakeDate})();
"""
# 解答例の文字列から盤を組む。置けるかは canPut() を通す（ページの操作と同じ道を通る）
SOLVE = r"""
window.__solve=function(expr){
  clearAll();
  const tk=expr.split(" ");
  let p=0;                               // 盤の中の位置
  const digit=x=>/^[0-9]$/.test(x);
  for(const w of tk){
    let x=w, fac=0;
    while(x.endsWith("!")){fac++;x=x.slice(0,-1)}
    if(digit(x)){p++}
    else if(x==="("){if(!canPut("lp",p))return "置けない ( @"+p;put("lp",p);p++}
    else if(x===")"){if(!canPut("rp",p))return "置けない ) @"+p;put("rp",p);p++}
    else if(x!==""){if(!canPut(x,p))return "置けない "+x+" @"+p;put(x,p);p++}
    for(let k=0;k<fac;k++){if(!canPut("!",p))return "置けない ! @"+p;put("!",p);p++}
  }
  render();
  return $("eq").textContent+"|"+$("sub").textContent;
};
"""


class UI:
    def __init__(self, chrome, base, results, viewport, size):
        self.c = chrome
        self.base = base              # http://127.0.0.1:PORT/daily/index.html
        self.results = results
        self.viewport = viewport
        self.size = size              # (幅, 高さ)。ケースの中で画面を変えたら戻すのに使う
        self.case = ""
        self._seed_id = None
        self._tz = None
        # 端末の配色は、暗い表示に固定する（D0.30。ページは D0.31 から端末の設定を見ないが、見ないことをケース light が
        # 確かめるため、ほかのケースでも同じ形にしておく）。ケースごとに作り直されるので、前のケースの切り替えもここで戻る
        self.media()

    def media(self, scheme="dark", reduce=False):
        """端末の設定を差し替える。scheme … "dark" / "light"（prefers-color-scheme）／reduce … 動きを減らす設定。
        開いているページにもすぐ効く。戻すときは引数なしで呼ぶ"""
        f = [{"name": "prefers-color-scheme", "value": scheme}]
        if reduce:
            f.append({"name": "prefers-reduced-motion", "value": "reduce"})
        self.c.ws.call("Emulation.setEmulatedMedia", {"features": f})

    def open(self, date=None, lang="ja", nav=None, now=None, tz=None, extra="",
             store=None, perf=False, api=None, hidden=False, motion=False, dark=True):
        """ページを開く。

        date … ?date=YYYY-MM-DD（テスト表示）。None なら付けない
        lang … ?lang= で固定する。既定は日本語（ケースの期待値は日本語で書く）。None なら付けない
        nav  … navigator.language を差し替える
        now  … 端末の時計（UTC の ms）。開いた後は tick() で進める。None なら本物の時計
               （perf=True のときは、開いた時の本物の時刻で止めた時計にする ―― tick() で進めるため）
        tz   … 時間帯（"Asia/Tokyo" など）。None なら変えない
        store … 保存データ。None なら空にしてから開く／dict ならその中身を仕込む／
                "keep" なら前に開いたときのまま／"blocked" なら保存できない環境にする
        perf … True なら、performance.now も差し替える（tick() で一緒に進む）
        motion … False（既定）なら、ポップアップの開く・閉じる動きの長さを 0 秒にする（D0.26。開いた直後に位置を測っても、
                 動きの途中の値にならないように）。動きそのものを見るケース（`popup`・`giveup`）だけが True で開く
        hidden … True なら、隠れたまま読み込まれたことにする（裏のタブで開いた。visibility("visible") で見せる）
        dark … True（既定）なら、読み込みの最初から html に dark を付けたままにして、ダークモード（黒と白）で回す（D0.31。
               ページの既定は白。ケースの色の期待値は黒と白で書いてある。DARK_SEED）。保存データは変えない ―― 設定のスイッチは切れたまま見える。
               白と、設定から入れるダークモードそのものは、ケース light が dark=False で見る
        api … 集計の送り先の返事の決め方（上の API の __APIMODE）。None なら {"mode": "fail"}（通信できない）。
              出た要求は api_calls() で読む"""
        # 読み込みの前に走る仕込みは、Chrome に 1 つだけ残す。UI はケースごとに作り直されるので、
        # 前の UI が仕込んだもの（保存データを消す処理など）を Chrome の側で覚えて外す。
        # 外し忘れると、store="keep" で開いても、残っていた仕込みが保存データを消してしまう
        old = getattr(self.c, "_daily_seed", None)
        if old:
            self.c.remove_on_new_document(old)
        if store == "keep":
            st = ""
        elif store == "blocked":
            st = NO_STORAGE
        else:
            st = "try{localStorage.clear();%s}catch(e){}" % (
                "" if store is None else "localStorage.setItem(%s,%s)" % (
                    json.dumps(SAVE_KEY), json.dumps(json.dumps(store, ensure_ascii=False))))
        self.c._daily_seed = self._seed_id = self.c.on_new_document(SEED % {
            "store": st + (DARK_SEED if dark else "") + (PERF if perf else "") + (
                "Object.defineProperty(document,'visibilityState',{get:()=>'hidden',configurable:true});"
                if hidden else ""),
            "nav": "" if nav is None else
            "Object.defineProperty(navigator,'language',{get:()=>%s,configurable:true});"
            % json.dumps(nav),
            "clock": CLOCK % {"ms": "%d" % now} if now is not None
            else CLOCK % {"ms": "RealDate.now()"} if perf else "",
            "api": API % json.dumps(api or {"mode": "fail"})})
        if tz != self._tz:
            self.c.ws.call("Emulation.setTimezoneOverride", {"timezoneId": tz or ""})
            self._tz = tz
        q = []
        if date:
            q.append("date=" + date)
        if lang:
            q.append("lang=" + lang)
        self.c.goto(self.base + ("?" + "&".join(q) if q else "") + extra, ready=READY)
        self.c.ev(SOLVE)
        if not motion:
            self.c.ev("document.documentElement.style.setProperty('--popIn','0s');"
                      "document.documentElement.style.setProperty('--popOut','0s')")

    def tick(self, ms):
        """端末の時計を進める（open(now=…) か open(perf=True) のとき。負の数で戻す）。
        performance.now を差し替えてあれば、それも一緒に進める"""
        self.c.ev("if('__now' in window)window.__now+=%d;if('__perf' in window)window.__perf+=%d" % (ms, ms))

    def visibility(self, state):
        """画面が隠れた（"hidden"）・見えた（"visible"）ことにする"""
        self.c.ev("Object.defineProperty(document,'visibilityState',{get:()=>%s,configurable:true});"
                  "document.dispatchEvent(new Event('visibilitychange'))" % json.dumps(state))

    def api_calls(self):
        """集計の送り先へ出た要求の記録（差し替えた fetch が覚えたもの）"""
        return self.c.ev("window.__API")

    def saved(self, raw=False):
        """保存データ（無ければ None）。
        既定では、既定のままの設定（set がどれも 0。D0.13）を外して返し、
        ほかに何も入っていなければ None にする。設定を切り替えてあれば、set は外さない。raw=True でそのまま返す"""
        text = self.c.ev("localStorage.getItem(%s)" % json.dumps(SAVE_KEY))
        data = json.loads(text) if text else None
        if raw or data is None:
            return data
        if data.get("set") == SET_DEFAULT:
            data.pop("set")
        return None if data == {"v": 1, "days": {}, "cur": None} else data

    def resize(self, w, h):
        """画面の大きさを変える（開き直す前に呼ぶ）。終わったら restore() で戻す"""
        self.c.metrics(w, h)

    def restore(self):
        self.c.metrics(*self.size)

    def ev(self, expr):
        return self.c.ev(expr)

    def text(self, el_id):
        return self.c.ev("(function(){const e=document.getElementById(%s);"
                         "return e?e.textContent:null})()" % json.dumps(el_id))

    def visible(self, el_id):
        return self.c.ev(
            "(function(){const e=document.getElementById(%s);if(!e)return false;"
            "const s=getComputedStyle(e);"
            "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0})()"
            % json.dumps(el_id))

    def errors(self):
        return self.c.ev("__ERRS")

    def scrolls(self):
        """縦にも横にもスクロールが出ていないか（出ていれば True）"""
        return self.c.ev(
            "document.documentElement.scrollHeight>innerHeight+1"
            "||document.documentElement.scrollWidth>innerWidth+1")

    def solve(self, expr, wait=0.6):
        r = self.c.ev("__solve(%s)" % json.dumps(expr))
        time.sleep(wait)
        return r

    def check(self, name, got, want):
        ok = got == want
        self.results.append((ok, self.viewport, self.case, name, got, want))
        return ok

    def check_no_errors(self, name="JS エラー 0"):
        return self.check(name, self.errors(), [])
