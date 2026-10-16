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
  python scripts/adviser.py --discounts            # 扫全菜单的划线价与门店标称优惠

模式：
  value     最省      —— 满足饱腹底线的前提下总价最低
  balanced  均衡      —— 蛋白 / 性价比 / 热量结构 / 脂肪钠 加权
  protein   高蛋白    —— 蛋白总量与每元蛋白优先，适配健身
  light     轻负担    —— 控热量与脂肪钠，保底蛋白

价格口径（三种「省」必须分清，否则就是在编数字）：
  ① 结构省  同一批商品换买法省下的钱。全部是真实现价 → 确定，本文件的主线。
  ② 标价差  门店划线价 − 现价。**不等于你省了钱**（你本来也不会按划线价买），
            只说明门店把优惠标成了多少。由 `--discounts` 单独呈现，不与 ① 相加。
  ③ 券后省  券带来的实测抵扣，口径在 coupon_doctor.py。
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
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

# 券名兜底规则：仅在**没有券快照**时使用。
# 有快照时请用 `--coupons`，走 `coupon_doctor` 的「实测 > 菜单反查 > 未知」口径 ——
# 那条路径有真实券码与实测价值，比这里的按名字猜要可靠得多。
COUPON_RULES: list[dict] = [
    {"id": "fries_bogo", "title": "中薯条买一送一", "kind": "bogo",
     "match": ("薯条",)},
    {"id": "mcflurry_bogo", "title": "人气麦旋风买一送一", "kind": "bogo",
     "match": ("麦旋风",)},
    {"id": "americano_99", "title": "9.9元中杯冰美式", "kind": "fixed",
     "match": ("美式",), "price": 9.9},
]

MODE_TARGETS = {
    "value": {"kcal": (450, 1000), "protein": 15, "required": {"staple"}},
    "balanced": {"kcal": (500, 900), "protein": 20,
                 "required": {"staple", "side", "drink"}},
    "protein": {"kcal": (600, 1200), "protein": 33,
                "required": {"staple", "side", "drink"}},
    "light": {"kcal": (330, 650), "protein": 17,
              "required": {"staple", "drink"}},
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
    list_price: float | None = None

    @property
    def subtotal(self) -> float:
        """未用券时的小计（元）。"""
        return round(self.unit_price * self.qty, 2)

    @property
    def paid(self) -> float:
        """用券后的实付小计（元）。"""
        return round(self.paid_price * self.qty, 2)

    @property
    def list_subtotal(self) -> float | None:
        """门店划线价小计（元）；没有划线价时返回 None，**不拿现价顶替**。"""
        if self.list_price is None:
            return None
        return round(self.list_price * self.qty, 2)

    @property
    def list_gap(self) -> float:
        """门店标称优惠 = 划线价 − 现价；无划线价时为 0。"""
        if self.list_price is None:
            return 0.0
        return round((self.list_price - self.unit_price) * self.qty, 2)


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
    coupons: list[dict] = field(default_factory=list)
    list_total: float = 0.0
    list_gap: float = 0.0
    price_tier: str = "standard"

    def to_dict(self) -> dict:
        """转成可 JSON 序列化的字典；剔除内部打分，附上下单参数。"""
        d = asdict(self)
        d.pop("score", None)
        d["nutrition"] = {k: (round(v, 1) if isinstance(v, float) else v)
                          for k, v in self.nutrition.items()}
        d["order_items"] = [{"productCode": l.code, "quantity": l.qty}
                            for l in self.lines if l.code]
        return d


# ------------------------------------------------------------------ 索引装载
def load_index() -> dict:
    """读取归一化索引；缺失时给出可执行的修复提示。"""
    if not INDEX.exists():
        raise SystemExit("缺少 data/index.json，请先运行 scripts/build_index.py")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def tags_of(name: str) -> set[str]:
    """按商品名推断忌口标签（beef / spicy / dairy ……）。"""
    return {t for t, keys in TAG_RULES.items() if any(k in name for k in keys)}


# 不参与推荐的商品：内容随机（"单品精选"类盲盒 / "任选"类自选拼盘）或纯周边。
# 推荐器必须对「买到的东西」有确定性，否则营养与价格估算都不可信 ——
# 「堡堡随心拼（7件任选）」¥72.5 是 7 件，但营养库里没有对应行，只能建模成一个巨无霸
# （513 kcal）。放进来会让求解器以为 ¥72.5 只吃到 513 kcal，比不推荐更糟。
EXCLUDE_NAME_KEYS = ("单品精选", "百宝袋", "任选")


def member_items(idx: dict) -> list[dict]:
    """菜单里必须持有麦金卡才能拿到那个价的商品。

    把 member 价当成人人可买，预算约束会被系统性放宽 ——
    本门店 8 组「三件套 > 四件套」的倒挂，四件套那一侧**全部**是会员价。
    """
    return [it for it in idx["items"].values() if it.get("priceTier") == "member"]


def build_pool(idx: dict, banned: set[str], allow_member: bool = False) -> list[dict]:
    """构造候选池：剔除周边商品、盲盒类商品、忌口项，默认再剔除会员价商品。

    挂上营养、标签、角色槽位与价格口径。
    """
    pool = []
    for code, it in idx["items"].items():
        if it["role"] == "nonfood":
            continue
        if it.get("priceTier") == "member" and not allow_member:
            continue
        name = it["name"]
        if any(k in name for k in EXCLUDE_NAME_KEYS):
            continue
        if tags_of(name) & banned:
            continue
        nut = idx["nutrition"].get(code)
        pool.append({**it, "tags": sorted(tags_of(name)), "nut": nut,
                     "roles": it.get("roles") or [it["role"]]})
    return pool


def provided_roles(idx: dict, codes: list[tuple[str, int]]) -> set[str]:
    """一个组合实际能占用的角色槽位。

    套餐在索引里带 `roles`（由 build_index 依套餐的**结构化组成**推出：
    三件套/四件套明确含薯条与饮品），所以「巨无霸三件套本身就算一份完整一餐」
    这件事能被回答，而不是看它被分进哪个 role 桶。
    内容自选的「随心配」不带额外槽位 —— 那是建模假设，不能拿来放宽结构约束。
    """
    roles: set[str] = set()
    for code, _ in codes:
        it = idx["items"][code]
        roles.update(it.get("roles") or [it["role"]])
    roles.discard("nonfood")
    return roles


# ------------------------------------------------------------------ 优惠券
def apply_coupons(
    codes: list[tuple[str, int]], idx: dict,
) -> tuple[list[Line], float, list[str], list[str]]:
    """把券规则套到商品行上。

    返回 (明细行, 券后总价, 命中券名, 待核验提示)。
    """
    lines: list[Line] = []
    hits: list[str] = []
    verify: list[str] = []
    total_paid = 0.0

    for code, qty in codes:
        it = idx["items"][code]
        unit = float(it["price"])
        listed = float(it.get("originalPrice") or unit)
        # 划线价只在**确实高于**现价时才带上；相等就当没有，不制造 0 优惠。
        list_price = listed if listed > unit + 1e-9 else None
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
                          applied_coupon=used, list_price=list_price))
        total_paid += paid_unit * qty

    return lines, round(total_paid, 2), hits, verify


# ------------------------------------------------------------------ 营养汇总
def sum_nutrition(lines: list[Line], idx: dict) -> tuple[dict, str]:
    """汇总整单营养，并给出置信度：exact / estimated / partial。"""
    total = {"kcal": 0.0, "protein": 0.0, "fat": 0.0,
             "carb": 0.0, "sodium": 0.0, "calcium": 0.0}
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
    """按模式给方案打分。只有 value 模式以压价为主目标，其余把钱当约束。"""
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
# 多人分享装的识别关键词。
# 注意：这里曾经有 "任选" 与 "七件" 两个键 —— 两个都是死规则，永远匹配不到：
# 「任选」类商品在 build_pool 就被剔除（内容不可确定），菜单里写的是阿拉伯数字「7件」。
# 已经删掉，避免读代码的人以为分享装覆盖到了自选拼盘。
SHARE_KEYS = ("拼盘", "十翅", "双人餐", "四宫格")


def solve(idx: dict, pool: list[dict], budget: float, people: int, mode: str,
          top: int, max_kcal: float | None,
          min_protein: float | None) -> list[Plan]:
    """在候选池上枚举组合，施加硬约束过滤，打分后返回 Top-K。

    硬约束：结构完整 → 券后总价 ≤ 预算 → 人均热量落区间 → 人均蛋白达标。
    不满足直接淘汰，不做"尽量满足"。
    """
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

    def evaluate(codes: list[tuple[str, int]]) -> None:
        """codes 为 (商品code, 数量)；数量已按人数展开。"""
        if not required <= provided_roles(idx, codes):
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
        list_total = round(sum(l.list_subtotal or l.subtotal for l in lines), 2)
        tiers = {idx["items"][code].get("priceTier", "standard") for code, _ in codes}
        plan = Plan(
            mode=mode, people=people, lines=lines,
            subtotal=subtotal, total=total, saved=round(subtotal - total, 2),
            per_person=round(total / people, 2), nutrition=nut, confidence=conf,
            score=round(score_plan(mode, total, people, nut), 3),
            list_total=list_total, list_gap=round(list_total - subtotal, 2),
            price_tier="promo" if "promo" in tiers else "standard",
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
        evaluate([(x["code"], people) for x in picks])

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
            evaluate(codes)

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


# ------------------------------------------------------------------ 券标注
def plan_components(plan: Plan, idx: dict) -> set[str]:
    """方案里实际会吃到的东西 —— 取营养索引记录的**确定组成**（identity）。

    套餐在营养索引里有 identity（如 ["巨无霸", "中薯条", "可乐中杯"]），
    所以「方案里有没有薯条」这件事能被真实回答，而不是靠猜。
    用 identity 而不是 components：靠兜底代餐得到的主体不算，
    否则「大堡口福三件套」会被当成含巨无霸的去匹配巨无霸的券。
    """
    comps: set[str] = set()
    for line in plan.lines:
        comps.add(line.name)
        nutri = idx["nutrition"].get(line.code) or {}
        for comp in nutri.get("identity") or nutri.get("components", []):
            comps.add(comp.split("x")[0])
    return comps


def coupons_for_plan(plan: Plan, idx: dict, coupons: list) -> list[dict]:
    """本单能用上的券：券对齐到的商品出现在方案的实际组成里。"""
    import build_index as BI
    import coupon_doctor as CD

    comps = plan_components(plan, idx)
    hits = []
    for c in coupons:
        target = CD.NAME_ALIGN.get(c.title)
        if not target or c.face_value is None:
            continue
        nutri_name = BI.ALIAS.get(target, target)
        if nutri_name in comps or target in comps:
            hits.append({"title": c.title, "face_value": c.face_value,
                         "value_source": c.value_source, "kind": c.kind})
    return hits


# ------------------------------------------------------------------ 按意图比价
def parse_intent(text: str) -> list[str]:
    """把「巨无霸+薯条+可乐」切成清单，并按菜单别名归一成营养库里的名字。

    归一很重要：菜单叫「薯条」「可乐」，营养库按「中薯条」「可乐中杯」分，
    不归一就没法判断某个套餐到底含不含你要的东西。
    """
    import build_index as BI

    parts = [p.strip() for p in re.split(r"[+＋、,，/]", text) if p.strip()]
    return [BI.ALIAS.get(p, p) for p in parts]


def cheapest_for(idx: dict, want: str, allow_member: bool = False) -> dict | None:
    """买到一个指定组件的最便宜**单品**买法。找不到返回 None —— 不猜。

    只认 identity 长度为 1 的商品，也就是真正的单品。否则会拿套餐自己来当它的组件：
    「吉士汉堡包套餐」的 identity 里含「吉士汉堡包」，于是「单点」一侧会把套餐价
    再算一遍，比价变成循环论证。
    """
    best = None
    for code, it in idx["items"].items():
        if it["role"] == "nonfood":
            continue
        if it.get("priceTier") == "member" and not allow_member:
            continue
        identity = (idx["nutrition"].get(code) or {}).get("identity") or []
        if len(identity) != 1:
            continue
        if it["name"] == want or want in identity:
            if best is None or it["price"] < best["price"]:
                best = it
    return best


def intent_covers(idx: dict, want: list[str], allow_member: bool = False) -> list[dict]:
    """找出**确定含有** want 全部组件的商品，按价格升序。

    判据是 `identity` 而不是 `components`：靠兜底代餐得到的主体不算
    （「大堡口福三件套」的营养按巨无霸估算，但它并不含巨无霸）。
    """
    want_set = set(want)
    rows = []
    for code, it in idx["items"].items():
        if it["role"] == "nonfood":
            continue
        if it.get("priceTier") == "member" and not allow_member:
            continue
        nutri = idx["nutrition"].get(code) or {}
        identity = nutri.get("identity") or []
        if not identity:
            continue
        if want_set <= set(identity):
            rows.append({"code": code, "name": it["name"], "price": it["price"],
                         "price_tier": it.get("priceTier", "standard")})
    rows.sort(key=lambda r: (r["price"], r["name"]))
    return rows


def compare_intent(idx: dict, want: list[str], allow_member: bool = False) -> dict:
    """同一个意图的两种买法：逐个单点 vs 本门店已有的组合商品。"""
    parts = []
    for name in want:
        item = cheapest_for(idx, name, allow_member)
        parts.append({"name": name,
                      "menu_name": item["name"] if item else None,
                      "price": item["price"] if item else None})
    cover = intent_covers(idx, want, allow_member)
    alcove = (round(sum(p["price"] for p in parts), 2)
              if all(p["price"] is not None for p in parts) else None)
    best = cover[0] if cover else None
    gap = (round(alcove - best["price"], 2)
           if alcove is not None and best is not None else None)
    # 会员口令只列**靠会员身份才拿得到**的那些，否则会把同一件商品列两遍。
    member_only = [r for r in intent_covers(idx, want, True)
                   if r["price_tier"] == "member"] if not allow_member else []
    return {"intent": want, "parts": parts, "single_total": alcove,
            "cover": cover, "best": best, "gap": gap, "member_cover": member_only}


def render_intent(idx: dict, result: dict, allow_member: bool) -> str:
    """把按意图比价的结果渲染成终端文本。"""
    store = idx["store"]
    out = [f"🎯 按意图比价 · {store['storeCode']} {store['storeName']}",
           f"   想吃到：{' + '.join(result['intent'])}",
           f"   价格口径：{'麦金卡会员价' if allow_member else '无条件价'}", ""]

    if result["single_total"] is None:
        missing = "、".join(p["name"] for p in result["parts"] if p["price"] is None)
        out.append(f"   ⚠️ 菜单里找不到「{missing}」的单价，无法给出单点合计。")
        out.append("      （菜单只有它的套餐形态，或它属于会员价商品。）")
        return "\n".join(out)

    line = " + ".join(f"{p['menu_name']} ¥{p['price']:.1f}" for p in result["parts"])
    out.append("   单点买法")
    out.append(f"     {line} = ¥{result['single_total']:.1f}")

    if not result["best"]:
        out.append("")
        out.append("   菜单里没有能确定覆盖这个意图的组合商品。")
        return "\n".join(out)

    out.append("")
    out.append("   结构买法（本门店已有的组合，价格更低者在前）")
    for row in result["cover"][:3]:
        extra = ""
        if row["name"] != result["best"]["name"]:
            over = row["price"] - result["best"]["price"]
            extra = f"　（比 {result['best']['name']} 贵 ¥{over:.1f}）"
        out.append(f"     ¥{row['price']:>6.1f}　{row['name']}{extra}")
    out.append(f"     {'─' * 26}")
    gap = result["gap"]
    if gap is not None and gap > 0.005:
        out.append(f"   你多花了 ¥{gap:.1f}")
    else:
        out.append("   单点更便宜或持平 —— 这个意图没有「份数更多反而更便宜」的空间。")

    if result["member_cover"]:
        out.append("")
        out.append("   麦金卡会员价（这些价需要持卡）")
        for row in result["member_cover"][:2]:
            out.append(f"     ¥{row['price']:>6.1f}　{row['name']}")
        best_m = result["member_cover"][0]["price"]
        out.append(f"     ⓘ 持卡后这个意图最低 ¥{best_m:.1f}"
                   f"，比无门槛最低价再低 ¥{result['best']['price'] - best_m:.1f}。")

    out.append("")
    out.append("   ⚠️ 组合商品「确定含有」的判据是它的建模组成（identity），"
               "营养估算已标注；")
    out.append("      实际可选范围与价格以门店/App 实时结果为准。")
    return "\n".join(out)


# ------------------------------------------------------------------ 折扣扫描
def discount_scan(idx: dict, top: int = 12) -> list[dict]:
    """扫全菜单的「门店标价 − 现价」，按差额降序。

    **口径提醒**：划线价是门店标注的参考价，不等于你真省下了这个数 ——
    你本来也不会按划线价买。它与「结构省」（同一批商品换买法）不是一回事，
    两者**不可相加**。本函数只回答「门店把优惠标成了多少」。
    带 `member` 口径的条目会如实标注，不混进无门槛优惠里。
    """
    rows: list[dict] = []
    for code, it in idx["items"].items():
        if it["role"] == "nonfood":
            continue
        price = float(it["price"])
        listed = float(it.get("originalPrice") or price)
        if listed <= price + 1e-9:
            continue
        rows.append({
            "code": code, "name": it["name"], "price": price,
            "list_price": listed, "gap": round(listed - price, 2),
            "off": round(1 - price / listed, 3),
            "price_tier": it.get("priceTier", "standard"),
        })
    rows.sort(key=lambda r: (-r["gap"], r["name"]))
    return rows[:top]


# ------------------------------------------------------------------ 渲染
def render_discounts(idx: dict, rows: list[dict]) -> str:
    """把折扣扫描渲染成终端文本，逐条标出价格口径。"""
    store = idx["store"]
    out = [f"🏷️  门店标价与现价差额 · {store['storeCode']} {store['storeName']}",
           f"   快照 {store['capturedAt']} · 全菜单扫描（只列差额最大的 {len(rows)} 件）",
           ""]
    if not rows:
        out.append("   本门店没有带划线价的商品。")
        return "\n".join(out)

    tier_label = {"standard": "无条件价", "promo": "限时促销价",
                  "member": "需麦金卡"}
    for r in rows:
        tag = tier_label.get(r["price_tier"], r["price_tier"])
        out.append(f"   ¥{r['price']:>6.1f}　{r['name']}")
        out.append(f"       标价 ¥{r['list_price']:.1f} → 差额 ¥{r['gap']:.1f}"
                   f"（-{r['off']:.0%}）· {tag}")
    out.append("")
    out.append("   ⚠️ 差额是**门店标价口径**，不等于你省了这些钱 —— 你本来也不会按标价买。")
    out.append("      真正算得清的是「同一批商品换买法」的结构差，见 adviser 的方案输出。")
    return "\n".join(out)


def render(idx: dict, plans: list[Plan], args) -> str:
    """把方案渲染成终端可读的文本（含营养、备注、券标注与下单参数）。"""
    import coupon_doctor as CD

    store = idx["store"]
    member = bool(getattr(args, "member", False))
    out: list[str] = []
    out.append(f"🍟 麦麦点餐参谋 · {store['storeCode']} {store['storeName']}")
    out.append(f"   预算 ¥{args.budget:.0f} / {args.people} 人 · 模式 {args.mode}"
               + (f" · 忌口 {','.join(sorted(args.banned))}" if args.banned else ""))
    out.append(f"   价格口径：{'麦金卡会员价（含 --member）' if member else '无条件价'}")
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
            mark = ""
            if l.list_price is not None:
                mark = f"（标价 ¥{l.list_subtotal:.1f}）"
            out.append(f"  · {l.name} ×{l.qty}　¥{l.subtotal:.1f}{mark}{cp}")
        n = p.nutrition
        pp = p.people
        out.append(f"  营养/人：{n['kcal']/pp:.0f} kcal | 蛋白 {n['protein']/pp:.1f}g "
                   f"| 脂肪 {n['fat']/pp:.1f}g | 钠 {n['sodium']/pp:.0f}mg")
        if p.list_gap > 0.01:
            note_gap = "（门店标价口径，不等于你省下的钱）"
            out.append(f"  🏷️ 门店标价合计 ¥{p.list_total:.1f}"
                       f"，标称优惠 ¥{p.list_gap:.1f}{note_gap}")
        for note in p.notes:
            out.append(f"  ⓘ {note}")
        for c in p.coupons:
            src = CD.VALUE_SOURCE_LABEL.get(c["value_source"], "来源未知")
            out.append(f"  🎟️ 本单可用：{c['title']}　再省 ¥{c['face_value']:.1f}（{src}）")
        out.append("  下单参数：" + json.dumps([{"productCode": l.code, "quantity": l.qty}
                                            for l in p.lines], ensure_ascii=False))
    out.append("─" * 46)
    if not member:
        excluded = len(member_items(idx))
        if excluded:
            out.append(f"ⓘ 已排除 {excluded} 件需麦金卡会员价的商品"
                       "（用 --member 按会员价纳入）。")
    out.append("⚠️ 价格为门店实时快照口径，最终以 calculate-price 结果为准；"
               "券需门店核验。")
    return "\n".join(out)


def main() -> int:
    """命令行入口：解析参数 → 求解 → 渲染或输出 JSON。"""
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
    ap.add_argument("--coupons", action="store_true",
                    help="读取仓库内置券快照，在方案上标注本单可用的券")
    ap.add_argument("--member", action="store_true",
                    help="按麦金卡会员价计入（默认只用无条件价；促销价始终计入）")
    ap.add_argument("--discounts", action="store_true",
                    help="不求解，改为扫描全菜单的门店标价与现价差额")
    ap.add_argument("--intent", default=None,
                    help="按意图比价，如 --intent \"巨无霸+薯条+可乐\"")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args()

    args.banned = {k for k in TAG_RULES if getattr(args, f"no_{k}")}

    idx = load_index()

    if args.intent:
        result = compare_intent(idx, parse_intent(args.intent), args.member)
        if args.json:
            print(json.dumps({"store": idx["store"], "compare": result},
                             ensure_ascii=False, indent=2))
        else:
            print(render_intent(idx, result, args.member))
        return 0

    if args.discounts:
        rows = discount_scan(idx, top=args.top if args.top > 3 else 12)
        if args.json:
            print(json.dumps({"store": idx["store"], "discounts": rows},
                             ensure_ascii=False, indent=2))
        else:
            print(render_discounts(idx, rows))
        return 0

    pool = build_pool(idx, args.banned, allow_member=args.member)
    plans = solve(idx, pool, args.budget, args.people, args.mode, args.top,
                  args.max_kcal, args.min_protein)

    if args.coupons:
        import coupon_doctor as CD
        coupons, _ = CD.load_coupons()
        menu_by_name = {it["name"]: it for it in idx["items"].values()}
        CD.attach_values(coupons, CD.load_probes(), menu_by_name)
        for p in plans:
            p.coupons = coupons_for_plan(p, idx, coupons)

    if args.json:
        print(json.dumps({
            "store": idx["store"],
            "query": {"budget": args.budget, "people": args.people, "mode": args.mode,
                      "banned": sorted(args.banned), "member": args.member},
            "plans": [p.to_dict() for p in plans],
        }, ensure_ascii=False, indent=2))
    else:
        print(render(idx, plans, args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
