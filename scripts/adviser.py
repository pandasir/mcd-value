#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adviser.py —— 麦麦点餐参谋核心引擎（约束求解式套餐推荐）

与"让大模型随口推荐"的根本区别：这是一个**显式约束求解器**。
给定预算 / 人数 / 营养目标 / 忌口 / 可用券，在真实菜单上枚举组合，
做硬约束过滤 + 多目标打分 + 帕累托去重，输出可解释、可直接下单的方案。

用法：
  python scripts/adviser.py --budget 40 --people 1 --mode balanced
  python scripts/adviser.py --budget 60 --people 2 --mode protein --no-beef
  python scripts/adviser.py --budget 35 --mode light --max-kcal 650 --json

模式：
  value     最省      —— 满足饱腹底线的前提下总价最低
  balanced  均衡      —— 蛋白 / 性价比 / 热量结构 / 脂肪钠 加权
  protein   高蛋白    —— 蛋白总量与每元蛋白优先，适配健身
  light     轻负担    —— 控热量与脂肪钠，保底蛋白
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index.json"

# ------------------------------------------------------------------ 标签与禁忌
TAG_RULES: dict[str, tuple[str, ...]] = {
    "beef": ("牛堡", "巨无霸", "吉士", "安格斯", "牛气", "不素之霸", "双牛", "吉士汉堡包"),
    "pork": ("猪柳", "培根", "火腿", "香肠", "图林根"),
    "chicken": ("鸡",),
    "fish": ("鳕鱼", "麦香鱼", "鱼排", "薯鱼"),
    "spicy": ("麦辣", "辣", "龙焰", "川香", "辣椒", "椒盐", "麻"),
    "caffeine": ("咖啡", "美式", "奶铁", "卡布奇诺", "玛奇朵", "鲜萃", "浓缩", "红茶", "黑巧", "抹茶"),
    "dairy": ("牛奶", "奶", "芝士", "冰淇淋", "新地", "麦旋风", "圆筒", "卡布奇诺"),
    "fried": ("薯条", "炸", "脆", "鸡翅", "麦乐鸡", "油条", "脆汁鸡", "鸡排"),
}

# 优惠券规则库（来源：mcd-mcp `available-coupons` 实际返回）
# 说明：MCP 只给券名不给细则，故这里按券名推断规则，并统一标注"待门店核验"。
COUPON_RULES: list[dict] = [
    {"id": "fries_bogo", "title": "中薯条买一送一", "kind": "bogo", "match": ("薯条",)},
    {"id": "mcflurry_bogo", "title": "人气麦旋风买一送一", "kind": "bogo", "match": ("麦旋风",)},
    {"id": "americano_99", "title": "9.9元中杯冰美式", "kind": "fixed", "match": ("美式",), "price": 9.9},
]

MODE_TARGETS = {
    "value":    {"kcal": (450, 1000), "protein": 15, "required": {"staple"}},
    "balanced": {"kcal": (500, 900),  "protein": 20, "required": {"staple", "side", "drink"}},
    "protein":  {"kcal": (600, 1200), "protein": 33, "required": {"staple", "side", "drink"}},
    "light":    {"kcal": (330, 650),  "protein": 17, "required": {"staple", "drink"}},
}

# 各模式下的价格权重：只有「最省」以压价为主目标，其余模式把钱当约束而非目标，
# 否则会退化成"挑最便宜的那个"而不是"预算内吃得最好"。
PRICE_WEIGHT = {"value": 10.0, "balanced": 0.25, "protein": 0.15, "light": 0.35}


@dataclass
class Line:
    code: str
    name: str
    qty: int
    unit_price: float
    paid_price: float
    role: str
    applied_coupon: str | None = None

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.qty, 2)

    @property
    def paid(self) -> float:
        return round(self.paid_price * self.qty, 2)


@dataclass
class Plan:
    mode: str
    people: int
    lines: list[Line] = field(default_factory=list)
    subtotal: float = 0.0
    total: float = 0.0
    saved: float = 0.0
    per_person: float = 0.0
    nutrition: dict = field(default_factory=dict)
    confidence: str = "exact"
    score: float = 0.0
    notes: list[str] = field(default_factory=list)
    needs_verify: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("score", None)
        d["nutrition"] = {k: (round(v, 1) if isinstance(v, float) else v)
                          for k, v in self.nutrition.items()}
        d["order_items"] = [{"productCode": l.code, "quantity": l.qty}
                            for l in self.lines if l.code]
        return d


# ------------------------------------------------------------------ 索引装载
def load_index() -> dict:
    if not INDEX.exists():
        raise SystemExit("缺少 data/index.json，请先运行 scripts/build_index.py")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def tags_of(name: str) -> set[str]:
    return {t for t, keys in TAG_RULES.items() if any(k in name for k in keys)}


# 不参与推荐的商品：内容随机（"单品精选"类盲盒）或纯周边。
# 推荐器必须对「买到的东西」有确定性，否则营养与价格估算都不可信。
EXCLUDE_NAME_KEYS = ("单品精选", "百宝袋", "任选")


def build_pool(idx: dict, banned: set[str]) -> list[dict]:
    pool = []
    for code, it in idx["items"].items():
        if it["role"] == "nonfood":
            continue
        name = it["name"]
        if any(k in name for k in EXCLUDE_NAME_KEYS):
            continue
        if tags_of(name) & banned:
            continue
        nut = idx["nutrition"].get(code)
        pool.append({**it, "tags": sorted(tags_of(name)), "nut": nut})
    return pool


# ------------------------------------------------------------------ 优惠券
def apply_coupons(codes: list[tuple[str, int]], idx: dict) -> tuple[list[Line], float, list[str], list[str]]:
    """返回 (明细行, 券后总价, 命中券名, 待核验提示)"""
    lines: list[Line] = []
    hits: list[str] = []
    verify: list[str] = []
    total_paid = 0.0

    for code, qty in codes:
        it = idx["items"][code]
        unit = float(it["price"])
        paid_unit = unit
        used = None
        for rule in COUPON_RULES:
            if not any(k in it["name"] for k in rule["match"]):
                continue
            if rule["kind"] == "bogo" and qty >= 2:
                paid_unit = unit * (math.ceil(qty / 2) / qty)
                used = rule["title"]
            elif rule["kind"] == "fixed" and unit > rule["price"]:
                paid_unit = float(rule["price"])
                used = rule["title"]
            if used:
                hits.append(rule["title"])
                verify.append(f"「{used}」需在门店/App 核验适用范围后使用")
                break
        lines.append(Line(code=code, name=it["name"], qty=qty, unit_price=unit,
                          paid_price=round(paid_unit, 2), role=it["role"],
                          applied_coupon=used))
        total_paid += paid_unit * qty

    return lines, round(total_paid, 2), hits, verify


# ------------------------------------------------------------------ 营养汇总
def sum_nutrition(lines: list[Line], idx: dict) -> tuple[dict, str]:
    total = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carb": 0.0, "sodium": 0.0, "calcium": 0.0}
    conf = "exact"
    for l in lines:
        n = idx["nutrition"].get(l.code)
        if not n:
            conf = "partial"
            continue
        if n["confidence"] != "exact":
            conf = "estimated" if conf == "exact" else conf
        for k in total:
            total[k] += n.get(k, 0) * l.qty
    return {k: round(v, 2) for k, v in total.items()}, conf


# ------------------------------------------------------------------ 打分
def score_plan(mode: str, total: float, people: int, nut: dict) -> float:
    pp_price = total / people
    kcal, prot = nut["kcal"] / people, nut["protein"] / people
    fat, sodium = nut["fat"] / people, nut["sodium"] / people
    w = PRICE_WEIGHT[mode]

    if mode == "value":
        return -pp_price * w - max(0, (450 - kcal)) * 0.02
    if mode == "protein":
        return (40 * (1 - math.exp(-prot / 30))
                + (prot / max(pp_price, 1e-6)) * 6
                - max(0, kcal - 1200) * 0.05
                - fat * 0.25
                - pp_price * w)
    if mode == "light":
        return (-kcal * 0.012 - fat * 0.5 - sodium * 0.004 + prot * 0.8 - pp_price * w)
    # balanced：蛋白收益递减，脂肪/钠惩罚加重，避免"高蛋白但高钠高脂"的方案夺冠
    return (40 * (1 - math.exp(-prot / 30))
            - fat * 0.55
            - sodium * 0.006
            - abs(kcal - 700) * 0.015
            - pp_price * w)


# ------------------------------------------------------------------ 求解
SHARE_KEYS = ("拼盘", "十翅", "双人餐", "四宫格", "任选", "七件")


def solve(idx: dict, pool: list[dict], budget: float, people: int,
          mode: str, top: int, max_kcal: float | None, min_protein: float | None) -> list[Plan]:
    tgt = MODE_TARGETS[mode]
    kcal_lo, kcal_hi = tgt["kcal"]
    if max_kcal:
        kcal_hi = max_kcal
    prot_floor = min_protein if min_protein is not None else tgt["protein"]

    staples = [x for x in pool if x["role"] == "staple" and x["nut"]]
    sides = [x for x in pool if x["role"] == "side" and x["nut"]]
    drinks = [x for x in pool if x["role"] == "drink" and x["nut"]]
    desserts = [x for x in pool if x["role"] == "dessert" and x["nut"]]
    share_sides = [x for x in sides if any(k in x["name"] for k in SHARE_KEYS)]
    regular_sides = [x for x in sides if x not in share_sides]

    required = tgt["required"]
    candidates: list[Plan] = []

    def evaluate(codes: list[tuple[str, int]], roles: set[str]) -> None:
        """codes 为 (商品code, 数量)；数量已按人数展开。"""
        if not required <= roles:
            return
        lines, total, hits, verify = apply_coupons(codes, idx)
        if total > budget + 1e-6:
            return
        nut, conf = sum_nutrition(lines, idx)
        per_kcal, per_prot = nut["kcal"] / people, nut["protein"] / people
        if not (kcal_lo <= per_kcal <= kcal_hi):
            return
        if per_prot < prot_floor:
            return

        subtotal = round(sum(l.subtotal for l in lines), 2)
        plan = Plan(
            mode=mode, people=people, lines=lines,
            subtotal=subtotal, total=total, saved=round(subtotal - total, 2),
            per_person=round(total / people, 2), nutrition=nut, confidence=conf,
            score=round(score_plan(mode, total, people, nut), 3),
            needs_verify=verify or ["价格与库存以门店实时结果为准"],
        )
        if hits:
            plan.notes.append("已套用：" + "、".join(sorted(set(hits))))
        if conf != "exact":
            plan.notes.append(f"营养为{'套餐建模估算' if conf == 'estimated' else '部分缺失'}，仅供参考")
        if any(l.role in ("side", "dessert") for l in lines):
            plan.notes.append("含可选配件，可自行删减以压价")
        candidates.append(plan)

    # 模式 A：标准点法（每人各一份）
    for staple, side, drink, dessert in itertools.product(
        staples, [None] + regular_sides, [None] + drinks, [None] + desserts
    ):
        picks = [x for x in (staple, side, drink, dessert) if x]
        if sum(x["price"] for x in picks) * people > budget + 1e-6:
            continue
        evaluate([(x["code"], people) for x in picks], {x["role"] for x in picks})

    # 模式 B：多人分享装（分享盘按 1 份计，主食与饮品按人数计）
    if people >= 2 and share_sides:
        for staple, share, drink, dessert in itertools.product(
            staples, share_sides, [None] + drinks, [None] + desserts
        ):
            picks = [x for x in (staple, share, drink, dessert) if x]
            if sum(x["price"] for x in picks) * people > budget + 1e-6:
                continue
            codes = [(staple["code"], people), (share["code"], 1)]
            codes += [(x["code"], people) for x in (drink, dessert) if x]
            evaluate(codes, {x["role"] for x in picks})

    candidates.sort(key=lambda p: p.score, reverse=True)

    # 帕累托去重：商品指纹相同只留最佳
    seen, kept = set(), []
    for p in candidates:
        fp = tuple(sorted((l.code, l.qty) for l in p.lines))
        if fp in seen:
            continue
        seen.add(fp)
        kept.append(p)
        if len(kept) >= top:
            break
    return kept


# ------------------------------------------------------------------ 渲染
def render(idx: dict, plans: list[Plan], args) -> str:
    store = idx["store"]
    out: list[str] = []
    out.append(f"🍟 麦麦点餐参谋 · {store['storeCode']} {store['storeName']}")
    out.append(f"   预算 ¥{args.budget:.0f} / {args.people} 人 · 模式 {args.mode}"
               + (f" · 忌口 {','.join(sorted(args.banned))}" if args.banned else ""))
    out.append("")

    if not plans:
        out.append("❌ 无可行方案。建议：提高预算、放宽热量区间，或减少忌口限制。")
        return "\n".join(out)

    for i, p in enumerate(plans, 1):
        head = f"方案 {i}　¥{p.total:.1f}"
        if p.people > 1:
            head += f"（人均 ¥{p.per_person:.1f}）"
        if p.saved > 0.01:
            head += f"　💰已省 ¥{p.saved:.1f}"
        out.append("─" * 46)
        out.append(head)
        for l in p.lines:
            cp = f"  ← {l.applied_coupon}" if l.applied_coupon else ""
            out.append(f"  · {l.name} ×{l.qty}　¥{l.subtotal:.1f}{cp}")
        n = p.nutrition
        out.append(f"  营养/人：{n['kcal']/p.people:.0f} kcal | 蛋白 {n['protein']/p.people:.1f}g "
                   f"| 脂肪 {n['fat']/p.people:.1f}g | 钠 {n['sodium']/p.people:.0f}mg")
        for note in p.notes:
            out.append(f"  ⓘ {note}")
        out.append("  下单参数：" + json.dumps([{"productCode": l.code, "quantity": l.qty}
                                            for l in p.lines], ensure_ascii=False))
    out.append("─" * 46)
    out.append("⚠️ 价格为门店实时快照口径，最终以 calculate-price 结果为准；券需门店核验。")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="麦麦点餐参谋 —— 约束求解式套餐推荐")
    ap.add_argument("--budget", type=float, default=40, help="总预算（元）")
    ap.add_argument("--people", type=int, default=1, help="人数")
    ap.add_argument("--mode", choices=list(MODE_TARGETS), default="balanced")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--max-kcal", type=float, default=None)
    ap.add_argument("--min-protein", type=float, default=None)
    ap.add_argument("--no-beef", action="store_true")
    ap.add_argument("--no-pork", action="store_true")
    ap.add_argument("--no-chicken", action="store_true")
    ap.add_argument("--no-fish", action="store_true")
    ap.add_argument("--no-spicy", action="store_true")
    ap.add_argument("--no-caffeine", action="store_true")
    ap.add_argument("--no-dairy", action="store_true")
    ap.add_argument("--no-fried", action="store_true")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args()

    args.banned = {k for k in TAG_RULES if getattr(args, f"no_{k}")}

    idx = load_index()
    pool = build_pool(idx, args.banned)
    plans = solve(idx, pool, args.budget, args.people, args.mode, args.top,
                  args.max_kcal, args.min_protein)

    if args.json:
        print(json.dumps({
            "store": idx["store"],
            "query": {"budget": args.budget, "people": args.people, "mode": args.mode,
                      "banned": sorted(args.banned)},
            "plans": [p.to_dict() for p in plans],
        }, ensure_ascii=False, indent=2))
    else:
        print(render(idx, plans, args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
