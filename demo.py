#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo.py —— 麦麦点餐参谋 · 30 秒演示

    python demo.py

单命令跑通，零依赖 / 零 Token / 不联网：读取仓库内置的真实门店快照，
展示「约束求解器算出来的方案」与「随手点会多花多少钱」的对比。

这个文件同时是端到端回归测试：内部对关键不变量做断言，
任何一条不成立就以退出码 1 结束（CI 会跑它）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import adviser as A  # noqa: E402  # 需先把 scripts/ 注入 sys.path
import coupon_doctor as CD  # noqa: E402

BAR = "─" * 52


# ------------------------------------------------------------------ 小工具
def yuan(x: float) -> str:
    """把金额格式化成 ¥xx.x。"""
    return f"¥{x:.1f}"


def items_by_name(idx: dict) -> dict[str, dict]:
    """按商品名建索引（菜单内名称唯一）。"""
    return {it["name"]: it for it in idx["items"].values()}


def advise(idx: dict, budget: float, people: int, mode: str, top: int = 1,
           banned: tuple[str, ...] = (), max_kcal: float | None = None,
           min_protein: float | None = None) -> tuple[SimpleNamespace, list]:
    """按给定约束调用求解器，返回 (模拟参数, 方案列表)。"""
    args = SimpleNamespace(budget=budget, people=people, mode=mode, top=top,
                           banned=set(banned), max_kcal=max_kcal,
                           min_protein=min_protein)
    pool = A.build_pool(idx, args.banned)
    plans = A.solve(idx, pool, budget, people, mode, top, max_kcal, min_protein)
    return args, plans


# ------------------------------------------------------------------ 场景一
def scene_wasted_money(idx: dict) -> dict:
    """同一意图的两种买法：逐个单点 vs 本门店已有的组合商品。

    这里刻意**不用**"全菜单最便宜的套餐"这种找法：那会把麦金卡会员价
    混进无门槛价里比较，得出的差额不成立。比价必须同一价格口径。
    """
    return A.compare_intent(idx, A.parse_intent("巨无霸+薯条+可乐"))


# ------------------------------------------------------------------ 场景二
BUNDLE_MARKS = ("三件套", "四件套", "套餐")


def scene_bundle_gap(idx: dict) -> list[dict]:
    """全菜单扫描：套餐价 比「按它的确定组成逐个单点」便宜多少。

    只在**同一价格口径**内比（会员价商品整条排除），所以结论无门槛、可复现。
    """
    rows = []
    for it in idx["items"].values():
        if it.get("priceTier") == "member":
            continue
        if not any(k in it["name"] for k in BUNDLE_MARKS):
            continue
        ident = (idx["nutrition"].get(it["code"]) or {}).get("identity") or []
        if len(ident) < 2:
            continue
        parts = [A.cheapest_for(idx, c) for c in ident]
        if any(p is None for p in parts):
            continue
        alcove = round(sum(p["price"] for p in parts), 2)
        rows.append({"name": it["name"], "bundle": float(it["price"]),
                     "alcove": alcove, "gap": round(alcove - float(it["price"]), 2)})
    rows.sort(key=lambda r: (-r["gap"], r["name"]))
    return rows


# ------------------------------------------------------------------ 场景三
def scene_member_gap(idx: dict) -> list[dict]:
    """麦金卡把同一份主食的四件套压到多少钱 —— 与同主食的三件套比。

    这两侧**都在会员可享的范围内**（会员同样买得到三件套），所以「四件套更便宜
    且多一份」这个结论成立。但它成立的前提是**你有卡**；没卡时四件套那个价拿不到。
    这正是 README 早先把会员价当普通价时会踩的坑。
    """
    by_name = items_by_name(idx)
    rows = []
    for it in idx["items"].values():
        if it.get("priceTier") != "member" or not it["name"].endswith("四件套"):
            continue
        three = by_name.get(it["name"].replace("四件套", "三件套"))
        if not three:
            continue
        rows.append({"name": it["name"].replace("四件套", ""),
                     "four": float(it["price"]), "three": float(three["price"]),
                     "gap": round(float(three["price"]) - float(it["price"]), 2)})
    rows.sort(key=lambda r: (-r["gap"], r["name"]))
    return rows


# ------------------------------------------------------------------ 输出
def head(idx: dict) -> None:
    """打印演示头。"""
    store = idx["store"]
    print(BAR)
    print("🍟 麦麦点餐参谋 · 30 秒演示")
    print(f"   门店 {store['storeCode']} {store['storeName']}"
          f"（{'到店自取' if store.get('beType') == 1 else '外送'}）")
    print(f"   菜单快照 {store['capturedAt']} · {idx['mealCount']} 件商品"
          f" · 营养覆盖 {idx['nutritionCoverage']:.0%}")
    print(BAR)


def print_wasted(result: dict) -> None:
    """场景一：这一单你多花了多少钱。"""
    print()
    print("① 这一单，你多花了多少钱")
    print(f"   意图：想吃到「{' + '.join(result['intent'])}」")
    print()
    line = " + ".join(f"{p['menu_name']} {yuan(p['price'])}" for p in result["parts"])
    print(f"   单点买法      {line} = {yuan(result['single_total'])}")
    best = result["best"]
    if best:
        print(f"   结构买法      {best['name']} ×1 = {yuan(best['price'])}")
        print(f"                 {'─' * 22}")
        print(f"   你多花了      {yuan(result['gap'])}")
    if result["member_cover"]:
        m = result["member_cover"][0]
        print(f"                 （持麦金卡还能到 {m['name']} {yuan(m['price'])}）")
    print()
    print("   两个数字都来自 query-meals 的原始返回，且**同一价格口径**（无条件价）。")
    print()


def print_bundle_gap(rows: list[dict]) -> None:
    """场景二：全菜单里，套餐比按组成单点便宜多少。"""
    print("② 全菜单：套餐比「按组成逐个单点」便宜多少")
    if not rows:
        print("   本门店没有可比对的套餐。")
        print()
        return
    gap_sum = sum(r["gap"] for r in rows if r["gap"] > 0)
    print(f"   扫出 {len(rows)} 组可比对套餐（全部为无条件价，不含会员价商品）：")
    for r in rows[:8]:
        print(f"     · {r['name']}：套餐 {yuan(r['bundle'])} < 单点 {yuan(r['alcove'])}"
              f"　→ 省 {yuan(r['gap'])}")
    print()
    print(f"   其中正的组合共 {sum(1 for r in rows if r['gap'] > 0)} 组，"
          f"合计可省 {yuan(gap_sum)}。")
    print()


def print_member_gap(rows: list[dict]) -> None:
    """场景三：麦金卡把四件套压到多少钱（只在会员可享范围内比较）。"""
    print("③ 麦金卡值多少：同一份主食，四件套比三件套便宜且多一份")
    if not rows:
        print("   本门店没有可比对的三件套/四件套。")
        print()
        return
    for r in rows[:6]:
        print(f"     · {r['name']}：三件套 {yuan(r['three'])} > 四件套 {yuan(r['four'])}"
              f"　→ 省 {yuan(r['gap'])}")
    print()
    print("   ⚠️ 这 8 组的四件套那一侧**全部是麦金卡会员价**。没卡时这个价拿不到，")
    print("      「份数更多反而更便宜」不成立 —— 成立的是「有卡每单省 ¥3~¥6.5」。")
    print("      本项目默认把会员价排除在推荐之外，用 --member 才会纳入。")
    print()


def print_discounts(rows: list[dict]) -> None:
    """场景四：门店标价口径的优惠幅度（与「结构省」严格分开）。"""
    print("④ 门店标价口径：标价与现价差多少（不是「你省了多少」）")
    for r in rows[:5]:
        tag = {"standard": "无条件价", "promo": "限时促销价",
               "member": "需麦金卡"}.get(r["price_tier"], r["price_tier"])
        print(f"     · {r['name']}：标价 {yuan(r['list_price'])} → {yuan(r['price'])}"
              f"（-{r['off']:.0%}）· {tag}")
    print()
    print("   ⚠️ 划线价是门店标注的参考价，不等于你省下了这些钱 —— 你本来也不会按标价买。")
    print("      本项目只把「同一批商品换买法」的结构差当作确定的省。")
    print()


def print_plan(title: str, note: str, args: SimpleNamespace, idx: dict,
               plans: list) -> None:
    """打印一个求解场景。"""
    print(title)
    if note:
        print(f"   {note}")
    print()
    print(A.render(idx, plans, args))
    print()


def print_coupons(idx: dict, plans: list, coupons: list) -> dict:
    """场景三：券的价值、体检、排程与可领取券。返回体检报告供断言使用。"""
    baseline = plans[0].total if plans else 45.0
    report = CD.analyze(baseline=baseline, orders_per_week=3.0,
                        orders=CD.load_orders() or None)
    print("⑤ 你的券在漏水：券不是「可用资源」，是有保质期的钱")
    print()
    for line in CD.render(report).splitlines():
        print("   " + line)
    print()
    print("   券还能叠到具体方案上（本单真的有券覆盖的商品时才标注）：")
    print("     $ python scripts/adviser.py --budget 30 --mode light --top 5 --coupons")
    _, light = advise(idx, budget=30, people=1, mode="light", top=5)
    for p in light:
        hits = A.coupons_for_plan(p, idx, coupons)
        if hits:
            names = " + ".join(line.name for line in p.lines)
            print(f"     方案 ¥{p.total:.1f}　{names}")
            for h in hits:
                src = CD.VALUE_SOURCE_LABEL.get(h["value_source"], "来源未知")
                print(f"       🎟️ 本单可用：{h['title']}　再省 ¥{h['face_value']:.1f}"
                      f"（{src}，需门店核验）")
            break
    print()
    return report


def main() -> int:
    """跑通全部演示场景；任一断言失败即返回非零退出码。"""
    idx = A.load_index()
    head(idx)

    # 先算「这一单」：券的体检要以它为基准，所以求解要走在券场景之前。
    args_b, plans_b = advise(idx, budget=45, people=1, mode="balanced", top=1)

    coupons, _ = CD.load_coupons()
    CD.attach_values(coupons, CD.load_probes(), items_by_name(idx))

    # ---- 场景一：冤枉钱 -------------------------------------------------
    wasted = scene_wasted_money(idx)
    print_wasted(wasted)

    # ---- 场景二：套餐 vs 单点（同价口径，全菜单） -------------------------
    gaps = scene_bundle_gap(idx)
    print_bundle_gap(gaps)

    # ---- 场景三：麦金卡值多少 -------------------------------------------
    member_gaps = scene_member_gap(idx)
    print_member_gap(member_gaps)

    # ---- 场景四：门店标价口径（与「结构省」严格分开） ---------------------
    print_discounts(A.discount_scan(idx, top=5))

    # ---- 场景五：券 ------------------------------------------------------
    report = print_coupons(idx, plans_b, coupons)

    # ---- 场景六：预算内的均衡一餐 ---------------------------------------
    print_plan("⑥ 预算 ¥45 吃一餐均衡的", "约束：主食 + 小食 + 饮品，热量 500–900 kcal",
               args_b, idx, plans_b)

    # ---- 场景七：硬约束（忌口） -----------------------------------------
    args7, plans7 = advise(idx, budget=45, people=1, mode="balanced", top=1,
                           banned=("beef", "fried"))
    print_plan("⑦ 同样的预算，忌牛肉 + 忌油炸",
               "忌口是硬约束：候选池里直接剔除，不是「尽量避开」",
               args7, idx, plans7)

    # ---- 断言：关键不变量 ------------------------------------------------
    assert plans_b, "均衡模式应给出方案"
    assert plans_b[0].total <= 45 + 1e-6, "预算是硬约束：券后总价不得超过预算"
    provided = A.provided_roles(idx, [(l.code, l.qty) for l in plans_b[0].lines])
    assert A.MODE_TARGETS["balanced"]["required"] <= provided, \
        "均衡模式必须构成完整一餐（套餐可同时占多个槽位）"
    for line in (plans7[0].lines if plans7 else []):
        assert not (A.tags_of(line.name) & {"beef", "fried"}), f"忌口未生效：{line.name}"
    assert wasted["gap"] is not None and wasted["gap"] > 0, "应能找到更便宜的套餐买法"
    assert wasted["best"]["price_tier"] != "member", \
        "招牌比价不得建立在会员价上"
    # 会员价默认不得进入任何方案 —— 这是本项目踩过的坑，用断言钉住。
    for plan in (plans_b + plans7):
        for line in plan.lines:
            tier = idx["items"][line.code].get("priceTier")
            assert tier != "member", f"会员价商品不该出现在默认方案里：{line.name}"
    assert gaps and gaps[0]["gap"] > 0, "应能扫到套餐比单点便宜的组"
    assert all(r["bundle"] > 0 for r in gaps), "套餐扫描不应出现非正价格"

    for c in coupons:
        assert c.value_source in ("probe", "reverse", "unknown"), \
            f"未知的价值来源：{c.value_source}"
        assert (c.face_value is None) == (c.value_source == "unknown"), \
            f"券面价值与来源不一致：{c.title}"
    chk = report["checkup"]
    assert chk["realizable"] <= chk["named_total"] + 1e-6, "可实现不应超过券面名义总额"
    if report["audit"]:
        assert report["frequency_source"] == "订单实测", "有订单数据就该用实测频率"
        assert report["audit"]["orders_per_week"] > 0, "点单频率应为正"
        assert report["audit"]["avg_ticket"] is None or \
            report["audit"]["avg_ticket"] > 0, "客单价应为正"

    # ---- 尾 --------------------------------------------------------------
    print(BAR)
    print("上面每一行都能在你自己的机器上复现：")
    print("  python scripts/adviser.py --intent \"巨无霸+薯条+可乐\"")
    print("  python scripts/adviser.py --budget 45 --people 1 --mode balanced")
    print("  python scripts/adviser.py --discounts")
    print("  python scripts/adviser.py --intent \"巨无霸+薯条+可乐\" --member")
    print("  python scripts/coupon_doctor.py --budget 45")
    print("  python -m unittest discover -s tests -v")
    print()
    print("价格为门店实时快照口径，最终以 calculate-price 结果为准；营养为估算的已标注。")
    print("会员价默认排除（--member 才纳入）；券的价值没有实测来源就报「未知」。")
    print("如果它帮你少花了一杯可乐的钱 → ⭐")
    print(BAR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
