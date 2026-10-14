#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py —— 把 MCP 原始快照归一化成引擎可直接消费的索引。

输入（data/raw/）：
  - meals_<storeCode>.json   来自 mcd-mcp `query-meals` 的原始返回
  - nutrition.txt            来自 mcd-mcp `list-nutrition-foods` 的原始返回

输出（data/）：
  - index.json   { store, capturedAt, items{}, categories[], nutrition{}, stats{} }

设计要点
--------
1. 名称对齐：菜单名与营养库名并不一一对应（菜单叫「薯条」，营养库按「中薯条/大薯条/小薯条」分）。
   因此需要显式别名表 + 后缀剥离规则，绝不做静默模糊匹配。
2. 套餐营养：三件套/四件套/随心选等在营养库里没有对应行，这里按「主体 + 薯条 + 饮品」建模推算，
   并把 confidence 标记为 "estimated"，绝不冒充实测值。
3. 角色分类：把商品归入 staple/side/drink/dessert/nonfood，供组合求解器分桶。
4. 门店选择：data/raw/ 下有多份 `meals_*.json` 时**不猜**，直接报错列出候选，
   要用哪家就用 `--store <storeCode>` 明说。理由见 `pick_meals_file()` 的说明。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "index.json"

# ---------------------------------------------------------------- 名称别名表
# 菜单名 -> 营养库名（仅收录确实无法靠规则推出的差异项）
ALIAS: dict[str, str] = {
    "薯条": "中薯条",
    "可乐": "可乐中杯",
    "雪碧": "雪碧中杯",
    "麦乐鸡": "麦乐鸡5块",
    "麦辣鸡翅": "麦辣鸡翅-2块",
    "新地": "朱古力新地",
    "派": "香芋派",
    "经典麦旋风": "奥利奥麦旋风",
    "玉米杯": "大杯玉米杯",
    "纯牛奶(盒装)": "纯牛奶（盒装）",
    "100% 苹果汁(盒装)": "100%苹果汁",
    "阳光橙麦炫酷": "麦旋酷阳光橙",
    "麦咖啡™美式": "热美式中杯",
    "麦咖啡™奶铁": "热奶铁中杯",
    "麦咖啡冰爽一夏": "特浓奶香雪冰中杯",
    "鲜萃咖啡": "小杯鲜萃咖啡",
    "阳光柠檬红茶": "阳光柠檬红茶中杯",
    "燕麦奶": "热燕麦奶中杯",
    "卡布奇诺": "卡布奇诺中杯",
    "怡泉+C": "中杯怡泉+C",
    "学生专享饮品随心选": "中杯怡泉+C",
    "那么大鸡排（椒盐风味）": "那么大鸡排",
    "麦麦脆汁鸡1块": "麦麦脆汁鸡-带骨里脊",
    "鱼排堡开心乐园餐": "儿童鱼排堡",
    "姜汁撞奶风味派": "香芋派",
    "牛奶": "纯牛奶（盒装）",
    "蘸酱麦麦脆汁鸡": "麦麦脆汁鸡-琵琶腿",
    "蘸酱炸鸡": "麦麦脆汁鸡-琵琶腿",
    "蘸酱脆皮鸡柳": "麦麦脆汁鸡-带骨里脊",
    "龙焰鸡腿堡": "麦辣鸡腿汉堡",
    "龙焰芝士棒鸡腿堡": "麦辣鸡腿汉堡",
    "“我就喜欢”鸡薯双全盒": "麦乐鸡5块",
    "鸡肉堡单品精选": "麦香鸡",
    "牛肉堡单品精选": "巨无霸",
}

# 套餐结构建模：后缀 -> 额外包含的组件
SET_SUFFIXES: list[str] = ["三件套", "四件套", "套餐", "随心选"]
SIDE_PLUS = {"中薯条": 1}
DRINK_PLUS = {"可乐中杯": 1}
FOURTH_PLUS = {"麦乐鸡5块": 1, "中薯条": 1, "可乐中杯": 1}
THREE_PLUS = {"中薯条": 1, "可乐中杯": 1}

# 某些套餐主体名在营养库里没有，退化为代表单品
BUNDLE_BASE_FALLBACK: dict[str, str] = {
    "大堡口福": "巨无霸",
    "精选单人餐": "巨无霸",
    "“辣”么快乐": "麦辣鸡腿汉堡",
    "辣么快乐": "麦辣鸡腿汉堡",
    "酥脆无双": "麦香鸡",
    "牛气满满": "牛气满满",
    "BFF四宫格小食盘": "麦乐鸡5块",
    "蘸酱BFF四宫格小食盘": "麦乐鸡5块",
    "BFF四宫格小食盘双人餐": "麦乐鸡5块",
    "堡堡随心拼（7件任选）": "巨无霸",
    "人气经典随心配": "双层吉士汉堡",
    "精选超值随心配": "麦香鸡",
    "学生专享汉堡小食随心选": "麦香鸡",
    "麦辣鸡翅4块套餐": "麦辣鸡翅-2块",
    "巨无霸四件套": "巨无霸",
    "人气超值四件套随心选": "巨无霸",
    "堡堡随心拼": "巨无霸",
    "薄皮V翅双拼十翅": "薄皮焦香V翅",
    "心形薯饼5块": "脆薯饼",
    "鱼牛汉堡四件套": "双层深海鳕鱼堡",
    "安格斯厚牛堡四件套": "芝士安格斯厚牛堡",
    "龙焰美味四件套": "麦辣鸡腿汉堡",
    "龙焰芝士棒鸡腿堡四件套": "麦辣鸡腿汉堡",
    "龙焰鸡腿堡四件套": "麦辣鸡腿汉堡",
    "高达吉士双牛堡": "双层吉士汉堡",
    "灰焰圆筒": "圆筒冰淇淋",
    "奶香大米派": "香芋派",
    "燕麦奶铁": "热奶铁中杯",
    "蓝莓爆爆珠麦旋风": "奥利奥麦旋风",
    "椰奶雪冰": "浓浓抹茶雪冰中杯",
    "马苏里拉拉丝芝士条": "脆薯饼",
}

# 「随心配 / 鸡薯盒」类商品内容自选，营养库无对应行。
# 这里按一类典型搭配补上配件，让估算不至于明显偏低，并在输出中明确标注为估算。
EXTRA_COMPONENTS: dict[str, dict[str, int]] = {
    "人气经典随心配": {"中薯条": 1},
    "精选超值随心配": {"中薯条": 1},
    "学生专享汉堡小食随心选": {"中薯条": 1},
    "“我就喜欢”鸡薯双全盒": {"中薯条": 1},
    "BFF四宫格小食盘": {"中薯条": 1},
    "蘸酱BFF四宫格小食盘": {"中薯条": 1},
    "BFF四宫格小食盘双人餐": {"中薯条": 1},
    "堡堡随心拼": {"中薯条": 1, "可乐中杯": 1},
    "薄皮V翅双拼十翅": {"薄皮焦香V翅": 1},
    "心形薯饼5块": {"脆薯饼": 2},
}

# ---------------------------------------------------------------- 角色分类
# 顺序即优先级。先判主食（含"堡/卷/套餐"字样），再判饮品，最后小食。
# "学生专享饮品随心选"这类名字同时含"饮品"和"随心选"，靠优先级才不会误判为主食。
ROLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("nonfood", ("帽", "捶", "挠", "百宝袋", "棒球", "牧场酱", "风味酱")),
    ("staple", ("汉堡", "堡", "卷", "三件套", "四件套", "套餐", "随心配",
                "单人餐", "麦满分", "乐园餐", "鱼排", "粥", "香肠卷")),
    ("drink", ("可乐", "雪碧", "咖啡", "奶铁", "牛奶", "豆浆", "红茶", "果汁", "怡泉",
               "柠", "橙橙", "雪冰", "阿芙佳朵", "玛奇朵", "卡布奇诺", "鲜萃", "纯悦",
               "燕麦奶", "抹茶牛奶", "浓浓黑巧", "燕麦黑巧", "饮品")),
    ("dessert", ("冰淇淋", "新地", "麦旋风", "派", "圆筒", "拉明顿", "麦炫酷", "yeyeyeye")),
    ("side", ("薯条", "薯饼", "鸡翅", "麦乐鸡", "鸡排", "鸡块", "芝士条", "小食", "拼盘",
              "玉米杯", "油条", "苹果片", "鸡球", "V翅", "脆汁鸡", "鸡柳", "香肠",
              "多笋卷", "蘸酱", "辣么")),
]


def classify(name: str) -> str:
    """按商品名判定角色：staple / side / drink / dessert / nonfood。"""
    for role, keys in ROLE_RULES:
        if any(k in name for k in keys):
            return role
    return "staple"


# ---------------------------------------------------------------- 营养库解析
def load_nutrition() -> dict[str, dict]:
    """解析营养库 CSV（首行是列定义），返回 名称 -> 营养 的映射。"""
    path = RAW / "nutrition.txt"
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    table: dict[str, dict] = {}
    for line in lines[1:]:  # 第一行是列定义
        parts = line.split(",")
        if len(parts) < 9:
            continue
        name = parts[0].strip()
        try:
            table[name] = {
                "kcal": int(parts[3]),
                "protein": float(parts[4]),
                "fat": float(parts[5]),
                "carb": float(parts[6]),
                "sodium": int(parts[7]),
                "calcium": int(parts[8]),
            }
        except (ValueError, IndexError):
            continue
    return table


def add_nutrition(a: dict, b: dict, times: int = 1) -> dict:
    """把 b 的营养按倍数加到 a 上，返回新字典（不改原对象）。"""
    out = dict(a)
    for k in ("kcal", "protein", "fat", "carb", "sodium", "calcium"):
        out[k] = round(out.get(k, 0) + b.get(k, 0) * times, 2)
    return out


ZERO = {"kcal": 0, "protein": 0, "fat": 0, "carb": 0, "sodium": 0, "calcium": 0}


def resolve_bundle(name: str, table: dict[str, dict]) -> dict | None:
    """把套餐名拆成 主体 + 固定配件，推算营养。返回 None 表示无法建模。"""
    base = name
    suffix = next((s for s in SET_SUFFIXES if name.endswith(s)), None)
    if suffix:
        base = name[: -len(suffix)]
    base = base.replace("（7件任选）", "").strip()

    key = ALIAS.get(base, base)
    if key not in table:
        key = BUNDLE_BASE_FALLBACK.get(base) or BUNDLE_BASE_FALLBACK.get(name)
    if key is None or key not in table:
        return None

    total = dict(table[key])
    comps = [key]
    plus = FOURTH_PLUS if suffix == "四件套" else THREE_PLUS if suffix else {}
    for comp, qty in plus.items():
        if comp in table:
            total = add_nutrition(total, table[comp], qty)
            comps.append(f"{comp}x{qty}")
    return {"nutri": total, "components": comps, "confidence": "estimated"}


# ---------------------------------------------------------------- 门店选择
def pick_meals_file(store: str | None) -> Path:
    """选出这次要用的菜单快照；多份并存时**拒绝猜测**。

    这里曾经是 `sorted(...)[0]` —— 从 data/raw/ 里多放一家门店的快照开始，
    索引就会**静默**换成那一家，而券快照、README 里的数字、demo 的断言
    都还停在原来的门店，错配无人察觉（实测发生过：覆盖门店后
    `test_nutrition_coverage` 才把它挡住）。

    所以改成分两种情况：`--store` 指定就按它找；没指定而候选多于一份就报错。
    """
    files = sorted(RAW.glob("meals_*.json"))
    if not files:
        raise SystemExit("缺少 data/raw/meals_<storeCode>.json")

    if store:
        hit = [p for p in files if p.stem == f"meals_{store}"]
        if not hit:
            names = "、".join(p.name for p in files)
            raise SystemExit(f"找不到 meals_{store}.json；现有：{names}")
        return hit[0]

    if len(files) > 1:
        names = "\n".join(f"  · {p.name}" for p in files)
        raise SystemExit(
            f"data/raw/ 下有 {len(files)} 份菜单快照，无法确定该用哪一份：\n{names}\n"
            f"请移走多余的，或用 --store <storeCode> 指定。"
        )
    return files[0]


# ---------------------------------------------------------------- 主流程
def main() -> None:
    """读取原始快照，生成 data/index.json 并打印覆盖率统计。"""
    ap = argparse.ArgumentParser(description="把 MCP 原始快照归一化成索引")
    ap.add_argument("--store", default=None,
                    help="门店编码；data/raw/ 下有多个 meals_*.json 时必填")
    args = ap.parse_args()

    table = load_nutrition()
    meals_file = pick_meals_file(args.store)
    raw = json.loads(meals_file.read_text(encoding="utf-8"))

    items: dict[str, dict] = {}
    nutrition: dict[str, dict] = {}
    unmatched: list[str] = []

    for code, m in raw["meals"].items():
        name = m["name"]
        role = classify(name)
        price = float(m.get("currentPrice") or 0)
        orig = float(m.get("originalPrice") or price)

        entry = {
            "code": code,
            "name": name,
            "role": role,
            "price": price,
            "originalPrice": orig,
            "discountType": m.get("discountType"),
            "canWithOrder": bool(m.get("canWithOrder")),
            "withOrder": m.get("withOrder"),
            "image": m.get("image", ""),
        }

        # 营养：先直查，再别名，最后按「套餐主体拆分 / 兜底代表单品」建模
        nutri = None
        if name in table:
            nutri = {"nutri": dict(table[name]), "components": [name],
                     "confidence": "exact"}
        else:
            alias = ALIAS.get(name)
            if alias and alias in table:
                nutri = {"nutri": dict(table[alias]), "components": [alias],
                         "confidence": "alias"}

        if nutri is None:
            nutri = resolve_bundle(name, table)

        # 内容自选类商品：补上典型配件
        if name in EXTRA_COMPONENTS and nutri is not None:
            for comp, qty in EXTRA_COMPONENTS[name].items():
                if comp in table:
                    nutri["nutri"] = add_nutrition(nutri["nutri"], table[comp], qty)
                    nutri["components"].append(f"{comp}x{qty}")
            if nutri["confidence"] == "exact":
                nutri["confidence"] = "estimated"

        if nutri is None and role != "nonfood":
            unmatched.append(f"{code} {name}")

        if nutri:
            nutrition[code] = {
                **nutri["nutri"],
                "confidence": nutri["confidence"],
                "components": nutri["components"],
            }
            entry["hasNutrition"] = True
        else:
            entry["hasNutrition"] = False

        items[code] = entry

    categories = [
        {"name": c["name"], "codes": [x["code"] for x in c["meals"]]}
        for c in raw.get("categories", [])
    ]

    index = {
        "store": raw["_meta"],
        "mealCount": len(items),
        "nutritionCoverage": round(len(nutrition) / max(len(items), 1), 3),
        "categories": categories,
        "items": items,
        "nutrition": nutrition,
        "unmatched": unmatched,
    }
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    by_role: dict[str, int] = {}
    for it in items.values():
        by_role[it["role"]] = by_role.get(it["role"], 0) + 1
    print(f"✅ 索引已生成：{OUT}")
    print(f"   商品 {len(items)} 个 | 营养覆盖 {len(nutrition)} 个 "
          f"({index['nutritionCoverage']:.0%})")
    print(f"   角色分布 {by_role}")
    if unmatched:
        print(f"   ⚠️ 无营养数据 {len(unmatched)} 个：{', '.join(unmatched[:12])}"
              + (" ..." if len(unmatched) > 12 else ""))


if __name__ == "__main__":
    main()
