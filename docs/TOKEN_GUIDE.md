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

然后回到仓库根目录：

```bash
python scripts/build_index.py     # 重建索引
python demo.py                    # 验证全流程
python -m unittest discover -s tests -v
```

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

`build_index.py` 只读取 `meals_*.json` 中**名字排序最靠前**的那个文件，
换店时请先移走旧文件。

## 5. 安全约定

- Token **只放环境变量或本地 `.env`**，绝不写进仓库、截图或日志。
- 提交前可以自查一遍：

  ```bash
  grep -rn "Bearer [A-Za-z0-9]\{10,\}" . | grep -v MCD_MCP_TOKEN
  ```

- `data/raw/` 里的快照必须**脱敏**：不含账号、手机号、地址、订单号。
  券快照里的 `couponId` / `couponCode` 是券本身的标识，不含个人信息，
  但如果你有顾虑，可以整体替换为占位符 —— 那样 `coupon_doctor` 会退回到"价值未知"，
  这是被支持的降级路径。
