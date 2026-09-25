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
        # '+'1×2 + '/'3 + '!'4×2 = 13、括弧 1 で 14、比 +2、全体が比 -1 = 15
        self.assertEqual(
            m.score_solution(tree, val, display.count("("), ev(tree)[3]),
            13 + m.SCORE_BONUS["paren"] + m.SCORE_BONUS["fac_ratio"]
            + m.SCORE_BONUS["whole_ratio"])
        # 0087 は途中に比があるだけなので戻さない
        tree2, val2, _ = self._tree("0! + 0! + 8! / 7!", [0, 0, 8, 7])
        self.assertFalse(m.is_whole_ratio(tree2, val2))

    def test_score_matches_spec_formula(self):
        # 0087  0! + 0! + 8! / 7! : '+'1×2 + '/'3 + '!'4×4 = 21、0! で +3、比 +2
        display, digits = "0! + 0! + 8! / 7!", [0, 0, 8, 7]
        tree, val, ev = self._tree(display, digits)
        self.assertEqual(
            m.score_solution(tree, val, display.count("("), ev(tree)[3]),
            21 + m.SCORE_BONUS["zero_factorial"] + m.SCORE_BONUS["fac_ratio"])

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
        #   括弧 1 組 = +1、分数なし、0! あり = +3、入れ子階乗なし
        #   -> 23
        import sqlite3
        m.run_annotate(self.db)
        conn = sqlite3.connect(self.db)
        sc = conn.execute(
            "SELECT score FROM solutions WHERE problem_id = '0004' "
            "AND display = ?", ("( 0! + 0! + 0! )! + 4",)).fetchone()[0]
        conn.close()
        self.assertEqual(sc, 23)

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
    0075 の 6 解はどれも `0 * 7` で 7 を潰すので全部 6-1 に掛かる。
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
        self.assertEqual(s["total"], 6)
        self.assertEqual(s["n_6_1"], 5)        # 6 解のうち救済した 1 解以外
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
        # 生成済みの make10.db で 0075 に残っている解と同じもの
        self.assertEqual(row[3], "( 0! + ( 0 * 7 )! ) * 5")

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


if __name__ == "__main__":
    unittest.main()
