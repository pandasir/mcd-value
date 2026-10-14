#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coupon_doctor.py —— 券的体检与排程

券不是"可用资源"，是**有保质期的钱**。本模块回答三个问题：

1. 这张券到底值多少钱？——实测优先（`calculate-price` 的 discount），
   其次从菜单反查原价；两条路都走不通就说"价值未知"，**绝不估一个看起来合理的数**。
2. 在我这个消费水平下，哪几张券其实不该用？——券包体检。
3. 券过期之前我只来得及点几单？用不上的部分就是注定要浪费的钱——用券排程。

三条写死的假设（写在文档里，不藏在代码里）：
  A. 基准消费 = 求解器给出的这一单方案总价（你本来就要花的钱）。
  B. 券全部过期前的窗口内，你还会点 K 单，每单最多用 1 张券。
  C. 用券不改变你的点单次数。

单位：`calculate-price` 返回**分**，`query-meals` 是**元**。
这个换算**只在本模块发生一次**，算法层只接触元。
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
COUPONS = RAW / "coupons_1420762.json"
PROBES = RAW / "coupon_probe_1420762.json"

# 券名 -> 菜单商品名的显式对齐表（券附带的商品名与菜单名并不一一对应）。
# 只收录**能确定**的对应关系；不确定的一律不写，让其落到"价值未知"。
# 绝不做静默模糊匹配 —— 匹配错了会把真实存在的价值报成 0，或报成一个错的数。
NAME_ALIGN: dict[str, str] = {
    "中薯条买一送一": "薯条",
    "人气麦旋风买一送一": "经典麦旋风",
    "9.9元中杯冰美式": "麦咖啡™美式",
    "13.9浓浓黑巧": "浓浓黑巧（冰/热）",
}

RE_FIXED = re.compile(r"^(\d+(?:\.\d+)?)\s*元?(?!\+)")
RE_MONEY_OFF = re.compile(r"满\s*(\d+(?:\.\d+)?)\s*减\s*(\d+(?:\.\d+)?)")

# 券的四种判定
HANDY = "顺手可用"
STRETCH = "努一把"
PAPER = "纸面富贵"
UNKNOWN = "无法判断"
VERDICT_ORDER = {HANDY: 0, STRETCH: 1, PAPER: 2, UNKNOWN: 3}

# 价值来源 → 面向用户的中文口径（对外展示统一走这里，不暴露内部术语）
VALUE_SOURCE_LABEL = {"probe": "实测", "reverse": "菜单反查", "unknown": "拿不到"}


@dataclass
class Coupon:
    """一张券。缺字段即"未知"，不补默认值。"""

    title: str
    status: str                       # claimed | claimable
    kind: str                         # bogo | free | fixed_price | money_off | unknown
    coupon_id: str | None = None
    coupon_code: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    price_with: float | None = None   # 用券实付（元）
    start_at: str | None = None
    end_at: str | None = None
    fixed_price: float | None = None  # 固定价券的固定价
    threshold: float | None = None    # 满减券的门槛
    face_value: float | None = None   # 券面价值（元）；None = 价值未知
    value_source: str = "unknown"     # probe | reverse | unknown
    net_value: float | None = None    # 体检后的净价值（元）
    verdict: str = UNKNOWN

    def to_dict(self) -> dict:
        """转成可 JSON 序列化的字典。"""
        return asdict(self)


# ------------------------------------------------------------------ 解析
def classify_form(title: str) -> str:
    """按券名判定券的形态。纯规则匹配，不联网、不猜。"""
    if "买一送一" in title:
        return "bogo"
    if "免费" in title:
        return "free"
    if RE_MONEY_OFF.search(title):
        return "money_off"
    if RE_FIXED.match(title):
        return "fixed_price"
    return "unknown"


def parse_dt(text: str | None) -> datetime | None:
    """解析 'YYYY-MM-DD HH:MM[:SS]' 或 'YYYY-MM-DD'；失败返回 None。"""
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def days_left(end_at: str | None, now: datetime) -> int | None:
    """距过期还有几天（向上取整）；无有效期返回 None。

    无有效期时**返回 None 而不是 0** —— 把"未知"说成"还剩 0 天"就是编造。
    """
    end = parse_dt(end_at)
    if end is None:
        return None
    return max(0, math.ceil((end - now).total_seconds() / 86400))


def load_coupons(path: Path | None = None) -> tuple[list[Coupon], dict]:
    """读取券快照，返回 (券列表, _meta)。"""
    raw = json.loads((path or COUPONS).read_text(encoding="utf-8"))
    coupons: list[Coupon] = []
    for c in raw["coupons"]:
        title = c["title"]
        fixed = RE_FIXED.match(title)
        money = RE_MONEY_OFF.search(title)
        coupons.append(Coupon(
            title=title,
            status=c.get("status", "unknown"),
            kind=classify_form(title),
            coupon_id=c.get("couponId"),
            coupon_code=c.get("couponCode"),
            product_code=c.get("productCode"),
            product_name=c.get("productName"),
            price_with=c.get("priceWith"),
            start_at=c.get("startAt"),
            end_at=c.get("endAt"),
            fixed_price=float(fixed.group(1)) if fixed else None,
            threshold=float(money.group(1)) if money else None,
        ))
    return coupons, raw.get("_meta", {})


def load_probes(path: Path | None = None) -> dict[str, dict]:
    """读取券价值实测缓存，按 couponId 建索引。文件不存在时返回空表。"""
    path = path or PROBES
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {p["couponId"]: p for p in raw.get("probes", [])}


# ------------------------------------------------------------------ 订单
ORDERS = RAW / "orders_1420762.json"                  # 本地完整脱敏快照（不入库）
ORDER_SUMMARY = RAW / "orders_summary_1420762.json"   # 只含派生指标（入库）


def sanitize_orders(raw: dict) -> dict:
    """把 `order-list` 的原始返回洗成**可以本地留存**的脱敏快照。

    去掉 orderId（账号）、storeCode / storeName / beCode（定位）、下单时刻的时分秒
    （行为时段）；只保留日期、取餐方式、状态、金额与商品名。
    """
    block = raw.get("data", raw)
    orders = []
    for o in block.get("list", []):
        orders.append({
            "date": (o.get("createTime") or "")[:10],
            "beType": o.get("beType"),
            "status": o.get("orderStatus"),
            "total": float(o.get("realTotalAmount") or 0),
            "items": [{"productCode": p.get("productCode"),
                       "name": p.get("productName"),
                       "quantity": p.get("quantity", 1)}
                      for p in o.get("orderProductList", [])],
        })
    return {"capturedAt": block.get("datetime") or raw.get("datetime"),
            "orders": orders}


def derive_orders(snapshot: dict) -> dict:
    """从脱敏快照派生审计指标。

    只统计「订单已完成」——已取消的单不代表真实消费。
    金额为 0 的单计入点单频率（它确实是一笔点单），但不计入客单价（它没花钱）。
    """
    done = [o for o in snapshot.get("orders", [])
            if o.get("status") == "订单已完成"]
    if not done:
        return {}

    dates = sorted(o["date"] for o in done if o.get("date"))
    anchor = parse_dt(snapshot.get("capturedAt")) or datetime.now()
    span_days = max(1, (anchor - datetime.strptime(dates[0], "%Y-%m-%d")).days)
    paid = [o["total"] for o in done if o.get("total")]

    counts: dict[str, int] = {}
    for o in done:
        for it in o.get("items", []):
            name = it.get("name")
            if name:
                counts[name] = counts.get(name, 0) + 1

    return {
        "n_orders": len(done),
        "n_paid": len(paid),
        "first_date": dates[0],
        "last_date": dates[-1],
        "span_days": span_days,
        "avg_ticket": round(sum(paid) / len(paid), 2) if paid else None,
        "total_spend": round(sum(paid), 2),
        "orders_per_week": round(len(done) / (span_days / 7), 4),
        "top_items": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
    }


def order_summary(snapshot: dict) -> dict:
    """把脱敏快照压成**可以提交**的摘要：只有派生指标，没有逐单明细。"""
    derived = derive_orders(snapshot)
    # 可提交的摘要不带逐单日期、不带商品名 —— 只留「花了多少、多久点一次」。
    keep = ("n_orders", "n_paid", "span_days", "avg_ticket",
            "total_spend", "orders_per_week")
    return {
        "capturedAt": snapshot.get("capturedAt"),
        "source": "order-list（麦当劳 MCP）",
        "note": "只保留派生指标；逐单明细、商品名与下单日期均不在仓库内。",
        "summary": {k: derived[k] for k in keep if k in derived},
    }


def load_orders(path: Path | None = None) -> dict:
    """读订单数据并返回审计指标。没有数据时返回空 dict —— 不猜。

    优先读**派生摘要**（`orders_summary_*.json`，随仓库提交）；
    没有就退回到**本地脱敏快照**（`orders_*.json`，需自己采集）并现场派生。
    """
    if path is None:
        path = ORDER_SUMMARY if ORDER_SUMMARY.exists() else ORDERS
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("summary"):          # 摘要格式：已是派生结果，直接用
        return dict(raw["summary"])
    return derive_orders(raw)


# ------------------------------------------------------------------ 价值
def reverse_value(c: Coupon, menu_by_name: dict[str, dict]) -> float | None:
    """兜底：从菜单反查这张券值多少钱。拿不到返回 None —— 不猜。"""
    if c.kind == "money_off":
        return None
    target = NAME_ALIGN.get(c.title)
    if target is None:
        return None
    item = menu_by_name.get(target)
    if item is None:
        return None
    price = float(item["price"])
    if c.kind in ("bogo", "free"):
        return round(price, 2)
    if c.kind == "fixed_price" and c.fixed_price is not None:
        return round(max(0.0, price - c.fixed_price), 2)
    return None


def attach_values(coupons: list[Coupon], probes: dict[str, dict],
                  menu_by_name: dict[str, dict]) -> None:
    """为每张券补齐 face_value / value_source。就地修改，不做返回值。"""
    for c in coupons:
        if c.kind == "money_off":
            money = RE_MONEY_OFF.search(c.title)
            if money:
                c.face_value = float(money.group(2))
                c.value_source = "reverse"
                continue

        probe = probes.get(c.coupon_id) if c.coupon_id else None
        if probe:
            c.face_value = round(probe["discountCents"] / 100, 2)
            c.price_with = round(probe["priceCents"] / 100, 2)
            c.product_name = probe.get("productName") or c.product_name
            c.value_source = "probe"
            continue

        value = reverse_value(c, menu_by_name)
        if value is None:
            c.face_value = None
            c.value_source = "unknown"
        else:
            c.face_value = value
            c.value_source = "reverse"


# ------------------------------------------------------------------ 体检
def cost_to_use(c: Coupon) -> float | None:
    """为了用这张券，你需要花出去的钱（元）。拿不到返回 None。"""
    if c.kind == "money_off" and c.threshold is not None:
        return c.threshold
    if c.price_with is not None:
        return c.price_with
    return None


def wallet_checkup(coupons: list[Coupon], baseline: float,
                   now: datetime) -> dict:
    """券包体检：在 baseline 这个消费水平下，逐张判定该不该用。

    净价值 = 券面价值 − 为用这张券、你本来不会花的那部分钱。
    """
    rows = []
    for c in coupons:
        if c.status != "claimed":
            continue
        cost = cost_to_use(c)
        if c.face_value is None or cost is None:
            c.verdict, c.net_value = UNKNOWN, None
        else:
            gap = max(0.0, cost - baseline)
            c.net_value = round(c.face_value - gap, 2)
            if gap <= 1e-9:
                c.verdict = HANDY
            elif c.net_value > 0:
                c.verdict = STRETCH
            else:
                c.verdict = PAPER
        rows.append({
            "title": c.title,
            "kind": c.kind,
            "face_value": c.face_value,
            "value_source": c.value_source,
            "cost_to_use": cost,
            "net_value": c.net_value,
            "verdict": c.verdict,
            "days_left": days_left(c.end_at, now),
        })

    rows.sort(key=lambda r: (VERDICT_ORDER[r["verdict"]], -(r["net_value"] or 0)))
    return {
        "baseline": round(baseline, 2),
        "rows": rows,
        "named_total": round(sum(r["face_value"] for r in rows
                                 if r["face_value"] is not None), 2),
        "realizable": round(sum(r["net_value"] for r in rows
                                if r["net_value"] is not None
                                and r["net_value"] > 0), 2),
        "unusable": round(sum(r["net_value"] for r in rows
                              if r["net_value"] is not None
                              and r["net_value"] <= 0), 2),
        "counts": {k: sum(1 for r in rows if r["verdict"] == k)
                   for k in VERDICT_ORDER},
    }


# ------------------------------------------------------------------ 排程
def orders_in_window(window: int, orders_per_week: float) -> int:
    """窗口内大概还会点几单。至少 1 单（否则排程没有意义）。"""
    return max(1, int(window * orders_per_week / 7))


def usable_coupons(coupons: list[Coupon]) -> list[Coupon]:
    """能进排程的券：手里已领、有正净价值、且有效期已知。"""
    return [c for c in coupons
            if c.status == "claimed" and c.end_at is not None
            and c.net_value is not None and c.net_value > 0]


def window_days(coupons: list[Coupon], now: datetime) -> int:
    """券全部过期前的窗口天数。"""
    usable = usable_coupons(coupons)
    if not usable:
        return 0
    return max((days_left(c.end_at, now) or 0) for c in usable)


def schedule(coupons: list[Coupon], orders_per_week: float, now: datetime) -> dict:
    """用券排程：券过期前你只来得及点 K 单，用不上的就是注定浪费的钱。

    可领取的券没有有效期，不参与窗口计算 —— 把"未知"当成"永久"就是编造。
    """
    window = window_days(coupons, now)
    slots = orders_in_window(window, orders_per_week)
    usable = sorted(usable_coupons(coupons),
                    key=lambda c: c.net_value or 0, reverse=True)
    assigned, dropped = usable[:slots], usable[slots:]

    def row(c: Coupon) -> dict:
        """把一张券压成排程输出用的最小字典。"""
        return {"title": c.title, "net_value": c.net_value,
                "days_left": days_left(c.end_at, now)}

    return {
        "window_days": window,
        "orders_per_week": orders_per_week,
        "orders_in_window": slots,
        "assigned": [row(c) for c in assigned],
        "dropped": [row(c) for c in dropped],
        "assigned_total": round(sum(c.net_value or 0 for c in assigned), 2),
        "wasted_total": round(sum(c.net_value or 0 for c in dropped), 2),
    }


def claimable(coupons: list[Coupon]) -> list[Coupon]:
    """还没领的券。未领取的券是唯一一种零成本的省钱来源。"""
    return [c for c in coupons if c.status == "claimable"]


# ------------------------------------------------------------------ 一站式
def analyze(baseline: float, orders_per_week: float = 3.0,
            now: datetime | None = None, orders: dict | None = None,
            force_frequency: float | None = None) -> dict:
    """读快照 → 补价值 → 体检 → 排程，返回全部结论。

    频率来源按优先级：显式指定（`force_frequency`）> 订单实测（`orders`）> 假设值。
    订单实测值来自脱敏快照派生，不来自任何猜测。
    """
    import adviser  # 延迟导入，避免顶层循环依赖

    idx = adviser.load_index()
    menu_by_name = {it["name"]: it for it in idx["items"].values()}
    coupons, meta = load_coupons()
    attach_values(coupons, load_probes(), menu_by_name)

    if now is None:
        now = parse_dt(meta.get("capturedAt")) or datetime.now()

    audit = orders or None
    if force_frequency is not None:
        orders_per_week, source = force_frequency, "命令行指定"
    elif audit:
        orders_per_week, source = audit["orders_per_week"], "订单实测"
    else:
        source = "假设"

    return {
        "meta": meta,
        "now": now,
        "checkup": wallet_checkup(coupons, baseline, now),
        "schedule": schedule(coupons, orders_per_week, now),
        "claimable": [c.to_dict() for c in claimable(coupons)],
        "coupons": [c.to_dict() for c in coupons],
        "audit": audit,
        "frequency_source": source,
    }


# ------------------------------------------------------------------ 渲染
def fmt_freq(x: float) -> str:
    """点单频率的显示格式：恰好是整数就不带小数点，否则保留两位。"""
    return f"{x:.0f}" if abs(x - round(x)) < 0.005 else f"{x:.2f}"


def render(report: dict) -> str:
    """把体检与排程渲染成给人看的报告。"""
    out: list[str] = []
    chk, sch = report["checkup"], report["schedule"]
    meta = report["meta"]

    out.append(f"🎟️  券包体检 · {meta.get('storeCode', '')} {meta.get('storeName', '')}")
    out.append(f"   基准：你这一单本来要花 ¥{chk['baseline']:.1f}"
               f" · 数据时点 {report['now']:%Y-%m-%d %H:%M}")
    out.append("")

    if not chk["rows"]:
        out.append("   没有已领取的券。")
        return "\n".join(out)

    for row in chk["rows"]:
        if row["verdict"] == UNKNOWN:
            continue
        days = "—" if row["days_left"] is None else f"{row['days_left']}天"
        face = f"面值 ¥{row['face_value']:.1f}"
        net = "" if row["net_value"] is None else f" · 净赚 ¥{row['net_value']:.1f}"
        src = VALUE_SOURCE_LABEL[row["value_source"]]
        out.append(f"   [{row['verdict']}] {row['title']}")
        out.append(f"        {face}（{src}）{net} · 还剩 {days}")

    unknown = [r for r in chk["rows"] if r["verdict"] == UNKNOWN]
    if unknown:
        names = "、".join(r["title"] for r in unknown)
        out.append(f"   [无法判断] {len(unknown)} 张价值未知：{names}")

    out.append("")
    out.append(f"   名义总额 ¥{chk['named_total']:.1f} → "
               f"按你的消费水平可实现 ¥{chk['realizable']:.1f}")
    counts = chk["counts"]
    if counts[UNKNOWN]:
        out.append(f"   ⓘ {counts[UNKNOWN]} 张价值未知 —— 券面推不出来，我们就不猜；"
                   f"领取后可用带券计价实测。")
    if counts[PAPER]:
        out.append(f"   ⚠️ {counts[PAPER]} 张建议劝退：为了用它们要多花的钱 ≥ 券面价值。")

    out.append("")
    audit = report.get("audit")
    if audit:
        if audit.get("first_date") and audit.get("last_date"):
            period = (f"（{audit['first_date']} → {audit['last_date']}，"
                      f"跨 {audit['span_days']} 天）")
        else:
            period = f"（跨度 {audit['span_days']} 天）"
        out.append(f"   消费审计：{audit['n_orders']} 笔已完成订单{period}")
        if audit.get("avg_ticket") is not None:
            per_month = audit["orders_per_week"] * 52 / 12
            out.append(f"     客单价 ¥{audit['avg_ticket']:.1f}"
                       f" · 累计 ¥{audit['total_spend']:.1f}"
                       f" · 点单 {audit['orders_per_week']:.2f} 单/周"
                       f"（≈ {per_month:.1f} 单/月）")
        if audit.get("top_items"):
            tops = "、".join(f"{n}×{c}" for n, c in audit["top_items"])
            out.append(f"     常点：{tops}")

    out.append(f"   用券排程（频率来源：{report['frequency_source']}）：窗口 "
               f"{sch['window_days']} 天 × {fmt_freq(sch['orders_per_week'])} 单/周"
               f" → 大概只会点 {sch['orders_in_window']} 单，最多用掉 "
               f"{sch['orders_in_window']} 张券")
    for i, a in enumerate(sch["assigned"], 1):
        out.append(f"     第 {i} 单 → {a['title']}　净赚 ¥{a['net_value']:.1f}"
                   f"（还剩 {a['days_left']} 天）")
    for d in sch["dropped"]:
        out.append(f"     排不上 → {d['title']}　净价值 ¥{d['net_value']:.1f}"
                   f"（还剩 {d['days_left']} 天）")
    reachable = sch["assigned_total"] + sch["wasted_total"]
    if sch["wasted_total"] > 0:
        out.append(f"   券包可实现 ¥{reachable:.1f}，但机会只够用掉 ¥{sch['assigned_total']:.1f}"
                   f" —— 剩下 ¥{sch['wasted_total']:.1f} 注定随券过期浪费。")

    claim = report["claimable"]
    if claim:
        out.append("")
        out.append(f"   还没领的券 {len(claim)} 张（领取免费）：")
        for c in claim:
            value = "价值未知" if c["face_value"] is None \
                else f"价值 ¥{c['face_value']:.1f}（菜单反查）"
            out.append(f"     · {c['title']}　{value}")
        out.append("   ⓘ 领取会改动账号状态，本工具只把选项摆清楚，领不领由你决定。")

    return "\n".join(out)


def main() -> int:
    """命令行入口：券包体检与用券排程；也可用 --sanitize 生成脱敏订单快照。"""
    import argparse

    ap = argparse.ArgumentParser(description="券包体检与用券排程")
    ap.add_argument("--baseline", type=float, default=None,
                    help="基准消费（元）；默认取求解器在该预算下的方案总价")
    ap.add_argument("--budget", type=float, default=45, help="预算（元），用于推导默认基准")
    ap.add_argument("--orders-per-week", type=float, default=None,
                    help="每周点单频率；显式给出则覆盖订单实测值")
    ap.add_argument("--orders", type=Path, default=None,
                    help="订单数据文件；默认读仓库内置的派生摘要")
    ap.add_argument("--no-orders", action="store_true",
                    help="忽略订单数据，退回 3 单/周的假设频率")
    ap.add_argument("--sanitize", type=Path, default=None,
                    help="把 order-list 的原始返回洗成脱敏快照后退出")
    ap.add_argument("--out", type=Path, default=None, help="--sanitize 的输出路径")
    ap.add_argument("--summary-out", type=Path, default=None,
                    help="--sanitize 同时导出的派生摘要路径（可提交的那份）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args()

    if args.sanitize:
        raw = json.loads(args.sanitize.read_text(encoding="utf-8"))
        snapshot = sanitize_orders(raw)
        out = args.out or ORDERS
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

        summary_path = args.summary_out or ORDER_SUMMARY
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(order_summary(snapshot), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

        for label, path in (("脱敏快照（本地留存）", out),
                            ("派生摘要（可提交）", summary_path)):
            try:
                shown = path.relative_to(ROOT)
            except ValueError:          # 输出到仓库之外时照原样显示
                shown = path
            print(f"✅ {label}：{shown}")
        return 0

    baseline = args.baseline
    if baseline is None:
        import adviser
        idx = adviser.load_index()
        plans = adviser.solve(idx, adviser.build_pool(idx, set()), args.budget, 1,
                              "balanced", 1, None, None)
        baseline = plans[0].total if plans else args.budget

    orders = None
    if not args.no_orders:
        orders = load_orders(args.orders) if args.orders else load_orders()
        if args.orders and not orders:
            print(f"ⓘ 未读到订单数据（{args.orders}），频率按 3 单/周假设。",
                  file=sys.stderr)

    report = analyze(baseline=baseline, orders=orders,
                     force_frequency=args.orders_per_week)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
