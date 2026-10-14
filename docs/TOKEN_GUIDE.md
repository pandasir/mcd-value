# MCP Token 申请与快照采集

本项目**不需要 Token 也能跑通全部演示与测试**（仓库内置真实快照）。
只有当你想把推荐换到自己附近的门店、或想刷新券数据时，才需要走完本文的步骤。

---

## 1. 申请 Token

1. 打开麦当劳 MCP 开放平台：<https://open.mcd.cn/mcp>
2. 用手机号登录，在控制台**激活**服务并复制 MCP Token。

## 2. 配置到 WorkBuddy

1. 打开 WorkBuddy，左侧边栏进入 **专家 · 技能 · 连接器 → 连接器**。
2. 点击右上角 **自定义连接器 → 配置 MCP**。
3. 粘贴仓库里 [`mcp-config.example.json`](../mcp-config.example.json) 的内容，
   把 `Bearer ${MCD_MCP_TOKEN}` 换成你自己的 Token：

   ```json
   {
     "mcpServers": {
       "mcd-mcp": {
         "type": "streamablehttp",
         "url": "https://mcp.mcd.cn",
         "headers": { "Authorization": "Bearer 你的Token" }
       }
     }
   }
   ```

4. 保存后回到「自定义连接器」，把 `mcd-mcp` 设为**启用**。

> 也可以在仓库根目录把 [`.env.example`](../.env.example) 复制为 `.env` 并填入 `MCD_MCP_TOKEN`。
> `.env` 已被 `.gitignore` 排除。

## 3. 采集快照

让 Agent 按顺序调用下面这些工具，并把**返回原样**写入 `data/raw/`：

| 步骤 | Tool | 写出到 | 说明 |
|---|---|---|---|
| 1 | `query-nearby-stores` | — | `beType=1` 到店自取；`searchType=2` 时需 city + keyword，拿到 `storeCode` |
| 2 | `query-meals` | `data/raw/meals_<storeCode>.json` | 传 `storeCode` + `orderType=1` + `beType=1`，**不要传 `beCode`** |
| 3 | `list-nutrition-foods` | `data/raw/nutrition.txt` | 营养库 |
| 4 | `query-store-coupons` | 并入 `data/raw/coupons_<storeCode>.json` | 传 `storeCode` + `orderType=1` + `beType=1`，拿到券码与券商品码 |
| 5 | `query-my-coupons` | 并入同上 | 卡包券资产（含"用券价格"与有效期） |
| 6 | `available-coupons` | 并入同上 | 可领取 + 已领取 |
| 7 | `calculate-price` | `data/raw/coupon_probe_<storeCode>.json` | **带券计价**：把券的商品码 + `couponId` + `couponCode` 传进去，返回的 `discount` 就是这张券的精确价值（单位：**分**） |
| 8 | `order-list` | 临时文件 `tmp_orders.json` | 历史订单。**不要直接放进 `data/raw/`** —— 先按下一节洗成脱敏快照 |

然后回到仓库根目录：

```bash
python scripts/build_index.py     # 重建索引
python demo.py                    # 验证全流程
python -m unittest discover -s tests -v
```

## 3.1 订单快照（可选，但强烈建议）

订单数据是**唯一含个人信息**的一类快照，所以单独走一条洗白链：

```bash
# 把 order-list 的原始返回存成 /tmp/raw.json（Agent 调用后原样保存）
python scripts/coupon_doctor.py --sanitize /tmp/raw.json
#   ✅ 脱敏快照（本地留存）：data/raw/orders_1420762.json      ← 被 .gitignore 排除，不会提交
#   ✅ 派生摘要（可提交）：data/raw/orders_summary_1420762.json ← 只有客单价/频率/单数/跨度
```

- **第一层（脱敏）**：去掉 `orderId`、`storeCode`、`storeName`、`beCode`，
  下单时刻只留到日。产物留在本地，`.gitignore` 已排除。
- **第二层（只提交摘要）**：仓库里放的是 `orders_summary_*.json`，
  里面**没有逐单明细、商品名与下单日期**。任何人拿到它也读不出"你吃了什么、什么时候吃的"。

洗完之后 `coupon_doctor.py` 会**默认**用这份摘要里的实测频率；
`--no-orders` 回到假设模式，`--orders 路径` 换成别的摘要。

> 旧的原始返回文件（`tmp_orders.json`）用完就删 —— 它含订单号，别留在仓库里。

## 4. 换门店时要留意的两处硬规则

- **价格单位不一致**：`query-meals` 用**元**，`calculate-price` 用**分**。
  本项目只在两个地方做换算：`coupon_doctor.py`（券价值）与下单前复核。别在别处再转一次。
- **`beCode` 传递规则**：到店自取（`beType=1`）**不允许**传 `beCode`，传了会报错；
  得来速（`beType=5`）与外送（`orderType=2`）**必须**传，且来源不同。
  速查：

  | 场景 | orderType | beCode | 来源 |
  |---|---|---|---|
  | 到店自取 `beType=1` | 1 | **不传** | — |
  | 得来速 `beType=5` | 1 | 必传 | `query-nearby-stores` |
  | 麦乐送 `beType=2` | 2 | 必传 | `delivery-query-stores` |
  | 企业团餐 `beType=6` | 2 | 必传 | `delivery-query-stores` |

`build_index.py` 在 `data/raw/` 下**只认一份** `meals_*.json`。同时存在多份时它不会猜：
会报错并列出候选。要用哪一家就用 `--store` 明说（不指定且只有一份时可省略）：

```bash
python scripts/build_index.py --store 1420888
```

> 换店不是换个 JSON 就完事。索引换了之后，**券快照还挂在原门店**（`coupons_<storeCode>.json`），
> README / `docs/demo-output.md` 里的价格与门店名也还是旧的，`demo.py` 的断言同样。
> 要么连这些一起换，要么就当作一次本地试跑 —— 别让它半新半旧地进仓库。

## 5. 安全约定

- Token **只放环境变量或本地 `.env`**，绝不写进仓库、截图或日志。
- 提交前可以自查一遍：

  ```bash
  grep -rn "Bearer [A-Za-z0-9]\{10,\}" . | grep -v MCD_MCP_TOKEN
  ```

- `data/raw/` 里的快照必须**脱敏**：不含账号、手机号、地址、订单号、券码。
- **订单数据一律不提交明细** —— 只提交 `orders_summary_*.json` 里的派生指标，
  完整的脱敏快照由 `.gitignore` 挡在仓库外。
- **`couponCode` 绝不入库。** 它是在门店可核销的账号凭证，公开即等于把券送人。
  实测券价值时你需要它，但**只缓存结果、不落盘**。提交前跑一次剥离：

  ```bash
  python - <<'PY'
  import json, pathlib
  for name in ("data/raw/coupons_1420762.json", "data/raw/coupon_probe_1420762.json"):
      p = pathlib.Path(name)
      d = json.loads(p.read_text(encoding="utf-8"))
      for row in d.get("coupons", []) + d.get("probes", []):
          row.pop("couponCode", None)
      p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  PY
  # 自查：应当没有任何输出
  grep -rnE "MCD[0-9A-Z]{15,}" data/ .github/ docs/ || echo "✅ 无券码"
  ```

  `couponId` 可以留 —— 它是本地标识，不含个人信息，
  且 `coupon_doctor` 只靠它把券与探针缓存对上。
