#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_pages.py —— 网页层的不变量回归测试

网页是最容易被手改的地方：改一个数字、漏跑一次生成脚本，就会出现
「README 说 ¥12.0、页面说 ¥11.5」这种谁也对不上的状态。本文件锁三件事：

1. `docs/demo-data.json` 与求解器一致（跑一遍重建必须逐字节相同）；
2. `docs/index.html` 的预渲染区块与 `demo-data.json` 同源；
3. 页面的静态 HTML 里**真的含有**核心数字（否则 SEO 预渲染等于没做）。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_demo as B  # noqa: E402
import build_pages as P  # noqa: E402


class TestDemoData(unittest.TestCase):
    """docs/demo-data.json 必须是求解器的产物，不能手改。"""

    def test_json_matches_rebuild(self) -> None:
        """重建结果应与提交的 demo-data.json 完全一致。"""
        on_disk = json.loads(
            (ROOT / "docs" / "demo-data.json").read_text(encoding="utf-8")
        )
        rebuilt = json.loads(
            json.dumps(B.build(B.load_idx()), ensure_ascii=False)
        )
        self.assertEqual(on_disk, rebuilt)

    def test_hero_scene(self) -> None:
        """首屏锚点：巨无霸 48.5 vs 三件套 36.5，差 12.0。"""
        data = B.build(B.load_idx())
        hero = next(
            (s for s in data["scenes"] if s["staple"]["name"] == "巨无霸"), None
        )
        self.assertIsNotNone(hero)
        self.assertEqual(hero["singleTotal"], 48.5)
        self.assertEqual(hero["bundle"]["price"], 36.5)
        self.assertEqual(hero["gap"], 12.0)


class TestPrerender(unittest.TestCase):
    """预渲染区块：内容必须同源，且真的写进了页面。"""

    def setUp(self) -> None:
        """准备页面文本与全量场景数据（页面用全量，首屏用前 8 个）。"""
        self.page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.data = B.build(B.load_idx(), max_scenes=None)
        self.block = P.render(self.data)

    def test_anchors_exist(self) -> None:
        """页面必须保留 prerender 锚点，否则生成脚本无法定位。"""
        self.assertIn(P.START, self.page)
        self.assertIn(P.END, self.page)

    def test_block_is_current(self) -> None:
        """页面里的区块必须与当前数据渲染结果逐字一致（CI 会因此失败）。"""
        self.assertIn(self.block, self.page)

    def test_all_scenes_present(self) -> None:
        """每个场景的商品名都要出现在静态 HTML 里（不依赖 JS）。"""
        for scene in self.data["scenes"]:
            self.assertIn(scene["staple"]["name"], self.block)

    def test_prices_present_in_static_html(self) -> None:
        """核心数字必须存在于静态 HTML，否则爬虫看不到。"""
        for token in ("¥48.5", "¥36.5", "¥12.0", "巨无霸三件套"):
            self.assertIn(token, self.page)

    def test_no_zero_for_unknown_value(self) -> None:
        """未知价格渲染成破折号，绝不写 0（与全项目口径一致）。"""
        self.assertEqual(P.money(None), "—")
        self.assertEqual(P.money(0.0), "¥0.0")

    def test_faq_block_valid(self) -> None:
        """FAQPage 结构化数据必须是合法 JSON，且每个场景一条问答。"""
        raw = self.page.split('<script type="application/ld+json">')
        faqs = [b.split("</script>")[0] for b in raw if '"FAQPage"' in b[:2000]]
        self.assertEqual(len(faqs), 1, "应恰好有一块 FAQPage")
        payload = json.loads(faqs[0])
        self.assertEqual(payload["@type"], "FAQPage")
        self.assertEqual(len(payload["mainEntity"]), len(self.data["scenes"]))
        for q in payload["mainEntity"]:
            self.assertIn("¥", q["acceptedAnswer"]["text"])


class TestStarCta(unittest.TestCase):
    """转化路径：页面上必须有指向仓库的 star 入口。"""

    def test_cta_present(self) -> None:
        """至少一处可见的 star 引导，且指向本仓库。"""
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("github.com/pandasir/mcd-value", page)
        self.assertIn("star", page)

    def test_utm_applied(self) -> None:
        """外链带上 utm 参数，否则日后无法归因 star 来源。"""
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("utm_source=gh-pages", page)


if __name__ == "__main__":
    unittest.main()
