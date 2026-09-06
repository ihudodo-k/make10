#!/usr/bin/env python3
"""Make10 問題データ生成パイプライン.

現時点で実装済みのサブコマンド:

    python make10.py generate   # 全探索して solutions に投入
    python make10.py annotate   # shape から特徴量と score (第7章) を再計算して埋める
    python make10.py curate     # 冗長解にフラグを立て、代表解を選出 (第6章)
    python make10.py constrain  # 演算子の使用回数による制約付き問題を生成 (第6-B章)
    python make10.py export     # puzzles からゲーム用 JSON を出力 (第8章)
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


def classify_nullified(tree, val):
    """6-1: 結果に影響しない部分式を含むか。理由文字列 or None を返す。

    x が演算子を1つ以上含む場合のみ対象:
        x * 0 / 0 * x  ,  x ^ 0  ,  1 ^ x
    ( '0 * x の結果に階乗を付けただけ' も、内側の '*' ノードを走査して検出する )
    """
    for n in iter_nodes(tree):
        if n[0] != "bin":
            continue
        op, a, b = n[1], n[2], n[3]
        if op == "*":
            if val(a) == 0 and has_operator(b):
                return "6-1: 0 * x"
            if val(b) == 0 and has_operator(a):
                return "6-1: x * 0"
        elif op == "^":
            if val(b) == 0 and has_operator(a):
                return "6-1: x ^ 0"
            if val(a) == 1 and has_operator(b):
                return "6-1: 1 ^ x"
    return None


def classify_identity(tree, val):
    """6-2: 値を変えない演算を含むか。理由文字列 or None を返す。

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


_CURATE_COLS = ("SELECT id, problem_id, shape, display, cnt_add, cnt_sub, "
                "cnt_mul, cnt_div, cnt_pow, cnt_fac, cnt_paren FROM solutions")


def run_curate(db_path, progress=None):
    """冗長解にフラグを立て代表解を選出する。集計 dict を返す。

    返り値: {"total", "kept", "n_6_1", "n_6_2", "n_6_3", "n_6_4", "problems"}

    6-1 / 6-2 は problem_id ごとに判定し、その問題に生き残りが1つ以上あるときだけ
    実際に適用する (第6章 6-4)。全滅する問題は 6-3 の読みやすさ順で1件だけ残し、
    その行の redundant_why に "6-4: kept (only solution)" を記録する。
    結果として、解が1つ以上ある問題はすべて problems テーブルに残る。
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

        flags = {}        # id -> redundant_why (is_redundant = 1 になる行)
        forced = {}       # id -> redundant_why (6-4 で残す行。is_redundant = 0)
        repr_ids = []

        for pid, prs in by_pid.items():
            digits = [int(ch) for ch in pid]
            ev = build_evaluator(digits)

            def val(n, _ev=ev):
                return _ev(n)[0]

            reasons = {}      # id -> 6-1/6-2 の理由 or None
            survivors = []
            for r in prs:
                tree = parse_shape(r[2])
                reason = (classify_nullified(tree, val)
                          or classify_identity(tree, val))
                reasons[r[0]] = reason
                if reason is None:
                    survivors.append(r)

            if survivors:
                # 通常ルート: 6-1 / 6-2 を適用し、生き残りを 6-3 で圧縮する
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
                        flags[m[0]] = "6-3: compressed into id=%d" % keep[0]
            else:
                # 6-4: このままでは解が全滅する。読みやすさ順で1件だけ残す
                prs_sorted = sorted(prs, key=_repr_sort_key)
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
        # 6-4 で残した行は「代表」だが、なぜ他が消えたかの痕跡として理由も残す
        conn.executemany(
            "UPDATE solutions SET redundant_why = ? WHERE id = ?",
            [(why, sid) for sid, why in forced.items()],
        )

        # problems テーブル: 冗長解を除いた解の数、代表解、スコアの最小/最大。
        # min_score / max_score は「冗長でない解」(is_redundant = 0) のスコア範囲。
        # これは constrain の base_min_score / puzzles.min_score と同じ基準。
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
            "n_6_2": sum(1 for w in flags.values() if w.startswith("6-2")),
            "n_6_3": sum(1 for w in flags.values() if w.startswith("6-3")),
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
        n_rej_noreprsurv = 0  # 冗長でない残存解が無いので不採用

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

                if not nonred:
                    # 冗長でない解が 1 つも無い -> 基本問題も含めて不採用
                    n_rej_noreprsurv += 1
                    continue

                example = min(nonred, key=_example_key)
                mn = example[3]                 # = 冗長でない残存解の最小スコア
                repr_surv_count = sum(1 for s in surv if s[2])

                if rc == 0:
                    hb = mn - base_min           # 定義上 0 (nonred == 全冗長でない解)
                    n_base += 1
                else:
                    hb = mn - base_min
                    if hb < 1:
                        n_rej_hb += 1
                        continue
                    n_constrained += 1

                puzzle_rows.append((
                    pid, rs, rc, len(surv), repr_surv_count, example[0],
                    mn, base_min, hb,
                ))

        conn.executemany(
            "INSERT INTO puzzles (problem_id, rules, rule_count, survivor_count, "
            "repr_survivor_count, example_solution_id, min_score, "
            "base_min_score, harder_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            puzzle_rows,
        )
        conn.commit()

        stats = {
            "puzzles": len(puzzle_rows),
            "problems": len(by_pid),
            "base": n_base,
            "constrained": n_constrained,
            "rejected_harder_by": n_rej_hb,
            "rejected_no_nonredundant": n_rej_noreprsurv,
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
    print("  6-1 (nullified subexpr) : %d removed" % s["n_6_1"])
    print("  6-2 (identity op)       : %d removed" % s["n_6_2"])
    print("  6-3 (compressed dup)    : %d removed" % s["n_6_3"])
    print("  6-4 (kept as only soln) : %d problem(s) rescued" % s["n_6_4"])


def _cmd_constrain(args):
    s = run_constrain(args.db)
    print("constrain: %d puzzle(s) from %d problem(s)"
          % (s["puzzles"], s["problems"]))
    print("  base (rule_count=0)              : %d" % s["base"])
    print("  constrained (adopted)           : %d" % s["constrained"])
    print("  rejected: harder_by<1           : %d" % s["rejected_harder_by"])
    print("  rejected: no non-redundant soln : %d"
          % s["rejected_no_nonredundant"])


def _cmd_export(args):
    s = run_export(args.db, args.out)
    print("export: %d puzzle(s) -> %s (%d bytes)"
          % (s["puzzles"], s["path"], s["bytes"]))
    print("  with constraint    : %d" % s["with_constraint"])
    print("  without constraint : %d" % s["without_constraint"])
    print("  needs_fac / needs_pow : %d / %d"
          % (s["needs_fac"], s["needs_pow"]))


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

    v = sub.add_parser("verify", help="re-check every display string == 10")
    v.add_argument("--db", default=DB_DEFAULT)
    v.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
