# -*- coding: utf-8 -*-
"""BLOB だけから「解答の一覧」を組む（6.9。GAME-SPEC 5-4・DATA-SPEC 8-B）。

ゲームがヒント 3 で送る一覧を、**ゲームのコードも make10.py も使わずに**組み直す。
ケース `hint_sols` が、ゲームの出す一覧と全 puzzle で本数・順とも突き合わせる
（検証は生成と独立に実装する ―― CLAUDE.md）。make10.db は読まない。
BLOB の一覧が DB と合っているかは `make10.py blob` の検証 18 の役目。

読むのは `docs/index.html` の ``const BLOB=`…`;`` だけ:

    §COURSE / §FREE / §CHAL  1 行 = id,rc,d,n,nf,np,sol
    §SHAPE                   1 行 = 形。番号は行の位置（0 始まり）
    §SOLS                    1 行 = 4桁,番号,番号,…（番号は 36 進）

形は後置記法（`0!1!+2!+!3+`。0〜3 は 4 桁の何文字目か）。一覧は 4 桁の行を
①制約で絞り ②同じグループは先頭だけ残す、で作る。グループは
（加減の数・乗除の数・^ の数・! の数・二項演算子を伏せた並び）が同じもの。
"""
import os
import re

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "index.html")
BAN = {"N": None, "A0": "+", "S0": "-", "M0": "*", "D0": "/", "P0": "^", "F0": "!"}
RANK = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
_cache = None


def _tree(cs):
    """後置記法 -> 木。葉は "0"〜"3"、階乗は ("!", 子)、二項は (演算子, 左, 右)"""
    st = []
    for ch in cs:
        if ch.isdigit():
            st.append(ch)
        elif ch == "!":
            st.append(("!", st.pop()))
        else:
            right = st.pop()
            st.append((ch, st.pop(), right))
    assert len(st) == 1, cs
    return st[0]


def _rank(node):
    if isinstance(node, str):
        return 5
    return 4 if node[0] == "!" else RANK[node[0]]


def _show(node, pid):
    """木 -> 式の文字列（BLOB の sol と同じ書き方）"""
    if isinstance(node, str):
        return pid[int(node)]
    if node[0] == "!":
        inner = _show(node[1], pid)
        return (inner if isinstance(node[1], str) else "( %s )" % inner) + "!"
    op, a, b = node
    me = RANK[op]
    left, right = _show(a, pid), _show(b, pid)
    # ^ は右結合なので同じ強さの左に括弧、ほかは左結合なので同じ強さの右に括弧
    if _rank(a) < me or (_rank(a) == me and op == "^"):
        left = "( %s )" % left
    if _rank(b) < me or (_rank(b) == me and op != "^"):
        right = "( %s )" % right
    return "%s %s %s" % (left, op, right)


def _group(cs):
    return (cs.count("+") + cs.count("-"), cs.count("*") + cs.count("/"),
            cs.count("^"), cs.count("!"), re.sub(r"[^0-3!]", "@", cs))


def load():
    """{"puzzles": [(区分, id, rc, sol)…], "lists": {(id, rc): [式…]}} を返す。"""
    global _cache
    if _cache is not None:
        return _cache
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    a = html.index("const BLOB=`") + len("const BLOB=`")
    blob = html[a:html.index("`;", a)]
    puzzles, shapes, rows, sec = [], [], {}, None
    for ln in blob.split("\n"):
        ln = ln.rstrip("\r")
        if not ln:
            continue
        if ln[0] == "§":
            sec = ln[1:]
        elif sec == "SHAPE":
            shapes.append(ln)
        elif sec == "SOLS":
            f = ln.split(",")
            rows[f[0]] = [int(x, 36) for x in f[1:]]
        else:
            f = ln.split(",")
            puzzles.append((sec, f[0], f[1], ",".join(f[6:])))
    lists = {}
    for _sec, pid, rc, _sol in puzzles:
        ban, seen, out = BAN[rc], set(), []
        for n in rows[pid]:
            cs = shapes[n]
            if ban and ban in cs:
                continue
            g = _group(cs)
            if g in seen:
                continue
            seen.add(g)
            out.append(_show(_tree(cs), pid))
        lists[(pid, rc)] = out
    _cache = {"puzzles": puzzles, "lists": lists,
              "shapes": len(shapes), "rows": len(rows),
              "entries": sum(len(v) for v in rows.values())}
    return _cache


def pretty(s):
    """画面の書き方（× ÷ −）。ゲームの pretty() と同じ置き換えを別に書く"""
    return s.replace("*", "×").replace("/", "÷").replace("-", "−")
