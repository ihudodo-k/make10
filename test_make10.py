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

    def test_nullified_x_pow_0(self):
        # ( 1 + 2 ) ^ 0 + 9  ->  x ^ 0 (x に演算子あり)
        tree = m.parse_shape("n0 n1 + n2 ^ n3 +")
        self.assertEqual(
            m.classify_nullified(tree, self._val(tree, [1, 2, 0, 9])),
            "6-1: x ^ 0")

    def test_nullified_needs_operator_in_x(self):
        # 5 ^ 0 は x に演算子が無いので 6-1 の対象外
        tree = m.parse_shape("n0 n1 ^ n2 + n3 +")   # (5^0) + 9 + 0
        self.assertIsNone(
            m.classify_nullified(tree, self._val(tree, [5, 0, 9, 0])))

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
    """6-4: 全解が 6-1/6-2 該当でも、問題を空にせず1件残す。"""

    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db)
        m.generate_into(self.db, 50, 50)     # 問題 0050 (数字 0,0,5,0)

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
        self.assertEqual(s["n_6_4"], 1)
        self.assertEqual(s["kept"], 1)

        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT is_repr, is_redundant, redundant_why FROM solutions "
            "WHERE problem_id = '0050' AND is_repr = 1").fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 0)
        self.assertEqual(row[2], "6-4: kept (only solution)")

        prob = conn.execute(
            "SELECT solution_count, repr_solution_id FROM problems "
            "WHERE problem_id = '0050'").fetchone()
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

    def test_invariants_and_idempotent(self):
        import sqlite3
        s1 = m.run_constrain(self.db)
        s2 = m.run_constrain(self.db)
        self.assertEqual(s1, s2)                    # 冪等

        conn = sqlite3.connect(self.db)
        rows = conn.execute(
            "SELECT problem_id, rules, rule_count, survivor_count, "
            "repr_survivor_count, example_solution_id, min_score, "
            "base_min_score, harder_by FROM puzzles").fetchall()

        # 各問題に rule_count=0 の無制約 puzzle がちょうど 1 件
        probs = set(p for p, in conn.execute(
            "SELECT DISTINCT problem_id FROM solutions"))
        for p in probs:
            zero = conn.execute(
                "SELECT COUNT(*), MIN(rules) FROM puzzles "
                "WHERE problem_id = ? AND rule_count = 0", (p,)).fetchone()
            self.assertEqual(zero[0], 1)
            self.assertEqual(zero[1], "")

        base_of = dict(conn.execute(
            "SELECT problem_id, base_min_score FROM puzzles "
            "WHERE rule_count = 0"))
        prob_min = dict(conn.execute(
            "SELECT problem_id, min_score FROM problems"))

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
            # base_min_score は無制約 puzzle とも problems.min_score とも一致
            self.assertEqual(base, base_of[pid])
            self.assertEqual(base, prob_min[pid])
            self.assertEqual(hb, mn - base)
            self.assertGreaterEqual(hb, 0)

            # 難易度と解答例は「同じ・冗長でない解」から来る
            ex_score, ex_red = conn.execute(
                "SELECT score, is_redundant FROM solutions WHERE id = ?",
                (ex,)).fetchone()
            self.assertEqual(ex_score, mn)
            self.assertEqual(ex_red, 0)

            if rc >= 1:
                # 制約付きは無制約より真に少ない残存解、かつ harder_by >= 1
                base_sc = conn.execute(
                    "SELECT survivor_count FROM puzzles WHERE problem_id = ? "
                    "AND rule_count = 0", (pid,)).fetchone()[0]
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
