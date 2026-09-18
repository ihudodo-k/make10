#!/usr/bin/env python3
"""Make10 問題データ生成パイプライン.

現時点で実装済みのサブコマンド:

    python make10.py generate   # 全探索して solutions に投入
    python make10.py annotate   # shape から特徴量と score (第7章) を再計算して埋める
    python make10.py curate     # 冗長解にフラグを立て、代表解を選出 (第6章)
    python make10.py constrain  # 演算子の使用回数による制約付き問題を生成 (第6-B章)
    python make10.py export     # puzzles からゲーム用 JSON を出力 (第8章)
    python make10.py blob       # docs/index.html の BLOB を組み直す (第8-B章)
    python make10.py verify     # 独立パーサで display 文字列を全件再検証

dump はまだ実装していない。

方針 (CLAUDE.md より):
  * 標準ライブラリのみ (fractions, sqlite3, argparse, math)
  * 浮動小数点は一切使わない。数値は必ず Fraction で厳密に扱う
  * 数式の正準表現は RPN のトークン列 (= 木構造)。表示用文字列はそこから毎回生成する
  * verify は generate とは独立に実装した再帰下降パーサで display を再評価する
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sqlite3
import sys
from fractions import Fraction
from itertools import combinations
from math import factorial

# ---------------------------------------------------------------------------
# 定数 (上限値などの調整はすべてここで行う。コード中に数字を散らさない)
# ---------------------------------------------------------------------------
DB_DEFAULT = "make10.db"
EXPORT_DEFAULT = "make10_puzzles.json"

# export (第8章) で JSON に埋め込むルール表。ゲーム側の計算エンジンと
# 生成側の解釈がずれていないことを起動時に確認させるためのもの。
EXPORT_RULES = {"pow_assoc": "right", "zero_pow_zero": 1,
                "double_factorial": False}

MAX_FACTORIAL_ARG = 12      # 階乗の引数の上限
MAX_EXPONENT_ABS = 24       # 指数の絶対値の上限
MAX_FAC_CHAIN = 2           # 1 つのノードに積み重ねてよい "!" の最大数

# スコアの重み (第7章・暫定版)。ここだけ変えて annotate を流し直せば反映される。
OP_COST = {"+": 1, "-": 1, "*": 2, "/": 3, "^": 5, "!": 4}
SCORE_BONUS = {
    "paren": 1,             # 括弧 1 組につき
    "fraction": 5,          # 途中で分数が現れる (0/1 判定)
    "zero_factorial": 3,    # 0! を使う (気づきにくい。0/1 判定)
    "nested_factorial": 8,  # ( 3! )! のような階乗の 2 回適用 (0/1 判定)
}

# constrain の制約候補 (第6-B章)。ここを変えれば作り直せる
CONSTRAINT_OPS = ("+", "-", "*", "/", "^", "!")
CONSTRAINT_RULE_KINDS = ("=0",)   # 使用禁止のみ (=1「ちょうど1回」は採用しない)
MAX_CONSTRAINTS = 1               # 制約は1個だけ

TARGET = Fraction(10)
BINARY_OPS = ("+", "-", "*", "/", "^")

# 表示用文字列を組み立てるときの優先順位
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
_PREC_FAC = 4
_PREC_ATOM = 5

_FRACS = [Fraction(i) for i in range(10)]
INVALID = object()          # 「有効な値を持たない部分式」を表すセンチネル

# 木ノードの表現:
#   ("num", slot)              slot は 0..3
#   ("fac", child)
#   ("bin", op, left, right)   op は BINARY_OPS のいずれか


# ---------------------------------------------------------------------------
# 式の木構造を列挙する (スロット番号ベース。数字には依存しない)
# ---------------------------------------------------------------------------
_struct_cache: dict = {}


def gen_structures(lo: int = 0, hi: int = 4):
    """スロット lo..hi-1 を固定順で使う式の木を全列挙して返す。

    結果は (lo, hi) でメモ化され、部分木のオブジェクトも共有される。
    これにより後段の評価で id(node) を鍵にした共有キャッシュが効く。
    """
    key = (lo, hi)
    cached = _struct_cache.get(key)
    if cached is not None:
        return cached

    if hi - lo == 1:
        base = [("num", lo)]
    else:
        base = []
        for mid in range(lo + 1, hi):
            lefts = gen_structures(lo, mid)
            rights = gen_structures(mid, hi)
            for left in lefts:
                for right in rights:
                    for op in BINARY_OPS:
                        base.append(("bin", op, left, right))

    out = []
    for node in base:
        cur = node
        out.append(cur)
        for _ in range(MAX_FAC_CHAIN):
            cur = ("fac", cur)
            out.append(cur)

    _struct_cache[key] = out
    return out


# ---------------------------------------------------------------------------
# 評価 (generate 側)。必ず Fraction。無効なら INVALID を返す
# ---------------------------------------------------------------------------
def _apply_bin(op, a, b):
    """二項演算を適用し (値, 使った指数の絶対値) を返す。無効なら (INVALID, 0)。"""
    if op == "+":
        return a + b, 0
    if op == "-":
        return a - b, 0
    if op == "*":
        return a * b, 0
    if op == "/":
        if b == 0:
            return INVALID, 0
        return a / b, 0
    # op == "^"
    if b.denominator != 1:            # 指数は整数のみ
        return INVALID, 0
    e = b.numerator
    ae = -e if e < 0 else e
    if ae > MAX_EXPONENT_ABS:
        return INVALID, 0
    if a == 0:
        if e == 0:
            return Fraction(1), 0     # 0 ^ 0 = 1
        if e < 0:
            return INVALID, 0         # 0 の負冪は無効
        return Fraction(0), ae
    return a ** e, ae


def build_evaluator(digits):
    """ev(node) -> (値|INVALID, max_fac_arg, max_exp_abs, uses_fraction) を返す。

    結果は id(node) でメモ化するので、共有された部分木は 1 回しか評価しない。

    memo の値には結果だけでなくノード自身も一緒に入れておく (memo[id(node)] =
    (node, res))。id() はメモリアドレスなので、木が解放されると別の木が同じ
    アドレスに配置され、古いキャッシュを誤って引いてしまう。ノードへの参照を
    memo が保持し続けることで、評価器が生きている間はその木も解放されず、
    アドレス衝突が起きない。
    """
    memo: dict = {}

    def ev(node):
        hit = memo.get(id(node))
        if hit is not None:
            return hit[1]

        tag = node[0]
        if tag == "num":
            res = (_FRACS[digits[node[1]]], 0, 0, False)
        elif tag == "fac":
            cv, cfa, cea, cuf = ev(node[1])
            if (cv is INVALID or cv.denominator != 1
                    or cv.numerator < 0 or cv.numerator > MAX_FACTORIAL_ARG):
                res = (INVALID, 0, 0, False)
            elif cv.numerator == 1 or cv.numerator == 2:
                # 1! = 1, 2! = 2 で値が変わらない。内側の階乗結果が 1 や 2 に
                # なる繰り返し適用 (例: (0!)!) も同じく無意味なので生成時に枝刈りする。
                # 値が変わる ( 3! )! = 720 は cv.numerator == 6 なので残る。
                res = (INVALID, 0, 0, False)
            else:
                v = Fraction(factorial(cv.numerator))
                arg = cv.numerator
                res = (v, cfa if cfa > arg else arg, cea, cuf)
        else:  # "bin"
            av, afa, aea, auf = ev(node[2])
            bv, bfa, bea, buf = ev(node[3])
            if av is INVALID or bv is INVALID:
                res = (INVALID, 0, 0, False)
            else:
                v, ae = _apply_bin(node[1], av, bv)
                if v is INVALID:
                    res = (INVALID, 0, 0, False)
                else:
                    mfa = afa if afa > bfa else bfa
                    mea = aea if aea > bea else bea
                    if ae > mea:
                        mea = ae
                    res = (v, mfa, mea,
                           auf or buf or (v.denominator != 1))

        memo[id(node)] = (node, res)
        return res

    return ev


def evaluate(node, digits):
    """単発評価 (テスト・簡易利用向け)。"""
    return build_evaluator(digits)(node)


# ---------------------------------------------------------------------------
# 木 -> 表示用文字列 / shape(スロットRPN) / 演算子カウント
# ---------------------------------------------------------------------------
def _render(node, numstr):
    tag = node[0]
    if tag == "num":
        return numstr(node[1]), _PREC_ATOM
    if tag == "fac":
        t, p = _render(node[1], numstr)
        # 子の優先順位が階乗より低いときはもちろん、階乗と同じとき (子も階乗)
        # も括弧で囲む。"!!" と並べると二重階乗と紛らわしいため必ず ( 3! )! と書く
        if p <= _PREC_FAC:
            t = "( " + t + " )"
        return t + "!", _PREC_FAC

    op = node[1]
    p = _PREC[op]
    lt, lp = _render(node[2], numstr)
    rt, rp = _render(node[3], numstr)
    # 左の子: 優先順位が低ければ括弧。^ は右結合なので同順位の左も括弧
    if lp < p or (lp == p and op == "^"):
        lt = "( " + lt + " )"
    # 右の子: 優先順位が低ければ括弧。左結合の演算子 (+ - * /) は同順位の右も
    # 括弧を付ける (でないと '4 * (9 / 4)' が '4 * 9 / 4' になり、標準の左結合で
    # 読み直すと別の木になってしまう。^ だけは右結合なので同順位の右は括弧不要)
    if rp < p or (rp == p and op != "^"):
        rt = "( " + rt + " )"
    return lt + " " + op + " " + rt, p


def render_display(node, digits):
    """人間が読む式。例: '( 0! + 0! + 0! )! + 4'"""
    return _render(node, lambda s: str(digits[s]))[0]


def render_shape(node):
    """スロット番号の RPN。例: 'n0 ! n1 ! + n2 ! + ! n3 +'"""
    out = []

    def walk(n):
        tag = n[0]
        if tag == "num":
            out.append("n%d" % n[1])
        elif tag == "fac":
            walk(n[1])
            out.append("!")
        else:
            walk(n[2])
            walk(n[3])
            out.append(n[1])

    walk(node)
    return " ".join(out)


def parse_shape(shape):
    """スロット RPN 文字列を木ノードに戻す (render_shape の逆)。

    例: 'n0 ! n1 ! + n2 ! + ! n3 +'
        -> ('bin', '+', ('fac', ('bin', '+', ...)), ('num', 3))
    """
    st = []
    for tok in shape.split():
        if tok[0] == "n":
            st.append(("num", int(tok[1:])))
        elif tok == "!":
            st.append(("fac", st.pop()))
        else:  # BINARY_OPS のいずれか
            right = st.pop()
            left = st.pop()
            st.append(("bin", tok, left, right))
    if len(st) != 1:
        raise ValueError("malformed shape RPN: %r" % (shape,))
    return st[0]


def count_ops(node):
    c = {"+": 0, "-": 0, "*": 0, "/": 0, "^": 0, "fac": 0}

    def w(n):
        tag = n[0]
        if tag == "num":
            return
        if tag == "fac":
            c["fac"] += 1
            w(n[1])
            return
        c[n[1]] += 1
        w(n[2])
        w(n[3])

    w(node)
    return c


def iter_nodes(node):
    """木の全ノードを行きがけ順で列挙する。"""
    yield node
    if node[0] == "fac":
        yield from iter_nodes(node[1])
    elif node[0] == "bin":
        yield from iter_nodes(node[2])
        yield from iter_nodes(node[3])


def has_operator(node):
    """部分式が演算子 (二項演算 or 階乗) を 1 つ以上含むか。"""
    return node[0] != "num"


def score_solution(tree, val, cnt_paren, uses_fraction):
    """第7章 (暫定) の解スコア = 演算子コスト合計 + ボーナス合計。

    val(node) は node の値 (Fraction) を返す関数。0! 判定に使う。
    ボーナスの zero_factorial / nested_factorial は「その手筋に気づけたか」を
    測る 0/1 判定 (出現回数では数えない)。
    """
    c = count_ops(tree)
    total = (c["+"] * OP_COST["+"] + c["-"] * OP_COST["-"]
             + c["*"] * OP_COST["*"] + c["/"] * OP_COST["/"]
             + c["^"] * OP_COST["^"] + c["fac"] * OP_COST["!"])

    has_zero_fac = False
    has_nested_fac = False
    for n in iter_nodes(tree):
        if n[0] == "fac":
            if n[1][0] == "fac":
                has_nested_fac = True
            cv = val(n[1])
            if cv is not INVALID and cv == 0:
                has_zero_fac = True

    total += SCORE_BONUS["paren"] * cnt_paren
    if uses_fraction:
        total += SCORE_BONUS["fraction"]
    if has_zero_fac:
        total += SCORE_BONUS["zero_factorial"]
    if has_nested_fac:
        total += SCORE_BONUS["nested_factorial"]
    return total


# ---------------------------------------------------------------------------
# SQLite スキーマ / generate
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS solutions (
    id             INTEGER PRIMARY KEY,
    problem_id     TEXT    NOT NULL,
    shape          TEXT    NOT NULL,
    display        TEXT    NOT NULL,
    cnt_add        INTEGER NOT NULL,
    cnt_sub        INTEGER NOT NULL,
    cnt_mul        INTEGER NOT NULL,
    cnt_div        INTEGER NOT NULL,
    cnt_pow        INTEGER NOT NULL,
    cnt_fac        INTEGER NOT NULL,
    cnt_paren      INTEGER NOT NULL,
    max_fac_arg    INTEGER NOT NULL,
    max_exp_abs    INTEGER NOT NULL,
    uses_fraction  INTEGER NOT NULL,
    score          INTEGER,
    is_redundant   INTEGER DEFAULT 0,
    redundant_why  TEXT,
    is_repr        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS problems (
    problem_id       TEXT PRIMARY KEY,
    solution_count   INTEGER,
    min_score        INTEGER,
    max_score        INTEGER,
    repr_solution_id INTEGER
);

-- 制約付き問題 (第6-B章)。1 つの problem_id から複数の puzzle が生まれる
CREATE TABLE IF NOT EXISTS puzzles (
    id                  INTEGER PRIMARY KEY,
    problem_id          TEXT    NOT NULL,
    rules               TEXT    NOT NULL,
    rule_count          INTEGER NOT NULL,
    survivor_count      INTEGER NOT NULL,
    repr_survivor_count INTEGER NOT NULL,
    example_solution_id INTEGER,
    min_score           INTEGER,
    base_min_score      INTEGER,
    harder_by           INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sol_problem ON solutions(problem_id);
CREATE INDEX IF NOT EXISTS idx_sol_shape   ON solutions(shape);
CREATE INDEX IF NOT EXISTS idx_puz_problem ON puzzles(problem_id);
"""

_INSERT = """
INSERT INTO solutions
 (problem_id, shape, display, cnt_add, cnt_sub, cnt_mul, cnt_div, cnt_pow,
  cnt_fac, cnt_paren, max_fac_arg, max_exp_abs, uses_fraction)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def _connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn):
    conn.executescript(_SCHEMA)
    conn.commit()


def generate_into(db_path, min_id=0, max_id=9999, progress=None):
    """0000..9999 の各問題について式の木を全列挙し、10 になるものを保存する。

    冪等: 対象 problem_id の既存行を削除してから挿入する。
    冗長解もこの段階では全部保存する (curate で後から除外する)。

    戻り値: {"rows": 挿入した行数の合計, "duplicate_display_hits": 異常件数}
    """
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        structures = gen_structures(0, 4)

        total_rows = 0
        duplicate_display_hits = 0

        for pid_int in range(min_id, max_id + 1):
            pid = "%04d" % pid_int
            digits = [int(ch) for ch in pid]
            ev = build_evaluator(digits)

            seen_shapes = set()
            seen_displays = set()
            rows = []
            for st in structures:
                val, mfa, mea, uf = ev(st)
                if val is INVALID or val != TARGET:
                    continue
                shape = render_shape(st)
                if shape in seen_shapes:      # 同一 ProblemID 内で shape 重複は 1 件
                    continue
                seen_shapes.add(shape)

                disp = render_display(st, digits)
                # _render は忠実出力 (同順位の右の子には必ず括弧を付ける。^ の
                # 右だけ右結合なので例外) なので、異なる木が同じ display 文字列に
                # なることは原理的に無いはず。ここでヒットしたら _render の
                # 不備を疑う。安全網として残し、件数だけ数えて報告する。
                if disp in seen_displays:
                    duplicate_display_hits += 1
                    continue
                seen_displays.add(disp)

                c = count_ops(st)
                rows.append((
                    pid, shape, disp,
                    c["+"], c["-"], c["*"], c["/"], c["^"], c["fac"],
                    disp.count("("), mfa, mea, 1 if uf else 0,
                ))

            conn.execute("DELETE FROM solutions WHERE problem_id = ?", (pid,))
            conn.executemany(_INSERT, rows)
            conn.commit()
            total_rows += len(rows)
            if progress:
                progress(pid, len(rows))

        return {"rows": total_rows, "duplicate_display_hits": duplicate_display_hits}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# verify : display 文字列を独立実装の再帰下降パーサで再評価する
# ---------------------------------------------------------------------------
#
# 文法 (^ は右結合、! は ^ より強い後置演算子):
#
#   expr    := term  (('+' | '-') term)*
#   term    := power (('*' | '/') power)*
#   power   := postfix ('^' power)?
#   postfix := atom '!'?     連続する '!' (括弧を挟まない '!!') は構文エラー。
#                            二重階乗と紛らわしいので ( 3! )! と書かねばならない
#   atom    := DIGIT | '(' expr ')'
#
class VerifyError(Exception):
    pass


def _tokenize(s):
    toks = []
    for ch in s:
        if ch == " ":
            continue
        if ch.isdigit() or ch in "()+-*/^!":
            toks.append(ch)
        else:
            raise VerifyError("bad character %r in %r" % (ch, s))
    return toks


class _Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0
        self.slot = 0    # parse_tree 用: 出現した digit を左から 0,1,2,3 と数える

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        ch = self.t[self.i]
        self.i += 1
        return ch

    def expect(self, ch):
        if self.peek() != ch:
            raise VerifyError("expected %r, got %r" % (ch, self.peek()))
        self.i += 1


def _pow(a, b):
    if b.denominator != 1:
        raise VerifyError("non-integer exponent")
    e = b.numerator
    if abs(e) > MAX_EXPONENT_ABS:
        raise VerifyError("exponent out of range")
    if a == 0:
        if e == 0:
            return Fraction(1)
        if e < 0:
            raise VerifyError("zero to a negative power")
        return Fraction(0)
    return a ** e


def _fac(v):
    if v.denominator != 1:
        raise VerifyError("factorial of a non-integer")
    n = v.numerator
    if n < 0:
        raise VerifyError("factorial of a negative number")
    if n > MAX_FACTORIAL_ARG:
        raise VerifyError("factorial argument out of range")
    return Fraction(factorial(n))


def _p_expr(p):
    v = _p_term(p)
    while p.peek() == "+" or p.peek() == "-":
        op = p.take()
        r = _p_term(p)
        v = v + r if op == "+" else v - r
    return v


def _p_term(p):
    v = _p_pow(p)
    while p.peek() == "*" or p.peek() == "/":
        op = p.take()
        r = _p_pow(p)
        if op == "*":
            v = v * r
        else:
            if r == 0:
                raise VerifyError("division by zero")
            v = v / r
    return v


def _p_pow(p):
    base = _p_postfix(p)
    if p.peek() == "^":
        p.take()
        base = _pow(base, _p_pow(p))     # 右結合
    return base


def _p_postfix(p):
    v = _p_atom(p)
    if p.peek() == "!":
        p.take()
        v = _fac(v)
        if p.peek() == "!":
            # '3!!' のような連続した '!'。二重階乗記法と混同されるため拒否する。
            # 階乗を 2 回かけたいときは '( 3! )!' と括弧で明示する。
            raise VerifyError("consecutive '!' (double-factorial notation); "
                              "write '( x! )!' instead")
    return v


def _p_atom(p):
    ch = p.peek()
    if ch == "(":
        p.take()
        v = _p_expr(p)
        p.expect(")")
        return v
    if ch is not None and ch.isdigit():
        p.take()
        return _FRACS[int(ch)]
    raise VerifyError("unexpected token %r" % (ch,))


def parse_eval(s):
    p = _Parser(_tokenize(s))
    v = _p_expr(p)
    if p.i != len(p.t):
        raise VerifyError("unexpected trailing tokens in %r" % (s,))
    return v


# ---------------------------------------------------------------------------
# verify の往復チェック用: display を木として読み直すパーサ。
#
# 12章の教訓 (検証は生成とは独立に実装する) に従い、render_display / _render /
# _PREC には一切依存しない。文法は上の _p_* (値を返す版) と同じものを独立に
# 再実装している。num ノードは digit の値ではなく「左から何番目の digit か」
# (0..3) を持たせ、parse_shape() が返す木 (num はスロット番号) とそのまま
# == 比較できるようにしてある。
# ---------------------------------------------------------------------------
def _pt_expr(p):
    n = _pt_term(p)
    while p.peek() == "+" or p.peek() == "-":
        op = p.take()
        n = ("bin", op, n, _pt_term(p))
    return n


def _pt_term(p):
    n = _pt_pow(p)
    while p.peek() == "*" or p.peek() == "/":
        op = p.take()
        n = ("bin", op, n, _pt_pow(p))
    return n


def _pt_pow(p):
    n = _pt_postfix(p)
    if p.peek() == "^":
        p.take()
        n = ("bin", "^", n, _pt_pow(p))     # 右結合
    return n


def _pt_postfix(p):
    n = _pt_atom(p)
    if p.peek() == "!":
        p.take()
        n = ("fac", n)
        if p.peek() == "!":
            raise VerifyError("consecutive '!' (double-factorial notation); "
                              "write '( x! )!' instead")
    return n


def _pt_atom(p):
    ch = p.peek()
    if ch == "(":
        p.take()
        n = _pt_expr(p)
        p.expect(")")
        return n
    if ch is not None and ch.isdigit():
        p.take()
        n = ("num", p.slot)
        p.slot += 1
        return n
    raise VerifyError("unexpected token %r" % (ch,))


def parse_tree(s):
    """display を独立文法で読み、num をスロット番号 (出現順 0..3) にした木を返す。"""
    p = _Parser(_tokenize(s))
    n = _pt_expr(p)
    if p.i != len(p.t):
        raise VerifyError("unexpected trailing tokens in %r" % (s,))
    return n


def run_verify(db_path):
    """(検証件数, 失敗リスト) を返す。失敗リストは (id, pid, display, 理由)。

    4つ目の検査 (往復チェック): display を独立文法で読み直した木が、
    shape (正準表現) から復元した木と構造として一致すること。値が一致しても
    木が違えば失敗にする。12章の教訓どおり render_display / _render / _PREC は
    一切使わない (parse_tree は独立実装、parse_shape は既存の shape パーサ)。
    """
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, problem_id, shape, display FROM solutions ORDER BY id")
        total = 0
        failures = []
        for sid, pid, shape, disp in cur:
            total += 1
            try:
                v = parse_eval(disp)
            except VerifyError as e:
                failures.append((sid, pid, disp, "parse/eval error: %s" % e))
                continue
            if v != TARGET:
                failures.append((sid, pid, disp, "evaluates to %s, not 10" % v))
                continue
            nums = [t for t in _tokenize(disp) if t.isdigit()]
            if nums != list(pid):
                failures.append((sid, pid, disp,
                                 "digit sequence %s != problem id %s"
                                 % ("".join(nums), pid)))
                continue
            try:
                disp_tree = parse_tree(disp)
            except VerifyError as e:
                failures.append((sid, pid, disp,
                                 "roundtrip parse error: %s" % e))
                continue
            shape_tree = parse_shape(shape)
            if disp_tree != shape_tree:
                failures.append((sid, pid, disp,
                                 "roundtrip mismatch: shape=%r (tree=%r) "
                                 "parse(display)=%r"
                                 % (shape, shape_tree, disp_tree)))
        return total, failures
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# annotate : shape から特徴量を再計算して solutions に埋める
# ---------------------------------------------------------------------------
#
# generate も同じ列を埋めているが、「何を特徴量とみなすか」を後から変えても
# 高価な全探索をやり直さずに済むよう、annotate は正準表現 (shape) だけを入力に
# 取り、そこから機械的に再計算する。冪等: 何度流しても同じ値になる。
#
# score は第7章 (暫定版) に従い score_solution() で計算して埋める。
# 重みは OP_COST / SCORE_BONUS。変えたら annotate を流し直すだけで反映される。
#
_ANNOTATE_UPDATE = """
UPDATE solutions SET
  cnt_add = ?, cnt_sub = ?, cnt_mul = ?, cnt_div = ?, cnt_pow = ?, cnt_fac = ?,
  cnt_paren = ?, max_fac_arg = ?, max_exp_abs = ?, uses_fraction = ?, score = ?
WHERE id = ?
"""


def run_annotate(db_path, progress=None):
    """全 solutions の特徴量列と score を shape / display から再計算する。件数を返す。"""
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT id, problem_id, shape, display FROM solutions ORDER BY id"
        ).fetchall()

        updates = []
        for sid, pid, shape, disp in rows:
            digits = [int(ch) for ch in pid]
            tree = parse_shape(shape)
            ev = build_evaluator(digits)
            val, mfa, mea, uf = ev(tree)
            if val is INVALID or val != TARGET:
                raise RuntimeError(
                    "annotate: id=%d shape=%r no longer evaluates to 10" %
                    (sid, shape))
            c = count_ops(tree)
            cnt_paren = disp.count("(")
            score = score_solution(tree, lambda n, _ev=ev: _ev(n)[0],
                                   cnt_paren, uf)
            updates.append((
                c["+"], c["-"], c["*"], c["/"], c["^"], c["fac"],
                cnt_paren, mfa, mea, 1 if uf else 0, score,
                sid,
            ))

        conn.executemany(_ANNOTATE_UPDATE, updates)
        conn.commit()
        if progress:
            progress(len(updates))
        return len(updates)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# curate : 冗長解にフラグを立て、代表解を選出する (第6章)
# ---------------------------------------------------------------------------
#
# 段階。前段で is_redundant が立った解は後段の対象にしない。
#   6-1  無効化される部分式 (結果に影響しない x。x は演算子を1つ以上含む)
#   6-2  恒等演算 (値を変えない演算)
#   6-3  6-1/6-2 を通過した解を「実質的に同じ形」でグループ化し代表1件に圧縮
#   6-4  6-1/6-2 は problem_id ごとに判定し、生き残りが1つ以上あるときだけ適用する。
#        全滅する問題は 6-3 の読みやすさ順で1件だけ残す (6-1/6-2 より優先)
#
# redundant_why は "6-1: ..." / "6-2: ..." / "6-3: ..." / "6-4: ..." で始め、後から
# どのルールで何件消えたか集計できるようにする。


def _nullified_by_pattern(tree, val):
    """6-1 の補完: 部分式そのものが結果に影響しない形を、パターンで捕まえる。

        x * 0 / 0 * x  ,  x ^ 0  ,  1 ^ x

    **これは列挙の名残ではなく、必要な補完である** (5.2 で位置づけを整理)。
    主判定の classify_nullified() は「その桁を別の値に替えても値が変わらないか」
    を見るが、定義域が狭い部分式ではその桁を動かせず判定できない。例:

        3639  ( 3! )! ^ ( 6 - 3! ) + 9      ( = 720 ^ 0 + 9 )
        5430  5 + ( 4 + ( 3! )! ^ 0 )

    `X ^ 0` は X が何であれ 1 なので X は寄与していないが、`( d! )!` は d=3 以外
    すべて無効 (0!/1!/2! は生成時に枝刈り、4! = 24 から 24! は上限超え) なので、
    桁を差し替える判定では「有効な差し替えが無い」になってしまう。実測でこの型の
    取りこぼしが 2,100 本あった。**桁単位の判定は「差し替えられる桁」にしか使えず、
    定義域が狭い部分式は部分式単位で見るしかない。** 両方を OR で使う。
    """
    for n in iter_nodes(tree):
        if n[0] != "bin":
            continue
        op, a, b = n[1], n[2], n[3]
        if op == "*":
            if val(a) == 0:
                return "6-1: 0 * x"
            if val(b) == 0:
                return "6-1: x * 0"
        elif op == "/":
            if val(a) == 0:
                # 0 / x は 0。x は「0 でなければ何でもよい」数字で、0 ^ x と
                # まったく同じ事情でここに置いてある ―― 桁単位の一般判定では
                # 除数の桁を動かせないことがあるため捕まらない。例:
                #     0319  0 / ( 3! )! + 1 + 9
                # 除数 ( 3! )! = 720 が何であっても結果は 0 なので 3 は消えて
                # いるが、( d! )! は d=3 以外すべて無効なので差し替えられない。
                # 3639 の X ^ 0 と同じ「部分式としては潰れているが桁単位では
                # 判定できない」ケース。
                # **元の 6-1 は / を一切見ていなかった。** 5.1 までは 0 * x が
                # 葉どうしで素通りしていたので 0 / x が解答例に選ばれる理由が無く、
                # 穴が露出していなかっただけである。
                # 除数が 0 になる解は存在しない (_apply_bin が INVALID を返すので
                # 生成されない。実測: 割り算を含む 94,573 解で除数 0 のノードは
                # 0 件)。したがって 0 / 0 を気にする必要はない
                return "6-1: 0 / x"
        elif op == "^":
            if val(b) == 0:
                # ここは 0 ^ 0 も通る。x ^ 0 が値 1 になるのは底によらないため、
                # 底が 0 かどうかで分ける必要がない（0 ^ 0 を別途足さないこと）
                return "6-1: x ^ 0"
            if val(a) == 1:
                return "6-1: 1 ^ x"
            if val(a) == 0:
                # 0 ^ x (x != 0) は 0。x は「0 でなければ何でもよい」数字で、
                # 0 / x と実質同じだが、**桁単位の一般判定では捕まらない** ――
                # x を 0 に差し替えると 0 ^ 0 = 1 になって値が変わるため、
                # 規則上は「寄与している」と出てしまう。捕まらない理由は
                # 「0 ^ 0 が定義されていて 0 / 0 が未定義」という定義の都合だけで、
                # プレイヤーから見れば同じ。3639 と同じく部分式としては潰れて
                # いるので、パターン側で受け持つ。
                # **一般判定の側に例外を入れないこと** ―― 「差し替えで値が
                # 変わるか」という規則に例外を作ると基準が濁る
                return "6-1: 0 ^ x"
    return None


def classify_nullified(tree, digits, base):
    """6-1: 数字を潰している解か。理由文字列 or None を返す。

    **判定の基準 (5.2 で承認):**

        その数字を別の値に変えても式の値が変わらないなら、その数字は寄与していない

    4 つの数字の位置を順に取り、その位置だけを 0〜9 の他の値に差し替えて
    評価し、**有効に評価できた差し替えのすべてで結果が変わらなければ**
    その数字は潰されていると判定する。1 つでも潰れていれば解ごと 6-1 とする。

    **なぜパターンの列挙をやめたか。** 5.1 までは `0 * x` / `x * 0` / `x ^ 0` /
    `1 ^ x` の 4 つを列挙し、しかも `and has_operator(...)` 付きで葉どうしには
    発火しなかった。そこを 6-2 の `x * 1` が偶然せき止めていたが、6-2 を廃止すると
    `1 ^ 6` が露出し、葉に広げると今度は `0 / x` へ、それも塞げば `0 ^ x` へ、と
    解答例が未対応の形へ移り続けた。**パターンを足す限り「次に何が漏れているか」が
    分からない。** そこで基準そのものを実装した。

    **評価できない差し替えは判定から除く** (0 除算、階乗の引数が負や非整数や上限超え
    など)。基準は式の「値」についての話で、「評価できない」は値ではないため。
    これを「値が違う」と数えると、0 除算を避けるだけの除数が寄与を主張できてしまう
    (実測で旧判定の取りこぼしが 26,764 本に膨らんだ)。逆に「有効な差し替えが 1 つも
    無い」場合を「潰されている」と数えるのも誤りで、

        3343  ( 3! )! / ( 3! * 4 * 3 )

    の最初の 3 のように、**差し替えられないだけで式の値を決めている**数字を
    誤って落とす (実測 27,507 本に誤検出が混ざった)。
    「差し替えられない」と「寄与していない」は別物である。よって、有効な差し替えが
    1 つも無い桁は「判定できない」として寄与している側に倒す。その取りこぼしは
    _nullified_by_pattern() が部分式単位で補う。

    **`0 ^ 0` に例外を設けないこと。** 5.2 の途中で「両辺とも 0 でなければ成立
    しないので寄与している」として除外したが、これは**指数側だけを見て底側を
    見落とした誤りだった**。底を何に変えても `x ^ 0 = 1` なので底は寄与していない。
    基準に照らせば捕まるのが正しい。数字を潰す形しか無い問題は解が全滅するが、
    6-4 (problem 単位) と 6-5 (puzzle 単位) の救済に任せる。実例は 0075
    (数字 0,0,7,5) で、6 解すべてが `0 * 7` などで 7 を潰し、6-4 が
    `( 0! + ( 0 * 7 )! ) * 5` を 1 件だけ残す。0009 (数字 0,0,0,9) は `0!` で
    1 を作れるので全滅しない (562 解中 189 解が非冗長)。

    **`0 ^ x` は単独では 6-1 に該当しない。** 「0 ^ 7 は 7 を何に変えても 0」は
    誤りで、指数を 0 にすると `0 ^ 0 = 1` になり値が変わる。底も指数も寄与して
    いる。一般判定へ切り替える理由は「0 ^ x という穴がある」ことではなく、
    **「パターン列挙では何が漏れているか分からない」**ことにある。

    なお、判定自体を部分式単位に一般化する案 (各ノードの値を上書きして結果が
    変わるかを見る) も検討したが、(桁単位の判定 ∪ パターン) で取りこぼしが 0 本に
    なったため採らなかった。**将来またパターン列挙が破綻したときの逃げ道として
    選択肢は存在する。**
    """
    for pos in range(len(digits)):
        orig = digits[pos]
        contributes = False
        seen_valid = False
        for d in range(10):
            if d == orig:
                continue
            sub = list(digits)
            sub[pos] = d
            v = build_evaluator(sub)(tree)[0]
            if v is INVALID:
                continue                  # 評価できない差し替えは判定から除く
            seen_valid = True
            if v != base:
                contributes = True
                break
        if not contributes and seen_valid:
            return "6-1: digit#%d not contributing" % pos
    return None


def classify_identity(tree, val):
    """6-2: 値を変えない演算を含むか。理由文字列 or None を返す。

    **5.2 でこの判定は使わなくなった (run_curate から呼んでいない)。**
    関数を残してあるのは、また同じ判断をしないための記録として。
    理由: 数字 4 つは全部使わなければならないので、0 を消費する最も自然な形が
    `+ 0` である。それを「値を変えない」として除外すると、たとえば 0025 の
    解答例が `0 + 0 + 2 * 5` (score 4) ではなく `0 - ( 0 - 2 * 5 )` (score 5)
    になり、人間が書かない式が解答例になってしまった (実測 2,423/9,161 = 26.4%
    の問題が該当)。6-1 (classify_nullified) は逆に残す必要がある ―― 外すと
    1279 が `1 ^ ( 2 + 7 ) + 9` になり、`( 2 + 7 )` が丸ごと 1 に潰れて
    2 と 7 が式から消え、4 数字を使う問題として成立しないため。

        x + 0 / 0 + x , x - 0 , x * 1 / 1 * x , x / 1 , x ^ 1
        値が 1 または 2 のものへの階乗 (1! = 1, 2! = 2)

    第6章の注記どおり、単位元が右にある形だけでなく左にある形
    (`0 + x`, `1 * x`) も対象にする (数学的に同じなので片側だけ拾うのは中途半端)。
    ここで全滅しても 6-4 が歯止めになる。
    `-` `/` `^` は単位元が左に来ないので右側だけ判定する。
    0! = 1 は値が変わるので対象外。generate で既に枝刈り済みでもある。
    """
    for n in iter_nodes(tree):
        if n[0] == "fac":
            v = val(n[1])
            if v == 1:
                return "6-2: 1!"
            if v == 2:
                return "6-2: 2!"
        elif n[0] == "bin":
            op, a, b = n[1], n[2], n[3]
            if op == "+" and (val(a) == 0 or val(b) == 0):
                return "6-2: x + 0"
            if op == "-" and val(b) == 0:
                return "6-2: x - 0"
            if op == "*" and (val(a) == 1 or val(b) == 1):
                return "6-2: x * 1"
            if op == "/" and val(b) == 1:
                return "6-2: x / 1"
            if op == "^" and val(b) == 1:
                return "6-2: x ^ 1"
    return None


def _paren_structure(shape):
    """6-3 のグループ化キーに使う『括弧構造』.

    二項演算子の種類を伏せた RPN。木の結合の仕方 (どこがまとまっているか) と
    階乗の位置だけを表す。演算子の種類の違いは、グループ化キーの
    (加減算の回数, 乗除算の回数, 累乗の回数, 階乗の回数) の側で吸収する。
    """
    return " ".join(
        "@" if t in ("+", "-", "*", "/", "^") else t for t in shape.split()
    )


def _repr_sort_key(row):
    """代表解の選び方 (第6章 6-3。プレイヤーにとって読みやすい順)。

    row = (id, problem_id, shape, display, cnt_add, cnt_sub, cnt_mul,
           cnt_div, cnt_pow, cnt_fac, cnt_paren)
    """
    return (
        row[10],        # 1. 括弧が少ない
        row[7],         # 2. 割り算が少ない
        row[5],         # 3. 引き算が少ない
        len(row[3]),    # 4. 表示文字列が短い
        row[0],         # (安定させるための最終タイブレーク)
    )


# 列: 0 id  1 problem_id  2 shape  3 display  4 cnt_add  5 cnt_sub  6 cnt_mul
#     7 cnt_div  8 cnt_pow  9 cnt_fac  10 cnt_paren  11 score
# score は 6-4 の救済で「最も簡単な解」を選ぶために要る (5.2)。末尾に足したので
# _repr_sort_key など既存の添字は変わらない
_CURATE_COLS = ("SELECT id, problem_id, shape, display, cnt_add, cnt_sub, "
                "cnt_mul, cnt_div, cnt_pow, cnt_fac, cnt_paren, score "
                "FROM solutions")


def _rescue_sort_key(row):
    """6-4 の救済で残す 1 件の選び方 (5.2)。_CURATE_COLS の行を取る。

    **順序は _example_key と同じ「スコア最小 -> 読みやすさ -> id」。**
    救済されるのは「その problem の解が全部 数字を潰す形」という問題で、
    どうせ潰す形しか無いなら、その中で最も簡単なものを見せるべきである。
    5.2 の途中までは _repr_sort_key (読みやすさだけ) で選んでいたため、
    439 件中 171 件で最小スコアでない解を救済していた。例:

        9949  採用 15 ( 9 - 9 )! ^ 4 + 9   / 最小 10 ( 9 / 9 ) ^ 4 + 9

    救済解はそのまま解答例になり min_score にもなるので、難易度が過大に付き、
    ヒントも余計に難しい式を見せていた。6-5 / 6-6 と基準を揃える。
    """
    return (row[11], row[10], row[7], row[5], len(row[3]), row[0])


def run_curate(db_path, progress=None):
    """冗長解にフラグを立て代表解を選出する。集計 dict を返す。

    返り値: {"total", "kept", "n_6_1", "n_6_2", "n_6_3", "n_6_4", "problems"}

    **5.2 で 6-2 を廃止し、6-3 の位置づけを変えた。**

      is_redundant = 1  ... 6-1 だけ (結果に影響しない部分式を含む = 解ではない)
      is_repr      = 1  ... 6-3 の各グループの代表 (重複を圧縮した一覧に出す 1 本)
      6-3 で圧縮された行は is_redundant = 0 のまま (redundant_why にだけ痕跡を残す)

    6-3 を is_redundant から外した理由: 6-3 は「実質同じ形が並ぶのを避ける」ための
    圧縮で、問題単位でグループ化する。一方 constrain は制約でパズル単位に解を絞る。
    6-3 を冗長扱いにすると、制約を満たす唯一の解が「制約を満たさない代表」に
    圧縮されて消え、解答例の score が上がる (実測 143 件) / パズルが 1 つも解を
    持てず消える (実測 247 件) という壊れ方をした。母集団から 6-3 を外すと
    score は下がるか同じにしかならない (実測 悪化 0 件・消失 0 件)。

    6-1 は problem_id ごとに判定し、その問題に生き残りが1つ以上あるときだけ
    実際に適用する (第6章 6-4)。全滅する問題は 6-3 の読みやすさ順で1件だけ残し、
    その行の redundant_why に "6-4: kept (only solution)" を記録する。
    6-2 の廃止後、この救済は実測で 0 件になったが、6-1 だけで全滅する問題が
    将来のデータで出ないとは言えないので歯止めとして残す。
    """
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        # 冪等性のため毎回リセットしてから付け直す
        conn.execute(
            "UPDATE solutions SET is_redundant = 0, redundant_why = NULL, "
            "is_repr = 0")

        rows = conn.execute(_CURATE_COLS + " ORDER BY id").fetchall()

        by_pid = {}
        for r in rows:
            by_pid.setdefault(r[1], []).append(r)

        flags = {}        # id -> redundant_why (is_redundant = 1 になる行 = 6-1)
        traces = {}       # id -> redundant_why (6-3 で圧縮。is_redundant = 0)
        forced = {}       # id -> redundant_why (6-4 で残す行。is_redundant = 0)
        repr_ids = []

        for pid, prs in by_pid.items():
            digits = [int(ch) for ch in pid]
            ev = build_evaluator(digits)

            def val(n, _ev=ev):
                return _ev(n)[0]

            reasons = {}      # id -> 6-1 の理由 or None
            survivors = []
            for r in prs:
                tree = parse_shape(r[2])
                base = val(tree)
                # 6-1 は 2 つの判定の OR (5.2)。桁単位の一般判定が主で、定義域が
                # 狭くて桁を動かせない部分式をパターン側が補う。どちらの docstring
                # にも、なぜ両方要るかを書いてある。
                # 6-2 (classify_identity) は 5.2 で廃止した。理由は同関数の docstring
                reason = (classify_nullified(tree, digits, base)
                          or _nullified_by_pattern(tree, val))
                reasons[r[0]] = reason
                if reason is None:
                    survivors.append(r)

            if survivors:
                # 通常ルート: 6-1 を適用し、生き残りを 6-3 で代表 1 件に圧縮する
                for r in prs:
                    if reasons[r[0]] is not None:
                        flags[r[0]] = reasons[r[0]]
                groups = {}
                for r in survivors:
                    key = (r[4] + r[5], r[6] + r[7], r[8], r[9],
                           _paren_structure(r[2]))
                    groups.setdefault(key, []).append(r)
                for members in groups.values():
                    members.sort(key=_repr_sort_key)
                    keep = members[0]
                    repr_ids.append(keep[0])
                    for m in members[1:]:
                        # 5.2: 6-3 は is_redundant を立てない (痕跡だけ残す)。
                        # 解答例と min_score の母集団はここを通した後の
                        # is_redundant = 0、つまり 6-1 を除いた全解になる
                        traces[m[0]] = "6-3: compressed into id=%d" % keep[0]
            else:
                # 6-4: このままでは解が全滅する。潰す形しか無いので、
                # その中で最も簡単な 1 件を残す（_rescue_sort_key）
                prs_sorted = sorted(prs, key=_rescue_sort_key)
                keep = prs_sorted[0]
                repr_ids.append(keep[0])
                forced[keep[0]] = "6-4: kept (only solution)"
                for m in prs_sorted[1:]:
                    flags[m[0]] = reasons[m[0]]

        conn.executemany(
            "UPDATE solutions SET is_redundant = 1, redundant_why = ? "
            "WHERE id = ?",
            [(why, sid) for sid, why in flags.items()],
        )
        conn.executemany(
            "UPDATE solutions SET is_repr = 1 WHERE id = ?",
            [(sid,) for sid in repr_ids],
        )
        # 6-3 で圧縮された行。is_redundant は立てず、痕跡だけ残す (5.2)
        conn.executemany(
            "UPDATE solutions SET redundant_why = ? WHERE id = ?",
            [(why, sid) for sid, why in traces.items()],
        )
        # 6-4 で残した行は「代表」だが、なぜ他が消えたかの痕跡として理由も残す
        conn.executemany(
            "UPDATE solutions SET redundant_why = ? WHERE id = ?",
            [(why, sid) for sid, why in forced.items()],
        )

        # problems テーブル: 代表解の数、代表解、スコアの最小/最大。
        # solution_count は is_repr = 1 の数 (重複を圧縮した一覧の本数)。
        # min_score / max_score は is_redundant = 0 (5.2 以降は「6-1 を除いた全解」)
        # のスコア範囲。これは constrain の base_min_score / puzzles.min_score と
        # 同じ基準。6-3 で圧縮された行もここには含まれる (5.2 で変わった点)。
        conn.execute("DELETE FROM problems")
        best = {}   # pid -> (sort_key, id)
        for r in conn.execute(_CURATE_COLS + " WHERE is_repr = 1 ORDER BY id"):
            pid = r[1]
            k = _repr_sort_key(r)
            if pid not in best or k < best[pid][0]:
                best[pid] = (k, r[0])
        counts = dict(conn.execute(
            "SELECT problem_id, COUNT(*) FROM solutions WHERE is_repr = 1 "
            "GROUP BY problem_id"))
        score_range = {
            pid: (lo, hi) for pid, lo, hi in conn.execute(
                "SELECT problem_id, MIN(score), MAX(score) FROM solutions "
                "WHERE is_redundant = 0 GROUP BY problem_id")
        }
        conn.executemany(
            "INSERT INTO problems (problem_id, solution_count, min_score, "
            "max_score, repr_solution_id) VALUES (?, ?, ?, ?, ?)",
            [(pid, counts[pid], score_range[pid][0], score_range[pid][1],
              best[pid][1]) for pid in counts],
        )

        conn.commit()

        stats = {
            "total": len(rows),
            "kept": len(repr_ids),
            "n_6_1": sum(1 for w in flags.values() if w.startswith("6-1")),
            # 6-2 は 5.2 で廃止したので常に 0。キーは残す (集計の形を変えない)
            "n_6_2": sum(1 for w in flags.values() if w.startswith("6-2")),
            # 6-3 は is_redundant を立てないので flags ではなく traces を数える
            "n_6_3": len(traces),
            "n_6_4": len(forced),
            "problems": len(counts),
        }
        if progress:
            progress(stats)
        return stats
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# constrain : 演算子の使用回数による制約付き問題を生成する (第6-B章)
# ---------------------------------------------------------------------------
#
# problem_id ごとに:
#   1. その問題の全解 (is_redundant を無視) を「制約判定の母集団」にする
#   2. 候補制約ルールを列挙 (CONSTRAINT_OPS × CONSTRAINT_RULE_KINDS)
#   3. 各ルールを「満たす解」のビットマスクにする
#   4. ルールを 1..MAX_CONSTRAINTS 個組み合わせ、マスク AND で残存解を求める
#   5. 残存解が無制約より真に少なく、採用条件を満たすものを puzzle にする
#   6. 残存解集合が同一の puzzle は、rules が短い→辞書順で先のものだけ残す
#   7. rule_count = 0 の無制約 puzzle は harder_by 条件なしで全問題に 1 件入れる
#
# 難易度と解答例は「冗長でない解」(is_redundant = 0) から取る (第6-B章)。
#   min_score / example_solution_id = 冗長でない残存解のうち最小スコアのもの
#                                     (同点は読みやすさ順)。難易度と解答例は同じ解。
#   base_min_score = その問題の冗長でない解の最小スコア (= problems.min_score)
#   harder_by      = min_score - base_min_score
# 採用条件 (制約付きのみ):
#   - 冗長でない残存解が 1 つ以上ある
#   - harder_by >= 1
#
# 「制約下で最もラクな解が冗長解でない」ことは保証しない。
#   - 「残存解が全部冗長」なら上の1つ目で弾ける。
#   - しかし「残存解の一部が冗長で、その冗長解が一番ラク」は素通りする
#     (実測 3,468 件)。min_score / example を冗長でない解から取るので
#     表示上の難易度と解答例は正しいが、プレイヤーは冗長な式でも突破できる。
#   - これは意図的に許容する。プレイヤーは何も強制されていないし、
#     基本問題 (rule_count = 0) でも同じ状況は起きるので、扱いを揃える。

_CONSTRAIN_SOL_COLS = (
    "SELECT id, problem_id, is_repr, score, cnt_paren, cnt_sub, cnt_div, "
    "LENGTH(display), cnt_add, cnt_mul, cnt_pow, cnt_fac, is_redundant "
    "FROM solutions ORDER BY problem_id, id")
# 列: 0 id  1 pid  2 is_repr  3 score  4 cnt_paren  5 cnt_sub  6 cnt_div
#     7 len(display)  8 cnt_add  9 cnt_mul  10 cnt_pow  11 cnt_fac  12 is_redundant

# CONSTRAINT_OPS の各記号 -> 上のクエリでの使用回数カラムのインデックス
_OP_COL = {"+": 8, "-": 5, "*": 9, "/": 6, "^": 10, "!": 11}
_IDX_REDUNDANT = 12


def _parse_kind(kind):
    """CONSTRAINT_RULE_KINDS の要素を (比較演算子, N) に分解する。

    '=0' -> ('=', 0) , '>=2' -> ('>=', 2) , '<=1' -> ('<=', 1)
    """
    i = 0
    while i < len(kind) and not (kind[i].isdigit() or kind[i] == "-"):
        i += 1
    return kind[:i], int(kind[i:])


def _kind_ok(count, cmp, n):
    if cmp == "=":
        return count == n
    if cmp == ">=":
        return count >= n
    if cmp == "<=":
        return count <= n
    raise ValueError("unknown constraint comparator %r" % (cmp,))


# 6-5 (5.2): puzzle 単位の救済の印。redundant_why の末尾に足す。
# 「example_solution_id の解が is_redundant=1」でも判別できるが、
# 6-4 と同じ作法で文字列にも残しておく
_RESCUE_MARK = " | 6-5: kept as constrained puzzle example"


def _example_key(s):
    """解答例の選び方: スコア最小 -> 読みやすさ (括弧->割り算->引き算->表示長) -> id。

    先頭にスコアを置くので、min_score とここで選ばれる解答例は必ず同じ解になる。
    """
    return (s[3], s[4], s[6], s[5], s[7], s[0])


def run_constrain(db_path, progress=None):
    """制約付き問題を puzzles テーブルに投入する。集計 dict を返す。"""
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        conn.execute("DELETE FROM puzzles")

        by_pid = {}
        for s in conn.execute(_CONSTRAIN_SOL_COLS):
            by_pid.setdefault(s[1], []).append(s)

        puzzle_rows = []
        n_base = 0          # rule_count = 0 (無制約。全問題に 1 件)
        n_constrained = 0   # rule_count >= 1 で採用したもの
        n_rej_hb = 0        # harder_by < 1 で不採用
        n_rej_noreprsurv = 0  # 制約を満たす解が 1 本も無いので不採用
        n_rescue_puzzle = 0   # 6-5: 潰す形しか無いので救済した puzzle
        rescued_ids = set()   # 6-5 で解答例にした解の id（痕跡を残す用）
        rescued_pids = set()
        surv_ids = []         # puzzle_rows と同じ並びの「制約を満たす解の id」
        already_repr = set()  # curate が is_repr=1 にした解の id（登場したぶんだけ）

        for pid, sols in by_pid.items():
            n = len(sols)
            full = (1 << n) - 1
            nonred_scores = [s[3] for s in sols if not s[_IDX_REDUNDANT]]
            # curate により全問題に is_redundant=0 の解が最低 1 つある
            base_min = min(nonred_scores)

            # --- 候補ルール -> マスク (同一マスクのルールは簡潔な方だけ残す) ---
            # 候補は CONSTRAINT_OPS × CONSTRAINT_RULE_KINDS のみ。>= や 2 個の
            # 組み合わせは (MAX_CONSTRAINTS で明示しない限り) 作らない。
            mask_to_rule = {}
            for op in CONSTRAINT_OPS:
                counts = [s[_OP_COL[op]] for s in sols]
                for kind in CONSTRAINT_RULE_KINDS:
                    cmp, nval = _parse_kind(kind)
                    m = 0
                    for i, c in enumerate(counts):
                        if _kind_ok(c, cmp, nval):
                            m |= 1 << i
                    if not (0 < m < full):
                        continue              # 全選択/全排除の制約は無意味
                    rt = op + kind
                    cur = mask_to_rule.get(m)
                    if cur is None or (len(rt), rt) < (len(cur), cur):
                        mask_to_rule[m] = rt

            rules = sorted(mask_to_rule.items(),
                           key=lambda mr: (len(mr[1]), mr[1]))  # [(mask, text)]

            # --- 1..MAX_CONSTRAINTS 個の組み合わせ -> 残存マスクごとに最良の定義 ---
            best = {}   # mask -> (rule_count, len(rules_str), rules_str)

            def offer(mask, rlist):
                rc = len(rlist)
                if rc >= 1 and not (0 < mask < full):
                    return                 # 空 or 無制約と同じ = 効いていない
                rs = " | ".join(sorted(rlist))
                cand = (rc, len(rs), rs)
                cur = best.get(mask)
                if cur is None or cand < cur:
                    best[mask] = cand

            offer(full, [])                       # rule_count = 0 (無制約)
            for k in range(1, MAX_CONSTRAINTS + 1):
                for combo in combinations(rules, k):
                    acc = full
                    for cmask, _ct in combo:
                        acc &= cmask
                    offer(acc, [ct for _cm, ct in combo])

            # --- puzzle 行を組み立てる ---
            for mask, (rc, _ln, rs) in best.items():
                surv = [sols[i] for i in range(n) if mask >> i & 1]
                nonred = [s for s in surv if not s[_IDX_REDUNDANT]]

                was_rescued = False
                if nonred:
                    pool = nonred
                elif surv:
                    # 6-5 (5.2): 制約を満たす解が「数字を潰す形」しか無い puzzle。
                    # is_redundant は「どれを解答例にするか」「一覧に何本並べるか」を
                    # 決める印であって、パズルの存在を左右するものではない。
                    # 0158 の 0! + 1 ^ 5 + 8 は合法な入力で正解になるので、
                    # プレイヤーは解ける。解けるパズルを帳簿の都合で消さない。
                    # 6-4 が problem 単位でやっている救済を puzzle 単位でも行う
                    pool = surv
                    was_rescued = True
                else:
                    # 制約を満たす解が 1 本も無い -> puzzle が成立しない
                    n_rej_noreprsurv += 1
                    continue

                example = min(pool, key=_example_key)
                # 救済時は「制約を満たす全解」の最小スコア。難易度もこの式で付く
                mn = example[3]

                if rc == 0:
                    hb = mn - base_min           # 定義上 0 (nonred == 全冗長でない解)
                    n_base += 1
                else:
                    hb = mn - base_min
                    if hb < 1:
                        n_rej_hb += 1
                        continue
                    n_constrained += 1

                # repr_survivor_count はまだ確定させない。このあと解答例を
                # 強制的に is_repr=1 にするので、その結果を織り込んで数え直す
                puzzle_rows.append([
                    pid, rs, rc, len(surv), None, example[0],
                    mn, base_min, hb,
                ])
                surv_ids.append([s[0] for s in surv])
                already_repr.update(s[0] for s in surv if s[2])
                # 印を付けるのは採用された puzzle だけ。harder_by で落ちた候補に
                # 付けると「救済されたのに存在しない puzzle」の痕跡が残ってしまう
                if was_rescued:
                    rescued_ids.add(example[0])
                    rescued_pids.add(pid)
                    n_rescue_puzzle += 1

        # --- 6-6 (5.2): 解答例を必ず「一覧」に載せる ---
        # 注: これは solutions.is_repr を書き換えるので、curate -> constrain の
        # 順に流すこと (curate が is_repr を 0 に戻してから代表を付け直す)。
        # constrain だけを 2 度流すと前回の昇格が残る
        # is_repr は 6-3 が problem 単位で選んだ代表なので、制約つき puzzle では
        # 「制約を満たす最良の解」が代表に選ばれていないことがある。そのままだと
        # ヒントが指す式が一覧に無い (ヒント 1・2 から一覧へ辿れない) ので、
        # 解答例に選ばれた解は強制的に is_repr = 1 にして、
        # 「解答例は必ず一覧にある」を DB 側の不変条件にする。
        promoted = {row[5] for row in puzzle_rows} - already_repr
        if promoted:
            conn.executemany("UPDATE solutions SET is_repr = 1 WHERE id = ?",
                             [(sid,) for sid in sorted(promoted)])
        # 昇格を織り込んで repr_survivor_count を確定させる
        repr_now = already_repr | promoted
        for row, ids in zip(puzzle_rows, surv_ids):
            row[4] = sum(1 for i in ids if i in repr_now)
        conn.executemany(
            "INSERT INTO puzzles (problem_id, rules, rule_count, survivor_count, "
            "repr_survivor_count, example_solution_id, min_score, "
            "base_min_score, harder_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(r) for r in puzzle_rows],
        )
        # 6-5 の痕跡。6-4 と同じく redundant_why に残す。is_redundant は 6-1 の
        # ままで下げない（その解は確かに数字を潰している）。何度流しても同じ
        # 結果になるよう、先に前回の印を落としてから付け直す
        conn.execute(
            "UPDATE solutions SET redundant_why = "
            "replace(redundant_why, ?, '') WHERE redundant_why LIKE ?",
            (_RESCUE_MARK, "%" + _RESCUE_MARK + "%"),
        )
        if rescued_ids:
            conn.executemany(
                "UPDATE solutions SET redundant_why = "
                "COALESCE(redundant_why, '') || ? WHERE id = ?",
                [(_RESCUE_MARK, sid) for sid in sorted(rescued_ids)],
            )
        conn.commit()

        stats = {
            "puzzles": len(puzzle_rows),
            "problems": len(by_pid),
            "base": n_base,
            "constrained": n_constrained,
            "rejected_harder_by": n_rej_hb,
            "rejected_no_nonredundant": n_rej_noreprsurv,
            "rescued_puzzle": n_rescue_puzzle,
            "promoted_repr": len(promoted),
            "rescued_problems": len(rescued_pids),
        }
        if progress:
            progress(stats)
        return stats
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# export : puzzles テーブルからゲーム用 JSON を出力する (第8章)
# ---------------------------------------------------------------------------
_EXPORT_QUERY = """
SELECT p.problem_id, p.rules, p.rule_count, p.min_score, p.survivor_count,
       s.display
FROM puzzles p
JOIN solutions s ON s.id = p.example_solution_id
ORDER BY p.problem_id, p.rule_count, p.rules, p.id
"""

# 第6-D章: その problem_id の解に cnt_fac=0 (cnt_pow=0) が 1 つも無ければ
# 「階乗 (累乗) を使わないと解けない」問題。母集団は全解。
_EXPORT_NEEDS_QUERY = """
SELECT problem_id, MIN(cnt_fac) > 0, MIN(cnt_pow) > 0
FROM solutions GROUP BY problem_id
"""


def _constraint_obj(rules):
    """puzzles.rules 文字列を JSON の constraint に変換する。

    ""    -> None (基本問題)
    "/=1" -> {"op": "/", "count": 1}
    """
    if not rules:
        return None
    if " | " in rules:
        raise ValueError("export: 複合制約は未対応: %r" % (rules,))
    cmp, n = _parse_kind(rules[1:])          # rules[0] が演算子記号
    if cmp != "=":
        raise ValueError("export: '=' 以外の制約は未対応: %r" % (rules,))
    return {"op": rules[0], "count": n}


def run_export(db_path, out_path, progress=None):
    """puzzles 全行を第8章の形式で JSON ファイルに書き出す。集計 dict を返す。"""
    conn = _connect(db_path)
    try:
        needs = {pid: (bool(nf), bool(np))
                 for pid, nf, np in conn.execute(_EXPORT_NEEDS_QUERY)}
        puzzles = []
        n_con = 0
        n_needs_fac = 0
        n_needs_pow = 0
        for pid, rules, rc, min_score, surv, display in conn.execute(
                _EXPORT_QUERY):
            constraint = _constraint_obj(rules)
            if constraint is not None:
                n_con += 1
            needs_fac, needs_pow = needs[pid]
            n_needs_fac += needs_fac
            n_needs_pow += needs_pow
            puzzles.append({
                "id": pid,
                "constraint": constraint,
                "difficulty": min_score,
                "solution": display,
                "solution_count": surv,
                "needs_fac": needs_fac,
                "needs_pow": needs_pow,
            })
    finally:
        conn.close()

    data = {"version": 1, "rules": EXPORT_RULES, "puzzles": puzzles}
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    stats = {
        "path": out_path,
        "bytes": len(text.encode("utf-8")),
        "puzzles": len(puzzles),
        "with_constraint": n_con,
        "without_constraint": len(puzzles) - n_con,
        "needs_fac": n_needs_fac,
        "needs_pow": n_needs_pow,
    }
    if progress:
        progress(stats)
    return stats


# ---------------------------------------------------------------------------
# BLOB (docs/index.html に埋め込む 3 区分のデータ)  ―― 5.2 で追加
#
# ゲーム本体は puzzles 全行をモード別に 3 つへ分けたテキストを読む
# (index.html の parseBlob)。行の形式は 1 行 1 puzzle の
#
#     id,rc,d,n,nf,np,sol
#
# で、区分の頭に "§COURSE" / "§FREE" / "§CHAL" の見出しを置く (DATA-SPEC 8-B)。
# 3 区分は puzzles を**重複なく**分けたもので、和集合が全 puzzle になる。
#
#   CHAL   … min_score >= CHAL_MIN_SCORE の全部 (挑戦モード)
#   COURSE … 残りから COURSE_N 問を選抜規則で選ぶ (本編)
#   FREE   … 残りの全部 (フリー・べつの問題)
#
# 選抜規則は決定的 (乱数を使わず COURSE_SEED からハッシュで順位を付ける) なので、
# 同じ DB からは何度流しても同じ COURSE になる。
# ---------------------------------------------------------------------------
BLOB_HTML_DEFAULT = "docs/index.html"
CHAL_MIN_SCORE = 17          # 挑戦モードの下限 (GAME-SPEC 7)
COURSE_N = 1000              # 本編の問題数
COURSE_SEED = "make10-course-v1"
# 検証用の定数 (5.3)。難易度の範囲は GAME-SPEC 6-2 の 3〜44
DIFF_MIN, DIFF_MAX = 3, 44
COURSE_BLOCK = 100           # 平均難易度を見るブロックの大きさ
COURSE_LATE_FROM = 201       # ここから先は難易度を絞る
COURSE_LATE_RANGE = (9, 16)  # _course_floor / _course_target の帰結
# index.html の RCS と同じ順。FREE / CHAL の並び順に使う
BLOB_RCS = ("N", "A0", "S0", "M0", "D0", "P0", "F0")
_BLOB_CODEOF = {"+": "A", "-": "S", "*": "M", "/": "D", "^": "P", "!": "F"}
_BLOB_MARK_BEGIN = "const BLOB=`"
_BLOB_MARK_END = "`;"


def _blob_rc(rules):
    """puzzles.rules を index.html の rc 表記にする。"" -> "N" / "!=0" -> "F0"。"""
    if not rules:
        return "N"
    if " | " in rules or rules[1] != "=":
        raise ValueError("blob: 未対応の制約: %r" % (rules,))
    return _BLOB_CODEOF[rules[0]] + rules[2:]


def _example_feat(display, pid):
    """解答例の中で「累乗が効いているか」「階乗の引数の最大値」を返す。

    判定は 6-1 と同じ「値が変わるか」を **ノード単位** に当てただけで、新しい
    基準を持ち込んでいない (5.2)。

    累乗が効いている (peff)
        `a ^ b` の値が底 `a` と違う。`a ^ b == a` になるのは `a == 1` /
        `b == 1` / (`a == -1` かつ `b` が奇数) の 3 つだけで、どれも `^` が
        何もしていない形である (代数的にこれで尽きる)。
        **6-1 だけでは足りない。** 6-1 は `1 ^ 7` を捕まえるが、`8117` のように
        全解が 6-1 該当の問題では 6-4 の救済で解答例に残る。さらに
        `9 - ( 8 - 9 ) ^ 3` は 6-1 を通る ―― 指数 3 を 0 に差し替えると
        `(-1) ^ 0 = 1` で値が変わるので、桁単位の判定では「寄与している」と
        出てしまう。桁ではなくノードを見るしかない。

    階乗の引数の最大値 (fmax)
        `1!` と `2!` は値が変わらないので **生成時に枝刈りされている**
        (build_evaluator)。したがって階乗の引数は 0 か 3 以上しかなく、
        「階乗が数を大きくしている」は引数 >= 3 と書ける。`0!` は 0 -> 1 と
        値は変える (6-1 には該当しない) が数を大きくはしていない。
    """
    tree = parse_tree(display)
    ev = build_evaluator([int(ch) for ch in pid])
    peff = False
    fmax = None
    for n in iter_nodes(tree):
        if n[0] == "bin" and n[1] == "^":
            if ev(n)[0] != ev(n[2])[0]:
                peff = True
        elif n[0] == "fac":
            arg = ev(n[1])[0]
            if fmax is None or arg > fmax:
                fmax = arg
    return peff, (int(fmax) if fmax is not None else None)


_BLOB_QUERY = """
SELECT p.problem_id, p.rules, p.min_score, p.survivor_count, s.display
FROM puzzles p
JOIN solutions s ON s.id = p.example_solution_id
ORDER BY p.problem_id, p.rules, p.id
"""


def _blob_rows(conn):
    """puzzles 全行を選抜と出力に必要な形にして返す。"""
    needs = {pid: (bool(nf), bool(np))
             for pid, nf, np in conn.execute(_EXPORT_NEEDS_QUERY)}
    rows = []
    for pid, rules, d, surv, sol in conn.execute(_BLOB_QUERY):
        nf, np_ = needs[pid]
        ops = set(ch for ch in sol if ch in "+-*/^!")
        # peff / fbig は COURSE の ★ の位置でしか使わないが、行ごとの素性として
        # まとめて持たせる (難易度で絞ると条件を足したときに取り落とす)
        if d <= CHAL_MIN_SCORE - 1:
            peff, fmax = _example_feat(sol, pid)
        else:
            peff, fmax = False, None
        rows.append({
            "id": pid, "rc": _blob_rc(rules), "d": d, "n": surv,
            "nf": nf, "np": np_, "sol": sol,
            "ops": ops, "par": "(" in sol, "free": not rules,
            "peff": peff, "fmax": fmax,
            "fbig": fmax is not None and fmax >= 3,
        })
    return rows


# --- COURSE の選抜規則 (GAME-SPEC 7-1) ---------------------------------------
# 段ごとの条件。★ の 2 段は「その演算子を使わないと解けない問題」であることに
# 加えて、**解答例でその演算子が実際に働いている**ことも要求する (5.2)。
def _course_stage_cond(i):
    if i <= 4:
        return lambda r: r["ops"] <= set("+-") and not r["par"]
    if i <= 10:
        return lambda r: (bool(r["ops"] & set("*/")) and not r["par"]
                          and not (r["ops"] & set("^!")))
    if i <= 20:
        return lambda r: r["par"]
    if i <= 25:
        return lambda r: len(r["ops"] & set("+-*/")) >= 2
    if i <= 28:                       # ★階乗必須 + 階乗が数を大きくしている
        return lambda r: r["nf"] and r["fbig"]
    if i <= 40:
        return lambda r: "!" in r["ops"]
    if i <= 43:                       # ★累乗必須 + 累乗が結果に効いている
        return lambda r: r["np"] and r["peff"]
    return lambda r: True


# 43 問目までは位置ごとに目標難易度を直接決める (導入の段なので手で置く)
COURSE_PIN = {
    **{i: 3 for i in range(1, 5)},
    5: 4, 6: 4, 7: 5, 8: 5, 9: 6, 10: 6,
    11: 5, 12: 5, 13: 5, 14: 6, 15: 6, 16: 6, 17: 7, 18: 7, 19: 7, 20: 8,
    21: 6, 22: 7, 23: 7, 24: 8, 25: 8,
    26: 8, 27: 9, 28: 10,
    29: 8, 30: 8, 31: 9, 32: 9, 33: 10, 34: 10, 35: 11, 36: 11,
    37: 9, 38: 10, 39: 10, 40: 11,
    41: 7, 42: 8, 43: 9,
}
# 44 問目以降の平均難易度。折れ線のアンカー (位置, 平均難易度)
COURSE_ANCH = [(44, 8.0), (150, 9.9), (250, 9.9), (350, 10.3), (450, 10.5),
               (550, 11.3), (650, 11.7), (750, 12.8), (850, 12.9), (1000, 13.3)]
# カーブの上下に振る量。平均は保ったまま 1 問ごとの手応えに緩急を付ける
COURSE_SPREAD = [-3, 2, -1, 3, 0, -2, 1, 2, -3, 1, -1, 0, 2, -2, 3, -1, 1, -3, 0, 2]


def _course_curve(i):
    if i <= COURSE_ANCH[0][0]:
        return COURSE_ANCH[0][1]
    for (x0, y0), (x1, y1) in zip(COURSE_ANCH, COURSE_ANCH[1:]):
        if i <= x1:
            return y0 + (y1 - y0) * (i - x0) / (x1 - x0)
    return COURSE_ANCH[-1][1]


def _course_floor(i):
    """難易度の下限。後半に簡単すぎる問題が落ちてこないようにする。"""
    if i < 44:
        return 3
    return min(9, 4 + (i - 44) * 5 / 156)


def _course_target(i):
    if i in COURSE_PIN:
        return COURSE_PIN[i]
    t = _course_curve(i) + COURSE_SPREAD[(i - 44) % len(COURSE_SPREAD)]
    return max(int(round(_course_floor(i))), min(16, int(round(t))))


def _course_want_constrained(i):
    """その位置に制約つきの問題を置きたいか。1〜50 は操作に慣れる段なので置かない。"""
    if i <= 50:
        return False
    if i <= 100:
        return (i % 4) == 0          # 1/4
    if i <= 200:
        return (i % 2) == 0          # 1/2
    return (i % 3) != 0              # 2/3


def _course_rank(i, r):
    """候補の順位。乱数ではなく位置と問題から決まるので毎回同じ COURSE になる。"""
    key = "%s:%d:%s:%s" % (COURSE_SEED, i, r["id"], r["rc"])
    return hashlib.blake2b(key.encode(), digest_size=8).digest()


def select_course(pool, n=COURSE_N):
    """pool (d <= 16 の全 puzzle) から本編の n 問を選ぶ。(選抜, 拡張回数) を返す。

    位置ごとに「段の条件」「目標難易度」「制約つきかどうか」を満たす候補を集め、
    _course_rank が最小のものを採る。候補が無ければ難易度の許容幅を 1 ずつ
    広げ、それでも無ければ最後に「直近 10 問に同じ 4 桁を出さない」を外す。
    """
    by = collections.defaultdict(list)
    for r in pool:
        by[(r["d"], r["free"])].append(r)
    used = set()
    recent = []
    chosen = []
    widen = collections.Counter()
    for i in range(1, n + 1):
        cond = _course_stage_cond(i)
        td = _course_target(i)
        wc = _course_want_constrained(i)
        pick = None
        for w in range(0, 14):
            for dd in ([td] if w == 0 else [td - w, td + w]):
                if not 3 <= dd <= CHAL_MIN_SCORE - 1:
                    continue
                for free in ([False, True] if wc else [True]):
                    if i <= 50 and not free:
                        continue
                    cands = [r for r in by[(dd, free)]
                             if (r["id"], r["rc"]) not in used and cond(r)
                             and r["id"] not in recent[-10:]]
                    if cands:
                        pick = min(cands, key=lambda r: _course_rank(i, r))
                        break
                if pick:
                    break
            if pick:
                widen[w] += 1
                break
        if pick is None:
            for w in range(0, 14):
                for dd in [td - w, td, td + w]:
                    if not 3 <= dd <= CHAL_MIN_SCORE - 1:
                        continue
                    for free in ([False, True] if wc else [True]):
                        if i <= 50 and not free:
                            continue
                        cands = [r for r in by[(dd, free)]
                                 if (r["id"], r["rc"]) not in used and cond(r)]
                        if cands:
                            pick = min(cands, key=lambda r: _course_rank(i, r))
                            break
                    if pick:
                        break
                if pick:
                    widen[("relax", w)] += 1
                    break
        if pick is None:
            raise ValueError("blob: 位置 %d の候補が無い (目標難易度 %d)" % (i, td))
        used.add((pick["id"], pick["rc"]))
        recent.append(pick["id"])
        chosen.append(pick)
    return chosen, widen


# --- 出力と検証 -------------------------------------------------------------
def _blob_sort_key(r):
    return (r["id"], BLOB_RCS.index(r["rc"]))


def _blob_line(r):
    return "%s,%s,%d,%d,%d,%d,%s" % (
        r["id"], r["rc"], r["d"], r["n"], 1 if r["nf"] else 0,
        1 if r["np"] else 0, r["sol"])


def _blob_text(sections):
    out = []
    for name in ("COURSE", "FREE", "CHAL"):
        out.append("§" + name)
        out.extend(_blob_line(r) for r in sections[name])
    return "\n".join(out)


def _plain_eval(node, digits):
    """検証用の素朴な評価器。build_evaluator とは別実装にしてある
    (同じ前提を共有した検証は検証にならない ―― CLAUDE.md)。"""
    tag = node[0]
    if tag == "num":
        return Fraction(digits[node[1]])
    if tag == "fac":
        v = _plain_eval(node[1], digits)
        if v.denominator != 1 or v.numerator < 0:
            raise ValueError("階乗の引数が不正: %s" % v)
        return Fraction(factorial(v.numerator))
    a = _plain_eval(node[2], digits)
    b = _plain_eval(node[3], digits)
    op = node[1]
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b
    if b.denominator != 1:
        raise ValueError("指数が整数でない: %s" % b)
    if a == 0 and b == 0:
        return Fraction(1)
    return a ** b.numerator


def _blob_verify(conn, sections, widen, text, rebuild=None):
    """生成と同じ実行で回す 12 項目。[(項目名, 合否, 詳細)] を返す。

    rebuild … 同じ DB からもう一度 BLOB を組んで本文を返す関数。
    検証 12 (再現性) だけが使う。省略すると 12 を「未実施」として落とす。
    """
    res = []
    course, free, chal = sections["COURSE"], sections["FREE"], sections["CHAL"]
    allrows = course + free + chal

    # 1. 件数と分割 (重複なく全 puzzle を覆う)
    db_keys = collections.Counter()
    for pid, rules in conn.execute("SELECT problem_id, rules FROM puzzles"):
        db_keys[(pid, _blob_rc(rules))] += 1
    got = collections.Counter((r["id"], r["rc"]) for r in allrows)
    res.append(("1. 件数と分割", len(course) == COURSE_N and got == db_keys,
                "COURSE %d / FREE %d / CHAL %d / 計 %d、DB の puzzles %d、"
                "取りこぼし %d・重複 %d"
                % (len(course), len(free), len(chal), len(allrows),
                   sum(db_keys.values()), len(db_keys - got), len(got - db_keys))))

    # 2. 難易度の境目
    bad = ([r for r in chal if r["d"] < CHAL_MIN_SCORE]
           + [r for r in course + free if r["d"] >= CHAL_MIN_SCORE])
    res.append(("2. 難易度の境目", not bad,
                "CHAL は d>=%d / COURSE・FREE は d<=%d、違反 %d 行"
                % (CHAL_MIN_SCORE, CHAL_MIN_SCORE - 1, len(bad))))

    # 3. COURSE の段の条件と制約なしの区間
    segs = [(1, 4, "足し引きのみ・括弧なし"), (5, 10, "×÷が入る"),
            (11, 20, "括弧を含む"), (21, 25, "四則2種以上"),
            (26, 28, "★階乗必須"), (29, 40, "階乗を含む"), (41, 43, "★累乗必須")]
    ng = [lab for a, b, lab in segs
          if not all(_course_stage_cond(a)(r) for r in course[a - 1:b])]
    free50 = all(r["free"] for r in course[:50])
    widen_ok = set(widen) == {0}
    res.append(("3. COURSE の段の条件", not ng and free50 and widen_ok,
                "7 段の充足 %d/7、1〜50 が全部制約なし %s、許容幅の拡張 %s"
                % (7 - len(ng), free50, dict(widen))))

    # 4. COURSE の重複と間隔
    dup = len(course) - len({(r["id"], r["rc"]) for r in course})
    mind = min((i - j for i, r in enumerate(course)
                for j in [max((k for k, q in enumerate(course[:i])
                               if q["id"] == r["id"]), default=None)]
                if j is not None), default=None)
    res.append(("4. COURSE の重複と間隔", dup == 0 and (mind is None or mind > 10),
                "(id,rc) の重複 %d、同じ 4 桁が再登場する最小間隔 %s 問"
                % (dup, mind)))

    # 5. DB との一致 (n は survivor_count)
    db = {}
    for pid, rules, d, surv, sol in conn.execute(_BLOB_QUERY):
        db[(pid, _blob_rc(rules))] = (d, surv, sol)
    needs = {pid: (bool(nf), bool(np))
             for pid, nf, np in conn.execute(_EXPORT_NEEDS_QUERY)}
    mism = [r for r in allrows
            if db[(r["id"], r["rc"])] != (r["d"], r["n"], r["sol"])
            or needs[r["id"]] != (r["nf"], r["np"])]
    res.append(("5. DB との一致", not mism,
                "d / n(=survivor_count) / nf / np / sol の不一致 %d 行 / %d 行"
                % (len(mism), len(allrows))))

    # 6. 解答例の再評価 (独立実装の _plain_eval で 10 になること)
    bad = []
    for r in allrows:
        try:
            digits = [int(ch) for ch in r["id"]]
            if _plain_eval(parse_tree(r["sol"]), digits) != 10:
                bad.append(r)
            elif [ch for ch in r["sol"] if ch.isdigit()] != list(r["id"]):
                bad.append(r)
        except Exception:
            bad.append(r)
    res.append(("6. 解答例の再評価", not bad,
                "値が 10 でない / 数字が id と違う行 %d / %d 行" % (len(bad), len(allrows))))

    # 7. ★ の導入位置
    f = [r for r in course[25:28]]
    p = [r for r in course[40:43]]
    ok7 = (all(r["nf"] and r["fbig"] for r in f)
           and all(r["np"] and r["peff"] for r in p))
    res.append(("7. ★ の導入位置", ok7,
                "26〜28 階乗の引数 %s / 41〜43 ^ が効く %s"
                % ([r["fmax"] for r in f], [r["peff"] for r in p])))

    # 8. テンプレートリテラルの安全性 (index.html の ` ` の中に入れるため)
    lines = [ln for ln in text.split("\n") if not ln.startswith("§")]
    bad_fields = [ln for ln in lines if len(ln.split(",")) != 7]
    bad_chars = [ch for ch in ("`", "${", "\r", "\\") if ch in text]
    res.append(("8. 埋め込みの安全性", not bad_fields and not bad_chars,
                "7 フィールドでない行 %d、危険な文字 %s、見出し %d 本"
                % (len(bad_fields), bad_chars or "なし",
                   len(text.split("\n")) - len(lines))))

    # 9. COURSE の難易度カーブ (100 問ブロックの平均が単調非減少)
    blocks = [course[k:k + COURSE_BLOCK]
              for k in range(0, len(course), COURSE_BLOCK)]
    avgs = [sum(r["d"] for r in b) / len(b) for b in blocks]
    drops = [(k + 1, round(avgs[k], 2), round(avgs[k + 1], 2))
             for k in range(len(avgs) - 1) if avgs[k] > avgs[k + 1] + 1e-9]
    res.append(("9. 難易度カーブ", not drops,
                "%d 問ブロックの平均 %s、下がった箇所 %d"
                % (COURSE_BLOCK, [round(a, 2) for a in avgs], len(drops))))

    # 10. 後半の難易度 (COURSE_LATE_FROM 問目以降が全部 9〜16)
    lo, hi = COURSE_LATE_RANGE
    late = course[COURSE_LATE_FROM - 1:]
    outr = [(i, r["d"]) for i, r in enumerate(late, COURSE_LATE_FROM)
            if not lo <= r["d"] <= hi]
    res.append(("10. 後半の難易度", not outr,
                "%d 問目以降 %d 問が d %d〜%d、範囲外 %d 問 (実測 %d〜%d)"
                % (COURSE_LATE_FROM, len(late), lo, hi, len(outr),
                   min(r["d"] for r in late), max(r["d"] for r in late))))

    # 11. 難易度の範囲 (区分の境目を見る 2 とは別に、上下の端を見る)
    bad_d = [r for r in allrows if not DIFF_MIN <= r["d"] <= DIFF_MAX]
    res.append(("11. 難易度の範囲", not bad_d,
                "全 %d 行が d %d〜%d、範囲外 %d 行 (実測 %d〜%d)"
                % (len(allrows), DIFF_MIN, DIFF_MAX, len(bad_d),
                   min(r["d"] for r in allrows), max(r["d"] for r in allrows))))

    # 12. 再現性 (同じ DB / 同じシードでもう一度組んでバイト単位で一致するか)
    if rebuild is None:
        res.append(("12. 再現性", False, "rebuild が渡されていないので未実施"))
    else:
        again = rebuild()
        same = again.encode("utf-8") == text.encode("utf-8")
        res.append(("12. 再現性", same,
                    "2 回組んで %s (%d / %d バイト)"
                    % ("バイト単位で一致" if same else "**不一致**",
                       len(text.encode("utf-8")), len(again.encode("utf-8")))))
    return res


def _blob_build(conn):
    """DB から 3 区分を組む。(sections, widen) を返す。

    検証 12 (再現性) がここをもう一度呼んで結果を突き合わせるので、
    **呼ぶたびに DB から読み直す独立した組み立て**になっている必要がある。
    """
    rows = _blob_rows(conn)
    chal = sorted((r for r in rows if r["d"] >= CHAL_MIN_SCORE),
                  key=_blob_sort_key)
    pool = [r for r in rows if r["d"] < CHAL_MIN_SCORE]
    course, widen = select_course(pool)
    taken = {(r["id"], r["rc"]) for r in course}
    free = sorted((r for r in pool if (r["id"], r["rc"]) not in taken),
                  key=_blob_sort_key)
    return {"COURSE": course, "FREE": free, "CHAL": chal}, widen


def run_blob(db_path, html_path, write=True, progress=None):
    """3 区分の BLOB を組み、index.html の const BLOB=`...` を差し替える。

    検証 12 項目は**同じ実行の中で**回し、1 つでも落ちたら書き込まない。
    """
    conn = _connect(db_path)
    try:
        sections, widen = _blob_build(conn)
        text = _blob_text(sections)
        checks = _blob_verify(conn, sections, widen, text,
                              lambda: _blob_text(_blob_build(conn)[0]))
    finally:
        conn.close()

    failed = [c for c in checks if not c[1]]
    wrote = False
    if write and not failed:
        with open(html_path, encoding="utf-8", newline="") as f:
            html = f.read()
        i = html.index(_BLOB_MARK_BEGIN) + len(_BLOB_MARK_BEGIN)
        j = html.index(_BLOB_MARK_END, i)
        old = html[i:j]
        html = html[:i] + text + html[j:]
        with open(html_path, "w", encoding="utf-8", newline="") as f:
            f.write(html)
        wrote = True
    else:
        old = None

    stats = {
        "counts": {k: len(v) for k, v in sections.items()},
        "chars": len(text), "checks": checks, "failed": len(failed),
        "wrote": wrote, "html": html_path, "old_chars": len(old) if old else None,
        "widen": dict(widen),
    }
    if progress:
        progress(stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_generate(args):
    if not (0 <= args.min_id <= args.max_id <= 9999):
        raise SystemExit("invalid --min-id / --max-id range")
    stats = generate_into(
        args.db, args.min_id, args.max_id,
        progress=lambda pid, n: print("%s: %d solution(s)" % (pid, n)),
    )
    print("generate: %d row(s) total" % stats["rows"])
    print("  duplicate display hits (anomaly, should be 0): %d"
          % stats["duplicate_display_hits"])


def _cmd_annotate(args):
    n = run_annotate(args.db, progress=lambda k: None)
    print("annotate: recomputed features + score for %d row(s)" % n)


def _cmd_curate(args):
    s = run_curate(args.db)
    print("curate: %d solution(s) in, %d kept, %d problem(s)"
          % (s["total"], s["kept"], s["problems"]))
    print("  6-1 (nullified subexpr) : %d flagged is_redundant" % s["n_6_1"])
    print("  6-2 (identity op)       : %d (abolished in 5.2, always 0)"
          % s["n_6_2"])
    print("  6-3 (compressed dup)    : %d not is_repr (is_redundant stays 0)"
          % s["n_6_3"])
    print("  6-4 (kept as only soln) : %d problem(s) rescued" % s["n_6_4"])


def _cmd_constrain(args):
    s = run_constrain(args.db)
    print("constrain: %d puzzle(s) from %d problem(s)"
          % (s["puzzles"], s["problems"]))
    print("  base (rule_count=0)              : %d" % s["base"])
    print("  constrained (adopted)           : %d" % s["constrained"])
    print("  rejected: harder_by<1           : %d" % s["rejected_harder_by"])
    print("  rejected: no surviving soln     : %d"
          % s["rejected_no_nonredundant"])
    print("  6-5 rescued (nullifying-only)   : %d puzzle(s) / %d problem(s)"
          % (s["rescued_puzzle"], s["rescued_problems"]))
    print("  6-6 promoted to is_repr         : %d solution(s)"
          % s["promoted_repr"])


def _cmd_export(args):
    s = run_export(args.db, args.out)
    print("export: %d puzzle(s) -> %s (%d bytes)"
          % (s["puzzles"], s["path"], s["bytes"]))
    print("  with constraint    : %d" % s["with_constraint"])
    print("  without constraint : %d" % s["without_constraint"])
    print("  needs_fac / needs_pow : %d / %d"
          % (s["needs_fac"], s["needs_pow"]))


def _cmd_blob(args):
    stats = run_blob(args.db, args.html, write=not args.dry_run)
    c = stats["counts"]
    print("blob: COURSE %d / FREE %d / CHAL %d  (計 %d 行 / %d 文字)"
          % (c["COURSE"], c["FREE"], c["CHAL"],
             c["COURSE"] + c["FREE"] + c["CHAL"], stats["chars"]))
    print("  難易度の許容幅を広げた回数: %s" % stats["widen"])
    for name, ok, detail in stats["checks"]:
        print("  [%s] %-20s %s" % ("OK" if ok else "NG", name, detail))
    if stats["failed"]:
        raise SystemExit("blob: 検証 %d 項目が落ちたので書き込んでいない"
                         % stats["failed"])
    if stats["wrote"]:
        print("  %s の BLOB を差し替えた (%d -> %d 文字)"
              % (stats["html"], stats["old_chars"], stats["chars"]))
    else:
        print("  --dry-run: 書き込んでいない")


def _cmd_verify(args):
    total, failures = run_verify(args.db)
    print("verify: checked %d row(s)" % total)
    for sid, pid, disp, why in failures[:50]:
        print("  FAIL  id=%d  %s  %-40s  -- %s" % (sid, pid, disp, why))
    if failures:
        print("%d failure(s)" % len(failures))
        raise SystemExit(1)
    print("OK: every display string evaluates to exactly 10")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="make10.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="enumerate solutions into the DB")
    g.add_argument("--db", default=DB_DEFAULT)
    g.add_argument("--min-id", type=int, default=0, help="0..9999")
    g.add_argument("--max-id", type=int, default=9999, help="0..9999")
    g.set_defaults(func=_cmd_generate)

    a = sub.add_parser("annotate", help="recompute feature columns from shape")
    a.add_argument("--db", default=DB_DEFAULT)
    a.set_defaults(func=_cmd_annotate)

    c = sub.add_parser("curate", help="flag redundant solutions, pick reprs")
    c.add_argument("--db", default=DB_DEFAULT)
    c.set_defaults(func=_cmd_curate)

    cn = sub.add_parser("constrain",
                        help="generate operator-count constrained puzzles")
    cn.add_argument("--db", default=DB_DEFAULT)
    cn.set_defaults(func=_cmd_constrain)

    e = sub.add_parser("export", help="write the game JSON from puzzles")
    e.add_argument("--db", default=DB_DEFAULT)
    e.add_argument("--out", default=EXPORT_DEFAULT)
    e.set_defaults(func=_cmd_export)

    b = sub.add_parser("blob", help="rebuild the BLOB inside docs/index.html")
    b.add_argument("--db", default=DB_DEFAULT)
    b.add_argument("--html", default=BLOB_HTML_DEFAULT)
    b.add_argument("--dry-run", action="store_true",
                   help="組んで検証するだけで index.html を書き換えない")
    b.set_defaults(func=_cmd_blob)

    v = sub.add_parser("verify", help="re-check every display string == 10")
    v.add_argument("--db", default=DB_DEFAULT)
    v.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
