# MCP_INTEGRATION.md

本文说明「麦麦点餐参谋」实际使用了哪些麦当劳 MCP Server / Tool、调用顺序、数据流向与业务价值。

## 1. 接入的 MCP Server

| 项 | 值 |
|---|---|
| 服务名 | `mcd-mcp` |
| 传输方式 | `streamablehttp` |
| 端点 | `https://mcp.mcd.cn` |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>`（仅环境变量注入，仓库内不存明文） |
| 配置示例 | [`mcp-config.example.json`](./mcp-config.example.json) |

**Token 安全约定**：本仓库所有文件、示例与日志中均不含真实 Token。`.gitignore` 已排除 `.env`、`*.local.json`。
仓库中的 `data/raw/` 为**已脱敏的接口返回快照**，仅保留商品编码、名称、价格与营养字段，
不含任何账号、手机号、地址、订单号等个人数据。

## 2. 实际调用的 Tool 与用途

| # | Tool | 在本项目中的用途 | 是否必需 |
|---|---|---|---|
| 1 | `now-time-info` | 校准服务器时间，用于判断早餐/午餐/夜市时段与预约窗口 | 辅助 |
| 2 | `query-nearby-stores` | 按城市 + 地标解析门店，取得 `storeCode`（`beType=1` 到店自取） | **必需** |
| 3 | `query-meals` | 拉取该门店实时菜单：分类、商品编码、现价、划线价、优惠标签、随单购信息 | **必需** |
| 4 | `list-nutrition-foods` | 拉取营养库（能量/蛋白/脂肪/碳水/钠/钙），为推荐提供营养口径 | **必需** |
| 5 | `available-coupons` | 读取用户可领取/已领取的券，构建券规则以计算券后价 | 可选（影响报价） |
| 6 | `query-my-account` | 读取麦享会积分，用于"积分可兑换"类延伸建议 | 可选 |
| 7 | `query-meal-detail` | 查询套餐组成与特调项（`roundList` / `modification`），供"换配菜"类需求 | 可选 |
| 8 | `calculate-price` | 下单前复核最终价格（含优惠），返回单位为**分** | 下单链路 |
| 9 | `create-order` | 用户确认后真正下单；`items` 直接复用引擎输出的 `order_items` | 下单链路 |

## 3. 调用流程

```
用户约束（预算/人数/模式/忌口）
        │
        ▼
query-nearby-stores ──► storeCode
        │
        ├──► query-meals ─────────► 商品编码 + 实时价格 + 优惠标签
        ├──► list-nutrition-foods ► 营养数据
        └──► available-coupons ───► 券规则
        │
        ▼
scripts/build_index.py   归一化：名称对齐 → 角色分类 → 套餐营养建模
        │
        ▼
scripts/adviser.py       约束求解 + 多目标打分 → Top-K 方案
        │
        ├──► 展示（可解释 + 营养达成度 + 券后总价）
        │
        ▼
calculate-price ──► create-order      （仅在用户明确确认下单时）
```

## 4. 与 MCP 数据的耦合点（工程要点）

1. **价格单位不一致**：`query-meals` 的价格是**元**（字符串），`calculate-price` 返回的是**分**。
   本项目在引擎内部统一用元，调用 `calculate-price` 处显式除以 100。这是最容易出错的地方。
2. **`beCode` 传递规则**：到店自取（`beType=1`）**不允许**传 `beCode`，传了会报错；
   而 `beType=5`（得来速）/ `orderType=2`（外送/团餐）**必须**传，且来源不同
   （`query-nearby-stores` vs `delivery-query-stores`）。本项目在 `SKILL.md` 中固化了这张对照表。
3. **套餐组成与营养无法直接对齐**：营养库按单品给数，菜单里的"三件套/四件套/随心配"没有对应行。
   本项目采用**显式建模 + 标注置信度**的方式处理（见 `build_index.py` 的 `resolve_bundle()`），
   绝不把估算值冒充实测值。
4. **券的规则不在接口里**：`available-coupons` 只返回券名与图片，不含使用细则。
   本项目按券名推断规则（买一送一 / 固定价），并在输出中统一标注"需门店核验"，避免向用户做过度承诺。
5. **商品内容随机的条目不可用于营养计算**：例如"牛肉堡单品精选"这类盲盒式商品，
   其内容不确定，本项目将其排除在推荐池之外，保证"推荐了什么 = 买到什么"。

## 5. 业务价值

- **对用户**：把"预算 + 口味 + 营养 + 券"四类约束一次性算清，替代在门店菜单前的反复比价；
  输出直接可下单，省掉"查编码—再比价—再下单"的三段式操作。
- **对麦当劳**：把 MCP 从"能查能下单"推进到"能决策"，提升客单价的合理性与点餐转化；
  `query-meals` 的优惠标签、随单购、1+1 随心配等能力被真实消费，而非停留在文档里。
- **可复现**：仓库内置真实快照与回归测试，评审可无 Token 直接跑通全流程验证结果。
