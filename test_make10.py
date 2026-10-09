#!/usr/bin/env python3
"""make10.py の generate / verify に対する小さなテスト。

    python -m unittest test_make10 -v
"""
import os
import tempfile
import unittest
from fractions import Fraction

import make10 as m


class ParserPitfalls(unittest.TestCase):
    """CLAUDE.md が明示している「既知の落とし穴」を verify のパーサで確認する。"""

    def test_pow_is_right_associative(self):
        # 0 ^ 0 ^ 0 は (0^0)^0 = 1 ではなく 0^(0^0) = 0^1 = 0
        self.assertEqual(m.parse_eval("0 ^ 0 ^ 0"), Fraction(0))

    def test_pow_then_factorial(self):
        # 2 ^ 3! は 2^(3!) = 2^6 = 64
        self.assertEqual(m.parse_eval("2 ^ 3!"), Fraction(64))

    def test_factorial_of_parenthesised_pow(self):
        # ( 2 ^ 3 )! は 8! = 40320
        self.assertEqual(m.parse_eval("( 2 ^ 3 )!"), Fraction(40320))

    def test_zero_pow_zero(self):
        self.assertEqual(m.parse_eval("0 ^ 0"), Fraction(1))

    def test_glued_factorial_tokens(self):
        # ')!' や '0!' のように ! が直前トークンに密着していても読める
        self.assertEqual(m.parse_eval("( 1 + 4 - 5 )!"), Fraction(1))
        self.assertEqual(m.parse_eval("0! + 9"), Fraction(10))


class ParserInvalidCases(unittest.TestCase):
    def test_zero_to_negative_power(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("0 ^ ( 0 - 1 )")

    def test_division_by_zero(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("1 / ( 2 - 2 )")

    def test_factorial_of_negative(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("( 0 - 1 )!")

    def test_non_integer_exponent(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("2 ^ ( 1 / 2 )")

    def test_exponent_out_of_range(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("2 ^ 5!")          # 指数 120 > MAX_EXPONENT_ABS

    def test_exponent_out_of_range_other_bases(self):
        # 6.7 で上限を外したのは底が -1 / 0 / 1 のときだけ。底 -2 も 24 まで
        with self.assertRaises(m.VerifyError):
            m.parse_eval("( 0 - 2 ) ^ 5!")
        self.assertEqual(m.parse_eval("2 ^ 4!"), Fraction(2 ** 24))   # 24 は有効

    def test_factorial_arg_out_of_range(self):
        with self.assertRaises(m.VerifyError):
            m.parse_eval("( 6 + 7 )!")      # 13 > MAX_FACTORIAL_ARG

    def test_double_factorial_is_syntax_error(self):
        # '3!!' は二重階乗と紛らわしいので構文エラー。( 3! )! と書かねばならない
        with self.assertRaises(m.VerifyError):
            m.parse_eval("3!!")
        with self.assertRaises(m.VerifyError):
            m.parse_eval("( 1 + 2 )!!")

    def test_parenthesised_repeated_factorial_ok(self):
        # 括弧で挟めば階乗の 2 回適用は有効。( 3! )! = 6! = 720
        self.assertEqual(m.parse_eval("( 3! )!"), Fraction(720))


class UnitBasePow(unittest.TestCase):
    """6.7: 底が -1 / 0 / 1 の累乗には指数の上限 (24) を掛けない。

    値は -1 / 0 / 1 にしかならないので安全装置が要らない。8959 は
    `( 8 - 9 ) ^ 5! + 9` = (-1)^120 + 9 でしか解けず、今まで封じられていた。
    生成側 (_apply_bin / _pow) と検証側 (_plain_eval) の両方で確かめる。
    """

    def ap(self, a, b):
        return m._apply_bin("^", Fraction(a), Fraction(b))

    def test_minus_one_even_and_odd(self):
        self.assertEqual(self.ap(-1, 120), (Fraction(1), 120))
        self.assertEqual(self.ap(-1, 5041), (Fraction(-1), 5041))
        self.assertEqual(self.ap(-1, 24), (Fraction(1), 24))      # 上限内も同じ値
        self.assertEqual(m.parse_eval("( 8 - 9 ) ^ 5! + 9"), Fraction(10))
        self.assertEqual(m.parse_eval("( 1 - 2 ) ^ ( 5! + 1 )"), Fraction(-1))

    def test_minus_one_negative_exponent(self):
        self.assertEqual(self.ap(-1, -121)[0], Fraction(-1))
        self.assertEqual(self.ap(-1, -120)[0], Fraction(1))
        self.assertEqual(m.parse_eval("( 1 - 2 ) ^ ( 0 - 5! )"), Fraction(1))

    def test_one_any_integer_exponent(self):
        self.assertEqual(self.ap(1, 479001600)[0], Fraction(1))
        self.assertEqual(self.ap(1, -720)[0], Fraction(1))
        self.assertEqual(m.parse_eval("1 ^ ( 0 - ( 3! )! )"), Fraction(1))

    def test_zero_positive_and_negative_exponent(self):
        self.assertEqual(self.ap(0, 720)[0], Fraction(0))
        self.assertEqual(self.ap(0, 0)[0], Fraction(1))           # 0 ^ 0 = 1 は不変
        self.assertIs(self.ap(0, -720)[0], m.INVALID)             # 0 の負冪は無効
        self.assertIs(self.ap(0, -1)[0], m.INVALID)
        with self.assertRaises(m.VerifyError):
            m.parse_eval("0 ^ ( 0 - 5! )")

    def test_non_integer_exponent_still_invalid(self):
        self.assertIs(self.ap(1, Fraction(1, 2))[0], m.INVALID)
        self.assertIs(self.ap(-1, Fraction(1, 2))[0], m.INVALID)
        with self.assertRaises(m.VerifyError):
            m.parse_eval("1 ^ ( 1 / 2 )")

    def test_other_bases_keep_the_limit(self):
        self.assertIs(self.ap(2, 25)[0], m.INVALID)
        self.assertIs(self.ap(-2, 25)[0], m.INVALID)
        self.assertIs(self.ap(Fraction(1, 2), 25)[0], m.INVALID)  # 分数の底も
        self.assertEqual(self.ap(2, 24), (Fraction(2 ** 24), 24))
        self.assertEqual(self.ap(2, -24)[0], Fraction(1, 2 ** 24))

    def test_huge_exponent_is_instant_and_capped(self):
        # `9 + 0! ^ 9! ^ 4!` の指数は 9!^24 (134 桁)。偶奇だけで決まるので一瞬で終わり、
        # max_exp_abs は SQLite の INTEGER に入るよう頭打ちになる
        import time
        t = time.perf_counter()
        tree = m.parse_tree("9 + 0! ^ 9! ^ 4!")
        val, _mfa, mea, _uf = m.build_evaluator([9, 0, 9, 4])(tree)
        self.assertEqual(val, Fraction(10))
        self.assertEqual(mea, m.MAX_EXP_ABS_STORED)
        self.assertEqual(m.MAX_EXP_ABS_STORED, 1 << 62)
        self.assertEqual(self.ap(-1, 10 ** 133)[1], 1 << 62)
        self.assertEqual(m.parse_eval("9 + 0! ^ 9! ^ 4!"), Fraction(10))
        self.assertLess(time.perf_counter() - t, 1.0)

    def test_plain_eval_agrees(self):
        # 検証 6 / 15 / 16 の独立実装も同じ規則で、範囲外は例外にする
        for s, digits, want in (
                ("( 8 - 9 ) ^ 5! + 9", [8, 9, 5, 9], Fraction(10)),
                ("( 0 - 0! ) ^ 7! + 9", [0, 0, 7, 9], Fraction(10)),
                ("9 + 1 ^ ( 6 / 1 )!", [9, 1, 6, 1], Fraction(10)),
                ("( 0 ^ 6! )! * ( 8 + 2 )", [0, 6, 8, 2], Fraction(10)),
                ("9 + 0! ^ 9! ^ 4!", [9, 0, 9, 4], Fraction(10))):
            self.assertEqual(m._plain_eval(m.parse_tree(s), digits), want, s)
        with self.assertRaises(ValueError):
            m._plain_eval(m.parse_tree("2 ^ 5! + 1"), [2, 5, 1])
        with self.assertRaises(ValueError):
            m._plain_eval(m.parse_tree("0 ^ ( 0 - 5! )"), [0, 0, 5])

    def test_generate_finds_8959(self):
        # 8959 の解はこれ 1 本だけで、6.6 までは 0 本だった。点数は 15
        # (- 1 + ^ 5 + ! 4 + + 1 + 括弧 1 + 負の底・偶数乗 3)
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(db)
        try:
            m.generate_into(db, 8959, 8959)
            m.run_annotate(db)
            import sqlite3
            conn = sqlite3.connect(db)
            rows = conn.execute("SELECT display, score, max_exp_abs FROM solutions "
                                "WHERE problem_id='8959'").fetchall()
            conn.close()
            self.assertEqual(rows, [("( 8 - 9 ) ^ 5! + 9", 15, 120)])
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(db + suffix)
                except OSError:
                    pass


class RenderRules(unittest.TestCase):
    def test_shape_and_display_example(self):
        # CLAUDE.md の例: ( 0! + 0! + 0! )! + 4  ->  n0 ! n1 ! + n2 ! + ! n3 +
        f = lambda s: ("fac", s)
        n = lambda i: ("num", i)
        b = lambda op, x, y: ("bin", op, x, y)
        tree = b("+", f(b("+", b("+", f(n(0)), f(n(1))), f(n(2)))), n(3))
        self.assertEqual(m.render_shape(tree), "n0 ! n1 ! + n2 ! + ! n3 +")
        self.assertEqual(m.render_display(tree, [0, 0, 0, 4]),
                         "( 0! + 0! + 0! )! + 4")

    def test_pow_left_nesting_gets_parens(self):
        n = lambda i: ("num", i)
        left = ("bin", "^", ("bin", "^", n(0), n(1)), n(2))   # (0^0)^0
        right = ("bin", "^", n(0), ("bin", "^", n(1), n(2)))  # 0^(0^0)
        self.assertEqual(m.render_display(left, [0, 0, 0, 0]), "( 0 ^ 0 ) ^ 0")
        self.assertEqual(m.render_display(right, [0, 0, 0, 0]), "0 ^ 0 ^ 0")

    def test_subtraction_right_child_gets_parens(self):
        n = lambda i: ("num", i)
        tree = ("bin", "-", n(0), ("bin", "-", n(1), n(2)))  # 9 - (1 - 2)
        self.assertEqual(m.render_display(tree, [9, 1, 2, 0]), "9 - ( 1 - 2 )")

    def test_factorial_of_factorial_renders_with_parens(self):
        # 階乗を 2 回適用した木は ( 3! )! とレンダリングされる。'3!!' にしてはいけない
        tree = ("fac", ("fac", ("num", 0)))
        out = m.render_display(tree, [3, 0, 0, 0])
        self.assertEqual(out, "( 3! )!")
        self.assertNotIn("!!", out)

    def test_mul_right_child_division_gets_parens(self):
        # 再発したバグ: op が '*' で右の子が '/' のとき括弧が落ちていた。
        # 0! + 4 * ( 9 / 4 ) を '0! + 4 * 9 / 4' と出すと、標準の左結合で
        # 読み直したときに別の木 ((0!+4)*9)/4 になってしまう。
        n = lambda i: ("num", i)
        f = lambda x: ("fac", x)
        tree = ("bin", "+", f(n(0)),
                ("bin", "*", n(1), ("bin", "/", n(2), n(3))))
        out = m.render_display(tree, [0, 4, 9, 4])
        self.assertEqual(out, "0! + 4 * ( 9 / 4 )")
        # 標準文法で読み直しても元の木と同じ意味 (往復チェックと同じ主旨)
        self.assertEqual(m.parse_eval(out), Fraction(10))

    def test_left_assoc_ops_get_parens_on_same_precedence_right_child(self):
        # 左結合の演算子は同順位の右の子に必ず括弧を付ける (^ は右結合なので例外)
        n = lambda i: ("num", i)
        add_right_add = ("bin", "+", n(0), ("bin", "+", n(1), n(2)))
        mul_right_mul = ("bin", "*", n(0), ("bin", "*", n(1), n(2)))
        self.assertEqual(m.render_display(add_right_add, [1, 2, 3, 0]),
                         "1 + ( 2 + 3 )")
        self.assertEqual(m.render_display(mul_right_mul, [1, 2, 3, 0]),
                         "1 * ( 2 * 3 )")


class IdentityFactorialPruning(unittest.TestCase):
    """値の変わらない階乗 (1!, 2!, 内側が 1/2 になる繰り返し適用) は generate で枝刈りする。"""

    def test_leaf_one_and_two_factorial_pruned(self):
        self.assertIs(m.evaluate(("fac", ("num", 0)), [1, 0, 0, 0])[0], m.INVALID)
        self.assertIs(m.evaluate(("fac", ("num", 0)), [2, 0, 0, 0])[0], m.INVALID)

    def test_repeated_application_to_one_pruned(self):
        # (0!)! : 内側 0! = 1 なので外側の階乗は無意味 -> 枝刈り
        self.assertIs(
            m.evaluate(("fac", ("fac", ("num", 0))), [0, 0, 0, 0])[0], m.INVALID)

    def test_value_changing_factorials_are_kept(self):
        # 0! = 1 は 0 -> 1 で値が変わるので残す
        self.assertEqual(
            m.evaluate(("fac", ("num", 0)), [0, 0, 0, 0])[0], Fraction(1))
        # ( 3! )! = 720 は値が変わるので残す
        self.assertEqual(
            m.evaluate(("fac", ("fac", ("num", 0))), [3, 0, 0, 0])[0],
            Fraction(720))

    def test_generate_emits_no_identity_factorial(self):
        structures = m.gen_structures(0, 4)
        for digits in ([1, 2, 3, 4], [2, 2, 6, 6], [0, 0, 7, 1], [3, 1, 2, 5]):
            ev = m.build_evaluator(digits)
            for st in structures:
                if ev(st)[0] is m.INVALID:
                    continue
                disp = m.render_display(st, digits)
                self.assertNotIn("1!", disp, disp)
                self.assertNotIn("2!", disp, disp)
                self.assertNotIn("!!", disp, disp)


class RoundTrip(unittest.TestCase):
    """木を評価した値と、その display を独立パーサで再評価した値が一致すること。

    表示側の括弧落ちバグ (過去のバグ) を検出するための最重要チェック。
    """

    def test_render_reparse_matches_tree_eval(self):
        structures = m.gen_structures(0, 4)
        checked = 0
        for digits in ([2, 3, 4, 5], [1, 2, 3, 4], [9, 0, 5, 3], [0, 0, 7, 1]):
            ev = m.build_evaluator(digits)
            for st in structures:
                val = ev(st)[0]
                if val is m.INVALID:
                    continue
                disp = m.render_display(st, digits)
                self.assertEqual(
                    m.parse_eval(disp), val,
                    "mismatch: %s  tree=%s  parsed=%s"
                    % (disp, val, m.parse_eval(disp)),
                )
                checked += 1
        self.assertGreater(checked, 1000)


class RoundTripStructural(unittest.TestCase):
    """display を独立文法で読み直した木が、元の木 (shape 相当) と構造一致すること。

    値だけの比較 (RoundTrip) では 4 * (9/4) 型の括弧欠落バグを検出できない
    (値は一致してしまう) ため、木そのものを比較する。verify の往復チェックと
    同じ主旨のテスト。
    """

    def test_parse_tree_matches_original_structure(self):
        structures = m.gen_structures(0, 4)
        checked = 0
        for digits in ([2, 3, 4, 5], [1, 2, 3, 4], [9, 0, 5, 3], [0, 0, 7, 1],
                       [4, 9, 4, 9]):
            ev = m.build_evaluator(digits)
            for st in structures:
                if ev(st)[0] is m.INVALID:
                    continue
                disp = m.render_display(st, digits)
                # shape 側は "num" にスロット番号を持つ。parse_tree も同じ規約
                shape_tree = m.parse_shape(m.render_shape(st))
                disp_tree = m.parse_tree(disp)
                self.assertEqual(
                    disp_tree, shape_tree,
                    "structural mismatch: %s  shape_tree=%s  parse_tree=%s"
                    % (disp, shape_tree, disp_tree),
                )
                checked += 1
        self.assertGreater(checked, 1000)


class EvaluatorMemoAddressReuse(unittest.TestCase):
    """build_evaluator の memo は id(node) キーだが、木への参照も一緒に持つため
    「木が解放されて別の木が同じアドレスに載る」ことによる誤キャッシュが起きない。

    1 つの評価器を使い回し、毎回 parse_shape で作り直した木を評価して、
    評価器を都度作り直す evaluate() の結果と一致することを確認する
    (旧実装 memo[id(node)] = res ではここが大量に食い違う)。
    """

    def test_shared_evaluator_matches_fresh_evaluate(self):
        digits = [3, 4, 3, 0]
        # 木の複雑さがばらけるよう間引いて数千個の shape を取る
        structs = m.gen_structures(0, 4)
        shapes = [m.render_shape(structs[i])
                  for i in range(0, len(structs), max(1, len(structs) // 3000))]
        del structs

        ev = m.build_evaluator(digits)
        checks = 0
        for _ in range(3):
            for sh in shapes:
                # 毎回新しい木を作り、参照を残さず捨てる。旧実装だと直前の木が
                # 解放されたアドレスに載って memo が誤った値を返す。
                fresh = m.evaluate(m.parse_shape(sh), digits)[0]
                shared = ev(m.parse_shape(sh))[0]
                self.assertEqual(
                    shared, fresh,
                    "shape=%s  shared=%s  fresh=%s" % (sh, shared, fresh))
                checks += 1
        self.assertGreater(checks, 2000)


class GenerateThenVerify(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_small_range_verifies_and_is_idempotent(self):
        m.generate_into(self.db, 4, 4)          # 問題 0004 のみ
        total1, failures1 = m.run_verify(self.db)
        self.assertEqual(failures1, [])
        self.assertGreater(total1, 0)           # 0004 には解がある

        # 冪等: もう一度流しても件数が変わらない
        m.generate_into(self.db, 4, 4)
        total2, failures2 = m.run_verify(self.db)
        self.assertEqual(failures2, [])
        self.assertEqual(total1, total2)

    def test_no_duplicate_display_hits(self):
        # _render は忠実出力になったので、異なる木が同じ display 文字列に
        # なることは原理的に無いはず。全件 (0000-9999) での確認は
        # 実運用の generate 実行時にログで確認する (このテストは速度優先で小範囲)。
        stats = m.generate_into(self.db, 0, 19)
        self.assertEqual(stats["duplicate_display_hits"], 0)

    def test_parallel_matches_single_including_ids(self):
        # 6.7: --jobs で列挙を並列にしても、solutions は id まで 1 本と同じ。
        # 既存の行がある DB (id が途中から振られる) で、分割を細かくして確かめる
        import sqlite3
        fd, other = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(other)
        saved = m.GENERATE_CHUNK
        try:
            for db in (self.db, other):
                m.generate_into(db, 0, 9)           # 先に入っている行
            m.generate_into(self.db, 3, 12)
            m.GENERATE_CHUNK = 3                    # 4 つに分かれる
            m.generate_into(other, 3, 12, jobs=2)
            q = "SELECT * FROM solutions ORDER BY id"
            a = sqlite3.connect(self.db)
            b = sqlite3.connect(other)
            ra, rb = a.execute(q).fetchall(), b.execute(q).fetchall()
            a.close()
            b.close()
            self.assertGreater(len(ra), 0)
            self.assertEqual(ra, rb)
        finally:
            m.GENERATE_CHUNK = saved
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(other + suffix)
                except OSError:
                    pass

    def test_known_solution_present(self):
        m.generate_into(self.db, 4, 4)
        import sqlite3
        conn = sqlite3.connect(self.db)
        rows = [r[0] for r in conn.execute(
            "SELECT display FROM solutions WHERE problem_id='0004'")]
        conn.close()
        self.assertIn("( 0! + 0! + 0! )! + 4", rows)


class ParseShapeRoundTrip(unittest.TestCase):
    """parse_shape は render_shape の逆 (木 -> shape -> 木 で一致)。"""

    def test_roundtrip_over_generated_structures(self):
        structures = m.gen_structures(0, 4)
        checked = 0
        for digits in ([0, 0, 0, 4], [2, 3, 4, 5], [9, 0, 3, 0]):
            ev = m.build_evaluator(digits)
            for st in structures:
                if ev(st)[0] is m.INVALID:
                    continue
                shape = m.render_shape(st)
                self.assertEqual(m.render_shape(m.parse_shape(shape)), shape)
                # 木から再構築しても値・表示が一致する
                self.assertEqual(
                    m.render_display(m.parse_shape(shape), digits),
                    m.render_display(st, digits))
                checked += 1
        self.assertGreater(checked, 500)


class CurateClassifiers(unittest.TestCase):
    def _val(self, tree, digits):
        ev = m.build_evaluator(digits)
        return lambda n: ev(n)[0]

    # 6-1 は 5.2 で「パターンの列挙」から「その桁を別の値に替えても値が変わらないか」
    # という一般判定 (classify_nullified) に作り直し、定義域が狭くて桁を動かせない
    # 部分式だけをパターン側 (_nullified_by_pattern) が補う形になった (DATA-SPEC 6-1)。
    # 両方を OR で使うので、両方を別々に確かめる
    def _nullified(self, shape, digits):
        tree = m.parse_shape(shape)
        ev = m.build_evaluator(digits)
        base = ev(tree)[0]
        return (m.classify_nullified(tree, digits, base),
                m._nullified_by_pattern(tree, lambda n: ev(n)[0]))

    def test_nullified_x_pow_0(self):
        # ( 1 + 2 ) ^ 0 + 9 : 底の 1 を何に替えても ( d + 2 ) ^ 0 = 1 で値が変わらない
        general, pattern = self._nullified("n0 n1 + n2 ^ n3 +", [1, 2, 0, 9])
        self.assertEqual(general, "6-1: digit#0 not contributing")
        self.assertEqual(pattern, "6-1: x ^ 0")

    def test_nullified_leaf_base_is_caught(self):
        # 5 ^ 0 + 9 + 0 : 5.1 までは「x に演算子が無い」ので対象外だったが、
        # 5.2 で葉にも広げた。5 を何に替えても d ^ 0 = 1（0 ^ 0 も 1）なので潰れている。
        # 葉を見逃すと 6-2 廃止後に `1 ^ 6` のような解答例が露出した (DATA-SPEC 6-1)
        general, pattern = self._nullified("n0 n1 ^ n2 + n3 +", [5, 0, 9, 0])
        self.assertEqual(general, "6-1: digit#0 not contributing")
        self.assertEqual(pattern, "6-1: x ^ 0")

    def test_nullified_all_digits_contribute(self):
        # ( 1 + 2 ) * 3 + 1 : どの桁を替えても値が変わる → どちらの判定にも掛からない
        self.assertEqual(
            self._nullified("n0 n1 + n2 * n3 +", [1, 2, 3, 1]), (None, None))

    def test_nullified_unsubstitutable_digit_contributes(self):
        # 3343 ( 3! )! / ( 3! * 4 * 3 ) : 最初の 3 は ( d! )! が d=3 以外すべて無効で
        # 差し替えられないが、式の値を決めている。「判定できない」は寄与している側に
        # 倒す (DATA-SPEC 6-1。逆に数えると 27,507 本に誤検出が混ざった)
        self.assertEqual(
            self._nullified("n0 ! ! n1 ! n2 * n3 * /", [3, 3, 4, 3]), (None, None))

    def test_identity_x_plus_0(self):
        # ( 3 + 0 ) + 0 + 7  ->  x + 0
        tree = m.parse_shape("n0 n1 + n2 + n3 +")
        self.assertEqual(
            m.classify_identity(tree, self._val(tree, [3, 0, 0, 7])),
            "6-2: x + 0")

    def test_identity_x_times_1(self):
        # ( 3 + 4 + 3 ) * 0!  ->  x * 1 (単位元は右)
        tree = m.parse_shape("n0 n1 + n2 + n3 ! *")
        self.assertEqual(
            m.classify_identity(tree, self._val(tree, [3, 4, 3, 0])),
            "6-2: x * 1")

    def test_identity_catches_left_unit(self):
        # 0! * ( 0! + 0! ) * 5  ->  1 * x も第6章 6-2 注記により対象
        tree = m.parse_shape("n0 ! n1 ! n2 ! + n3 * *")
        self.assertEqual(
            m.classify_identity(tree, self._val(tree, [0, 0, 0, 5])),
            "6-2: x * 1")

    def test_identity_catches_left_zero_add(self):
        # 0 + 2 * ( 1 + 4 )  ->  0 + x
        tree = m.parse_shape("n0 n1 n2 n3 + * +")
        self.assertEqual(
            m.classify_identity(tree, self._val(tree, [0, 2, 1, 4])),
            "6-2: x + 0")

    def test_zero_factorial_is_not_identity(self):
        # 0! = 1 は値が変わるので恒等演算ではない
        tree = m.parse_shape("n0 ! n1 ! + n2 ! + n3 +")
        self.assertIsNone(
            m.classify_identity(tree, self._val(tree, [0, 0, 0, 8])))


class TenOverBonus(unittest.TestCase):
    """10 の倍数を作って割り戻す形の加点 (第7章。5.6)。

    式はすべて make10.db に実在するもの (括弧内は problem_id)。
    """

    def _over(self, display, digits):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        return any(m.is_ten_over(n, val) for n in m.iter_nodes(tree))

    def test_plain_case_is_counted(self):
        # 5663: 30 を作って 3 で割り戻す
        self.assertTrue(self._over("5 * 6 / ( 6 - 3 )", [5, 6, 6, 3]))
        # 8898: 割られる側が括弧の中の足し算 (展開しない)
        self.assertTrue(self._over("( 8 + 8 * 9 ) / 8", [8, 8, 9, 8]))
        # 5722: 割られる側だけが階乗 (120 ÷ 12)。階乗どうしの比ではない
        self.assertTrue(self._over("5! / ( 7 * 2 - 2 )", [5, 7, 2, 2]))

    def test_node_in_the_middle_is_counted(self):
        # 0254: 最上位は '+' で、対象は式の途中の 240 / 24
        self.assertTrue(self._over("0 + 2 * 5! / 4!", [0, 2, 5, 4]))

    def test_non_integer_divisor_is_excluded(self):
        # 4175: 24 ÷ 2.4。「10 の倍数を作る」に当たらない
        self.assertFalse(self._over("4! / ( 1 + 7 / 5 )", [4, 1, 7, 5]))

    def test_factorial_ratio_is_excluded(self):
        # 0089: 10! / 9! は n!/(n-1)! の手筋で、倍率を作って割り戻す形ではない
        self.assertFalse(self._over("( 0! + 0! + 8 )! / 9!", [0, 0, 8, 9]))

    def test_cancelling_is_excluded(self):
        # 8222: 掛けた 2 をそのまま割り戻しただけ
        self.assertFalse(self._over("( 8 + 2 ) * 2 / 2", [8, 2, 2, 2]))

    def test_divisor_one_is_excluded(self):
        # 4611: b = 1 は割り戻しではない
        self.assertFalse(self._over("( 4 + 6 ) / 1 * 1", [4, 6, 1, 1]))

    def test_score_matches_spec_formula(self):
        # 5663  5 * 6 / ( 6 - 3 ) : '*'2 + '/'3 + '-'1 + 括弧1 = 7、10a/a で +2
        display, digits = "5 * 6 / ( 6 - 3 )", [5, 6, 6, 3]
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        _v, _fa, _ea, uf = ev(tree)
        self.assertEqual(
            m.score_solution(tree, (lambda n: ev(n)[0]), display.count("("), uf),
            7 + m.SCORE_BONUS["ten_over"])

    def test_bonus_is_added_once_per_solution(self):
        """対象ノードが複数あっても加点は 1 回。

        4 桁ではそういう式が 1 つも作れない (make10.db の全 246,977 解で 0 件)
        ので、ここは人工の木で確かめる。
        (( 5+5+5+5 )/2 + ( 5+5+5+5 )/2 + ( 5+5+5+5 )/2) / 3 = 10
        """
        def add4(i):
            return ("bin", "+", ("bin", "+", ("num", i), ("num", i + 1)),
                    ("bin", "+", ("num", i + 2), ("num", i + 3)))

        twenty_over_two = lambda i: ("bin", "/", add4(i), ("num", i + 4))
        inner = ("bin", "+", ("bin", "+", twenty_over_two(0),
                              twenty_over_two(5)), twenty_over_two(10))
        tree = ("bin", "/", inner, ("num", 15))
        digits = [5, 5, 5, 5, 2] * 3 + [3]
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10))
        self.assertEqual(
            sum(1 for n in m.iter_nodes(tree) if m.is_ten_over(n, val)), 4)
        c = m.count_ops(tree)
        bare = (c["+"] * m.OP_COST["+"] + c["/"] * m.OP_COST["/"])
        self.assertEqual(m.score_solution(tree, val, 0, ev(tree)[3]),
                         bare + m.SCORE_BONUS["ten_over"])


class FacRatioBonus(unittest.TestCase):
    """隣り合う階乗の比の 3 規則 (第7章。5.7)。

    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _tree(self, display, digits):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        return tree, val, ev

    def _ratio(self, display, digits):
        tree, val, _ev = self._tree(display, digits)
        return m.has_fac_ratio(tree, val)

    def _ten_over_counted(self, display, digits):
        """規則 1 を通って 10a/a の加点が実際に付くか。"""
        tree, val, _ev = self._tree(display, digits)
        return any(m.is_ten_over(n, val) and not m.fac_ratio_pairs(conn, val)
                   for n, conn in m.iter_conn(tree))

    def test_adjacent_ratio_is_counted(self):
        # 0087: 8!/7! は隣り合う階乗の比
        self.assertTrue(self._ratio("0! + 0! + 8! / 7!", [0, 0, 8, 7]))
        # 7622: 引き算の中に書かれた 7!/6! も、それ自体が 1 つのつながり
        self.assertTrue(self._ratio("( 7! / 6! - 2 ) * 2", [7, 6, 2, 2]))

    def test_non_adjacent_ratio_is_not_counted(self):
        # 0253: 5!/3! は 2 つ離れているので組にならない (隣り合う比だけが対象)
        self.assertFalse(self._ratio("0! / 2 * ( 5! / 3! )", [0, 2, 5, 3]))
        # 0243: 6!/4! も同じ
        self.assertFalse(self._ratio("( ( 0! + 2 )! )! / 4! / 3", [0, 2, 4, 3]))

    def test_ten_over_is_suppressed_by_ratio(self):
        """規則 1: つながりが比として読めるなら 10a/a は付けない。"""
        # 0054: ( 0!+0! ) * 5! / 4! は 240/24 だが、5!/4! の比として読める
        tree, val, ev = self._tree("( 0! + 0! ) * 5! / 4!", [0, 0, 5, 4])
        self.assertTrue(any(m.is_ten_over(n, val) for n in m.iter_nodes(tree)))
        self.assertFalse(self._ten_over_counted("( 0! + 0! ) * 5! / 4!",
                                                [0, 0, 5, 4]))
        self.assertTrue(m.has_fac_ratio(tree, val))

    def test_plus_minus_with_nonzero_sibling_is_not_a_ratio(self):
        """+ - をまたぐ組は拾わない。10a/a のほうが残る。"""
        # 6254: ( 6!/2 - 5! ) / 4! は 360-120=240 を 24 で割り戻す 10a/a で、
        # 5!/4! の比ではない (5! の相手が 6!/2 = 360 で 0 ではない)
        self.assertFalse(self._ratio("( 6! / 2 - 5! ) / 4!", [6, 2, 5, 4]))
        self.assertTrue(self._ten_over_counted("( 6! / 2 - 5! ) / 4!",
                                               [6, 2, 5, 4]))
        # 0554: ( 0 + 5! + 5! ) / 4! も 240/24 で、比ではない
        self.assertFalse(self._ratio("( 0 + 5! + 5! ) / 4!", [0, 5, 5, 4]))

    def test_decorative_zero_is_counted(self):
        """飾りの 0 (相手が 0 の + -) は今までどおり拾う。"""
        # 0098: ( 0 + 9! ) / 8! は 9!/8! の比
        self.assertTrue(self._ratio("0! + ( 0 + 9! ) / 8!", [0, 0, 9, 8]))
        # 0098: 引き算でも同じ
        self.assertTrue(self._ratio("0! - ( 0 - 9! ) / 8!", [0, 0, 9, 8]))

    def test_divisor_side_must_be_the_term_itself(self):
        """割る側は項そのものが階乗のときだけ拾う。"""
        # 0542: 5! / ( 4! / 2 ) は分解すると割る側の項が 4! なので組になる
        self.assertTrue(self._ratio("0 + 5! / ( 4! / 2 )", [0, 5, 4, 2]))
        self.assertFalse(self._ten_over_counted("0 + 5! / ( 4! / 2 )",
                                                [0, 5, 4, 2]))
        # 4877: 4! / ( 8! / 7! ) は 8! が割る側・7! が掛ける側へ回るので拾えない
        # (DATA-SPEC 7 章。詰めずに見送った形の回帰)
        self.assertFalse(self._ratio("4! / ( 8! / 7! ) + 7", [4, 8, 7, 7]))

    def test_whole_ratio_gives_back_one(self):
        """規則 3: 式全体が比だけで完結しているなら 1 点戻す。"""
        display, digits = "( 0 + 1 + 9 )! / 9!", [0, 1, 9, 9]
        tree, val, ev = self._tree(display, digits)
        self.assertTrue(m.is_whole_ratio(tree, val))
        # '+'1×2 + '/'3 + '!'4×2 = 13、括弧 1 で 14、比 +2、全体が比 -1 = 15、
        # 6.1: ( 0 + 1 + 9 )! は引数が式なので +2 (9! は数字なので対象外) -> 17
        self.assertEqual(
            m.score_solution(tree, val, display.count("("), ev(tree)[3]),
            13 + m.SCORE_BONUS["paren"] + m.SCORE_BONUS["fac_ratio"]
            + m.SCORE_BONUS["whole_ratio"] + m.SCORE_BONUS["expr_factorial"])
        # 0087 は途中に比があるだけなので戻さない
        tree2, val2, _ = self._tree("0! + 0! + 8! / 7!", [0, 0, 8, 7])
        self.assertFalse(m.is_whole_ratio(tree2, val2))

    def test_score_matches_spec_formula(self):
        # 0087  0! + 0! + 8! / 7! : '+'1×2 + '/'3 + '!'4×4 = 21、比 +2 -> 23
        # 0! は 5.9 で加点 (+3) の対象外 (引数が数字の 0 そのものなので)。
        # さらに 6.0 で 2 つ目の 0! の '!' を数えないので -4 -> 19
        display, digits = "0! + 0! + 8! / 7!", [0, 0, 8, 7]
        tree, val, ev = self._tree(display, digits)
        self.assertEqual(
            m.score_solution(tree, val, display.count("("), ev(tree)[3]),
            21 - m.OP_COST["!"] + m.SCORE_BONUS["fac_ratio"])

    def test_bonus_is_added_once_per_solution(self):
        """組が 2 つあっても加点は 1 回（4 桁では作れないので人工の木）。

        5! / 4! * ( 4! / 3! ) / 2 = 5 * 4 / 2 = 10。5!/4! と 4!/3! の 2 組。
        根の 20/2 は 10a/a に当たるが、同じつながりが比として読めるので
        規則 1 で消える。
        """
        fac = lambda i: ("fac", ("num", i))
        left = ("bin", "/", fac(0), fac(1))          # 5! / 4!
        right = ("bin", "/", fac(2), fac(3))         # 4! / 3!
        tree = ("bin", "/", ("bin", "*", left, right), ("num", 4))
        digits = [5, 4, 4, 3, 2]
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10))
        self.assertEqual(len(m.fac_ratio_pairs(tree, val)), 2)
        self.assertTrue(any(m.is_ten_over(n, val) for n in m.iter_nodes(tree)))
        c = m.count_ops(tree)
        bare = (c["*"] * m.OP_COST["*"] + c["/"] * m.OP_COST["/"]
                + c["fac"] * m.OP_COST["!"])
        self.assertEqual(m.score_solution(tree, val, 0, ev(tree)[3]),
                         bare + m.SCORE_BONUS["fac_ratio"])


class NegPowBonus(unittest.TestCase):
    """負の累乗の加点 3 種類と、2 つの詰め (第7章。5.8)。

    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _kinds(self, display, digits):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        got = set()
        for n in m.iter_nodes(tree):
            got |= m.pow_kinds(n, val)
        return got

    def _bare(self, tree):
        c = m.count_ops(tree)
        return (c["+"] * m.OP_COST["+"] + c["-"] * m.OP_COST["-"]
                + c["*"] * m.OP_COST["*"] + c["/"] * m.OP_COST["/"]
                + c["^"] * m.OP_COST["^"] + c["fac"] * m.OP_COST["!"])

    def test_negative_exponent(self):
        # 2523: 5 ^ -1 = 1/5 で逆数になる
        self.assertEqual(self._kinds("2 / 5 ^ ( 2 - 3 )", [2, 5, 2, 3]), {"A"})

    def test_negative_base_even(self):
        # 1692: ( -3 ) ^ 2 = 9 で符号が消える
        self.assertEqual(self._kinds("1 + ( 6 - 9 ) ^ 2", [1, 6, 9, 2]), {"B"})
        # 9674: ( -1 ) ^ 4 = 1 も同じ
        self.assertEqual(self._kinds("9 + ( 6 - 7 ) ^ 4", [9, 6, 7, 4]), {"B"})

    def test_negative_base_odd(self):
        # 2133: ( -2 ) ^ 3 = -8
        self.assertEqual(self._kinds("2 - ( 1 - 3 ) ^ 3", [2, 1, 3, 3]), {"C"})

    def test_positive_power_is_not_counted(self):
        # 2417: 底も指数も正。★累乗の導入問題
        self.assertEqual(self._kinds("2 ^ 4 + 1 - 7", [2, 4, 1, 7]), set())

    def test_ineffective_power_is_excluded(self):
        """詰め①: `^` が効いていない (値が底と同じ) 形は対象外。"""
        # 0019: 1 ^ -1 = 1。底が 1 なので指数が負でも何も起きない
        self.assertEqual(self._kinds("0! ^ ( 0 - 1 ) + 9", [0, 0, 1, 9]), set())
        # 1091: ( -9 ) ^ 1 = -9。指数 1 は恒等
        self.assertEqual(self._kinds("1 - ( 0 - 9 ) ^ 1", [1, 0, 9, 1]), set())

    def test_exponent_zero_is_excluded(self):
        """詰め②: 指数 0 は B にも C にも入れない。

        `( -1 ) ^ 0 = 1` は「負の数を偶数乗すると符号が消える」ではなく、
        `^ 0` が何を入れても 1 にしているだけ。値 1 は底 -1 と違うので
        詰め① (pow_effective) では落ちない。
        """
        # 0009
        tree = m.parse_tree("( 0 - 0! ) ^ 0 + 9")
        ev = m.build_evaluator([0, 0, 0, 9])
        val = (lambda n: ev(n)[0])
        pw = [n for n in m.iter_nodes(tree) if n[0] == "bin" and n[1] == "^"]
        self.assertTrue(m.pow_effective(pw[0], val))      # 詰め① は通る
        self.assertEqual(self._kinds("( 0 - 0! ) ^ 0 + 9", [0, 0, 0, 9]), set())

    def test_peff_is_shared_with_star_position(self):
        """`^` が効いているかの判定は ★ の導入位置と同じ関数を使う。"""
        # 2417 は ★累乗の導入問題 (効いている)、1091 は効いていない
        self.assertTrue(m._example_feat("2 ^ 4 + 1 - 7", "2417")[0])
        self.assertFalse(m._example_feat("1 - ( 0 - 9 ) ^ 1", "1091")[0])
        tree = m.parse_tree("2 ^ 4 + 1 - 7")
        ev = m.build_evaluator([2, 4, 1, 7])
        val = (lambda n: ev(n)[0])
        pw = [n for n in m.iter_nodes(tree) if n[0] == "bin" and n[1] == "^"]
        self.assertTrue(m.pow_effective(pw[0], val))

    def test_score_matches_spec_formula(self):
        # 1692  1 + ( 6 - 9 ) ^ 2 : '+'1 + '-'1 + '^'5 = 7、括弧 1、負の底・偶数乗 +3
        display, digits = "1 + ( 6 - 9 ) ^ 2", [1, 6, 9, 2]
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        self.assertEqual(
            m.score_solution(tree, (lambda n: ev(n)[0]), display.count("("),
                             ev(tree)[3]),
            7 + m.SCORE_BONUS["paren"] + m.SCORE_BONUS["neg_base_even"])

    def test_bonus_is_added_once_per_kind(self):
        """同じ種類が 2 か所あっても 1 回（4 桁では作れないので人工の木）。

        ( ( 0 - 1 ) ^ 2 + ( 0 - 2 ) ^ 2 ) * 2 = ( 1 + 4 ) * 2 = 10
        """
        tree = ("bin", "*", ("bin", "+",
                ("bin", "^", ("bin", "-", ("num", 0), ("num", 1)), ("num", 2)),
                ("bin", "^", ("bin", "-", ("num", 3), ("num", 4)), ("num", 5))),
                ("num", 6))
        digits = [0, 1, 2, 0, 2, 2, 2]
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10))
        pw = [n for n in m.iter_nodes(tree) if n[0] == "bin" and n[1] == "^"]
        self.assertEqual([sorted(m.pow_kinds(n, val)) for n in pw], [["B"], ["B"]])
        self.assertEqual(m.score_solution(tree, val, 0, ev(tree)[3]),
                         self._bare(tree) + m.SCORE_BONUS["neg_base_even"])

    def test_kinds_stack(self):
        """違う種類は重ねて付く（人工の木）。

        ( 0 - 2 ) ^ ( 0 - 1 ) * ( 4 - 9 ) * 4 = -1/2 * -5 * 4 = 10
        負の指数（A）と 負の底・奇数乗（C）の両方に当たる。
        """
        tree = ("bin", "*", ("bin", "*",
                ("bin", "^", ("bin", "-", ("num", 0), ("num", 1)),
                 ("bin", "-", ("num", 2), ("num", 3))),
                ("bin", "-", ("num", 4), ("num", 5))), ("num", 6))
        digits = [0, 2, 0, 1, 4, 9, 4]
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10))
        pw = [n for n in m.iter_nodes(tree) if n[0] == "bin" and n[1] == "^"]
        self.assertEqual(sorted(m.pow_kinds(pw[0], val)), ["A", "C"])
        self.assertTrue(ev(tree)[3])                      # 途中に分数が出る
        self.assertEqual(m.score_solution(tree, val, 0, ev(tree)[3]),
                         self._bare(tree) + m.SCORE_BONUS["fraction"]
                         + m.SCORE_BONUS["neg_exp"] + m.SCORE_BONUS["neg_base_odd"])


class ZeroFacBonus(unittest.TestCase):
    """引数が 0 の階乗の加点と、`0!` を外した詰め (第7章。5.9)。

    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _score(self, display, digits, cnt_paren):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        return tree, val, m.score_solution(tree, val, cnt_paren, ev(tree)[3])

    def test_bare_zero_factorial_is_not_counted(self):
        """0! だけの解には付かない (5.9 で外した側)。"""
        # 0595: '+'1×2 + '-'1 + '!'4 = 7。加点なし
        _t, _v, sc = self._score("0! + 5 + 9 - 5", [0, 5, 9, 5], 0)
        self.assertEqual(sc, 7)
        # 0026: 0! が 2 つあっても +3 は付かない。'!' の 4 点は 6.0 で
        # 1 回だけになったので '+'1×3 + '!'4 = 7 (BareZeroFacOnce で詰める)
        _t, _v, sc2 = self._score("0! + 0! + 2 + 6", [0, 0, 2, 6], 0)
        self.assertEqual(sc2, 7)

    def test_computed_zero_argument_is_counted(self):
        """引数が式で値が 0 の階乗には今までどおり付く。"""
        # 0009: '+'1×2 + '*'2 + '!'4 = 8、括弧 2 組 = +2、0 の階乗 = +3 -> 13
        _t, _v, sc = self._score("0 + ( ( 0 * 0 )! + 9 )", [0, 0, 0, 9], 2)
        self.assertEqual(sc, 8 + 2 + m.SCORE_BONUS["zero_factorial"])
        self.assertEqual(sc, 13)

    def test_both_kinds_keep_the_bonus(self):
        """0! と ( 0 * 0 )! の両方を含む解は 0/1 判定なので +3 のまま。"""
        # 0005: '+'1 + '*'2×2 + '!'4×2 = 13、括弧 2 組 = +2、+3 -> 18
        _t, _v, sc = self._score("( 0! + ( 0 * 0 )! ) * 5", [0, 0, 0, 5], 2)
        self.assertEqual(sc, 13 + 2 + m.SCORE_BONUS["zero_factorial"])
        self.assertEqual(sc, 18)

    def test_bonus_does_not_depend_on_scan_order(self):
        """同じ 2 つの階乗を入れ替えて書いた 0005 の 2 解で点が変わらない。"""
        a = self._score("( 0! + ( 0 * 0 )! ) * 5", [0, 0, 0, 5], 2)[2]
        b = self._score("( ( 0 * 0 )! + 0! ) * 5", [0, 0, 0, 5], 2)[2]
        self.assertEqual(a, b)
        # ( 0 - 0 )! の側も同じ (こちらは '-'1 なので 1 点安い)
        c = self._score("( 0! + ( 0 - 0 )! ) * 5", [0, 0, 0, 5], 2)[2]
        d = self._score("( ( 0 - 0 )! + 0! ) * 5", [0, 0, 0, 5], 2)[2]
        self.assertEqual((c, d), (17, 17))

    def test_plain_score_agrees(self):
        """検証 15 の独立実装 (_plain_score) も同じ判定をする。"""
        for display, digits, cp in (("0! + 5 + 9 - 5", [0, 5, 9, 5], 0),
                                    ("0! + 0! + 2 + 6", [0, 0, 2, 6], 0),
                                    ("0 + ( ( 0 * 0 )! + 9 )", [0, 0, 0, 9], 2),
                                    ("( 0! + ( 0 * 0 )! ) * 5", [0, 0, 0, 5], 2)):
            tree, _val, sc = self._score(display, digits, cp)
            # この 4 式には 10a/a・階乗の比・負の累乗は無いので素の点と一致する
            self.assertEqual(m._plain_score(tree, digits, cp)[0], sc, display)


class BareZeroFacOnce(unittest.TestCase):
    """`0!` の `!` は解ごとに 1 回だけ (第7章。6.0)。

    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _score(self, display, digits, cnt_paren=0):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        return tree, m.score_solution(tree, val, cnt_paren, ev(tree)[3])

    def test_one_bare_zero_is_charged_normally(self):
        """1 個なら今までどおり 4 点。"""
        # 0595  0! + 5 + 9 - 5 : '+'1×2 + '-'1 + '!'4 = 7
        _t, sc = self._score("0! + 5 + 9 - 5", [0, 5, 9, 5])
        self.assertEqual(sc, 2 * m.OP_COST["+"] + m.OP_COST["-"]
                         + m.OP_COST["!"])
        self.assertEqual(sc, 7)

    def test_two_bare_zeros_are_charged_once(self):
        """2 個目の `!` は数えない。"""
        # 0026  0! + 0! + 2 + 6 : '+'1×3 + '!'4×1 = 7 (5.9 までは 11)
        _t, sc = self._score("0! + 0! + 2 + 6", [0, 0, 2, 6])
        self.assertEqual(sc, 3 * m.OP_COST["+"] + m.OP_COST["!"])
        self.assertEqual(sc, 7)

    def test_three_bare_zeros_are_charged_once(self):
        """3 個でも 1 回。DATA-SPEC 7 章で帰結として受け入れた形。"""
        # 0007  0! + 0! + 0! + 7 : '+'1×3 + '!'4×1 = 7 (5.9 までは 15)
        _t, sc = self._score("0! + 0! + 0! + 7", [0, 0, 0, 7])
        self.assertEqual(sc, 3 * m.OP_COST["+"] + m.OP_COST["!"])
        self.assertEqual(sc, 7)
        # 同じ問題で 0! が 1 個増えるほど安くなるわけではない ―― 括弧の分だけ高い
        _t2, sc2 = self._score("0! + ( 0! + 0! + 7 )", [0, 0, 0, 7], 1)
        self.assertEqual(sc2, sc + m.SCORE_BONUS["paren"])

    def test_other_factorials_are_counted_per_node(self):
        """`0!` 以外の階乗はノードごとに 4 点のまま。"""
        # 0233  0 - 2 + 3! + 3! : '-'1 + '+'1×2 + '!'4×2 = 11
        _t, sc = self._score("0 - 2 + 3! + 3!", [0, 2, 3, 3])
        self.assertEqual(sc, m.OP_COST["-"] + 2 * m.OP_COST["+"]
                         + 2 * m.OP_COST["!"])
        self.assertEqual(sc, 11)

    def test_computed_zero_factorial_is_counted_per_node(self):
        """引数が式の階乗は `0!` ではないので 1 個目から数える。"""
        # 0005  ( 0! + ( 0 * 0 )! ) * 5 : '+'1 + '*'2×2 + '!'4×2 = 13、
        # 括弧 2 組 = +2、0 の階乗 = +3 -> 18。6.0 で 1 点も動かない
        _t, sc = self._score("( 0! + ( 0 * 0 )! ) * 5", [0, 0, 0, 5], 2)
        self.assertEqual(sc, 13 + 2 * m.SCORE_BONUS["paren"]
                         + m.SCORE_BONUS["zero_factorial"])
        self.assertEqual(sc, 18)
        # 書く順を変えても同じ
        _t2, sc2 = self._score("( ( 0 * 0 )! + 0! ) * 5", [0, 0, 0, 5], 2)
        self.assertEqual(sc2, 18)

    def test_plain_score_agrees(self):
        """検証 15 の独立実装 (_plain_score) も同じ数え方をする。"""
        for display, digits, cp in (("0! + 5 + 9 - 5", [0, 5, 9, 5], 0),
                                    ("0! + 0! + 2 + 6", [0, 0, 2, 6], 0),
                                    ("0! + 0! + 0! + 7", [0, 0, 0, 7], 0),
                                    ("0 - 2 + 3! + 3!", [0, 2, 3, 3], 0),
                                    ("( 0! + ( 0 * 0 )! ) * 5", [0, 0, 0, 5], 2)):
            tree, sc = self._score(display, digits, cp)
            # この 5 式には 10a/a・階乗の比・負の累乗は無いので素の点と一致する
            self.assertEqual(m._plain_score(tree, digits, cp)[0], sc, display)


class ExprFactorialBonus(unittest.TestCase):
    """引数が式の階乗の加点 (第7章。6.1)。ノードごとに +2。

    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _score(self, display, digits, cnt_paren=0):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val = (lambda n: ev(n)[0])
        self.assertEqual(val(tree), Fraction(10), display)   # 式が 10 になる
        return tree, m.score_solution(tree, val, cnt_paren, ev(tree)[3])

    def _n_expr_fac(self, display, digits):
        """引数が式で値が 0 でない階乗のノード数 (テスト側で数え直す)。"""
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        k = 0
        for n in m.iter_nodes(tree):
            if n[0] == "fac" and n[1][0] != "num" and ev(n[1])[0] != 0:
                k += 1
        return k

    def test_expression_argument_is_counted(self):
        """`( 8 - 7 + 2 )!` は +2。"""
        # 8724: '-'1 + '+'1×2 = 3、'!'4、括弧 1 組 = +1、式の階乗 = +2 -> 10
        _t, sc = self._score("( 8 - 7 + 2 )! + 4", [8, 7, 2, 4], 1)
        self.assertEqual(sc, 3 + m.OP_COST["!"] + m.SCORE_BONUS["paren"]
                         + m.SCORE_BONUS["expr_factorial"])
        self.assertEqual(sc, 10)
        self.assertEqual(self._n_expr_fac("( 8 - 7 + 2 )! + 4", [8, 7, 2, 4]), 1)

    def test_digit_argument_is_not_counted(self):
        """`3!` は引数が数字なので付かない。"""
        # 3652: '!'4 + '-'1 + '+'1 + '*'2 = 8。加点なし
        _t, sc = self._score("3! - 6 + 5 * 2", [3, 6, 5, 2])
        self.assertEqual(sc, m.OP_COST["!"] + m.OP_COST["-"] + m.OP_COST["+"]
                         + m.OP_COST["*"])
        self.assertEqual(sc, 8)
        self.assertEqual(self._n_expr_fac("3! - 6 + 5 * 2", [3, 6, 5, 2]), 0)

    def test_zero_valued_argument_is_excluded(self):
        """引数の値が 0 の階乗は対象外 (5.9 の線引きに揃えた)。"""
        # 0075: '+'1 + '*'2×2 = 5、'!'4×2 = 8、括弧 2 組 = +2、0 の階乗 = +3 -> 18。
        # `0!` も `( 0 * 7 )!` もどちらも式の階乗には数えない
        _t, sc = self._score("( 0! + ( 0 * 7 )! ) * 5", [0, 0, 7, 5], 2)
        self.assertEqual(sc, 5 + 8 + 2 * m.SCORE_BONUS["paren"]
                         + m.SCORE_BONUS["zero_factorial"])
        self.assertEqual(sc, 18)
        # 0009: ( 0 * 0 )! だけの解も動かない ('+'1×2 + '*'2 + '!'4 + 括弧 2 + 3)
        _t2, sc2 = self._score("0 + ( ( 0 * 0 )! + 9 )", [0, 0, 0, 9], 2)
        self.assertEqual(sc2, 13)

    def test_nested_factorial_stacks(self):
        """`( 3! )!` は nested_factorial (+8) と重なり、外側だけが対象。"""
        # 0319: '*'2 + '+'1×2 = 4、'!'4×2 = 8、括弧 1 組 = +1、
        # 階乗の 2 回適用 = +8、式の階乗 = +2 (外側だけ) -> 23
        _t, sc = self._score("0 * ( 3! )! + 1 + 9", [0, 3, 1, 9], 1)
        self.assertEqual(sc, 4 + 8 + m.SCORE_BONUS["paren"]
                         + m.SCORE_BONUS["nested_factorial"]
                         + m.SCORE_BONUS["expr_factorial"])
        self.assertEqual(sc, 23)
        # 内側の `3!` は引数が数字なので数えない -> 対象は 1 ノードだけ
        self.assertEqual(self._n_expr_fac("0 * ( 3! )! + 1 + 9", [0, 3, 1, 9]), 1)

    def test_counted_per_node(self):
        """0/1 判定ではなくノードごと ―― 2 個あれば +4。"""
        # 0334: '+'1 + '-'1 + '+'1 = 3、'!'4×2 = 8、括弧 2 組 = +2、
        # 式の階乗 = +2×2 (外側の ( … - 3 )! と内側の ( 0 + 3 )!) -> 17
        d = "( ( 0 + 3 )! - 3 )! + 4"
        self.assertEqual(self._n_expr_fac(d, [0, 3, 3, 4]), 2)
        _t, sc = self._score(d, [0, 3, 3, 4], 2)
        self.assertEqual(sc, 3 + 8 + 2 * m.SCORE_BONUS["paren"]
                         + 2 * m.SCORE_BONUS["expr_factorial"])
        self.assertEqual(sc, 17)

    def test_star_stage_wants_a_digit_argument(self):
        """★階乗 (26〜28 問目) の段は引数が数字の解答例だけを採る (6.1)。"""
        # 4144 は 6.1 の 28 問目 (4! の形)、4568 は式の階乗なので採らない
        self.assertFalse(m._example_feat("4 + 1 * 4! / 4", "4144")[2])
        self.assertTrue(m._example_feat("4 + ( 5 + 6 - 8 )!", "4568")[2])
        cond = m._course_stage_cond(26)
        base = {"nf": True, "fbig": True, "ops": set("+!"), "np": False,
                "peff": False, "par": False}
        self.assertTrue(cond(dict(base, fexpr=False)))
        self.assertFalse(cond(dict(base, fexpr=True)))

    def test_plain_score_agrees(self):
        """検証 15 の独立実装 (_plain_score) も同じ数え方をする。"""
        for display, digits, cp in (("( 8 - 7 + 2 )! + 4", [8, 7, 2, 4], 1),
                                    ("3! - 6 + 5 * 2", [3, 6, 5, 2], 0),
                                    ("( 0! + ( 0 * 7 )! ) * 5", [0, 0, 7, 5], 2),
                                    ("0 * ( 3! )! + 1 + 9", [0, 3, 1, 9], 1),
                                    ("( ( 0 + 3 )! - 3 )! + 4", [0, 3, 3, 4], 2)):
            tree, sc = self._score(display, digits, cp)
            # この 5 式には 10a/a・階乗の比・負の累乗は無いので素の点と一致する
            self.assertEqual(m._plain_score(tree, digits, cp)[0], sc, display)


class ExampleKeyDecorations(unittest.TestCase):
    """解答例の選び方に足した 2 鍵 (6.3。DATA-SPEC 6-B「解答例の選び方」)。

    スコアの次に「飾りが少ない」→「分数を通らない」を見る。
    式はすべて make10.db に実在するもの (コメントの 4 桁が problem_id)。
    """

    def _decor(self, display, digits):
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        self.assertEqual(ev(tree)[0], Fraction(10), display)   # 式が 10 になる
        return m.count_decorations(tree, digits)

    def _row(self, sid, display, digits):
        """_CONSTRAIN_SOL_COLS と同じ並びの行を組む。"""
        tree = m.parse_tree(display)
        ev = m.build_evaluator(digits)
        val, _mfa, _mea, uf = ev(tree)
        self.assertEqual(val, Fraction(10), display)
        c = m.count_ops(tree)
        cp = display.count("(")
        score = m.score_solution(tree, lambda n: ev(n)[0], cp, uf)
        return (sid, "".join(str(d) for d in digits), 0, score, cp,
                c["-"], c["/"], len(display), c["+"], c["*"], c["^"],
                c["fac"], 0, "", m.render_shape(tree), 1 if uf else 0)

    def _pick(self, *rows):
        """_example_key が選ぶ行を返す (run_constrain と同じ呼び方)。"""
        decor = {r[0]: m._decorations_of(r) for r in rows}
        return min(rows, key=lambda s: m._example_key(s, decor))

    # --- 飾りの数え方 ---------------------------------------------------
    def test_bare_zero_added_is_a_decoration(self):
        """`0 +` は飾り 1 つ。0348"""
        self.assertEqual(self._decor("0 + 3! - 4 + 8", [0, 3, 4, 8]), 1)
        self.assertEqual(self._decor("0! - 3 + 4 + 8", [0, 3, 4, 8]), 0)

    def test_bare_one_multiplied_is_a_decoration(self):
        """`* 1` は飾り 1 つ。3371"""
        self.assertEqual(self._decor("3! - 3 + 7 * 1", [3, 3, 7, 1]), 1)
        self.assertEqual(self._decor("3 * 3! - 7 - 1", [3, 3, 7, 1]), 0)

    def test_zero_factorial_identity_is_a_decoration(self):
        """`0! *` は飾り 1 つ (単位元を `0!` で作っている)。0302"""
        self.assertEqual(self._decor("0! * ( 3! - 0! ) * 2", [0, 3, 0, 2]), 1)
        # 同じ式の `3! - 0!` は「引き算の右が 1」なので飾りではない (単位元は 0)
        self.assertEqual(self._decor("( 0! - 3! ) * ( 0 - 2 )", [0, 3, 0, 2]), 0)

    def test_several_decorations_are_counted_per_node(self):
        """`+ 0` と `/ 1` で飾り 2 つ。3071"""
        self.assertEqual(self._decor("3 + 0 + 7 / 1", [3, 0, 7, 1]), 2)

    def test_compound_zero_is_not_counted(self):
        """`3! - 6`（式で作った 0）を足す形は数えない。3652 = 本編 26 問目"""
        self.assertEqual(self._decor("3! - 6 + 5 * 2", [3, 6, 5, 2]), 0)

    def test_compound_one_is_not_counted(self):
        """`6 / 6`（式で作った 1）を掛ける形は数えない。6691"""
        self.assertEqual(self._decor("6 / 6 * 9 + 1", [6, 6, 9, 1]), 0)
        # 同じ 4 桁で `9 * 1` は素の 1 なので数える
        self.assertEqual(self._decor("6 / 6 + 9 * 1", [6, 6, 9, 1]), 1)

    def test_subtracting_bare_one_is_not_a_decoration(self):
        """`- 1` は値を変えるので飾りではない。3371"""
        self.assertEqual(self._decor("3 * 3! - 7 - 1", [3, 3, 7, 1]), 0)

    # --- 同点の崩し方 ---------------------------------------------------
    def test_decoration_breaks_the_tie(self):
        """同点なら飾りの無いほうを選ぶ。0348 (どちらも 7 点)"""
        a = self._row(1, "0 + 3! - 4 + 8", [0, 3, 4, 8])
        b = self._row(2, "0! - 3 + 4 + 8", [0, 3, 4, 8])
        self.assertEqual(a[3], b[3])                      # スコアが同点
        self.assertIs(self._pick(a, b), b)
        self.assertIs(self._pick(b, a), b)                # 並び順に依らない

    def test_decoration_wins_over_parenthesis_count(self):
        """飾りは括弧より先に見る。0302 (どちらも 14 点・括弧は 1 対 2)"""
        a = self._row(1, "0! * ( 3! - 0! ) * 2", [0, 3, 0, 2])
        b = self._row(2, "( 0! - 3! ) * ( 0 - 2 )", [0, 3, 0, 2])
        self.assertEqual(a[3], b[3])
        self.assertLess(a[4], b[4])                       # 飾りつきの方が括弧は少ない
        self.assertIs(self._pick(a, b), b)

    def test_fraction_breaks_the_tie(self):
        """飾りが同じなら分数を通らないほうを選ぶ。2366 (どちらも 11 点)"""
        a = self._row(1, "2 / 3 * 6 + 6", [2, 3, 6, 6])
        b = self._row(2, "2 * ( 3! - 6 / 6 )", [2, 3, 6, 6])
        self.assertEqual(a[3], b[3])
        self.assertEqual((a[15], b[15]), (1, 0))          # 分数を通るのは a だけ
        self.assertEqual(m._decorations_of(a), m._decorations_of(b))
        self.assertIs(self._pick(a, b), b)

    def test_score_still_comes_first(self):
        """スコアは第 1 の鍵のまま。飾りが無くても高い解は選ばれない。0348"""
        cheap = self._row(1, "0 + 3! - 4 + 8", [0, 3, 4, 8])       # 7 点・飾り 1
        dear = self._row(2, "0! - ( 3 - 4 - 8 )", [0, 3, 4, 8])    # 8 点・飾り 0
        self.assertLess(cheap[3], dear[3])
        self.assertEqual(m._decorations_of(dear), 0)
        self.assertIs(self._pick(cheap, dear), cheap)

    def test_key_order(self):
        """鍵の並びが仕様どおりか。"""
        r = self._row(7, "0 + 3! - 4 + 8", [0, 3, 4, 8])
        decor = {7: 3}
        self.assertEqual(m._example_key(r, decor),
                         (r[3], 3, r[15], r[4], r[6], r[5], r[7], r[0]))

    # --- 独立実装との一致 -----------------------------------------------
    def test_plain_implementation_agrees(self):
        """検証 6 の独立実装 (_plain_decorations / _plain_uses_fraction) と一致する。"""
        for display, digits in (("0 + 3! - 4 + 8", [0, 3, 4, 8]),
                                ("0! - 3 + 4 + 8", [0, 3, 4, 8]),
                                ("3! - 3 + 7 * 1", [3, 3, 7, 1]),
                                ("0! * ( 3! - 0! ) * 2", [0, 3, 0, 2]),
                                ("3 + 0 + 7 / 1", [3, 0, 7, 1]),
                                ("3! - 6 + 5 * 2", [3, 6, 5, 2]),
                                ("6 / 6 * 9 + 1", [6, 6, 9, 1]),
                                ("6 / 6 + 9 * 1", [6, 6, 9, 1]),
                                ("2 / 3 * 6 + 6", [2, 3, 6, 6]),
                                ("2 * ( 3! - 6 / 6 )", [2, 3, 6, 6])):
            tree = m.parse_tree(display)
            ev = m.build_evaluator(digits)
            self.assertEqual(m._plain_decorations(tree, digits),
                             m.count_decorations(tree, digits), display)
            self.assertEqual(m._plain_uses_fraction(tree, digits),
                             bool(ev(tree)[3]), display)


class CourseFormRule(unittest.TestCase):
    """本編 1〜100 問目の「同じ形」の制限 (6.2。DATA-SPEC 8-B)。

    式はすべて make10.db に実在する解答例 (コメントの 4 桁が problem_id)。
    """

    def test_skeleton_merges_plus_and_minus(self):
        """粒度 B: 符号の並びだけが違う式は同じ骨格になる。"""
        # 4058 と 4759。6.1 では 34・39 問目に並んでいた 2 問
        a = m._form_skeleton("4 + ( 0 - 5 + 8 )!")
        b = m._form_skeleton("4 + ( 7 + 5 - 9 )!")
        self.assertEqual(a, b)
        self.assertEqual(a, "_ ± ( _ ± _ ± _ ) !")
        # 括弧と演算子の位置が違えば別の骨格 (7448)
        self.assertNotEqual(a, m._form_skeleton("( 7 - 4 )! - 4 + 8"))

    def test_add_sub_only_is_exempt(self):
        """`+` `-` だけの式は対象外 (1〜4 問目は骨格が 1 通りしか無い)。"""
        self.assertEqual(m._form_skeleton("8 + 8 - 4 - 2"), "")      # 8842
        self.assertEqual(m._form_skeleton("0 + 7 + 5 - 2"), "")      # 0752
        # 階乗が入れば対象外ではない (3769)
        self.assertEqual(m._form_skeleton("3! + 7 + 6 - 9"),
                         "_ ! ± _ ± _ ± _")
        # 掛け算が入れば対象外ではない (9156)
        self.assertEqual(m._form_skeleton("9 - 1 * 5 + 6"), "_ ± _ * _ ± _")

    def test_fac_values_are_the_arguments_of_expression_factorials(self):
        """粒度 D: 引数が式の階乗の、引数の値の多重集合。"""
        # 4058 も 7448 も「3 を作って階乗する」なので同じ鍵になる
        self.assertEqual(m._form_fac_values("4 + ( 0 - 5 + 8 )!", "4058"), "3")
        self.assertEqual(m._form_fac_values("( 7 - 4 )! - 4 + 8", "7448"), "3")
        # 0319: ( 3! )! は外側だけが対象 (引数 3! の値 6)
        self.assertEqual(m._form_fac_values("0 * ( 3! )! + 1 + 9", "0319"), "6")
        # 0199: ( 0 + 1 + 9 )! は対象・9! は数字なので対象外
        self.assertEqual(m._form_fac_values("( 0 + 1 + 9 )! / 9!", "0199"), "10")

    def test_digit_factorial_is_exempt(self):
        """`3!` `4!` のように引数が数字だけの階乗は対象外 (★階乗の 3 問のため)。"""
        for display, pid in (("3! - 6 + 5 * 2", "3652"),      # 26 問目
                             ("0 + 3! / 2 + 7", "0327"),      # 27 問目
                             ("4 + 1 * 4! / 4", "4144"),      # 28 問目
                             ("8 / 8 + 0! + 8", "8808")):     # 0! も対象外
            self.assertEqual(m._form_fac_values(display, pid), "", display)

    def test_same_form_uses_either_key(self):
        """B と D のどちらか一方でも一致したら同じ形とみなす。空の鍵は当たらない。"""
        ban = (frozenset(["_ ± ( _ ± _ ± _ ) !"]), frozenset(["3"]))
        self.assertTrue(m._course_same_form({"fb": "_ ± ( _ ± _ ± _ ) !",
                                             "fd": "9"}, ban))     # B で一致
        self.assertTrue(m._course_same_form({"fb": "_ ! ± _", "fd": "3"}, ban))
        self.assertFalse(m._course_same_form({"fb": "_ ! ± _", "fd": "9"}, ban))
        # 空の鍵 (対象外) は ban に入っていても当たらない
        self.assertFalse(m._course_same_form({"fb": "", "fd": ""},
                                             (frozenset([""]), frozenset([""]))))

    def test_ban_window_and_range(self):
        """窓は直前 COURSE_FORM_WINDOW 問。COURSE_FORM_UNTIL より後ろは制限しない。"""
        rows = [{"fb": "b%d" % i, "fd": "d%d" % i} for i in range(30)]
        ban_b, ban_d = m._course_form_ban(rows, 20)
        self.assertEqual(len(ban_b), m.COURSE_FORM_WINDOW)
        self.assertIn("b%d" % (30 - m.COURSE_FORM_WINDOW), ban_b)
        self.assertNotIn("b%d" % (30 - m.COURSE_FORM_WINDOW - 1), ban_b)
        self.assertEqual(len(ban_d), m.COURSE_FORM_WINDOW)
        # 101 問目以降は空
        self.assertEqual(m._course_form_ban(rows, m.COURSE_FORM_UNTIL + 1),
                         (frozenset(), frozenset()))
        # 空の鍵は ban に入れない
        self.assertEqual(m._course_form_ban([{"fb": "", "fd": ""}], 5),
                         (frozenset(), frozenset()))

    def test_tokens_reject_unknown_text(self):
        """トークンに分解できない文字列は黙って通さない。"""
        with self.assertRaises(ValueError):
            m._form_tokens("4 + x")


class AnnotateAndCurate(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)
        m.generate_into(self.db, 4, 4)     # 問題 0004

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_annotate_is_idempotent_and_fills_score(self):
        m.run_annotate(self.db)
        import sqlite3
        conn = sqlite3.connect(self.db)
        rows1 = conn.execute(
            "SELECT id, score FROM solutions ORDER BY id").fetchall()
        # 全行 score が埋まっている
        self.assertTrue(all(sc is not None and sc > 0 for _, sc in rows1))
        conn.close()

        m.run_annotate(self.db)             # もう一度流しても同じ
        conn = sqlite3.connect(self.db)
        rows2 = conn.execute(
            "SELECT id, score FROM solutions ORDER BY id").fetchall()
        conn.close()
        self.assertEqual(rows1, rows2)

    def test_score_matches_spec_formula(self):
        # ( 0! + 0! + 0! )! + 4 :
        #   演算子 = '+'*3 + '!'*4 = 3*1 + 4*4 = 19
        #   括弧 1 組 = +1、分数なし、入れ子階乗なし
        #   0! は 5.9 で加点の対象外 (外側の階乗の引数は 3 なので 0 でもない)
        #   6.0: 0! が 3 つあるので 2 つ目と 3 つ目の '!' を数えない -> -8
        #   (外側の ( … )! は 0! ではないので 4 点のまま)
        #   6.1: 外側の ( … )! は引数が式 (値 3) なので 式の階乗 +2
        #   (内側の 0! は引数が数字なので対象外) -> 20 - 8 + 2 = 14
        import sqlite3
        m.run_annotate(self.db)
        conn = sqlite3.connect(self.db)
        sc = conn.execute(
            "SELECT score FROM solutions WHERE problem_id = '0004' "
            "AND display = ?", ("( 0! + 0! + 0! )! + 4",)).fetchone()[0]
        conn.close()
        self.assertEqual(sc, 14)

    def test_curate_partitions_rows_and_is_idempotent(self):
        m.run_annotate(self.db)
        s1 = m.run_curate(self.db)
        s2 = m.run_curate(self.db)
        self.assertEqual(s1, s2)
        self.assertEqual(
            s1["kept"] + s1["n_6_1"] + s1["n_6_2"] + s1["n_6_3"], s1["total"])
        self.assertEqual(s1["n_6_4"], 0)   # 0004 は生き残りがあるので 6-4 は不要

        import sqlite3
        conn = sqlite3.connect(self.db)
        # 各行はちょうど「代表」か「冗長」のどちらか
        both = conn.execute(
            "SELECT COUNT(*) FROM solutions "
            "WHERE is_repr = 1 AND is_redundant = 1").fetchone()[0]
        neither = conn.execute(
            "SELECT COUNT(*) FROM solutions "
            "WHERE is_repr = 0 AND is_redundant = 0").fetchone()[0]
        self.assertEqual((both, neither), (0, 0))

        kept = conn.execute(
            "SELECT COUNT(*) FROM solutions WHERE is_repr = 1").fetchone()[0]
        self.assertEqual(kept, s1["kept"])

        # problems は代表解の数と repr_solution_id を持つ
        row = conn.execute(
            "SELECT solution_count, repr_solution_id FROM problems "
            "WHERE problem_id = '0004'").fetchone()
        self.assertEqual(row[0], kept)
        self.assertEqual(
            conn.execute("SELECT is_repr FROM solutions WHERE id = ?",
                         (row[1],)).fetchone()[0], 1)
        conn.close()

    def test_curate_still_verifies(self):
        m.run_annotate(self.db)
        m.run_curate(self.db)
        _, failures = m.run_verify(self.db)
        self.assertEqual(failures, [])


class Curate64OnlySolution(unittest.TestCase):
    """6-4: 全解が 6-1 該当でも、問題を空にせず1件残す。

    5.1 までは問題 0050 (数字 0,0,5,0) で確かめていた。0050 は全 10 解が 6-2
    (`x * 1` / `x + 0` など) に掛かって全滅していたが、**5.2 で 6-2 を廃止した**ので
    6 解が生き残り、救済が起きなくなった (test_0050_no_longer_needs_rescue)。
    救済の経路は、今の 6-1 で実際に全滅する 0075 (数字 0,0,7,5) で確かめる。
    0075 の 6 解（6.7 から 8 解）はどれも 7 を潰すので全部 6-1 に掛かる。
    """

    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)
        m.generate_into(self.db, 75, 75)     # 問題 0075 (数字 0,0,7,5)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_only_solution_is_kept_and_marked(self):
        import sqlite3
        m.run_annotate(self.db)
        s = m.run_curate(self.db)
        # 6.7 で 6 → 8 解。底が 0 / 1 の累乗に指数の上限を掛けなくなり、
        # `( 0! + 0! ^ 7! ) * 5`（1^5040）と `( 0! + ( 0 ^ 7! )! ) * 5`（0^5040）が
        # 増えた。どちらも 7 を潰すので 6-1。救済される 1 解は変わらない
        self.assertEqual(s["total"], 8)
        self.assertEqual(s["n_6_1"], 7)        # 8 解のうち救済した 1 解以外
        self.assertEqual(s["n_6_4"], 1)
        self.assertEqual(s["kept"], 1)

        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT is_repr, is_redundant, redundant_why, display FROM solutions "
            "WHERE problem_id = '0075' AND is_repr = 1").fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 0)
        self.assertEqual(row[2], "6-4: kept (only solution)")
        # 残す 1 件は「スコア最小 → 読みやすさ → id」(_rescue_sort_key)。
        # 生成済みの make10.db で 0075 に残っている解と同じもの。
        # 5.8 までは 18 点の `( 0! + ( 0 * 7 )! ) * 5` だった ―― 5.9 で `0!` が
        # 加点の対象外になり、`( 0! + 0! ^ 7 ) * 5` が 20 → 17 点で最小になった
        # (`( 0 * 7 )!` のほうは引数が式なので 18 点のまま)
        self.assertEqual(row[3], "( 0! + 0! ^ 7 ) * 5")

        prob = conn.execute(
            "SELECT solution_count, repr_solution_id FROM problems "
            "WHERE problem_id = '0075'").fetchone()
        self.assertEqual(prob[0], 1)
        self.assertIsNotNone(prob[1])
        conn.close()

        # verify も通る
        _, failures = m.run_verify(self.db)
        self.assertEqual(failures, [])

    def test_idempotent(self):
        m.run_annotate(self.db)
        s1 = m.run_curate(self.db)
        s2 = m.run_curate(self.db)
        self.assertEqual(s1, s2)

    def test_0050_no_longer_needs_rescue(self):
        # 6-2 廃止 (5.2) の回帰。0050 の `( 0! + 0! ) * 5 + 0` などは `+ 0` で
        # 余った 0 を吸収しているだけで、数字は潰していない (DATA-SPEC 6-2)。
        # 10 解のうち 6-3 で 4 解が圧縮され、6 解が代表として残る。救済は起きない
        # setUp の DB には 0075 が入っていて統計が合算されるので、専用の DB を使う
        import sqlite3
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(db)
        self.addCleanup(lambda: [os.path.exists(db + x) and os.unlink(db + x)
                                 for x in ("", "-wal", "-shm")])
        m.generate_into(db, 50, 50)
        m.run_annotate(db)
        s = m.run_curate(db)
        self.assertEqual(s["total"], 10)
        self.assertEqual(s["n_6_4"], 0)
        self.assertEqual(s["n_6_1"], 0)
        conn = sqlite3.connect(db)
        kept = conn.execute(
            "SELECT COUNT(*) FROM solutions WHERE problem_id = '0050' "
            "AND is_repr = 1 AND is_redundant = 0").fetchone()[0]
        why = conn.execute(
            "SELECT COUNT(*) FROM solutions WHERE problem_id = '0050' "
            "AND redundant_why LIKE '6-4%'").fetchone()[0]
        conn.close()
        self.assertEqual(kept, 6)
        self.assertEqual(why, 0)


class Constrain(unittest.TestCase):
    """constrain (第6-B章) の不変条件。"""

    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)
        # 解の多い問題をいくつか。6988 は CLAUDE.md の例
        m.generate_into(self.db, 0, 30)
        m.generate_into(self.db, 6988, 6988)
        m.run_annotate(self.db)
        m.run_curate(self.db)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def _db_state(self):
        import sqlite3
        conn = sqlite3.connect(self.db)
        state = (
            conn.execute(
                "SELECT problem_id, rules, rule_count, survivor_count, "
                "repr_survivor_count, example_solution_id, min_score, "
                "base_min_score, harder_by FROM puzzles "
                "ORDER BY problem_id, rules").fetchall(),
            conn.execute(
                "SELECT id, is_repr, is_redundant, redundant_why FROM solutions "
                "ORDER BY id").fetchall(),
        )
        conn.close()
        return state

    def test_invariants_and_idempotent(self):
        import sqlite3
        s1 = m.run_constrain(self.db)
        d1 = self._db_state()
        s2 = m.run_constrain(self.db)
        d2 = self._db_state()
        # 冪等 = 2 回流しても DB の中身が変わらないこと
        self.assertEqual(d1, d2)
        # promoted_repr は「この実行で is_repr を 0 → 1 に昇格させた解答例の数」(6-6)。
        # 昇格は DB に残るので、constrain だけを 2 度流すと 2 回目は昇格済みで 0 になる
        # (make10.py の 6-6 のコメントどおり。curate が is_repr を付け直してから
        # constrain を流すのが正規の順)。それ以外の統計は完全に一致する
        self.assertGreater(s1["promoted_repr"], 0)  # 0 だとこの確認が空振りになる
        self.assertEqual(s2["promoted_repr"], 0)
        self.assertEqual({k: v for k, v in s1.items() if k != "promoted_repr"},
                         {k: v for k, v in s2.items() if k != "promoted_repr"})
        # 正規の順 (curate → constrain) で流し直せば、統計も DB も 1 回目と完全に一致する
        m.run_curate(self.db)
        s3 = m.run_constrain(self.db)
        self.assertEqual(s3, s1)
        self.assertEqual(self._db_state(), d1)

        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT problem_id, rules, rule_count, survivor_count, "
            "repr_survivor_count, example_solution_id, min_score, "
            "base_min_score, harder_by FROM puzzles").fetchall()

        # 5.5 規則 2 をここで独立に書く: 「6-1 の解」= redundant_why が 6-1 / 6-4 で
        # 始まる解。制約を満たす解 (where) の中で、6-1 の解の最小が 6-1 でない解の
        # 最小より真に大きいときだけ puzzle になる。(6-1 の最小, 6-1 でない最小, 全解の最小)
        NUL = ("(COALESCE(redundant_why, '') LIKE '6-1%' "
               "OR COALESCE(redundant_why, '') LIKE '6-4%')")
        col = {"+": "cnt_add", "-": "cnt_sub", "*": "cnt_mul", "/": "cnt_div",
               "^": "cnt_pow", "!": "cnt_fac"}

        def mins(pid, rules):
            where = "" if not rules else " AND %s = 0" % col[rules[0]]
            return conn.execute(
                "SELECT MIN(CASE WHEN %s THEN score END), "
                "MIN(CASE WHEN NOT %s THEN score END), MIN(score) "
                "FROM solutions WHERE problem_id = ?%s" % (NUL, NUL, where),
                (pid,)).fetchone()

        def rule2(nmin, omin):
            return omin is not None and (nmin is None or nmin > omin)

        # 無制約の puzzle は各問題に高々 1 件で、あるのは規則 2 を満たす問題だけ
        # (5.4 までは「全問題にちょうど 1 件」。5.5 で一番簡単な解が 6-1 の式の
        # 問題は無制約でも採らなくなった)
        probs = set(p for p, in conn.execute(
            "SELECT DISTINCT problem_id FROM solutions"))
        no_base = 0
        for p in probs:
            zero = conn.execute(
                "SELECT COUNT(*), MIN(rules) FROM puzzles "
                "WHERE problem_id = ? AND rule_count = 0", (p,)).fetchone()
            want = 1 if rule2(*mins(p, "")[:2]) else 0
            self.assertEqual(zero[0], want, p)
            if want:
                self.assertEqual(zero[1], "")
            else:
                no_base += 1
        # 規則 2 で無制約の puzzle が落ちる問題 (0009 など) が範囲内にあること。
        # 0 だとこの確認が空振りになる
        self.assertGreater(no_base, 0)

        base_of = dict(conn.execute(
            "SELECT problem_id, base_min_score FROM puzzles "
            "WHERE rule_count = 0"))
        prob_min = dict(conn.execute(
            "SELECT problem_id, min_score FROM problems"))
        all_min = dict(conn.execute(
            "SELECT problem_id, MIN(score) FROM solutions GROUP BY problem_id"))

        seen = set()
        for (pid, rules, rc, sc, rsc, ex, mn, base, hb) in rows:
            self.assertGreaterEqual(sc, 1)                    # 残存解は空でない
            self.assertLessEqual(rc, m.MAX_CONSTRAINTS)
            self.assertGreaterEqual(sc, rsc)
            self.assertGreaterEqual(rsc, 1)          # 冗長でない残存解が必ずある
            self.assertEqual((rc == 0), (rules == ""))
            # 残存解集合 (problem_id, rules) は一意 (重複排除できている)
            self.assertNotIn((pid, rules), seen)
            seen.add((pid, rules))
            # base_min_score は 6-1 を含む全解の最小 (規則 1)。無制約 puzzle が
            # あればそれとも、problems.min_score とも一致
            self.assertEqual(base, all_min[pid])
            if pid in base_of:
                self.assertEqual(base, base_of[pid])
            self.assertEqual(base, prob_min[pid])
            self.assertEqual(hb, mn - base)
            self.assertGreaterEqual(hb, 0)
            # 規則 2: 6-1 の解の最小が 6-1 でない解の最小より真に大きい。
            # 規則 1: 難易度は制約を満たす全解の最小で、それは 6-1 でない解の最小
            nmin, omin, smin = mins(pid, rules)
            self.assertTrue(rule2(nmin, omin), (pid, rules, nmin, omin))
            self.assertEqual(mn, smin)
            self.assertEqual(mn, omin)

            # 難易度と解答例は「同じ・冗長でない解」から来る
            ex_score, ex_red = conn.execute(
                "SELECT score, is_redundant FROM solutions WHERE id = ?",
                (ex,)).fetchone()
            self.assertEqual(ex_score, mn)
            self.assertEqual(ex_red, 0)

            if rc >= 1:
                # 制約付きは無制約より真に少ない残存解、かつ harder_by >= 1。
                # 無制約の残存解 = その問題の全解 (5.5 から無制約 puzzle が無い
                # 問題があるので、puzzles ではなく solutions から数える)
                base_sc = conn.execute(
                    "SELECT COUNT(*) FROM solutions WHERE problem_id = ?",
                    (pid,)).fetchone()[0]
                self.assertLess(sc, base_sc)
                self.assertGreaterEqual(hb, 1)
        conn.close()

    def test_6988_gets_constrained_puzzles(self):
        # CLAUDE.md の例題。制約付き puzzle ができ、無制約より解が減り難化する
        import sqlite3
        m.run_constrain(self.db)
        conn = sqlite3.connect(self.db)
        base = conn.execute(
            "SELECT survivor_count FROM puzzles WHERE problem_id='6988' "
            "AND rule_count=0").fetchone()[0]
        cons = conn.execute(
            "SELECT rules, rule_count, survivor_count, harder_by "
            "FROM puzzles WHERE problem_id='6988' AND rule_count>=1").fetchall()
        conn.close()
        self.assertGreater(len(cons), 0)
        for rules, rc, sc, hb in cons:
            self.assertLess(sc, base)
            self.assertGreaterEqual(hb, 1)
            self.assertTrue(rules.endswith("=0"))   # =0 (使用禁止) のみ

    def test_no_equals_one_rules(self):
        import sqlite3
        m.run_constrain(self.db)
        conn = sqlite3.connect(self.db)
        kinds = set(r for r, in conn.execute(
            "SELECT DISTINCT rules FROM puzzles WHERE rule_count >= 1"))
        conn.close()
        for k in kinds:
            self.assertTrue(k.endswith("=0"), k)


class Export(unittest.TestCase):
    """export (第8章)。"""

    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)
        self.out = self.db + ".json"
        m.generate_into(self.db, 0, 20)
        m.generate_into(self.db, 6988, 6988)
        m.run_annotate(self.db)
        m.run_curate(self.db)
        m.run_constrain(self.db)

    def tearDown(self):
        for path in (self.db, self.db + "-wal", self.db + "-shm", self.out):
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_json_shape_and_counts(self):
        import json
        import sqlite3
        s = m.run_export(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["version"], 1)
        self.assertEqual(data["rules"], {
            "pow_assoc": "right", "zero_pow_zero": 1, "double_factorial": False})

        conn = sqlite3.connect(self.db)
        n_puz = conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
        n_con = conn.execute(
            "SELECT COUNT(*) FROM puzzles WHERE rule_count >= 1").fetchone()[0]
        conn.close()

        self.assertEqual(len(data["puzzles"]), n_puz)
        self.assertEqual(s["puzzles"], n_puz)
        self.assertEqual(s["with_constraint"], n_con)
        self.assertEqual(s["without_constraint"], n_puz - n_con)

        self.assertEqual(s["needs_fac"],
                         sum(1 for p in data["puzzles"] if p["needs_fac"]))
        self.assertEqual(s["needs_pow"],
                         sum(1 for p in data["puzzles"] if p["needs_pow"]))

        for p in data["puzzles"]:
            self.assertEqual(set(p), {
                "id", "constraint", "difficulty", "solution", "solution_count",
                "needs_fac", "needs_pow"})
            self.assertRegex(p["id"], r"^\d{4}$")
            self.assertIsInstance(p["solution_count"], int)
            self.assertIsInstance(p["needs_fac"], bool)
            self.assertIsInstance(p["needs_pow"], bool)
            if p["constraint"] is not None:
                self.assertEqual(set(p["constraint"]), {"op", "count"})
                self.assertIn(p["constraint"]["op"], list("+-*/^!"))
                self.assertEqual(p["constraint"]["count"], 0)   # =0 のみ

        # 各問題に constraint=null がちょうど 1 件
        base = [p for p in data["puzzles"] if p["constraint"] is None]
        self.assertEqual(len(base), len(set(p["id"] for p in base)))

    def test_difficulty_matches_example_solution(self):
        import json
        import sqlite3
        m.run_export(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        conn = sqlite3.connect(self.db)
        for p in data["puzzles"]:
            row = conn.execute(
                "SELECT score, is_redundant FROM solutions "
                "WHERE problem_id = ? AND display = ?",
                (p["id"], p["solution"])).fetchone()
            self.assertIsNotNone(row)
            score, is_red = row
            self.assertEqual(p["difficulty"], score)   # 難易度と解答例は同じ解
            self.assertEqual(is_red, 0)                 # 冗長でない解
        conn.close()

    def test_needs_flags_match_solutions(self):
        import json
        import sqlite3
        m.run_export(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        conn = sqlite3.connect(self.db)
        for p in data["puzzles"]:
            mnf, mnp = conn.execute(
                "SELECT MIN(cnt_fac), MIN(cnt_pow) FROM solutions "
                "WHERE problem_id = ?", (p["id"],)).fetchone()
            self.assertEqual(p["needs_fac"], mnf > 0)
            self.assertEqual(p["needs_pow"], mnp > 0)
        conn.close()

    def test_idempotent(self):
        m.run_export(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            first = f.read()
        m.run_export(self.db, self.out)
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(f.read(), first)


class BlobSols(unittest.TestCase):
    """全解答の区分 §SHAPE / §SOLS (6.9。DATA-SPEC 8-B)。DISPLAYS の式は make10.db に実在する。"""

    DISPLAYS = [
        "8 + 8 - ( 4 + 2 )",
        "8 + ( 8 - 4 ) / 2",
        "( ( 8! - 8! )! + 4 ) * 2",
        "5 / ( ( 3! )! / ( ( 3! )! + ( 3! )! ) )",
        "( 8 - 9 ) ^ 5! + 9",
        "( 0! + 0! + 0! )! + 4",
    ]

    def test_shape_compact(self):
        self.assertEqual(m._shape_compact("n0 ! n1 ! + n2 ! + ! n3 +"), "0!1!+2!+!3+")
        self.assertEqual(m._shape_compact("n0 n1 + n2 - n3 -"), "01+2-3-")

    def test_b36(self):
        self.assertEqual([m._b36(n) for n in (0, 9, 10, 35, 36, 12558)],
                         ["0", "9", "a", "z", "10", "9ou"])
        self.assertEqual(int("9ou", 36), 12558)

    def test_display_is_rebuilt_from_shape(self):
        # 表示 -> 木 -> 形 -> 詰めた形 -> (独立実装で) 表示 が元の文字列に戻る
        for disp in self.DISPLAYS:
            pid = "".join(ch for ch in disp if ch.isdigit())
            cs = m._shape_compact(m.render_shape(m.parse_tree(disp)))
            self.assertEqual(m._plain_shape_display(cs, pid), disp)
            self.assertEqual(m.parse_eval(disp), Fraction(10))

    def test_list_keeps_first_of_each_group_and_filters_constraint(self):
        # ここは形だけを見る単体テスト (値が 10 になる式とは限らない)。
        # a と b は同じグループ (加減 3 回・同じ結合) なので先頭だけ残る
        a, b, c = "01+2-3-", "01+2+3+", "01-!2+3*"
        self.assertEqual(m._plain_sols_list([a, b, c], None), [a, c])
        self.assertEqual(m._plain_sols_list([b, a, c], None), [b, c])
        # `-` 禁止なら a と c が消え、b がグループの先頭になる
        self.assertEqual(m._plain_sols_list([a, b, c], "-"), [b])
        # 結合の仕方が違えば別のグループ (8 + 8 - ( 4 + 2 ))
        self.assertEqual(m._plain_sols_list([a, "01+23+-"], None), [a, "01+23+-"])

    def test_sols_of_generated_db(self):
        import sqlite3
        fd, db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(db)
        try:
            m.generate_into(db, 8842, 8842)
            m.generate_into(db, 6988, 6988)
            m.run_annotate(db)
            m.run_curate(db)
            m.run_constrain(db)
            conn = sqlite3.connect(db)
            sols = m._blob_sols(conn)
            rows = dict(sols["rows"])
            puz = conn.execute(
                "SELECT p.problem_id, p.rules, s.display FROM puzzles p "
                "JOIN solutions s ON s.id = p.example_solution_id").fetchall()
            conn.close()
            self.assertTrue(puz)
            self.assertEqual(sorted(rows), sorted({p[0] for p in puz}))
            self.assertEqual(len(set(sols["shapes"])), len(sols["shapes"]))
            for pid, rules, example in puz:
                ban = rules[0] if rules else None
                got = [m._plain_shape_display(cs, pid) for cs in m._plain_sols_list(
                    [sols["shapes"][n] for n in rows[pid]], ban)]
                self.assertEqual(got[0], example)            # 1 本目は解答例
                for disp in got:
                    self.assertEqual(m.parse_eval(disp), Fraction(10))
                    if ban:
                        self.assertNotIn(ban, disp)
                if pid == "8842" and not rules:
                    self.assertEqual(len(got), 12)           # make10.db と同じ本数
                    self.assertEqual(got[1], "8 + 8 - ( 4 + 2 )")
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(db + suffix)
                except OSError:
                    pass


class DailyColumn(unittest.TestCase):
    """デイリーの問題の列 (DAILY-SPEC 3〜6 章。D0.1)。

    候補は手で組んだ小さい集合を使う (4 桁と解答例は見た目だけで、DB には当てない。
    DB と突き合わせる確かめは `make10.py daily` の中にある)。"""

    @staticmethod
    def row(pid, d, rc="N"):
        return {"id": "%04d" % pid, "rc": rc, "d": d, "free": rc == "N",
                "sol": "1 + 2 + 3 + 4"}

    def pool(self, weeks, extra_e=0):
        """どの枠もちょうど weeks 週ぶんの 4 桁を持つ候補。4 桁は枠ごとに別の番号帯。"""
        out = []
        for i in range(2 * weeks):
            out.append(self.row(1000 + i, 6 + i % 3))            # A 月・火
            out.append(self.row(2000 + i, 9 + i % 3))            # B 水・木
        for i in range(weeks):
            out.append(self.row(3000 + i, 12 + i % 2, "N" if i % 2 else "A0"))   # C 金
            out.append(self.row(4000 + i, 14 + i % 3, "N" if i % 2 else "M0"))   # D 土
        for i in range(weeks + extra_e):
            out.append(self.row(5000 + i, 9 + i % 3, "S0"))       # E 日
        return out

    def test_start_must_be_monday(self):
        self.assertEqual(m.daily_start().weekday(), 0)           # 置いてある値が月曜
        self.assertEqual(m.daily_start("2099-01-05").isoformat(), "2099-01-05")
        for bad in ("2099-01-04", "2099-01-06", "2099-01-11"):   # 日・火・日
            with self.assertRaises(ValueError):
                m.daily_start(bad)

    def test_classes_are_the_spec_table(self):
        # DAILY-SPEC 4 章の表そのもの。曜日は 0 = 月 … 6 = 日で、7 日を 1 回ずつ覆う
        self.assertEqual(m.DAILY_CLASSES, (
            ("A", (0, 1), 6, 8, "free"), ("B", (2, 3), 9, 11, "free"),
            ("C", (4,), 12, 13, "any"), ("D", (5,), 14, 16, "any"),
            ("E", (6,), 9, 11, "con")))
        self.assertEqual(sorted(wd for c in m.DAILY_CLASSES for wd in c[1]),
                         list(range(7)))

    def test_candidates_drop_chal_and_course_head(self):
        course = [self.row(i, 8) for i in range(201)]            # 201 問目 = 0200
        free = [self.row(5, 12, "A0"),      # 本編 6 問目と同じ 4 桁 (制約が違う) -> 除く
                self.row(200, 12, "A0"),    # 本編 201 問目と同じ 4 桁 -> 残す
                self.row(7000, 10)]
        chal = [self.row(8000, 17), self.row(7000, 20, "M0")]    # 挑戦の puzzle -> 除く
        got = m.daily_candidates({"COURSE": course, "FREE": free, "CHAL": chal})
        self.assertEqual(sorted((r["id"], r["rc"]) for r in got),
                         [("0200", "A0"), ("0200", "N"), ("7000", "N")])

    def test_rows_fit_weekday_table_and_never_repeat(self):
        col = m.select_daily(self.pool(6), 6)
        self.assertEqual([x["no"] for x in col], list(range(1, 43)))
        self.assertEqual(len({x["id"] for x in col}), 42)        # 同じ 4 桁は一度
        table = {wd: c for c in m.DAILY_CLASSES for wd in c[1]}
        for x in col:
            wd = (x["no"] - 1) % 7                               # #1 は月曜
            _name, _days, lo, hi, con = table[wd]
            self.assertEqual(x["wd"], wd)
            self.assertTrue(lo <= x["d"] <= hi, x)
            if con != "any":
                self.assertEqual(x["rc"] == "N", con == "free", x)

    def test_scarce_class_gets_its_ids(self):
        """水・木 (B) の 4 桁が、ぜんぶ日曜 (E) にも使えるとき。日曜が先に取ると
        水・木が足りなくなるが、持ち分の分け方は B に全部を回す。"""
        weeks = 5
        pool = self.pool(weeks)
        for i in range(2 * weeks):                # B の 4 桁に、日曜に使える puzzle も持たせる
            pool.append(self.row(2000 + i, 10, "D0"))
        t, owned, rest = m.daily_partition(pool)
        self.assertEqual(t, weeks)
        self.assertEqual(sorted(owned["B"]), ["%04d" % (2000 + i) for i in range(10)])
        self.assertEqual(rest, 0)
        col = m.select_daily(pool, weeks)
        self.assertEqual(len(col), 35)
        for x in col:                             # 水・木に出るのは制約なしのほう
            if x["wd"] in (2, 3):
                self.assertEqual((x["id"][0], x["rc"]), ("2", "N"))

    def test_monday_tuesday_skip_zero_factorial_examples(self):
        """月・火は、解答例に `0!` を含む問題を使わない (`3!` などほかの階乗は使う)。
        水〜日は `0!` を含んでいても使う。DAILY-SPEC 4 章"""
        self.assertEqual(m.DAILY_NO_ZERO_FAC, ("A",))
        a, b = m.DAILY_CLASSES[0], m.DAILY_CLASSES[1]
        for sol, ok in (("0! - 9 + 6 * 3", False), ("7 - 0! - 5 + 9", False),
                        ("( 0! + 0! ) * 5 + 0", False), ("3! + 9 - 1 * 5", True),
                        ("( 3 - 3 )! + 9 + 0", True), ("1 + 2 + 3 + 4", True)):
            r = dict(self.row(1234, 7), sol=sol)
            self.assertEqual(m._daily_class_ok(a, r), ok, sol)
            self.assertTrue(m._daily_class_ok(b, dict(r, d=10)), sol)   # 水・木は使う
        # 列にしたとき: 月・火に使える 4 桁の半分が 0! を含むと、出せる週数は半分になり、
        # 月・火には 0! を含まないほうだけが出る
        weeks = 4
        pool = self.pool(weeks)
        for r in pool:
            if r["id"][0] == "1" and int(r["id"]) % 2:
                r["sol"] = "0! + 2 + 3 + 4"
            if r["id"][0] == "2":
                r["sol"] = "0! + 0! + 3 + 5"
        self.assertEqual(m.daily_partition(pool)[0], weeks // 2)
        col = m.select_daily(pool, weeks // 2)
        for x in col:
            self.assertEqual("0!" in x["sol"], x["wd"] in (2, 3), x)

    def test_ids_are_moved_to_make_room(self):
        """日曜 (E) に使える 4 桁が、どれも金曜 (C) にも使える (同じ 4 桁が、日曜向きの
        問題と金曜向きの問題を両方持つ)。先に金曜へ入った 4 桁を日曜へ動かさないと、
        日曜が足りなくなる。"""
        weeks = 6
        pool = [r for r in self.pool(weeks) if r["id"][0] not in "35"]
        for i in range(weeks):
            pool.append(self.row(3000 + i, 12))            # 金曜にしか使えない (制約なし)
            pool.append(self.row(5000 + i, 10, "S0"))      # 日曜に使える問題と、
            pool.append(self.row(5000 + i, 13, "A0"))      # 金曜に使える問題を持つ 4 桁
        t, owned, rest = m.daily_partition(pool)
        self.assertEqual((t, rest), (weeks, 0))
        self.assertEqual(sorted(owned["C"]), ["%04d" % (3000 + i) for i in range(weeks)])
        self.assertEqual(sorted(owned["E"]), ["%04d" % (5000 + i) for i in range(weeks)])
        self.assertEqual(len(m.select_daily(pool, weeks)), weeks * 7)

    def test_same_input_same_column_and_input_order_is_ignored(self):
        pool = self.pool(8, extra_e=5)
        a = m.select_daily(pool, 8)
        self.assertEqual(a, m.select_daily(pool, 8))
        self.assertEqual(a, m.select_daily(list(reversed(pool)), 8))

    def test_extending_keeps_existing_rows(self):
        pool = self.pool(8, extra_e=5)
        long = m.select_daily(pool, 8)
        for weeks in (1, 3, 7):
            self.assertEqual(m.select_daily(pool, weeks), long[:weeks * 7])

    def test_refuses_more_weeks_than_every_weekday_can_fill(self):
        pool = self.pool(4)
        self.assertEqual(m.daily_partition(pool)[0], 4)
        m.select_daily(pool, 4)
        with self.assertRaises(RuntimeError):
            m.select_daily(pool, 5)
        # 金曜の 4 桁を 1 つ減らすと、ほかの曜日が余っていても 3 週までになる
        short = [r for r in pool if r["id"] != "3000"]
        self.assertEqual(m.daily_partition(short)[0], 3)

    def test_line_format(self):
        x = {"no": 12, "id": "5671", "rc": "N", "d": 12,
             "sols": ["5! / ( 6 + 7 - 1 )", "( 5 + 6 - 1 ) * 7 / 7"]}
        self.assertEqual(m._daily_line(x),
                         "12,5671,N,12,5! / ( 6 + 7 - 1 );( 5 + 6 - 1 ) * 7 / 7")

    # ── ページへの埋め込み (D0.2) ──
    PAGE = ('<script>\nconst DAILY_VERSION="0.2";\nconst DAILY_START="2099-01-05";\n'
            'const DAILY=`%s`;\nconst REST=1;\n</script>\n')

    def test_page_read_and_write(self):
        html = self.PAGE % ""
        self.assertEqual(m.daily_page_read(html), ("2099-01-05", []))
        text = "1,3915,N,8,3! + 9 - 1 * 5;3! + 9 * 1 - 5\n2,9730,N,7,9 + 7 - 3! + 0"
        new = m.daily_page_write(html, "2099-01-12", text)
        self.assertEqual(m.daily_page_read(new), ("2099-01-12", text.split("\n")))
        # 印の間のほかは 1 文字も変わらない
        self.assertEqual(new, (self.PAGE % text).replace("2099-01-05", "2099-01-12"))
        # 同じ中身をもう一度書いても変わらない。ファイルが CRLF なら CRLF で書く
        self.assertEqual(m.daily_page_write(new, "2099-01-12", text), new)
        crlf = m.daily_page_write(html.replace("\n", "\r\n"), "2099-01-05", text)
        self.assertNotIn("\n", crlf.replace("\r\n", ""))
        self.assertEqual(m.daily_page_read(crlf)[1], text.split("\n"))
        # 印が無い・2 か所あるページには書かない
        for bad in (html.replace("const DAILY=`", "const DAILIES=`"),
                    html + 'const DAILY_START="2099-01-05";'):
            with self.assertRaises(ValueError):
                m.daily_page_write(bad, "2099-01-05", text)

    def build(self, pool, weeks, keep=None):
        """DB を使わずに _daily_build を回す (全解答は解答例 1 本にする)"""
        orig = m._daily_sols
        m._daily_sols = lambda conn, col: {(x["id"], x["rc"]): [x["sol"]] for x in col}
        try:
            return m._daily_build(None, weeks, pool=pool, keep=keep)
        finally:
            m._daily_sols = orig

    def test_rows_already_on_the_page_are_never_changed(self):
        pool = self.pool(8, extra_e=5)
        page = self.build(pool, 3)["text"].split("\n")            # ページに 3 週ぶんある
        # DB が同じなら、作り直した列の頭はページと同じ。続きが足されるだけ
        b = self.build(pool, 5, keep=page)
        self.assertEqual((b["frozen"], b["diff"]), (0, []))
        self.assertEqual(b["text"], self.build(pool, 5)["text"])
        self.assertEqual(b["text"].split("\n")[:21], page)
        # DB を作り直して、ページの 2 行目の問題が候補から消えた場合
        gone = page[1].split(",")[1]
        changed = [r for r in pool if r["id"] != gone]
        self.assertNotEqual(self.build(changed, 5)["text"].split("\n")[:21], page)
        b = self.build(changed, 5, keep=page)
        lines = b["text"].split("\n")
        self.assertEqual(lines[:21], page)                        # ページの行は 1 文字も変えない
        self.assertEqual(b["frozen"], 21)
        self.assertIn(2, b["diff"])                               # 食い違いを報告する
        self.assertEqual([int(ln.split(",")[0]) for ln in lines], list(range(1, 36)))
        ids = [ln.split(",")[1] for ln in lines]
        self.assertEqual(len(set(ids)), 35)                       # 続きは、ページに出た 4 桁を使わない
        table = {wd: c for c in m.DAILY_CLASSES for wd in c[1]}
        for x in b["rows"][21:]:                                  # 続きも曜日の表に合う
            _n, _d, lo, hi, _c = table[(x["no"] - 1) % 7]
            self.assertTrue(lo <= x["d"] <= hi, x)
        # もう一度伸ばしても、前に足した行は変わらない
        again = self.build(changed, 6, keep=lines)
        self.assertEqual(again["text"].split("\n")[:35], lines)
        # ページの長さちょうどなら、何も足さない
        self.assertEqual(self.build(changed, 3, keep=page)["text"].split("\n"), page)

    def test_page_rows_must_be_whole_weeks_and_not_longer_than_asked(self):
        pool = self.pool(8, extra_e=5)
        page = self.build(pool, 3)["text"].split("\n")
        with self.assertRaises(ValueError):
            self.build(pool, 5, keep=page[:20])                   # 週の単位でない
        with self.assertRaises(ValueError):
            self.build(pool, 2, keep=page)                        # ページより短くは作れない

    def test_rebuild_is_refused_once_published(self):
        """--rebuild (ページの行を捨てて作り直す) は、起点日が今日以前なら断る。"""
        import datetime
        here = os.path.dirname(os.path.abspath(__file__))
        fd, page = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            rows = "\n".join("%d,%04d,N,7,1 + 2 + 3 + 4" % (i + 1, 1000 + i) for i in range(7))
            with open(page, "w", encoding="utf-8", newline="") as f:
                f.write(self.PAGE % rows)
            with self.assertRaises(ValueError):
                m.run_daily("nothing.db", os.path.join(here, "docs", "index.html"), page,
                            write=True, rebuild=True, today=m.daily_start())
            with open(page, encoding="utf-8", newline="") as f:
                self.assertEqual(f.read(), self.PAGE % rows)     # ページは変わっていない
        finally:
            os.unlink(page)


if __name__ == "__main__":
    unittest.main()
