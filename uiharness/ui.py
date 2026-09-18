# -*- coding: utf-8 -*-
"""ケースから使う道具一式。

判定は**できるだけ DOM の見える値**で取る（`ui.text("cnum")` など）。
内部の変数を直接読むのは、画面に出ていないもの（保存データの選別結果など）と、
盤面を組むところに限る ―― 見えている文字で判定しないと、
「変数は正しいのに画面には出ていない」を見落とす（4.5 → 4.6 で 1 度やった）。
"""
import json
import time

# 保存データを仕込む種まき script。読み込みのたびに本体より先に走る。
# JS エラーは window.__ERRS に、トーストは window.__TOASTS に溜める
SEED = """
window.__ERRS=[];
window.__TOASTS=[];
addEventListener('error',e=>__ERRS.push('error: '+(e.message||e)));
addEventListener('unhandledrejection',e=>__ERRS.push('reject: '+e.reason));
(function(){
  const o=console.error;
  console.error=function(){__ERRS.push('console.error: '+[].join.call(arguments,' '));
    o.apply(console,arguments)};
})();
try{
  localStorage.removeItem(%(key)s);
  %(seed)s
}catch(e){}
"""

# 解答例どおりに記号を置いて解く。数字は最初から並んでいるので読み飛ばす。
# put() は canPut() を通さないが、置く場所は解答例そのものなので合法な並びになる
SOLVE = """
window.__solve=function(){
  let i=0;
  for(const ch of cur.sol.replace(/\\s+/g,'')){
    if(/[0-9]/.test(ch)){i++;}
    else if(ch==='('){put('lp',i);i++;}
    else if(ch===')'){put('rp',i);i++;}
    else if(ch==='!'){put('!',i);i++;}
    else {put(ch,i);i++;}
  }
  render();
  return $('eq').textContent+'|'+$('sub').textContent;
};
(function(){
  const o=window.toast;
  window.toast=function(m){__TOASTS.push(m);return o.apply(this,arguments)};
})();
"""

SAVE_KEY = "make10.progress.v4"


class Fail(Exception):
    pass


class UI:
    def __init__(self, chrome, url, results, viewport):
        self.c = chrome
        self.url = url
        self.results = results
        self.viewport = viewport      # "normal" / "compact"
        self._seed_id = None
        self.case = ""

    # ── 開く ───────────────────────────────────────────────
    def open(self, save=None):
        """保存データを仕込んでから開き直す。save=None なら保存データ無し。"""
        seed = ""
        if save is not None:
            seed = "localStorage.setItem(%s,%s);" % (
                json.dumps(SAVE_KEY),
                json.dumps(json.dumps(save, ensure_ascii=False)))
        if self._seed_id:
            self.c.remove_on_new_document(self._seed_id)
        self._seed_id = self.c.on_new_document(
            SEED % {"key": json.dumps(SAVE_KEY), "seed": seed})
        self.c.goto(self.url)
        self.c.ev(SOLVE)

    # ── 読む ───────────────────────────────────────────────
    def ev(self, expr):
        return self.c.ev(expr)

    def text(self, el_id):
        """見えている文字。要素が無ければ None を返す（非表示は空文字と区別する）"""
        return self.c.ev("(function(){const e=$(%s);return e?e.textContent:null})()"
                         % json.dumps(el_id))

    def visible(self, el_id):
        return self.c.ev(
            "(function(){const e=$(%s);if(!e)return false;"
            "const s=getComputedStyle(e);"
            "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0})()"
            % json.dumps(el_id))

    def click(self, el_id):
        self.c.ev("$(%s).click()" % json.dumps(el_id))
        time.sleep(0.12)

    def errors(self):
        return self.c.ev("__ERRS")

    def toasts(self):
        return self.c.ev("__TOASTS")

    def scrolls(self):
        """問題画面はスクロールを発生させない（CLAUDE.md 画面のルール）"""
        return self.c.ev(
            "document.documentElement.scrollHeight>innerHeight+1")

    # ── 解く ───────────────────────────────────────────────
    def solve(self, wait=1.0):
        """今の問題を解答例どおりに解いて win() の発火を待つ。
        戻り値は #eq と #sub の文字（"10|正解" になるはず）"""
        r = self.c.ev("__solve()")
        time.sleep(wait)
        return r

    # ── 判定 ───────────────────────────────────────────────
    def check(self, name, got, want):
        ok = got == want
        self.results.append((ok, self.viewport, self.case, name, got, want))
        return ok

    def check_no_errors(self, name="JS エラー 0"):
        return self.check(name, self.errors(), [])
