# 报名与提交检查清单

> 依据：[`activityGuidelines.md`](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)
> 本文只做核对，规则以官方原文为准。

---

## 一、时间

| 项 | 时间（北京时间） |
|---|---|
| 活动时间 | 2026-10-09 10:30 — 2026-10-25 23:59 |
| **报名截止** | 2026-10-25 23:59 |
| **排行榜数据截止** | 2026-10-26 00:00 |

**排名依据**：截至 2026-10-26 00:00 项目累计获得的**公开 Star 总数**。
活动开始前已获得的 Star 也计入。

## 二、仓库要求

- [ ] 仓库**公开可访问**
- [ ] 仓库创建时间在 **2025-12-25 00:00 — 2026-10-25 23:59** 之间
- [ ] 项目**真实使用**麦当劳 MCP 能力
- [ ] 参与 WorkBuddy 专项奖励的，项目**真实使用**腾讯 WorkBuddy 并提交 `workbuddy.md`

### 必备文件

- [x] `README.md` —— 项目介绍、安装方法、使用示例、目标用户
- [x] `CONTEST_DECLARATION.md` —— 参赛声明（原创性 / 合规性 / 敏感信息）
      ⚠️ 官方文本**一个字符都不能改**
- [x] `MCP_INTEGRATION.md` —— 实际使用的 MCP Server、Tool、调用流程与业务价值
- [x] `mcp-config.example.json` —— 脱敏配置示例，只允许环境变量占位符
- [x] `workbuddy.md` —— WorkBuddy 对话上下文（专项奖励用）

## 三、报名 Issue

在活动页面按指定模板提交，格式参照官方示例：

```text
【参赛申请】
项目名称：麦麦点餐参谋
项目地址：https://github.com/pandasir/mcd-value
项目简介：……
```

- [ ] 三项信息齐全：项目名称 / 项目地址 / 项目简介
- [ ] 项目地址写成**纯 URL**（不要用 Markdown 链接语法 `[文字](url)`），与官方示例保持一致
- [ ] 提交前再点一次链接，确认能公开打开
- [ ] 提交后留意 Issue 回复，确认收到参赛确认

## 四、合规红线（官方原文归纳）

提交前逐条自查：

- [ ] 不宣扬**不健康饮食方式**、奢靡浪费、拜金主义、娱乐至上
      → 本项目不做"薅券薅奖"式炫技，所有推荐遵守均衡与节约原则
- [ ] 不将麦当劳品牌、产品**与其他品牌对比**，不贬低麦当劳形象
- [ ] 不出现政治敏感、违法违规、公序良俗相关内容
- [ ] 不侵害第三方知识产权、隐私权、商业秘密
- [ ] **不刷 Star**：机器人、脚本、多账号、群控等一律取消资格
- [ ] 项目为原创或已取得合法授权
- [ ] 仓库与 Issue 里**不含任何真实 Token 或个人数据**

## 五、逐项自查命令

```bash
# 1) 五个必备文件是否齐备
for f in README.md CONTEST_DECLARATION.md MCP_INTEGRATION.md \
         mcp-config.example.json workbuddy.md; do
  [ -f "$f" ] && echo "✅ $f" || echo "❌ 缺失 $f"
done

# 2) 官方参赛声明是否被改动过（应输出空）
curl -sL https://raw.githubusercontent.com/M-China/mcd-developer-innovation-challenge/main/CONTEST_DECLARATION.md | diff - CONTEST_DECLARATION.md

# 3) 全流程可跑（评审也会这么验）
python scripts/build_index.py
python scripts/style_check.py
python -m unittest discover -s tests -v
python demo.py

# 4) 凭据扫描（应无输出）
grep -rn "Bearer [A-Za-z0-9]\{10,\}" . | grep -v MCD_MCP_TOKEN
```

## 六、报名之后的持续交付

排名只看 Star，**报名不是终点**。以下动作在报名后同样计入：

- 继续完善项目（每次提交都会出现在仓库活动时间线上）
- 在真实渠道分享：V2EX、掘金、即刻、小红书、少数派、开发者社群
- 把 README 的第一屏当作转化漏斗来打磨（30 秒体验 → 一张图 → 一个刺点）

> 说明：以上是本站对规则的理解，不构成对活动规则的解释。如有疑问以官方原文与麦当劳公告为准。
