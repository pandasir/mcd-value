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

BAR = "─" * 52

# 套餐类后缀：用于把套餐名还原成「主体」，也用于识别一个商品是不是套餐。
SET_SUFFIXES = ("三件套", "四件套", "套餐", "随心选")

# 明确标注「件数」的后缀，用于检测菜单结构倒挂（件数更多反而更便宜）。
COUNTED_SUFFIX = {"三件套": 3, "四件套": 4}


# ------------------------------------------------------------------ 小工具
def yuan(x: float) -> str:
    """把金额格式化成 ¥xx.x。"""
    return f"¥{x:.1f}"


def items_by_name(idx: dict) -> dict[str, dict]:
    """按商品名建索引（菜单内名称唯一）。"""
    return {it["name"]: it for it in idx["items"].values()}


def bundle_base(name: str) -> tuple[str, str] | None:
    """把套餐名拆成 (主体, 后缀)；非套餐返回 None。"""
    for suffix in SET_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    return None


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
def cheapest_bundle_for(base: str, idx: dict) -> dict | None:
    """在同一主食名下，取最便宜的套餐（三件套/四件套/套餐）。"""
    best = None
    for it in idx["items"].values():
        split = bundle_base(it["name"])
        if not split or split[0] != base or split[1] == "随心选":
            continue
        if best is None or it["price"] < best["price"]:
            best = it
    return best


def scene_wasted_money(idx: dict) -> dict:
    """同内容的两种买法：单点 vs 套餐，算出「多花了多少钱」。"""
    by_name = items_by_name(idx)
    intent = ("巨无霸", "薯条", "可乐")
    parts = [(n, by_name[n]["price"]) for n in intent]
    alc_total = round(sum(p for _, p in parts), 2)
    bundle = cheapest_bundle_for(intent[0], idx)
    gap = round(alc_total - bundle["price"], 2) if bundle else None
    return {"intent": intent, "parts": parts, "alc_total": alc_total,
            "bundle": bundle, "gap": gap}


# ------------------------------------------------------------------ 场景二
def scene_menu_trap(idx: dict) -> list[dict]:
    """扫描菜单，找出「件数更多反而更便宜」的结构倒挂。"""
    groups: dict[str, dict[int, dict]] = {}
    for it in idx["items"].values():
        split = bundle_base(it["name"])
        if not split:
            continue
        base, suffix = split
        if suffix in COUNTED_SUFFIX:
            groups.setdefault(base, {})[COUNTED_SUFFIX[suffix]] = it

    traps = []
    for base, by_count in groups.items():
        if 3 in by_count and 4 in by_count and by_count[4]["price"] < by_count[3]["price"]:
            traps.append({
                "base": base,
                "three": by_count[3],
                "four": by_count[4],
                "gap": round(by_count[3]["price"] - by_count[4]["price"], 2),
            })
    traps.sort(key=lambda t: t["gap"], reverse=True)
    return traps


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


def print_wasted(idx: dict, wasted: dict) -> None:
    """场景一：这一单你多花了多少钱。"""
    bundle = wasted["bundle"]
    print()
    print("① 这一单，你多花了多少钱")
    print(f"   意图：想吃到「{' + '.join(wasted['intent'])}」")
    print()
    line = " + ".join(f"{n} {yuan(p)}" for n, p in wasted["parts"])
    print(f"   单点买法      {line} = {yuan(wasted['alc_total'])}")
    if bundle:
        extra = "（含这三样，还多一份麦乐鸡）" if "四件套" in bundle["name"] else ""
        print(f"   求解器买法    {bundle['name']} ×1 = {yuan(bundle['price'])}{extra}")
        print(f"                 {'─' * 22}")
        print(f"   你多花了      {yuan(wasted['gap'])}")
    print()


def print_trap(traps: list[dict]) -> None:
    """场景二：菜单本身的结构倒挂。"""
    print("② 菜单里本来就有坑：份数更多，反而更便宜")
    if not traps:
        print("   本门店未发现「三件套 > 四件套」的倒挂。")
        print()
        return
    print(f"   全菜单扫出 {len(traps)} 组（直接来自 query-meals 的原始价格）：")
    for t in traps:
        print(f"     · {t['base']}：三件套 {yuan(t['three']['price'])}"
              f" > 四件套 {yuan(t['four']['price'])}　→ 省 {yuan(t['gap'])}")
    print()
    print("   同一份主食，点『三件套』的人多花钱、还少拿一份。")
    print()


def print_plan(title: str, note: str, idx: dict, args: SimpleNamespace, plans: list) -> None:
    """打印一个求解场景。"""
    print(title)
    if note:
        print(f"   {note}")
    print()
    print(A.render(idx, plans, args))
    print()


def main() -> int:
    """跑通全部演示场景；任一断言失败即返回非零退出码。"""
    idx = A.load_index()
    head(idx)

    # ---- 场景一：冤枉钱 -------------------------------------------------
    wasted = scene_wasted_money(idx)
    print_wasted(idx, wasted)

    # ---- 场景二：菜单倒挂 -----------------------------------------------
    traps = scene_menu_trap(idx)
    print_trap(traps)

    # ---- 场景三：预算内的均衡一餐 ---------------------------------------
    args3, plans3 = advise(idx, budget=45, people=1, mode="balanced", top=1)
    print_plan("③ 预算 ¥45 吃一餐均衡的", "约束：主食 + 小食 + 饮品，热量 500–900 kcal",
               idx, args3, plans3)

    # ---- 场景四：硬约束（忌口） -----------------------------------------
    args4, plans4 = advise(idx, budget=45, people=1, mode="balanced", top=1,
                           banned=("beef", "fried"))
    print_plan("④ 同样的预算，忌牛肉 + 忌油炸",
               "忌口是硬约束：候选池里直接剔除，不是「尽量避开」",
               idx, args4, plans4)

    # ---- 断言：关键不变量 ------------------------------------------------
    assert plans3, "均衡模式应给出方案"
    p3 = plans3[0]
    assert p3.total <= 45 + 1e-6, "预算是硬约束：券后总价不得超过预算"
    roles3 = {l.role for l in p3.lines}
    assert A.MODE_TARGETS["balanced"]["required"] <= roles3, "均衡模式必须构成完整一餐"
    if plans4:
        for line in plans4[0].lines:
            assert not (A.tags_of(line.name) & {"beef", "fried"}), \
                f"忌口未生效：{line.name}"
    assert wasted["alc_total"] > 0, "单点基线应大于 0"
    assert wasted["gap"] is not None and wasted["gap"] > 0, "应能找到更便宜的套餐买法"

    # ---- 尾 --------------------------------------------------------------
    print(BAR)
    print("上面每一行都能在你自己的机器上复现：")
    print("  python scripts/adviser.py --budget 45 --people 1 --mode balanced")
    print("  python scripts/adviser.py --budget 45 --people 1 --mode balanced"
          " --no-beef --no-fried")
    print("  python -m unittest discover -s tests -v")
    print()
    print("价格为门店实时快照口径，最终以 calculate-price 结果为准；营养为估算的已标注。")
    print("如果它帮你少花了一杯可乐的钱 → ⭐")
    print(BAR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
