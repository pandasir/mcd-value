# data/raw —— 真实 MCP 返回快照

这里存放的是**麦当劳 MCP 的真实返回**，用于让 `demo.py`、单元测试与 CI
在**不需要 Token、不联网**的前提下复现整套流水线。

## 快照清单

| 文件 | 来源 Tool | 采集时间 | 说明 |
|---|---|---|---|
| `meals_1420762.json` | `query-meals` | 2026-10-14 16:41:06 | 门店 1420762（深圳同方信息港）的完整菜单：分类、商品编码、现价、划线价、优惠标签 |
| `nutrition.txt` | `list-nutrition-foods` | 2026-10-14 | 营养库，160 条，含能量/蛋白/脂肪/碳水/钠/钙 |
| `coupons_1420762.json` | `query-store-coupons` + `query-my-coupons` + `available-coupons` | 2026-10-14 17:26:54 | 12 张券：券名、状态、有效期、券自带商品码与用券实付。**不含券码**（`couponCode`） |
| `coupon_probe_1420762.json` | `calculate-price` | 2026-10-14 17:27:02 | 券价值实测缓存：把券商品码 + `couponId` + `couponCode` 传给 `calculate-price`，返回的 `discount`（单位**分**）就是券的精确价值。归档版**只留 `couponId` 与结果，不留券码** |
| `orders_summary_1420762.json` | `order-list` | 2026-10-14 17:45:09 | **只含派生指标**：已完成单数、客单价、点单频率、跨度。**没有逐单明细、商品名与下单日期** |

## 脱敏说明

菜单与营养快照**不含任何个人数据**：没有账号、手机号、地址、订单号。

券快照只保留 `couponId`，**不含 `couponCode`**。

`couponId` 是券在本地的标识，用来让「券价值靠 `calculate-price` 实测」这件事**可被审计**
（探针缓存 `coupon_probe_*.json` 要与之一一对应）。而 `couponCode` 是在门店可核销的
**账号凭证**，一旦公开就可能被他人用掉 —— 所以它**从不落盘**：实测完成后只缓存结果。

你不用为这个取舍担心复现问题：`scripts/coupon_doctor.py` 只按 `couponId` 关联，
券码缺失不影响任何结论。**你自己采集快照时**（见 `docs/TOKEN_GUIDE.md`）拿到的是带券码的原始返回，
提交前剥掉即可 —— 那里有一条现成命令。

订单数据做了**两层**处理：

1. **脱敏**（`--sanitize`）：去掉 `orderId`、`storeCode`、`storeName`、`beCode`，
   下单时刻只留到日、去掉时分秒。产物 `orders_1420762.json` 被 `.gitignore` 排除。
2. **只提交派生摘要**：`orders_summary_<storeCode>.json` 里**只有**客单价、频率、单数、跨度，
   没有逐单明细、商品名与下单日期。

也就是说：**仓库里既没有原始订单，也没有可直接读出你吃了什么、什么时候吃的文件。**

## 订单摘要怎么生成

```bash
# 1. 把 order-list 的原始返回存成 raw.json（Agent 调用后原样保存）
# 2. 一条命令产出「本地脱敏快照」+「可提交派生摘要」
python scripts/coupon_doctor.py --sanitize raw.json
#   ✅ 脱敏快照（本地留存）：data/raw/orders_1420762.json      （被 .gitignore 排除）
#   ✅ 派生摘要（可提交）：data/raw/orders_summary_1420762.json
```

派生口径：只统计「订单已完成」；已取消的不计；金额为 0 的单计入频率但不计入客单价。

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

`build_index.py` 在 `data/raw/` 下**只认一份** `meals_*.json`。如果同时存在多份，
它不会猜 —— 会直接报错并列出候选，让你移走多余的，或者用 `--store <storeCode>` 指定：

```bash
python scripts/build_index.py --store 1420888
```

> 这条是**故意做硬的**：早先它是「取文件名排序最靠前的一份」，于是往本目录多放一家门店的
> 快照就会**静默换店** —— 索引换了，而券快照、README 里的价格、`demo.py` 的断言
> 还停在原来的门店，错配没人发现。宁可报错，也不要在你不知道的情况下换一家店算账。

## 为什么快照要进仓库

把真实响应提交进仓库，有三个直接好处：

1. **可复现**：任何人 clone 下来就能跑，不用先申请 Token；
2. **可审计**：README 与 demo 里的每个价格，都能在快照里逐字对上；
3. **可回归**：`demo.py` 同时是端到端测试，CI 会因为 `data/index.json`
   与快照重建结果不一致而失败。
