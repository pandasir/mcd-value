# data/raw —— 真实 MCP 返回快照

这里存放的是**麦当劳 MCP 的真实返回**，用于让 `demo.py`、单元测试与 CI
在**不需要 Token、不联网**的前提下复现整套流水线。

## 快照清单

| 文件 | 来源 Tool | 采集时间 | 说明 |
|---|---|---|---|
| `meals_1420762.json` | `query-meals` | 2026-10-14 16:41:06 | 门店 1420762（深圳同方信息港）的完整菜单：分类、商品编码、现价、划线价、优惠标签 |
| `nutrition.txt` | `list-nutrition-foods` | 2026-10-14 | 营养库，160 条，含能量/蛋白/脂肪/碳水/钠/钙 |

## 脱敏说明

快照**不含任何个人数据**：没有账号、手机号、地址、订单号、券码。
只保留商品编码、名称、价格与营养字段。`_meta` 中的 `storeCode` 是公开门店编码。

## 怎么换成你自己的门店

1. 在 WorkBuddy 中配置好 `mcd-mcp` 连接器（见仓库根目录 `.env.example` 与 README）。
2. 让 Agent 依次调用，并把返回原样写入本目录：
   - `query-nearby-stores`（`beType=1` 到店自取）→ 拿到 `storeCode`
   - `query-meals`（`storeCode` + `orderType=1` + `beType=1`）→ 写成 `meals_<storeCode>.json`
   - `list-nutrition-foods` → 写成 `nutrition.txt`
3. 回到仓库根目录执行：

   ```bash
   python scripts/build_index.py
   python demo.py
   ```

`build_index.py` 只读取 `meals_*.json` 中**名字排序最靠前**的那个文件，
所以换店时请先移走旧的 `meals_<storeCode>.json`。

## 为什么快照要进仓库

把真实响应提交进仓库，有三个直接好处：

1. **可复现**：任何人 clone 下来就能跑，不用先申请 Token；
2. **可审计**：README 与 demo 里的每个价格，都能在快照里逐字对上；
3. **可回归**：`demo.py` 同时是端到端测试，CI 会因为 `data/index.json`
   与快照重建结果不一致而失败。
