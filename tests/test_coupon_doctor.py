#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_coupon_doctor.py —— 券模块的回归测试

覆盖：券形态判定、价值来源优先级（实测 > 菜单反查 > 未知）、
券包体检四分类、用券排程的机会约束、可领取券，以及
**绝不编造价值** 这条红线。
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import adviser  # noqa: E402
import coupon_doctor as CD  # noqa: E402

NOW = datetime(2026, 10, 14, 17, 26)


def coupon(**kw) -> CD.Coupon:
    """构造一张测试用券，只覆盖需要的字段。"""
    base = {"title": "测试券", "status": "claimed", "kind": "unknown"}
    base.update(kw)
    return CD.Coupon(**base)


def menu_by_name() -> dict[str, dict]:
    """菜单的 名称 -> 商品 映射。"""
    return {it["name"]: it for it in adviser.load_index()["items"].values()}


class TestForm(unittest.TestCase):
    """券形态判定：只做规则匹配，不猜。"""

    def test_bogo(self) -> None:
        """「买一送一」判为 bogo。"""
        self.assertEqual(CD.classify_form("中薯条买一送一"), "bogo")

    def test_free(self) -> None:
        """「免费」判为 free。"""
        self.assertEqual(CD.classify_form("免费脆薯饼"), "free")

    def test_fixed_price_with_yuan(self) -> None:
        """「9.9元…」判为固定价券。"""
        self.assertEqual(CD.classify_form("9.9元中杯冰美式"), "fixed_price")

    def test_fixed_price_without_yuan(self) -> None:
        """「13.9浓浓黑巧」不带「元」字，同样是固定价券。"""
        self.assertEqual(CD.classify_form("13.9浓浓黑巧"), "fixed_price")

    def test_money_off(self) -> None:
        """「满50减12」判为满减券。"""
        self.assertEqual(CD.classify_form("满50减12"), "money_off")

    def test_unknown_stays_unknown(self) -> None:
        """看不出来的券名就保持 unknown，不要硬套一个形态。"""
        self.assertEqual(CD.classify_form("王牌小食拼"), "unknown")


class TestTime(unittest.TestCase):
    """有效期解析：拿不到就说拿不到。"""

    def test_days_left_rounds_up(self) -> None:
        """剩余天数向上取整：三天内到期就显示 3 天。"""
        self.assertEqual(CD.days_left("2026-10-16 23:59", NOW), 3)

    def test_days_left_none_when_no_expiry(self) -> None:
        """没有有效期时返回 None，而不是 0。"""
        self.assertIsNone(CD.days_left(None, NOW))

    def test_days_left_never_negative(self) -> None:
        """已过期的券显示 0 天，不显示负数。"""
        self.assertEqual(CD.days_left("2026-10-01 00:00", NOW), 0)

    def test_parse_seconds_format(self) -> None:
        """快照的 capturedAt 带秒，必须能解析。"""
        self.assertEqual(CD.parse_dt("2026-10-14 17:26:54"),
                         datetime(2026, 10, 14, 17, 26, 54))


class TestValue(unittest.TestCase):
    """券价值：实测优先，其次菜单反查，都拿不到就是未知。"""

    @classmethod
    def setUpClass(cls) -> None:
        """装载菜单，供反查用。"""
        cls.menu = menu_by_name()

    def test_probe_wins_over_reverse(self) -> None:
        """有实测结果时，以实测为准（分 → 元只在这里换算一次）。"""
        c = coupon(title="中薯条买一送一", kind="bogo",
                   coupon_id="X", price_with=99.0)
        probes = {"X": {"couponId": "X", "discountCents": 1450,
                        "priceCents": 1450}}
        CD.attach_values([c], probes, self.menu)
        self.assertEqual(c.face_value, 14.5)
        self.assertEqual(c.price_with, 14.5)
        self.assertEqual(c.value_source, "probe")

    def test_reverse_for_bogo(self) -> None:
        """买一送一券没有实测结果时，价值 = 该商品的菜单单价。"""
        c = coupon(title="中薯条买一送一", kind="bogo")
        CD.attach_values([c], {}, self.menu)
        self.assertEqual(c.face_value, self.menu["薯条"]["price"])
        self.assertEqual(c.value_source, "reverse")

    def test_no_alignment_means_unknown(self) -> None:
        """对不上菜单商品的券一律标未知 —— 不猜。"""
        c = coupon(title="免费脆薯饼", kind="free")
        CD.attach_values([c], {}, self.menu)
        self.assertIsNone(c.face_value)
        self.assertEqual(c.value_source, "unknown")

    def test_money_off_takes_the_discount(self) -> None:
        """满减券的价值就是减免额。"""
        c = coupon(title="满50减12", kind="money_off", threshold=50.0)
        CD.attach_values([c], {}, self.menu)
        self.assertEqual(c.face_value, 12.0)


class TestCheckup(unittest.TestCase):
    """券包体检：净价值 = 券面价值 − 为用券你本来不会花的钱。"""

    def test_handy_when_baseline_already_meets_threshold(self) -> None:
        """基准消费已过门槛 → 顺手可用，净价值等于券面价值。"""
        c = coupon(title="满50减12", kind="money_off",
                   threshold=50.0, face_value=12.0)
        CD.wallet_checkup([c], baseline=60.0, now=NOW)
        self.assertEqual(c.verdict, CD.HANDY)
        self.assertEqual(c.net_value, 12.0)

    def test_stretch_when_gap_smaller_than_value(self) -> None:
        """差额小于券面价值 → 努一把，标出净赚多少。"""
        c = coupon(title="满50减12", kind="money_off",
                   threshold=50.0, face_value=12.0)
        CD.wallet_checkup([c], baseline=45.0, now=NOW)
        self.assertEqual(c.verdict, CD.STRETCH)
        self.assertEqual(c.net_value, 7.0)

    def test_paper_wealth_is_rejected(self) -> None:
        """差额不小于券面价值 → 纸面富贵，算出硬用会亏多少。"""
        c = coupon(title="满50减12", kind="money_off",
                   threshold=50.0, face_value=12.0)
        report = CD.wallet_checkup([c], baseline=20.0, now=NOW)
        self.assertEqual(c.verdict, CD.PAPER)
        self.assertEqual(c.net_value, -18.0)
        self.assertEqual(report["counts"][CD.PAPER], 1)

    def test_unknown_value_is_not_counted_as_zero(self) -> None:
        """价值未知的券不得当成 0 计入总额。"""
        c = coupon(title="免费脆薯饼", kind="free")
        report = CD.wallet_checkup([c], baseline=45.0, now=NOW)
        self.assertEqual(c.verdict, CD.UNKNOWN)
        self.assertIsNone(c.net_value)
        self.assertEqual(report["named_total"], 0.0)

    def test_claimable_excluded_from_checkup(self) -> None:
        """体检只针对手里的券，可领取的另算。"""
        c = coupon(title="9.9元中杯冰美式", status="claimable",
                   kind="fixed_price", fixed_price=9.9, face_value=2.0)
        report = CD.wallet_checkup([c], baseline=45.0, now=NOW)
        self.assertEqual(report["rows"], [])


class TestSchedule(unittest.TestCase):
    """用券排程：机会有限，用不上的就是注定浪费的钱。"""

    def _coupons(self) -> list[CD.Coupon]:
        """造三张有效期不同的券。"""
        return [
            coupon(title="A", kind="free", face_value=20.0, net_value=20.0,
                   end_at="2026-10-16 23:59"),
            coupon(title="B", kind="free", face_value=10.0, net_value=10.0,
                   end_at="2026-10-16 23:59"),
            coupon(title="C", kind="free", face_value=5.0, net_value=5.0,
                   end_at="2026-10-20 23:59"),
        ]

    def test_window_is_the_longest_expiry(self) -> None:
        """窗口取最晚过期的券：10-20 23:59 距 10-14 17:26 是 6.27 天，向上取整为 7。"""
        self.assertEqual(CD.window_days(self._coupons(), NOW), 7)

    def test_orders_in_window_at_least_one(self) -> None:
        """点单频率再低，窗口内也至少按 1 单算。"""
        self.assertEqual(CD.orders_in_window(3, 0.5), 1)

    def test_assigns_highest_value_first(self) -> None:
        """机会足够时，全部券都能排上。"""
        sch = CD.schedule(self._coupons(), orders_per_week=7.0, now=NOW)
        self.assertEqual([a["title"] for a in sch["assigned"]], ["A", "B", "C"])
        self.assertEqual(sch["wasted_total"], 0.0)

    def test_wasted_when_slots_run_out(self) -> None:
        """机会不够时，按净价值从高到低排，剩下的计为浪费。"""
        sch = CD.schedule(self._coupons(), orders_per_week=0.5, now=NOW)
        self.assertEqual([a["title"] for a in sch["assigned"]], ["A"])
        self.assertEqual(sch["wasted_total"], 15.0)

    def test_coupon_without_expiry_is_not_scheduled(self) -> None:
        """没有有效期的券不进排程 —— 把「未知」当「永久」就是编造。"""
        c = coupon(title="D", kind="free", face_value=9.0, net_value=9.0)
        sch = CD.schedule([c], orders_per_week=7.0, now=NOW)
        self.assertEqual(sch["assigned"], [])
        self.assertEqual(sch["window_days"], 0)


class TestRealSnapshot(unittest.TestCase):
    """对着仓库里的真实券快照跑一遍，把事实钉住。"""

    def test_real_snapshot_matches_expectations(self) -> None:
        """三张券的价值来自实测，可领取券 3 张，窗口 6 天。"""
        report = CD.analyze(baseline=45.0, orders_per_week=3.0)
        coupons, _ = CD.load_coupons()
        CD.attach_values(coupons, CD.load_probes(), menu_by_name())

        probed = {c.title for c in coupons if c.value_source == "probe"}
        self.assertEqual(probed, {"中薯条买一送一", "王牌小食拼", "13.9浓浓黑巧"})
        self.assertEqual(len(CD.claimable(coupons)), 3)
        self.assertEqual(report["schedule"]["window_days"], 6)

    def test_probe_finds_value_reverse_cannot(self) -> None:
        """「王牌小食拼」券名无数字、菜单无对应商品 —— 反查拿不到，实测能。"""
        coupons, _ = CD.load_coupons()
        CD.attach_values(coupons, CD.load_probes(), menu_by_name())
        target = next(c for c in coupons if c.title == "王牌小食拼")
        self.assertEqual(target.value_source, "probe")
        self.assertEqual(target.face_value, 6.1)

    def test_no_coupon_has_a_value_without_a_source(self) -> None:
        """红线：没有来源就不给价值。"""
        coupons, _ = CD.load_coupons()
        CD.attach_values(coupons, CD.load_probes(), menu_by_name())
        for c in coupons:
            if c.face_value is None:
                self.assertEqual(c.value_source, "unknown", c.title)
            else:
                self.assertIn(c.value_source, ("probe", "reverse"), c.title)


class TestOrders(unittest.TestCase):
    """消费审计：脱敏、派生客单价与频率。用构造的合成快照，不读真实订单。"""

    RAW = {
        "datetime": "2026-10-14 17:45:09",
        "data": {"list": [
            {"orderId": "SECRET-1", "createTime": "2026-09-25 18:26:26",
             "beType": "1", "beCode": "BE-9", "storeCode": "1420962",
             "storeName": "某门店", "orderStatus": "订单已完成",
             "realTotalAmount": "0",
             "orderProductList": [{"productCode": "1", "productName": "随心配1+1",
                                   "quantity": 1}]},
            {"orderId": "SECRET-2", "createTime": "2026-06-25 12:00:00",
             "beType": "1", "beCode": "BE-9", "storeCode": "1420962",
             "storeName": "某门店", "orderStatus": "订单已完成",
             "realTotalAmount": "30",
             "orderProductList": [{"productCode": "2", "productName": "巨无霸",
                                   "quantity": 2}]},
            {"orderId": "SECRET-3", "createTime": "2026-04-25 12:00:00",
             "beType": "1", "beCode": "BE-9", "storeCode": "1420962",
             "storeName": "某门店", "orderStatus": "订单已取消",
             "realTotalAmount": "20",
             "orderProductList": [{"productCode": "2", "productName": "巨无霸",
                                   "quantity": 1}]},
        ]},
    }

    def _snapshot(self, data: dict) -> Path:
        """把合成快照写进临时文件，返回路径。"""
        import json
        import tempfile
        fd, name = tempfile.mkstemp(suffix=".json")
        with open(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        self.addCleanup(Path(name).unlink)
        return Path(name)

    def test_sanitize_drops_personal_fields(self) -> None:
        """脱敏后不含订单号、门店、BE 码与下单时刻。"""
        clean = CD.sanitize_orders(self.RAW)
        blob = str(clean)
        for leaked in ("SECRET", "1420962", "某门店", "BE-9"):
            self.assertNotIn(leaked, blob)
        self.assertEqual(clean["orders"][0]["date"], "2026-09-25")

    def test_sanitize_keeps_money_and_items(self) -> None:
        """金额与商品名保留 —— 审计要用的就是这些。"""
        clean = CD.sanitize_orders(self.RAW)
        self.assertEqual(clean["orders"][1]["total"], 30.0)
        self.assertEqual(clean["orders"][1]["items"][0]["name"], "巨无霸")

    def test_load_orders_excludes_cancelled(self) -> None:
        """已取消的订单不算消费。"""
        audit = CD.load_orders(self._snapshot(CD.sanitize_orders(self.RAW)))
        self.assertEqual(audit["n_orders"], 2)

    def test_zero_amount_not_in_ticket_but_in_frequency(self) -> None:
        """金额 0 的单计入点单频率，但不拉低客单价。"""
        audit = CD.load_orders(self._snapshot(CD.sanitize_orders(self.RAW)))
        self.assertEqual(audit["avg_ticket"], 30.0)
        self.assertEqual(audit["n_orders"], 2)

    def test_missing_file_returns_empty(self) -> None:
        """没有订单快照就返回空 —— 不猜。"""
        self.assertEqual(CD.load_orders(Path("/nonexistent/orders.json")), {})

    def test_analyze_switches_to_measured_frequency(self) -> None:
        """给了订单就用实测频率，并在报告里标明来源。"""
        audit = CD.load_orders(self._snapshot(CD.sanitize_orders(self.RAW)))
        assumed = CD.analyze(baseline=45.0, orders_per_week=3.0, now=NOW)
        measured = CD.analyze(baseline=45.0, orders_per_week=3.0, now=NOW,
                              orders=audit)
        self.assertEqual(assumed["frequency_source"], "假设")
        self.assertEqual(measured["frequency_source"], "订单实测")
        self.assertAlmostEqual(measured["schedule"]["orders_per_week"],
                               audit["orders_per_week"])

    def test_fmt_freq_keeps_integers_clean(self) -> None:
        """整数频率不带小数点，小数频率保留两位。"""
        self.assertEqual(CD.fmt_freq(3.0), "3")
        self.assertEqual(CD.fmt_freq(0.264151), "0.26")


if __name__ == "__main__":
    unittest.main(verbosity=2)
