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
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import adviser  # noqa: E402
import build_index  # noqa: E402
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
        """均衡模式必须构成「主食 + 小食 + 饮品」。

        判据是方案**能提供的槽位**，不是每条 line 的 role —— 套餐（三件套/四件套）
        自带薯条与饮品，它一个人就构成完整一餐。
        """
        for plan in self._plans(mode="balanced"):
            codes = [(line.code, line.qty) for line in plan.lines]
            provided = adviser.provided_roles(self.idx, codes)
            self.assertLessEqual({"staple", "side", "drink"}, provided,
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


class TestPriceTier(unittest.TestCase):
    """价格口径：会员价不能当成人人可买的价格。

    这条不是理论洁癖。本门店 8 组「三件套 > 四件套」的倒挂，四件套那一侧
    **全部**是麦金卡会员价 —— 早先把它们当普通价，README 的招牌数字就变成了
    拿会员价与非会员价比。
    """

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def test_member_items_exist_and_are_tagged(self) -> None:
        """会员价商品必须被识别出来，且带 membershipCode 佐证。"""
        members = adviser.member_items(self.idx)
        self.assertGreater(len(members), 0, "应能识别出会员价商品")
        for it in members:
            self.assertEqual(it["priceTier"], "member")
            self.assertEqual(it["discountType"], "随单购麦金卡优惠")
            self.assertTrue(it["withOrder"], "会员价商品应带 withOrder 信息")

    def test_member_excluded_by_default(self) -> None:
        """默认候选池里不得出现会员价商品。"""
        pool = adviser.build_pool(self.idx, set())
        tiers = {x.get("priceTier") for x in pool}
        self.assertNotIn("member", tiers)

    def test_member_included_when_asked(self) -> None:
        """--member 时会员价商品应进入候选池。"""
        pool = adviser.build_pool(self.idx, set(), allow_member=True)
        self.assertIn("member", {x.get("priceTier") for x in pool})

    def test_plans_never_use_member_price_by_default(self) -> None:
        """默认求解结果里不得混进会员价商品。"""
        for mode in ("value", "balanced", "protein", "light"):
            pool = adviser.build_pool(self.idx, set())
            for plan in self._solve(pool, mode=mode, budget=60):
                for line in plan.lines:
                    tier = self.idx["items"][line.code].get("priceTier")
                    self.assertNotEqual(tier, "member", f"{mode} 混入会员价：{line.name}")

    def _solve(self, pool: list, **kw) -> list:
        """按给定约束跑一次求解。"""
        args = dict(budget=45, people=1, mode="balanced", top=2,
                    max_kcal=None, min_protein=None)
        args.update(kw)
        return adviser.solve(self.idx, pool, **args)


class TestBundleRoles(unittest.TestCase):
    """套餐的角色槽位：结构化套餐才扩展，建模假设不算。"""

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def _by_name(self, name: str) -> dict:
        """按商品名取条目（菜单内名称唯一）。"""
        for it in self.idx["items"].values():
            if it["name"] == name:
                return it
        raise AssertionError(f"菜单里没有「{name}」")

    def test_three_piece_set_covers_meal(self) -> None:
        """三件套应同时占主食 + 小食 + 饮品三个槽位。"""
        roles = set(self._by_name("巨无霸三件套")["roles"])
        self.assertLessEqual({"staple", "side", "drink"}, roles)

    def test_self_select_keeps_single_role(self) -> None:
        """「随心配」内容自选，配件是建模假设 —— 不得据此占额外槽位。"""
        self.assertEqual(self._by_name("人气经典随心配")["roles"], ["staple"])

    def test_three_piece_alone_is_a_full_meal(self) -> None:
        """一件三件套自己就应满足均衡模式的结构要求。"""
        it = self._by_name("巨无霸三件套")
        provided = adviser.provided_roles(self.idx, [(it["code"], 1)])
        self.assertLessEqual({"staple", "side", "drink"}, provided)


class TestIdentity(unittest.TestCase):
    """identity 与 components 的区别：营养代餐不是身份。

    拿代餐当身份会让「牛肉堡单品精选」（盲盒，¥15）冒充巨无霸，
    比价与券对齐全错。
    """

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def _nutri(self, name: str) -> dict:
        """按商品名取营养条目。"""
        for it in self.idx["items"].values():
            if it["name"] == name:
                return self.idx["nutrition"].get(it["code"], {})
        raise AssertionError(f"菜单里没有「{name}」")

    def test_blind_box_has_no_identity(self) -> None:
        """盲盒商品内容随机 → identity 必须为空，不能凭代餐认领巨无霸。"""
        for name in ("牛肉堡单品精选", "鸡肉堡单品精选"):
            self.assertEqual(self._nutri(name)["identity"], [],
                             f"{name} 不应有确定身份")

    def test_fallback_base_is_not_identity(self) -> None:
        """靠兜底代餐得到的主体不算身份：大堡口福三件套不含巨无霸。"""
        identity = self._nutri("大堡口福三件套")["identity"]
        self.assertNotIn("巨无霸", identity)
        self.assertIn("中薯条", identity)

    def test_real_bundle_keeps_identity(self) -> None:
        """真名对齐的套餐保留完整身份。"""
        identity = self._nutri("巨无霸三件套")["identity"]
        self.assertLessEqual({"巨无霸", "中薯条", "可乐中杯"}, set(identity))

    def test_proxy_alias_bundle_is_not_identity(self) -> None:
        """借代餐别名建模的套餐，不得认领代餐主体。

        「龙焰鸡腿堡」在 ALIAS 里指向「麦辣鸡腿汉堡」，只为借一行营养估算热量；
        两者是不同商品（¥24.0 / ¥22.5，各自独立编码）。若把这层别名当成精确命中，
        「龙焰鸡腿堡三件套」（¥26.9）就会认领麦辣鸡腿汉堡 —— 问「麦辣+薯条+可乐
        怎么买」被答成 ¥26.9、多花 ¥18.6，而真实答案是 ¥33.5、多花 ¥12.0。
        """
        identity = self._nutri("龙焰鸡腿堡三件套")["identity"]
        self.assertNotIn("麦辣鸡腿汉堡", identity)
        self.assertIn("中薯条", identity)

    def test_no_duplicated_components(self) -> None:
        """营养不得重复计入。

        菜单名以「随心选」结尾的商品会先经套餐拆分拿到「主体+薯条+可乐」，
        若 EXTRA_COMPONENTS 再补一次同样的配件，「学生专享汉堡小食随心选」
        会被算成两份中薯条（1094 kcal）。
        """
        for code, nut in self.idx["nutrition"].items():
            comps = [c.split("x")[0] for c in nut.get("components", [])]
            self.assertEqual(len(comps), len(set(comps)),
                             f"组件重复计入：{self.idx['items'][code]['name']}")


class TestIntentCompare(unittest.TestCase):
    """按意图比价：同一价格口径内比较，差额必须确定。"""

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def test_parse_intent_normalizes_names(self) -> None:
        """「薯条」「可乐」要归一成营养库口径。"""
        self.assertEqual(adviser.parse_intent("巨无霸+薯条+可乐"),
                         ["巨无霸", "中薯条", "可乐中杯"])

    def test_compare_uses_same_tier(self) -> None:
        """招牌比价的结论不得建立在会员价上。"""
        result = adviser.compare_intent(self.idx, adviser.parse_intent("巨无霸+薯条+可乐"))
        self.assertIsNotNone(result["best"])
        self.assertNotEqual(result["best"]["price_tier"], "member")
        self.assertEqual(result["best"]["name"], "巨无霸三件套")
        self.assertIsNotNone(result["gap"])
        self.assertGreater(result["gap"], 0)

    def test_member_side_reported_separately(self) -> None:
        """会员价另列，且只列靠会员身份才拿得到的那些。"""
        result = adviser.compare_intent(self.idx, adviser.parse_intent("巨无霸+薯条+可乐"))
        self.assertTrue(result["member_cover"], "应能列出会员价买法")
        for row in result["member_cover"]:
            self.assertEqual(row["price_tier"], "member")

    def test_other_burgers_bundle_cannot_win(self) -> None:
        """别的汉堡的套餐不能顶替所问的汉堡，差价也不得被它放大。

        龙焰鸡腿堡三件套（¥26.9）曾因代餐别名混进麦辣的候选里，
        把「多花 ¥12.0」算成「多花 ¥18.6」。
        """
        result = adviser.compare_intent(
            self.idx, adviser.parse_intent("麦辣鸡腿汉堡+薯条+可乐"))
        self.assertEqual(result["best"]["name"], "麦辣鸡腿汉堡三件套")
        self.assertAlmostEqual(result["gap"], 12.0, places=1)

    def test_member_flag_changes_price_basis(self) -> None:
        """--member 时比价按会员价口径，结构买法应更便宜。"""
        base = adviser.compare_intent(self.idx, ["巨无霸", "中薯条", "可乐中杯"])
        member = adviser.compare_intent(self.idx, ["巨无霸", "中薯条", "可乐中杯"],
                                        allow_member=True)
        self.assertLess(member["best"]["price"], base["best"]["price"])


class TestDiscountScan(unittest.TestCase):
    """门店标价口径：只做事实陈述，不与「结构省」混淆。"""

    @classmethod
    def setUpClass(cls) -> None:
        """装载一次索引，供全部用例复用。"""
        cls.idx = adviser.load_index()

    def test_rows_have_real_gap(self) -> None:
        """只有划线价确实高于现价的商品才入列，且差额算得对。"""
        rows = adviser.discount_scan(self.idx, top=999)
        self.assertTrue(rows)
        for r in rows:
            self.assertGreater(r["list_price"], r["price"])
            self.assertAlmostEqual(r["gap"], round(r["list_price"] - r["price"], 2), 2)

    def test_sorted_desc(self) -> None:
        """按差额降序。"""
        rows = adviser.discount_scan(self.idx, top=999)
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r["gap"], r["name"])))

    def test_member_rows_are_labelled(self) -> None:
        """会员价条目必须如实标注，不混进无门槛优惠里。"""
        rows = adviser.discount_scan(self.idx, top=999)
        tiers = {r["price_tier"] for r in rows}
        self.assertIn("member", tiers)
        for r in rows:
            self.assertIn(r["price_tier"], ("standard", "promo", "member"))


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


class TestMealsSelection(unittest.TestCase):
    """data/raw/ 下有多份门店快照时，必须报错而不是静默挑一份。

    这条不是假想的：实测发生过 —— 往 data/raw/ 多放一家门店的 meals_*.json，
    索引就被静默换成了那一家，而券快照、README 里的数字、demo 的断言
    都还停在原门店。整套流程只在最后被营养覆盖率那条断言拦下来。
    """

    def _with_raw(self, names: list[str]) -> None:
        """把 build_index.RAW 临时指向一个装着占位快照的目录。"""
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name)
        for name in names:
            (path / name).write_text("{}", encoding="utf-8")
        original = build_index.RAW
        build_index.RAW = path
        self.addCleanup(setattr, build_index, "RAW", original)
        self.addCleanup(tmp.cleanup)

    def test_single_snapshot_is_used(self) -> None:
        """只有一份时正常返回它。"""
        self._with_raw(["meals_1420762.json"])
        picked = build_index.pick_meals_file(None)
        self.assertEqual(picked.name, "meals_1420762.json")

    def test_multiple_snapshots_refuse_to_guess(self) -> None:
        """两份并存 → SystemExit，且报错里两份都要点出来。"""
        self._with_raw(["meals_1420762.json", "meals_1420888.json"])
        with self.assertRaises(SystemExit) as ctx:
            build_index.pick_meals_file(None)
        message = str(ctx.exception)
        self.assertIn("meals_1420762.json", message)
        self.assertIn("meals_1420888.json", message)

    def test_explicit_store_picks_that_store(self) -> None:
        """--store 能在一堆候选里精确挑出指定门店。"""
        self._with_raw(["meals_1420762.json", "meals_1420888.json"])
        picked = build_index.pick_meals_file("1420888")
        self.assertEqual(picked.name, "meals_1420888.json")

    def test_unknown_store_lists_candidates(self) -> None:
        """指定了不存在的门店 → 报错要告诉用户实际有哪些。"""
        self._with_raw(["meals_1420762.json"])
        with self.assertRaises(SystemExit) as ctx:
            build_index.pick_meals_file("9999999")
        self.assertIn("meals_1420762.json", str(ctx.exception))

    def test_no_snapshot_at_all(self) -> None:
        """一份都没有 → 明确提示缺什么。"""
        self._with_raw([])
        with self.assertRaises(SystemExit):
            build_index.pick_meals_file(None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
