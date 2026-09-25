"""GAME-SPEC 12章の教訓に従い、make10.py とは独立に実装した検証。

solutions.display を「GAME-SPEC 2-2 の標準文法」で読み直し、
そこから uses_fraction / score を再計算して DB の値と突き合わせる。
生成側のコードは一切参照しない。10a/a（5.6）・階乗の比の 3 規則（5.7）・
負の累乗（5.8）もここで独立に書き直してある（DATA-SPEC 7 章）。
"""
import sqlite3
from fractions import Fraction
from math import factorial

OP_COST = {"+": 1, "-": 1, "*": 2, "/": 3, "^": 5, "!": 4}
BONUS = {"paren": 1, "fraction": 5, "zero_factorial": 3, "nested_factorial": 8,
         "ten_over": 2, "fac_ratio": 2, "whole_ratio": -1,
         "neg_exp": 4, "neg_base_even": 3, "neg_base_odd": 2}
POW_BONUS = {"A": "neg_exp", "B": "neg_base_even", "C": "neg_base_odd"}
MAX_FAC = 12
MAX_EXP = 24


class Bad(Exception):
    pass


def tokenize(s):
    # 表示は '0!' や ') !' ではなく ')!' のように '!' が直前に密着する
    out = []
    for w in s.split():
        while w and w.endswith("!"):
            out.append(w[:-1])
            w = None
            break
        else:
            out.append(w)
            continue
    # 上の書き方だと複数 '!' を扱えないので素直に文字単位で組み直す
    out = []
    for w in s.split():
        i = 0
        while i < len(w) and w[i] != "!":
            i += 1
        head, tail = w[:i], w[i:]
        if head:
            out.append(head)
        for ch in tail:
            out.append(ch)
    return out


# expr := term (('+'|'-') term)*      左結合
# term := power (('*'|'/') power)*    左結合
# power := postfix ('^' power)?       右結合
# postfix := atom '!'?                '!' の連続は構文エラー
# atom := DIGIT | '(' expr ')'
class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        v = self.t[self.i]
        self.i += 1
        return v

    def expr(self):
        n = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            n = ("bin", op, n, self.term())
        return n

    def term(self):
        n = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            n = ("bin", op, n, self.power())
        return n

    def power(self):
        n = self.postfix()
        if self.peek() == "^":
            self.take()
            n = ("bin", "^", n, self.power())
        return n

    def postfix(self):
        n = self.atom()
        if self.peek() == "!":
            self.take()
            n = ("fac", n)
            if self.peek() == "!":
                raise Bad("'!!' は構文エラー")
        return n

    def atom(self):
        tk = self.take()
        if tk == "(":
            n = self.expr()
            if self.take() != ")":
                raise Bad("括弧が閉じない")
            return n
        if len(tk) == 1 and tk.isdigit():
            return ("num", int(tk))
        raise Bad("予期しないトークン: " + tk)


def parse(s):
    p = P(tokenize(s))
    n = p.expr()
    if p.i != len(p.t):
        raise Bad("末尾に余りがある")
    return n


INVALID = object()


def ev(n, seen):
    """(値, 分数が現れたか) を返す。seen には中間値を積む。"""
    tag = n[0]
    if tag == "num":
        return Fraction(n[1])
    if tag == "fac":
        v = ev(n[1], seen)
        if v is INVALID or v.denominator != 1 or v.numerator < 0 or v.numerator > MAX_FAC:
            return INVALID
        r = Fraction(factorial(v.numerator))
        seen.append(r)
        return r
    a = ev(n[2], seen)
    b = ev(n[3], seen)
    if a is INVALID or b is INVALID:
        return INVALID
    op = n[1]
    if op == "+":
        r = a + b
    elif op == "-":
        r = a - b
    elif op == "*":
        r = a * b
    elif op == "/":
        if b == 0:
            return INVALID
        r = a / b
    else:  # ^
        if b.denominator != 1 or abs(b.numerator) > MAX_EXP:
            return INVALID
        if a == 0 and b.numerator < 0:
            return INVALID
        if a == 0 and b.numerator == 0:
            r = Fraction(1)
        else:
            r = a ** b.numerator
    seen.append(r)
    return r


def walk(n):
    yield n
    if n[0] == "fac":
        yield from walk(n[1])
    elif n[0] == "bin":
        yield from walk(n[2])
        yield from walk(n[3])


def conns(tree):
    """(ノード, そのノードを含む * / のつながりの根) の列（DATA-SPEC 7 章。5.7）。

    * / のノードは親も * / ならその根を引き継ぎ、そうでなければ自分が根。
    """
    out = []

    def go(n, root):
        mul = n[0] == "bin" and n[1] in ("*", "/")
        cr = (n if root is None else root) if mul else None
        out.append((n, cr))
        if n[0] == "fac":
            go(n[1], None)
        elif n[0] == "bin":
            go(n[2], cr)
            go(n[3], cr)

    go(tree, None)
    return out


def split_mul(n):
    """n を * と / で展開して（掛ける側の項, 割る側の項）に分ける。"""
    num, den = [], []

    def go(x, pos):
        if x[0] == "bin" and x[1] in ("*", "/"):
            go(x[2], pos)
            go(x[3], pos if x[1] == "*" else not pos)
            return
        (num if pos else den).append(x)

    go(n, True)
    return num, den


def fac_args_num(term):
    """掛ける側の項の中の階乗の引数（DATA-SPEC 7 章。5.7）。

    項の根からその階乗までの経路に + または - があり、もう一方の枝の値が 0 で
    なければ拾わない。`( 6! / 2 - 5! ) / 4!` の 5! は比ではないため。
    """
    out = []

    def go(x):
        if x[0] == "fac":
            v = ev(x[1], [])
            if v is not INVALID and v.denominator == 1:
                out.append(int(v))
            go(x[1])
        elif x[0] == "bin":
            if x[1] in ("+", "-"):
                if ev(x[3], []) == 0:
                    go(x[2])
                if ev(x[2], []) == 0:
                    go(x[3])
            else:
                go(x[2])
                go(x[3])

    go(term)
    return out


def fac_ratio(connroot):
    """つながりに (m+1)! / m! の組があるか（規則 2 の判定。5.7）。

    割る側は項そのものが階乗のときだけ拾う。
    """
    num, den = split_mul(connroot)
    dens = []
    for t in den:
        if t[0] == "fac":
            v = ev(t[1], [])
            if v is not INVALID and v.denominator == 1:
                dens.append(int(v))
    if not dens:
        return False
    for t in num:
        for a in fac_args_num(t):
            if any(a == d + 1 for d in dens):
                return True
    return False


def pow_kinds(n):
    """負の累乗の種類（DATA-SPEC 7 章。5.8）。

    `^` が効いている（値が底と違う）ものだけが対象。指数 0 は B にも C にも
    入れない（`^ 0` は何を入れても 1 にしているだけ）。
    """
    if n[0] != "bin" or n[1] != "^":
        return set()
    a = ev(n[2], [])
    b = ev(n[3], [])
    v = ev(n, [])
    if a is INVALID or b is INVALID or v is INVALID or v == a:
        return set()
    out = set()
    if b < 0:
        out.add("A")
    if a < 0 and b.denominator == 1 and b != 0:
        out.add("B" if b.numerator % 2 == 0 else "C")
    return out


def whole_ratio(tree):
    """式全体がその比だけで完結しているか（規則 3。5.7）。"""
    if tree[0] != "bin" or tree[1] != "/":
        return False
    if ev(tree, []) != 10:
        return False
    if tree[2][0] != "fac" or tree[3][0] != "fac":
        return False
    a = ev(tree[2][1], [])
    b = ev(tree[3][1], [])
    if a is INVALID or b is INVALID:
        return False
    return a.denominator == 1 and b.denominator == 1 and a == b + 1


def ten_over(n):
    """「10 の倍数を作ってから割り戻す」形か（DATA-SPEC 7 章。5.6）。

    a / b で 値(a) == 10 * 値(b)、値(b) は 2 以上の整数、a と b がどちらも
    階乗ではない（10!/9! 型を除く）、a を * と / で展開した掛ける側の項に
    値(b) と同じものが無い（打ち消しを除く）。
    """
    if n[0] != "bin" or n[1] != "/":
        return False
    a = ev(n[2], [])
    b = ev(n[3], [])
    if a is INVALID or b is INVALID:
        return False
    if b < 2 or b.denominator != 1 or a != 10 * b:
        return False
    if n[2][0] == "fac" and n[3][0] == "fac":
        return False
    terms = []

    def factors(x, pos):
        if x[0] == "bin" and x[1] in ("*", "/"):
            factors(x[2], pos)
            factors(x[3], pos if x[1] == "*" else not pos)
            return
        if pos:
            v = ev(x, [])
            if v is not INVALID:
                terms.append(v)

    factors(n[2], True)
    return all(t != b for t in terms)


def rescore(disp):
    tree = parse(disp)
    seen = []
    val = ev(tree, seen)
    if val is INVALID:
        return None
    uses_fraction = any(v.denominator != 1 for v in seen)
    total = 0
    neg_pow = set()
    zero_fac = nested_fac = over = ratio = False
    for n, conn in conns(tree):
        if n[0] == "bin":
            total += OP_COST[n[1]]
            neg_pow |= pow_kinds(n)
            # 規則 1（5.7）: つながりが階乗の比として読めるなら 10a/a にしない
            if ten_over(n) and not fac_ratio(conn):
                over = True
            if conn is n and fac_ratio(n):
                ratio = True
        elif n[0] == "fac":
            total += OP_COST["!"]
            if n[1][0] == "fac":
                nested_fac = True
            s2 = []
            cv = ev(n[1], s2)
            if cv is not INVALID and cv == 0:
                zero_fac = True
    total += BONUS["paren"] * disp.count("(")
    if uses_fraction:
        total += BONUS["fraction"]
    if zero_fac:
        total += BONUS["zero_factorial"]
    if nested_fac:
        total += BONUS["nested_factorial"]
    if over:
        total += BONUS["ten_over"]
    if ratio:                                   # 規則 2（5.7）
        total += BONUS["fac_ratio"]
        if whole_ratio(tree):                   # 規則 3（5.7）
            total += BONUS["whole_ratio"]
    for k in sorted(neg_pow):                   # 負の累乗（5.8）
        total += BONUS[POW_BONUS[k]]
    return val, uses_fraction, total


def main():
    c = sqlite3.connect("make10.db")
    rows = c.execute(
        "SELECT id, problem_id, display, score, uses_fraction FROM solutions"
    ).fetchall()

    bad_val = []
    frac_mismatch = []
    score_mismatch = []
    parse_err = []

    for sid, pid, disp, score, uf in rows:
        try:
            r = rescore(disp)
        except Bad as e:
            parse_err.append((sid, disp, str(e)))
            continue
        if r is None:
            bad_val.append((sid, pid, disp))
            continue
        val, uf2, sc2 = r
        if val != 10:
            bad_val.append((sid, pid, disp, str(val)))
        if int(uf2) != uf:
            frac_mismatch.append((sid, pid, disp, uf, int(uf2)))
        if sc2 != score:
            score_mismatch.append((sid, pid, disp, score, sc2))

    print("解の総数            :", len(rows))
    print("構文エラー          :", len(parse_err))
    print("値が10でない/計算不能:", len(bad_val))
    print("uses_fraction 不一致 :", len(frac_mismatch))
    print("score 不一致        :", len(score_mismatch))
    print()
    for lbl, lst in (("構文エラー", parse_err), ("値の異常", bad_val),
                     ("分数フラグ不一致", frac_mismatch), ("スコア不一致", score_mismatch)):
        if lst:
            print("--- %s の例 ---" % lbl)
            for x in lst[:8]:
                print("   ", x)
            print()


if __name__ == "__main__":
    main()
