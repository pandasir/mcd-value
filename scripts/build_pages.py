#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_pages.py —— 把比价结果预渲染进 docs/index.html（爬虫可读）

为什么需要这一步：
  网页 Demo 的结果是 JS 运行时算出来的，静态 HTML 里只有一个「正在读取菜单快照…」。
  百度不执行 JS，Google 的渲染也不保证 —— 也就是说整站对
  「巨无霸三件套多少钱」这类真实长尾搜索词是零命中。

做法：
  在 `docs/index.html` 里留一对 `<!-- prerender:start/end -->` 锚点，
  由本脚本把全部场景渲染成一张静态表格塞进去。JS 仍然接管首屏的互动区，
  但**关掉 JS 也能读到全部数字**。

口径纪律（与本项目其他部分一致）：
  数字只来自 `build_demo.build()`，与 `docs/demo-data.json`、CLI、终端演示同一套函数。
  本脚本只做 HTML 拼接，不重算任何价格。

用法：
  python scripts/build_pages.py           # 写入 docs/index.html
  python scripts/build_pages.py --check   # 校验页面与数据是否一致（CI 用）
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_demo as B  # noqa: E402

PAGE = ROOT / "docs" / "index.html"
START = "<!-- prerender:start -->"
END = "<!-- prerender:end -->"
COUPON_DOC = "https://github.com/pandasir/mcd-value/blob/main/docs/COUPON_METHOD.md"


def money(value: float | None) -> str:
    """把价格渲染成 `¥48.5`；缺值渲染成破折号，绝不写 0。"""
    return "—" if value is None else f"¥{value:.1f}"


def bundle_cell(bundle: dict | None) -> str:
    """套餐名 + 套餐价；没有套餐时如实写「本店无对应套餐」。"""
    if not bundle:
        return "本店无对应套餐"
    return (
        escape(bundle["name"])
        + f'<span class="sub">{money(bundle["price"])}</span>'
    )


def render_rows(scenes: list[dict]) -> list[str]:
    """把每个场景渲染成一行表格（含商品编码锚点，便于将来拆独立页）。"""
    rows = []
    for s in scenes:
        parts = " + ".join(p["name"] for p in s["parts"])
        code = escape(s["staple"]["code"])
        rows.append(
            f'          <tr id="s-{code}">'
            f'<th scope="row">{escape(s["staple"]["name"])}'
            f"<small>单点：{escape(parts)}</small></th>"
            f'<td class="num">{money(s["singleTotal"])}</td>'
            f'<td class="num">{bundle_cell(s["bundle"])}</td>'
            f'<td class="gap">{money(s["gap"]) if s["gap"] else "—"}</td>'
            f"</tr>"
        )
    return rows


def render_caption(data: dict) -> str:
    """表格标题 + 口径说明（爬虫读得到的第一段实质内容）。"""
    store = data["store"]
    stats = data["stats"]
    gap = stats["uniformGap"]
    if gap is not None:
        headline = f"这家店 {stats['verified']} 个汉堡，套餐全都便宜 {money(gap)}"
        body = (
            f"{stats['verified']} 个能逐个单点的汉堡，全部匹配到本店已有的套餐；"
            f"每一个的差价都正好是 {money(gap)} —— 差价不挑商品，变的是起点价。"
        )
    else:
        headline = f"这家店 {stats['verified']} 个汉堡的套餐差价"
        body = "下表逐行列出单点合计与套餐价。"
    body += (
        f" 数据来自{store['storeName']} {store['capturedAt'][:10]} 的菜单快照，"
        "只比较无条件价（会员价不参与，否则会拿一个你拿不到的价格去比）。"
    )
    return f"{escape(headline)}。{escape(body)}"


def render(data: dict) -> str:
    """把场景列表渲染成静态 HTML 片段（整段插到两个锚点之间）。"""
    note = (
        '  <p class="note" style="margin-top:10px">'
        "「多花了」= 同一批商品的单点合计 − 本店套餐价，两侧都是这家店的真实现价。"
        "这里不算「划线价省了多少」—— 你本来也不会按划线价买，"
        "把划线价当基准能把「省」吹得很漂亮，但那是假的。"
        f'完整的比价口径见 <a href="{COUPON_DOC}">券的口径</a>。</p>'
    )
    return "\n".join(
        [
            START,
            '  <h2 class="section-label" id="matrix">全部场景：单点 vs 套餐，一行一个汉堡</h2>',
            '  <div class="matrix-wrap">',
            '    <table class="matrix">',
            f"      <caption>{render_caption(data)}</caption>",
            "      <thead>",
            '        <tr><th scope="col">想吃到</th>'
            '<th scope="col" style="text-align:right">单点合计</th>'
            '<th scope="col">换个买法</th>'
            '<th scope="col" style="text-align:right">多花了</th></tr>',
            "      </thead>",
            "      <tbody>",
            *render_rows(data["scenes"]),
            "      </tbody>",
            "    </table>",
            "  </div>",
            note,
            render_faq(data),
            END,
        ]
    )


def render_faq(data: dict) -> str:
    """生成 FAQPage 结构化数据（一条场景一个问题）。

    FAQ 的答案与表格同源，不做任何额外表述 —— 否则就是两套口径。
    搜索结果的 rich snippet 直接复它。
    """
    store = data["store"]
    origin = f'{store["storeName"]} {store["capturedAt"][:10]} 的菜单快照'
    main_entity = []
    for s in data["scenes"]:
        bundle = s["bundle"]
        if not bundle:
            continue
        parts = " + ".join(p["name"] for p in s["parts"])
        answer = (
            f"{s['staple']['name']}单点合计 {money(s['singleTotal'])}"
            f"（{parts}），本店套餐「{bundle['name']}」{money(bundle['price'])}，"
            f"两者相差 {money(s['gap'])}。价格来自{origin}，只比较无条件价。"
        )
        main_entity.append(
            {
                "@type": "Question",
                "name": f"{s['staple']['name']}单点还是套餐便宜？多少钱？",
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }
    # `<` 转义成 \u003c，避免商品名里出现 `</script>` 时截断脚本标签
    body = json.dumps(payload, ensure_ascii=False, indent=1).replace("<", "\\u003c")
    return f'  <script type="application/ld+json">\n{body}\n  </script>'


def inject(page: str, block: str) -> str:
    """把 `block` 替换到页面的 prerender 锚点之间。"""
    if START not in page or END not in page:
        raise SystemExit(f"{PAGE} 里找不到 {START} / {END} 锚点")
    head, rest = page.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{block}{tail}"


def main(argv: list[str]) -> int:
    """命令行入口：默认写回页面，`--check` 只比对不写盘。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验页面是否与数据一致")
    args = ap.parse_args(argv)

    data = B.build(B.load_idx(), max_scenes=None)
    block = render(data)
    page = PAGE.read_text(encoding="utf-8")

    if args.check:
        if block not in page:
            print(
                "CHECK FAIL：docs/index.html 的预渲染区块与数据不一致，"
                "请运行 python scripts/build_pages.py"
            )
            return 1
        print(f"CHECK OK：{len(data['scenes'])} 个场景已预渲染进 {PAGE.name}")
        return 0

    PAGE.write_text(inject(page, block), encoding="utf-8")
    print(
        f"wrote {PAGE.relative_to(ROOT)}：{len(data['scenes'])} 个场景"
        f"（{len(block)} 字符静态 HTML）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
