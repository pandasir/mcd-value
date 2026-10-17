#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_demo.py —— 为网页 Demo 生成精简数据（docs/demo-data.json）

为什么不直接把 data/index.json 丢给前端：
  1. 前端只需要展示字段，index.json 里还有门店元信息、营养覆盖率等无关内容；
  2. **比价口径只能有一份**。这里直接调用 `adviser.compare_intent()` 和
     `demo.scene_bundle_gap()`——终端演示用的就是这两个函数，网页端不重算。
     这个项目最贵的资产是"数字可信"，不能让 JS 再实现一遍求解逻辑。

所以：Python 算，JS 只切场景、渲染。

用法：
  python scripts/build_demo.py            # 写 docs/demo-data.json
  python scripts/build_demo.py --check    # 只校验关键数字，不写文件
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import adviser as A  # noqa: E402
import demo as D  # noqa: E402

INDEX = ROOT / "data" / "index.json"
OUT = ROOT / "docs" / "demo-data.json"

# 场景固定为「一个汉堡 + 中薯条 + 可乐中杯」——这是绝大多数人的真实点法
SIDE = "中薯条"
DRINK = "可乐中杯"
MAX_SCENES = 8
HERO_STAPLE = "巨无霸"


def load_idx(path: Path = INDEX) -> dict:
    """读菜单索引（默认仓库内置的那份快照）。"""
    return json.loads(path.read_text(encoding="utf-8"))


def identity_of(idx: dict, code: str) -> list[str]:
    """取这个商品「确定含有」的组件名（可能为空，表示不知道）。"""
    return list((idx["nutrition"].get(code) or {}).get("identity") or [])


def staple_singles(idx: dict) -> list[dict]:
    """主食类真单品（identity 只有自己），排除会员价。"""
    out = []
    for it in idx["items"].values():
        if it["role"] != "staple" or it.get("priceTier") == "member":
            continue
        ident = identity_of(idx, it["code"])
        if len(ident) != 1:
            continue
        out.append(
            {
                "code": it["code"],
                "name": it["name"],
                "identity": ident[0],
                "price": float(it["price"]),
                "image": it.get("image") or "",
            }
        )
    out.sort(key=lambda x: (x["name"] != HERO_STAPLE, x["price"]))
    return out


def build(idx: dict, max_scenes: int | None = MAX_SCENES) -> dict:
    """把菜单索引压成网页 Demo 需要的数据（场景、统计、门店元信息）。

    `max_scenes=None` 保留全部场景：网页首屏只需要前几个，
    但静态预渲染（build_pages.py）要用全部场景铺长尾关键词。
    """
    # ---- 全菜单扫描：复用终端演示的口径 ----
    rows = D.scene_bundle_gap(idx)
    scan = {
        "comparable": len(rows),
        "cheaper": sum(1 for r in rows if r["gap"] > 0),
        "totalSave": round(sum(r["gap"] for r in rows if r["gap"] > 0), 1),
    }

    # ---- 逐个主食算「两种买法」 ----
    # 只保留「能被肉眼验证」的场景：套餐名里必须真的含这个汉堡的名字。
    # 起因是数据里存在代餐把身份算错的情况（龙焰鸡腿堡借用麦辣鸡腿汉堡的营养行），
    # 单看 identity 分不出来，但看名字一眼就能分出来。页面上的每一条判断
    # 都要经得起读者对照菜单名核对。
    scenes = []
    for s in staple_singles(idx):
        if not s["identity"]:
            continue
        want = [s["identity"], SIDE, DRINK]
        r = A.compare_intent(idx, want)
        if r["single_total"] is None:
            continue
        best = r["best"]
        if not best or s["name"] not in best["name"]:
            continue
        bundle_ident = identity_of(idx, best["code"])
        if len(bundle_ident) < 3:  # 身份缺件的套餐不参与比价
            continue
        member = r["member_cover"][0] if r["member_cover"] else None
        scenes.append(
            {
                "staple": s,
                "want": want,
                "parts": [
                    {"name": p["menu_name"] or p["name"], "price": float(p["price"])}
                    for p in r["parts"]
                ],
                "singleTotal": float(r["single_total"]),
                "bundle": (
                    {
                        "name": best["name"],
                        "price": float(best["price"]),
                        "image": best.get("image") or "",
                    }
                    if best
                    else None
                ),
                "gap": float(r["gap"]) if r["gap"] is not None else None,
                "member": (
                    {"name": member["name"], "price": float(member["price"])}
                    if member and best is None
                    else None
                ),
            }
        )
    # 首屏默认巨无霸，其余按差价从大到小
    scenes.sort(key=lambda x: (x["staple"]["name"] != HERO_STAPLE, -(x["gap"] or 0)))

    # 页面只报「已验证场景」内部的统计，不引用全菜单扫描的合计数：
    # 那份扫描目前混着身份算错的行（见文件头注释与 README），改数据前不对外引用。
    gaps = {s["gap"] for s in scenes}
    stats = {
        "verified": len(scenes),
        "uniformGap": round(next(iter(gaps)), 1) if len(gaps) == 1 else None,
    }
    if max_scenes is not None:
        scenes = scenes[:max_scenes]

    return {
        "store": idx["store"],
        "side": SIDE,
        "drink": DRINK,
        "scenes": scenes,
        "stats": stats,
    }


def main(argv: list[str]) -> int:
    """命令行入口：默认写文件，`--check` 只校验关键数字。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验关键数字")
    args = ap.parse_args(argv)

    data = build(load_idx())
    st = data["stats"]
    print(f"已验证场景 {st['verified']} 个，统一差价 {st['uniformGap']}")
    for s in data["scenes"][:3]:
        b = s["bundle"]
        print(
            f"  {s['staple']['name']}：单点 ¥{s['singleTotal']}"
            f" vs {'套餐 ¥%.1f（%s）' % (b['price'], b['name']) if b else '无套餐'}"
            f" → 差 {'¥%.1f' % s['gap'] if s['gap'] is not None else '—'}"
        )
    print(f"场景 {len(data['scenes'])} 个")

    if args.check:
        hero = next((s for s in data["scenes"] if s["staple"]["name"] == "巨无霸"), None)
        ok = (
            hero is not None
            and hero["singleTotal"] == 48.5
            and hero["bundle"] is not None
            and hero["bundle"]["price"] == 36.5
            and hero["gap"] == 12.0
            and st["verified"] >= 8
            and st["uniformGap"] == 12.0
        )
        print("CHECK", "OK" if ok else "FAIL")
        return 0 if ok else 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
