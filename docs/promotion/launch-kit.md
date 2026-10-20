# 麦麦点餐参谋：曝光素材包

> 当前口径：深圳同方信息港门店 2026-10-14 快照；12 组已验证的汉堡单点与对应三件套，每组差 ¥12。数据与演示页一致。项目为独立作品，非麦当劳官方产品。

## 核心素材

- GitHub：<https://github.com/pandasir/mcd-value>
- 在线试玩：<https://pandasir.github.io/mcd-value/>（免 Token，使用脱敏快照）
- 主视觉（手机竖版 PNG）：`assets/promo-card-vertical.png`
- 主视觉（手机竖版 SVG 源文件）：`assets/promo-card-vertical.svg`
- 主视觉（横版）：`assets/demo-dual-view.svg`
- 接入说明：`MCP_INTEGRATION.md`

## 15–20 秒演示视频脚本

1. 画面：输入“巨无霸 + 薯条 + 可乐，怎么点最划算？”字幕：“同一顿饭，买法不一样，差 ¥12”。
2. 画面：展示单点 ¥48.5 与巨无霸三件套 ¥36.5 并排比较。
3. 画面：快速展示营养 / 忌口 / 优惠券功能；字幕：“价格来自门店快照，算不准就标未知”。
4. 结尾：打开在线试玩；字幕：“免 Token 试玩 · GitHub 查看源码”。

避免把会员价说成人人都能买，也避免把快照价格说成实时价格。

## 掘金 / 开发者社区短版

### 我用麦当劳官方 MCP 做了个点餐参谋：先把价格算准，再让 AI 推荐

想吃巨无霸、薯条和可乐，单点合计 ¥48.5；同一家门店的巨无霸三件套是 ¥36.5，差 ¥12。这个差价来自深圳同方信息港 2026-10-14 的菜单快照，在线 Demo 可以直接复现。

我做的「麦麦点餐参谋」把门店菜单、营养和优惠券数据交给 Python 求解器处理：预算、忌口和营养目标作为约束；会员价默认排除；套餐营养标注估算；券价值没有来源就显示未知。大模型负责理解需求，数字交给确定性计算。

项目代码和免 Token 演示：
- [GitHub 源码](https://github.com/pandasir/mcd-value?utm_source=juejin&utm_medium=community&utm_campaign=2026_mcd_contest)
- [在线 Demo](https://pandasir.github.io/mcd-value/?utm_source=juejin&utm_medium=community&utm_campaign=2026_mcd_contest)

这是一个独立开发项目，不是麦当劳官方产品。欢迎试用、指出数据或计算问题；觉得有用的话，可以在 GitHub 留 Star。

## V2EX / 技术讨论短版

### 分享一个基于麦当劳 MCP 的小项目：点单方案用代码算，不让模型心算价格

最近把麦当劳官方 MCP 接进一个本地点餐助手。它拉取门店菜单和营养数据，再用约束求解比较单点、套餐与组合：比如巨无霸 + 薯条 + 可乐，在一份门店快照里单点 ¥48.5、三件套 ¥36.5。

比较时我踩到几个坑：会员价不能当人人可得的价格；套餐营养需要标明估算；券名经常推不出面值；商品身份不确定时不能拿相似营养数据冒充商品组成。项目把这些边界写进规则和测试里。

代码：[GitHub 仓库](https://github.com/pandasir/mcd-value?utm_source=v2ex&utm_medium=community&utm_campaign=2026_mcd_contest)
免 Token Demo：[在线试玩](https://pandasir.github.io/mcd-value/?utm_source=v2ex&utm_medium=community&utm_campaign=2026_mcd_contest)

想听听大家对 MCP 项目目录评分、工具可发现性，以及“本地算法 + 官方远程 MCP”这种产品形态的看法。项目为独立作品，非麦当劳官方产品。

## 小红书图文短版

同样是巨无霸 + 薯条 + 可乐，单点 ¥48.5，换成巨无霸三件套 ¥36.5，差 ¥12。

我做了个小工具，把麦当劳门店菜单里的单点、套餐和组合放一起比较。还可以按预算、忌口、营养目标筛方案，也会把会员价和估算营养明确标出来。

数字来自 2026-10-14 的单店菜单快照，不代表所有门店当前价格。在线 Demo 免 Token：[点此试玩](https://pandasir.github.io/mcd-value/?utm_source=xiaohongshu&utm_medium=social&utm_campaign=2026_mcd_contest)。源码：[GitHub](https://github.com/pandasir/mcd-value?utm_source=xiaohongshu&utm_medium=social&utm_campaign=2026_mcd_contest)。

## 即刻短帖

做了个麦当劳点餐小参谋。最直观的例子：巨无霸 + 薯条 + 可乐，单点 ¥48.5；同店巨无霸三件套 ¥36.5，差 ¥12。不是模型猜价，数据来自一份标明日期的门店菜单快照。

更花时间的是把边界说清楚：会员价单独算，套餐营养标估算，券价值没法核实就不猜。做 MCP 项目时，能诚实地说“不知道”也算功能的一部分。

免 Token Demo：[试玩](https://pandasir.github.io/mcd-value/?utm_source=jike&utm_medium=social&utm_campaign=2026_mcd_contest) · 源码：[GitHub](https://github.com/pandasir/mcd-value?utm_source=jike&utm_medium=social&utm_campaign=2026_mcd_contest)。

## MCP / WorkBuddy 社区短版

我把麦当劳官方 MCP 接进了一个本地点餐流程：先用 `query-meals` 取门店菜单，再用本地 Python 求解器按预算、忌口和营养约束筛选；券价值用计价返回校验，推不出来就标未知。价格口径里也把需麦金卡的会员价单独处理。

免 Token 的脱敏快照 Demo：[试玩](https://pandasir.github.io/mcd-value/?utm_source=mcp_workbuddy&utm_medium=community&utm_campaign=2026_mcd_contest)
源码与接入步骤：[GitHub](https://github.com/pandasir/mcd-value?utm_source=mcp_workbuddy&utm_medium=community&utm_campaign=2026_mcd_contest)

项目不托管麦当劳 MCP Server。要看实时门店数据，需要用户自行申请并配置官方 MCP Token；离线演示无需 Token。

## LobeHub 条目建议文案

**建议名称**：麦麦点餐参谋｜McDonald's Meal Adviser

**建议定位 / 分类**：本地点餐助手 / MCP 驱动的工作流。项目使用麦当劳官方 MCP 获取实时数据，仓库本身提供 Python 求解器、技能流程和离线演示；它不托管 MCP Server。若目录只接受可直接调用的 MCP Server，应明确说明依赖外部服务和 Token，不能伪报本项目自有工具数量。

**简介**：

麦麦点餐参谋是一个基于麦当劳官方 MCP 数据的本地点餐助手。仓库提供 Python 求解器、营养与优惠券分析流程，以及可离线复现的脱敏演示数据。实时门店数据通过用户自行配置的麦当劳官方 MCP Token 获取；本项目不托管 MCP 服务端，也不提供匿名云端接口。可先打开免 Token 演示，再按说明接入实时菜单。

**主要能力**：按预算 / 忌口 / 营养目标筛选点餐方案；比较同一批商品的单点与套餐价格；分析优惠券价值和有效期。套餐营养会标明估算；会员价默认不纳入；无法核实的券价值会标为未知。

**链接顺序**：免 Token Demo → GitHub 源码 → MCP 接入说明。标签建议：`mcdonalds`、`meal-planning`、`budgeting`、`coupons`、`nutrition`、`chinese`。

当前公开详情页仍含旧快照文案（包括“20 组里 17 组更便宜、合计省 ¥193.3”），和本仓库验证后的 12 组示例不一致。公开详情页没有编辑入口；管理页会转到登录页：<https://app.lobehub.com/community/mcp/pandasir-mcd-value>。登录后用上面的名称、简介、标签和链接顺序更新条目，并确认旧简介已刷新。目录页没有展示本项目自有工具数量；不要伪报工具数量。

## 短期发布节奏（2026-10-20 至 2026-10-25）

| 日期 | 动作 | 发布素材 |
|---|---|---|
| 10-20 | 对齐 GitHub / Demo / LobeHub 文案，录制 15–20 秒演示 | 竖版主视觉 + 视频脚本 |
| 10-21 | 发布技术长文 | 掘金稿，重点讲 MCP 数据与确定性计算 |
| 10-22 | 发起工程讨论 | V2EX 稿，重点讲会员价、身份匹配与目录可发现性 |
| 10-23 | 发图文短帖 | 小红书 / 即刻稿，突出 ¥48.5 vs ¥36.5 |
| 10-24 | 参与相关 MCP / WorkBuddy 讨论并答疑 | MCP 接入说明 + Demo 链接 |
| 10-25 | 仅在已有受众渠道做一次截止提醒 | 简短、自愿 Star 邀请；以官方截止时间为准 |

**发布状态**：所有稿件和物料已准备；尚未发布。发布日程供账号持有人直接执行，发布后将数据填入 `docs/promotion/tracking.csv`。

## 来源链接与复盘表

每个渠道使用独立的 UTM 参数，便于将来在站点启用分析后按来源区分访问：

| 渠道 | Demo 来源参数 |
|---|---|
| 掘金 | `utm_source=juejin&utm_medium=community` |
| V2EX | `utm_source=v2ex&utm_medium=community` |
| 小红书 | `utm_source=xiaohongshu&utm_medium=social` |
| 即刻 | `utm_source=jike&utm_medium=social` |
| MCP / WorkBuddy 社区 | `utm_source=mcp_workbuddy&utm_medium=community` |

当前静态 Demo 没有接入 GA / GTM，因此 UTM 本身不会产生站内访问报表。发布后先记平台原生点击与互动数据，再用 GitHub Traffic 的来源域名和仓库访问量做辅助观察；不要声称能精确归因到单个帖子。

| 顺序 | 渠道 | 内容角度 | 记录指标 |
|---|---|---|---|
| 1 | 掘金 | MCP 接入、确定性计算、实现细节 | 阅读、收藏、评论、GitHub 引荐访问 |
| 2 | V2EX / 开发者社区 | 工程取舍与 MCP 目录可发现性讨论 | 回复、点击、GitHub 引荐访问 |
| 3 | 小红书 / 即刻 | ¥48.5 vs ¥36.5 的图或短视频 | 展示、互动、Demo 点击 |
| 4 | MCP / WorkBuddy 社区 | 接入与真实工具调用场景 | 讨论、安装问题、GitHub 引荐访问 |

每个平台发布后记录日期、帖子链接、阅读 / 展示数、互动数、试玩访问和 GitHub Star 变化。优先使用平台自带统计与 GitHub Traffic；不要声称有精确归因，除非落地页已配置并验证分析工具。

比赛相关信息发布前，按官方活动页面再次核对截止时间、排名口径和宣传规范。Star 邀请保持自愿，不做互刷、抽奖换星或任何操纵行为。

## 截止后的长尾内容

1. 发布一篇技术复盘：从官方 MCP 返回到门店菜单索引，再到约束求解、价格口径和优惠券估值。
2. 把真实问题拆成独立短文：会员价如何过滤、套餐营养如何标估算、券面价值未知时为何不猜。
3. 随菜单快照或算法口径更新写简短版本记录，并继续把在线 Demo、源码和接入说明互相串联。
