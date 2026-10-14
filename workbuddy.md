# workbuddy.md

> 本文件记录本项目使用腾讯 WorkBuddy 智能体开发的对话上下文，用于「麦当劳程序员创意开发大赛」WorkBuddy 专项奖励的资格核验。

## 基本信息

| 项 | 值 |
|---|---|
| 项目名称 | 麦麦点餐参谋（mcd-value） |
| 使用工具 | 腾讯 WorkBuddy（Agent 模式） |
| 使用能力 | MCP 连接器调用、代码生成与重构、脚本执行、测试运行、文档撰写 |
| 开发日期 | 2026-10-14 |
| 接入的 MCP | `mcd-mcp`（streamablehttp，`https://mcp.mcd.cn`） |

## 对话上下文（按时间顺序）

### 1. 需求理解

用户给出大赛规则仓库地址，要求评估可行性并给出方向建议。
WorkBuddy 抓取 `activityGuidelines.md` 与活动 README，梳理出关键机制：

- 排名**完全由 GitHub 公开 Star 数决定**（截至 2026-10-26 00:00），与技术难度无关；
- 时间窗口仅 11 天；必交文件为 README / CONTEST_DECLARATION / MCP_INTEGRATION / 源码 / workbuddy.md；
- 官方 README 已举例「套餐推荐助手 / 省钱助手 / 活动推荐助手」，该方向为红海；
- 合规红线明确禁止刷榜，且不得宣扬不健康饮食方式。

**结论**：在红海方向里做出差异化，靠"结构约束 + 券后价 + 可下单参数"形成硬差异。

### 2. 能力面勘察

WorkBuddy 直连 `mcd-mcp` 并逐个验证工具，实际调用了：

`now-time-info`、`list-nutrition-foods`、`available-coupons`、`query-my-account`、
`query-nearby-stores`（深圳·科技园）、`query-meals`（门店 1420762）、`query-meal-detail`。

据此确认了真实数据结构、价格单位（`query-meals` 为元、`calculate-price` 为分）、
`beCode` 传递规则，以及营养库与菜单名称不对齐等工程细节。

### 3. 方案设计与实现

WorkBuddy 完成以下交付：

| 文件 | 说明 |
|---|---|
| `SKILL.md` | WorkBuddy Skill 定义，固化执行流程与安全红线 |
| `scripts/build_index.py` | 名称对齐、角色分类、套餐营养显式建模 |
| `scripts/adviser.py` | 约束求解器 + 四模式多目标打分 + CLI |
| `tests/test_adviser.py` | 13 项回归测试 |
| `data/raw/` | 真实 MCP 返回快照（脱敏） |
| `README.md` / `MCP_INTEGRATION.md` | 项目文档与 MCP 集成说明 |

### 4. 迭代修正（关键过程）

开发过程中 WorkBuddy 通过**实际运行**发现并修复了三个真实缺陷：

1. **均衡模式退化为"挑最便宜的"**：预算 40 元却只推荐 15 元的单品。
   修复：引入「完整一餐」的结构约束（主食+小食+饮品），并把价格从主目标降为约束。
2. **角色分类误判**：「学生专享**饮品**随心选」因含"随心选"被判为主食，导致拼出没有主食的"套餐"。
   修复：重写分类优先级规则，并新增对应测试用例钉住。
3. **随心配类商品营养缺失**：内容自选商品在营养库无对应行，估算明显偏低。
   修复：建立显式建模 + 置信度标注机制，绝不把估算冒充实测值。

### 5. 验证

```bash
python scripts/build_index.py     # ✅ 112 商品 / 营养覆盖 92%
python -m unittest discover -s tests -v   # ✅ 13 tests OK
python scripts/adviser.py --budget 45 --people 1 --mode balanced   # ✅ 输出可下单方案
```

## 说明

- 上述过程均在 WorkBuddy 对话中完成，包含 MCP 调用、代码编写、执行与测试。
- 仓库内所有文件均不含真实 MCP Token；`mcp-config.example.json` 仅使用环境变量占位符。
- 项目为参赛者独立开发，非麦当劳官方产品。
