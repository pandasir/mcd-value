---
name: mcd-meal-adviser
description: |
  麦麦点餐参谋 —— 基于麦当劳 MCP 的约束求解式点餐推荐。当用户问"今天麦当劳吃什么""预算 X 元怎么点最划算""减脂期能吃哪套""不要牛肉的套餐""几个人聚餐怎么点"时使用。输入预算/人数/营养目标/忌口，输出多套可解释、可直接下单的套餐方案。
  McDonald's China ordering advisor and meal-planning skill. Use when the user asks what to eat at McDonald's, how to order a budget meal cheaply, which combo beats ordering items separately, what fits a calorie or protein target, or how to use expiring coupons. Compares a-la-carte, combo, and bundle prices from a real store menu snapshot, then applies coupons. Prices and item codes come from McDonald's MCP responses, never from memory; anything it cannot compute is reported as unknown instead of estimated.
---

# 麦麦点餐参谋

## 何时使用

- 用户表达"帮我点麦当劳 / 今天吃什么 / 不知道怎么选"
- 用户给出预算、人数、热量或蛋白目标、忌口偏好
- 用户想把优惠券用在最优的搭配上

## 核心原则

**不要凭印象推荐，也不要凭空报价。** 所有商品编码与价格必须来自麦当劳 MCP 的真实返回；
所有营养数值必须来自营养库或本项目的建模口径，并如实标注置信度。

## 执行流程

### 第 0 步 · 先确认能不能取数（每次开场都做，不要跳过）

本技能的数据只有两条来源，二选一：

| 通道 | 需要什么 | 拿到什么 |
|---|---|---|
| 麦当劳 MCP 工具 | 已配置且有效的 MCP Token | 用户所在门店的实时菜单与价格 |
| 仓库内置快照 | 什么都不需要 | 2026-10-14 深圳同方信息港的固定数据 |

**开口回答任何点餐问题之前，先探测 MCP 工具是否可用**：查看当前可用工具里有没有
`query-nearby-stores`、`query-meals`、`list-nutrition-foods`，或者直接试调其中一个轻量查询。

**探测失败时必须立刻主动告诉用户，不能默默改用快照，更不能凭印象报菜单。**
按下面对应的情况措辞（用用户当前使用的语言说）：

- **工具列表里根本没有 `mcd-mcp`**：说明还没配置连接器。

  > 我这边没有连上麦当劳 MCP，取不到你所在门店的实时菜单和价格。
  > 需要先配一个 MCP Token，免费申请：打开 https://open.mcd.cn/mcp ，手机号登录，
  > 进「控制台」点「激活」，复制那串 Token。配置方法见项目 README 的「安装」一节
  > （WorkBuddy 用方式一，Claude / Cursor / VS Code 等用方式二）。

- **有 `mcd-mcp` 但报鉴权错误（401 / 403）或超时**：说明 Token 失效或未激活。

  > 麦当劳 MCP 连上了但鉴权失败，Token 可能已过期或没激活。
  > 去 https://open.mcd.cn/mcp 的控制台重新激活并复制一次 Token，更新配置后重试。

两种情况下都接着给出退路，并把选择权交给用户：

> 在你配好之前，我可以先用项目自带的 2026-10-14 深圳同方信息港门店快照给你算一版，
> 结论只对那家店那天成立，不是实时价格。要这样先看吗？

用户怎么选就怎么做：

- 选「先看快照」：用 `data/index.json` 继续算，**每一条输出开头都要注明数据口径**
  （例如「以下基于 2026-10-14 深圳同方信息港快照，非实时价格」）。
- 选「先配 Token」：停下，等用户配置完，重新走第 0 步。
- 用户没回答：不要自行假定，等确认。

用户一上手就说了具体门店（例如「深圳同方信息港那家」）也不能省掉这一步：
实时菜单依然要有 Token 才取得到，门店名不构成取数能力。

### 第 1 步 · 收集约束（缺什么问什么，不要一次问一堆）

| 参数 | 说明 | 默认 |
|---|---|---|
| 预算 | 总预算（元） | 无默认，必问 |
| 人数 | 用餐人数 | 1 |
| 模式 | `balanced` 均衡 / `value` 最省 / `protein` 高蛋白 / `light` 轻负担 | `balanced` |
| 忌口 | 牛肉 / 猪肉 / 鸡肉 / 鱼 / 辣 / 咖啡因 / 乳制品 / 油炸 | 无 |
| 硬指标 | 热量上限、蛋白下限 | 按模式内置 |

### 第 2 步 · 取真实门店与菜单

1. 用 `query-nearby-stores`（`beType=1` 到店自取；`searchType=2` 需 city + keyword）拿到 `storeCode`。
   用户没说位置时，先问城市/地标，不要编造门店。
2. 用 `query-meals`（`storeCode` + `orderType=1` + `beType=1`）拿实时菜单与价格。
3. 用 `list-nutrition-foods` 拿营养库。
4. 把三份返回写入 `data/raw/`，执行 `python scripts/build_index.py` 生成索引。
   > 只有第 0 步探测成功、或者用户明确选择用快照时，才走这条路径。
   > 若用户已提供 `data/index.json` 且门店一致，可直接复用，跳过 2–4 步。

### 第 3 步 · 求解

```bash
python scripts/adviser.py --budget <预算> --people <人数> --mode <模式> \
    [--no-beef] [--no-spicy] [--max-kcal N] [--min-protein N] [--top 3] [--json]
```

引擎会枚举组合并施加硬约束，输出按得分排序的 Top-K。**不要手工改写引擎算出的价格与营养数字。**
要改方案，就改参数重跑。

**用户说的是「想吃到某几样」而不是「给我配一餐」时，走按意图比价：**

```bash
python scripts/adviser.py --intent "巨无霸+薯条+可乐"            # 单点 vs 组合，差多少
python scripts/adviser.py --intent "巨无霸+薯条+可乐" --member   # 换会员价口径再比一次
```

这条路径回答的是「你多花了多少钱」：同一批商品，逐个单点 vs 本门店已有的组合商品。
**两侧必须同一价格口径**，否则差额不成立。

> **价格有三种口径，默认只认无条件价。** `query-meals` 的 `discountType` 区分为
> `standard`（无条件）/ `promo`（限时促销）/ `member`（**需麦金卡会员身份**）。
> 会员价默认排除，只有用户明确持卡时才用 `--member` 纳入 ——
> 把会员价当普通价报给没卡的人，是错误而非近似。
> 呈现时若用了会员价，必须写明「需麦金卡」。

### 第 3.5 步 · 门店标价（用户问「有没有折扣 / 便宜了多少」时）

```bash
python scripts/adviser.py --discounts
```

这是**第三种口径**：门店划线价 − 现价。它不是「你省了多少钱」——用户本来也不会按划线价买。
呈现时必须说清这是门店标价口径，**不得与结构省、券后省相加**。

### 第 4 步 · 券的口径（用户提到券、或问"我的券怎么用"时）

**券不是"可用资源"，是有保质期的钱。** 不要凭券名猜面值，按下面的优先级来：

1. 有券码时：把券自带商品码 + `couponId` + `couponCode` 传给 `calculate-price`，
   返回的 `discount`（单位**分**）就是这张券的**精确价值**。
2. 没券码时：从菜单反查原价（买一送一/免费券 = 商品单价；固定价券 = 原价 − 固定价；满减券 = 减免额）。
3. **两条都走不通时，如实说"价值未知"，绝不估一个看起来合理的数。**

```bash
python scripts/adviser.py --budget <预算> --mode <模式> --coupons   # 在方案上标注本单可用的券
python scripts/coupon_doctor.py --budget <预算>                    # 券包体检 + 消费审计 + 用券排程
```

三条假设（基准消费 = 本单方案总价；窗口内还会点 K 单；每单最多用 1 张券）见
[`docs/COUPON_METHOD.md`](docs/COUPON_METHOD.md)。

> **点单频率默认来自订单实测**：`order-list` 的返回必须先经 `--sanitize` 洗成
> 「本地脱敏快照 + 可提交派生摘要」，**仓库里只放派生指标，不放逐单明细**。
> `--no-orders` 可回到 3 单/周的假设模式。

> **不擅自替用户领券。** 领取会改动账号状态，必须先取得用户明确同意；
> 本工具负责把"有哪些没领、值不值"摆清楚。

### 第 5 步 · 呈现

用表格或清单展示每套方案的：商品与数量、总价（含券后）、人均营养、推荐理由。
**必须同时给出免责说明**：价格为门店快照口径、券需核验、营养为估算的需注明、
券价值"未知"的不得写成 0。

### 第 6 步 · 下单（用户明确要下单时才做）

1. 用 `calculate-price` 复核最终价格（返回单位为"分"，需除以 100）。
2. 用户确认后，用 `create-order` 下单（`takeWayCode` 取自 `calculate-price` 的 `takeWayList[].code`）。
3. 把 `adviser.py --json` 输出的 `order_items` 直接作为 `items` 入参，不要重新拼商品码。

## 边界与红线

- 不虚构商品、价格、门店、券信息；接口报错就如实说明。
- **MCP 取数不可用时必须主动提醒用户去配 Token**（见第 0 步），不许静默降级到快照，
  也不许在没说明数据口径的情况下继续给方案。
- **价格口径不得混用。** 需麦金卡才拿得到的价格（`priceTier=member`）默认不参与推荐；
  要用就必须先确认用户持卡，并在输出里写明「需麦金卡」。三种口径
  （结构省 / 券后省 / 标价差）各自成立，**不得相加**。
- **营养代餐不是商品身份。** 内容随机的盲盒商品与靠相近单品估算营养的商品，
  只能说营养，不能说「这单里有某商品」——本项目用 `identity` 区分，不要绕过它。
- **券的价值没有来源就说"未知"**，不得填 0 或估一个数；领取券（`auto-bind-coupons`）是写操作，
  必须先取得用户明确同意。
- 不承诺"最健康""疗效"等结论，营养数据仅供参考，不构成医疗或营养建议。
- 不诱导超量点餐；推荐需符合均衡与节约原则。
- MCP Token 只放环境变量，禁止写入仓库或日志。
