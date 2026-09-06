"""GAME-SPEC 12章の教訓に従い、make10.py とは独立に実装した検証。

solutions.display を「GAME-SPEC 2-2 の標準文法」で読み直し、
そこから uses_fraction / score を再計算して DB の値と突き合わせる。
生成側のコードは一切参照しない。
"""
import sqlite3
from fractions import Fraction
from math import factorial

OP_COST = {"+": 1, "-": 1, "*": 2, "/": 3, "^": 5, "!": 4}
BONUS = {"paren": 1, "fraction": 5, "zero_factorial": 3, "nested_factorial": 8}
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


def rescore(disp):
    tree = parse(disp)
    seen = []
    val = ev(tree, seen)
    if val is INVALID:
        return None
    uses_fraction = any(v.denominator != 1 for v in seen)
    total = 0
    zero_fac = nested_fac = False
    for n in walk(tree):
        if n[0] == "bin":
            total += OP_COST[n[1]]
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
