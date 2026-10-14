#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_adviser.py —— 核心不变量的回归测试（标准库 unittest，无第三方依赖）

运行：  python -m unittest discover -s tests -v
覆盖：  角色分类 / 预算硬约束 / 结构约束 / 忌口过滤 / 优惠券生效 / CLI JSON 契约
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import adviser  # noqa: E402
from build_index import classify  # noqa: E402

PY = sys.executable


def run_cli(*args: str) -> str:
    """跑一次命令行入口，返回 stdout。"""
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / "adviser.py"), *args],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout


class TestClassification(unittest.TestCase):
    """角色分类决定了组合是否会拼出「三个饮品」这种荒唐套餐，必须有测试钉住。"""

    def test_drink_not_staple(self) -> None:
        """名字里同时含「饮品」和「随心选」时，必须先判为饮品。"""
        self.assertEqual(classify("学生专享饮品随心选"), "drink")
        self.assertEqual(classify("燕麦奶铁"), "drink")
        self.assertEqual(classify("雪碧"), "drink")

    def test_staple(self) -> None:
        """汉堡、套餐与随心配都归为主食。"""
        self.assertEqual(classify("麦香鸡"), "staple")
        self.assertEqual(classify("巨无霸三件套"), "staple")
        self.assertEqual(classify("人气经典随心配"), "staple")

    def test_side_and_dessert(self) -> None:
        """小食与甜品要分开，否则「主食 + 小食」的结构约束会失效。"""
        self.assertEqual(classify("心形薯饼5块"), "side")
        self.assertEqual(classify("蘸酱脆皮鸡柳"), "side")
        self.assertEqual(classify("姜汁撞奶风味派"), "dessert")

    def test_nonfood(self) -> None:
        """周边与调味酱不得进推荐池。"""
        self.assertEqual(classify("北美招牌牧场酱"), "nonfood")
        self.assertEqual(classify("麦当劳联名复古棒球帽"), "nonfood")


class TestEngine(unittest.TestCase):
    """求解器的硬约束与输出契约。"""

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def _plans(self, **kw) -> list:
        """按给定约束跑一次求解。"""
        args = dict(budget=40, people=1, mode="balanced", top=3,
                    max_kcal=None, min_protein=None)
        args.update(kw)
        banned = args.pop("banned", set())
        pool = adviser.build_pool(self.idx, banned)
        return adviser.solve(self.idx, pool, **args)

    def test_nutrition_coverage(self) -> None:
        """营养覆盖率跌破 85%，推荐结果的营养口径就会明显失真。"""
        self.assertGreater(self.idx["nutritionCoverage"], 0.85,
                           "营养覆盖率跌破 85%，推荐结果的营养口径会失真")

    def test_budget_is_hard_constraint(self) -> None:
        """四种模式下，券后总价都不得超过预算。"""
        for mode in ("value", "balanced", "protein", "light"):
            for plan in self._plans(mode=mode, budget=45):
                self.assertLessEqual(round(plan.total, 2), 45.0,
                                     f"{mode} 突破预算")

    def test_balanced_requires_full_meal(self) -> None:
        """均衡模式必须构成「主食 + 小食 + 饮品」。"""
        for plan in self._plans(mode="balanced"):
            roles = {line.role for line in plan.lines}
            self.assertLessEqual({"staple", "side", "drink"}, roles,
                                 "均衡模式必须包含主食 + 小食 + 饮品")

    def test_exclusion_is_respected(self) -> None:
        """忌口是硬约束：候选池里直接剔除，方案里也不得出现。"""
        pool = adviser.build_pool(self.idx, {"beef"})
        self.assertFalse([x for x in pool if "beef" in x["tags"]])
        for plan in self._plans(banned={"beef"}, mode="value", budget=60):
            for line in plan.lines:
                self.assertNotIn("beef", adviser.tags_of(line.name))

    def test_kcal_ceiling(self) -> None:
        """热量上限生效（允许 0.5 的浮点容差）。"""
        for plan in self._plans(mode="light", budget=60, max_kcal=600):
            self.assertLessEqual(plan.nutrition["kcal"] / plan.people, 600.5)

    def test_order_payload_shape(self) -> None:
        """下单参数必须能直接喂给 create-order。"""
        plan = self._plans(mode="value", budget=60)[0]
        for item in plan.to_dict()["order_items"]:
            self.assertEqual(set(item), {"productCode", "quantity"})
            self.assertTrue(item["productCode"])
            self.assertGreaterEqual(item["quantity"], 1)

    def test_bogo_coupon_applied(self) -> None:
        """买一送一券：同一商品 2 份时应只付 1 份。"""
        target = next((c for c, it in self.idx["items"].items()
                       if "麦旋风" in it["name"] and c in self.idx["nutrition"]), None)
        self.assertIsNotNone(target, "菜单里找不到麦旋风，券测试失效")
        lines, total, hits, _ = adviser.apply_coupons([(target, 2)], self.idx)
        unit = float(self.idx["items"][target]["price"])
        self.assertLess(total, unit * 2 - 1e-6, "买一送一未生效")
        self.assertTrue(hits, "应命中券名")
        self.assertIsNotNone(lines[0].applied_coupon)

    def test_no_plan_when_impossible(self) -> None:
        """预算过低时应返回空集，而不是硬凑一个方案。"""
        self.assertEqual(self._plans(budget=3, mode="balanced"), [],
                         "预算过低时应返回空集而不是硬凑")


class TestCli(unittest.TestCase):
    """命令行输出是给下游脚本消费的契约，不能随意改形状。"""

    def test_json_contract(self) -> None:
        """--json 的结构必须稳定。"""
        out = run_cli("--budget", "40", "--people", "1", "--mode", "value",
                      "--json")
        data = json.loads(out)
        self.assertIn("store", data)
        self.assertIn("plans", data)
        self.assertEqual(data["query"]["budget"], 40)
        for plan in data["plans"]:
            self.assertIn("order_items", plan)
            self.assertIn("nutrition", plan)
            self.assertIn("total", plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
