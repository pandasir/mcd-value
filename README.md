<div align="center">

# McDonald's Ordering Strategist

**Same meal, different way to buy it — and it can differ by a dozen yuan.**

Say you want a "Big Mac + fries + Coke" —

Order the obvious way **¥48.5** 　→　 Order it a different way **¥36.5** 　→　 You overpaid **¥12.0**

![Same intent, two ways to buy: obvious order ¥48.5, better order ¥36.5](assets/demo-dual-view.svg)

Identical items. You even get the same fries and the same Coke.

<a href="https://github.com/pandasir/mcd-value/stargazers"><img src="https://img.shields.io/badge/%E2%AD%90_Star-this_repo-DA291C?style=for-the-badge&logo=github&logoColor=white" alt="Star this repo" height="28"></a>

</div>

---

<div align="center">

Tell it what you want to eat, your budget, whether you're cutting fat or avoiding certain ingredients —
in plain language. It lays out every way to buy that meal at this store, tells you which one is cheaper,
where you're overpaying, and how to use your coupons.

![tests](https://github.com/pandasir/mcd-value/actions/workflows/tests.yml/badge.svg)
![license](https://img.shields.io/badge/license-MIT-green)
![mcp](https://img.shields.io/badge/MCP-mcd.cn-DA291C)

[Live demo](https://pandasir.github.io/mcd-value/) · [What it is](#what-it-is) · [How much you can save](#three-places-you-overpay-every-day) · [Install](#installation) · [How to use](#how-to-use) · [Who it's for](#who-its-for) · [Honest notes](#a-few-honest-notes)

<sub>Entry for the McDonald's Programmer Creative Development Contest · Not an official McDonald's product · MIT</sub>

</div>

---

## What it is

A **McDonald's ordering strategist**.

You tell it: "I want a Big Mac + fries + Coke. What's the cheapest way to order that?"

It does three things:

1. **Pulls the real menu for your store** — no making up items from memory; the prices are that store's prices for that day;
2. **Puts every way to buy the same items side by side** — à la carte, combos, bundles — so you can see at a glance which is cheaper;
3. **Factors in the coupons you already have** — how much each is worth, which to use first, and which are doomed to expire.

It **doesn't guess, doesn't invent, doesn't estimate**. If it can't compute something, it says so.

> Also known as: McDonald's Ordering Strategist / McDonald's Savings Assistant / Fat-loss Ordering Helper / MCD Value Strategist.

---

## Three places you overpay every day

The three examples below all come from the **real menu snapshot (2026-10-14) of one store (Shenzhen Tongfang Information Port)**.
The numbers aren't cherry-picked — they're that store's actual listed prices.

### ① Same items, a different way to buy saves ¥12.0

```
À la carte    Big Mac ¥25.5 + Fries ¥13.5 + Coke ¥9.5   = ¥48.5
Other way     "Big Mac Trio" ×1                         = ¥36.5
                                                        ─────────
You overpaid                                            ¥12.0
```

People who order the trio pay 12 yuan less and get exactly the same three items.

This isn't a one-off. Scanning the whole menu: **13 combos whose items can each be ordered individually — all 13 are cheaper, and every single one is cheaper by exactly ¥12.0** —
the combo discount is fixed at this store, regardless of items:

```
Spicy Chicken Burger Trio      Combo ¥33.5  <  Items separately ¥45.5   → Save ¥12.0
Double Beef Burger Trio        Combo ¥37.5  <  Items separately ¥49.5   → Save ¥12.0
Big Mac Trio                   Combo ¥36.5  <  Items separately ¥48.5   → Save ¥12.0
Bacon Veggie Double Beef Trio  Combo ¥35.5  <  Items separately ¥47.5   → Save ¥12.0
```

### ② Your coupons are quietly leaking value

Coupons aren't "resources you hold" — they're **money with an expiration date**.

The trouble is that coupon names often don't state an amount. How much is the "Ace Snack Platter" coupon worth?
The name doesn't say, and the menu has no such item — its true face value can only be measured by taking the coupon to the store and pricing it.

For one account, the measurement came out like this:

```
[Ready to use]  Medium fries buy-one-get-one    worth ¥13.5 · 3 days left
[Ready to use]  13.9 Rich Dark Chocolate        worth ¥7.1  · 6 days left
[Ready to use]  Ace Snack Platter               worth ¥6.1  · 3 days left
[Unclear]       6 breakfast coupons             amount can't be inferred from names, so we don't guess

Nominal total ¥26.7, all achievable at your spending level — looks good.

But look at your ordering habits: 8 orders over 212 days, average ticket ¥23.6, 0.26 orders/week.
These coupons expire in 6 days, meaning you'll likely place only 1 more order.

The coupon wallet can deliver ¥26.7, but you only have enough opportunities to use ¥13.5 —
the remaining ¥13.2 is guaranteed to expire unused. Wasted.
```

**This is the most valuable thing about this table: how much a coupon is worth and whether you'll actually use it are two completely different questions.**
An assistant that only sums "total face value" will tell you "you have ¥26.7 in coupons";
this one tells you "you can only use ¥13.5, and the other ¥13.2 will be wasted."

> That ordering frequency isn't made up — it's computed from your own order history (8 real orders).
> With an assumed "3 orders per week," the conclusion flips from "waste ¥13.2" to "almost no waste" — **wrong assumptions produce wrong advice.**

### ③ "More portions for less money" comes with conditions

The menu has 8 cases where "the trio costs more than the quartet":

```
Bacon Angus Thick Beef Burger   Trio ¥45.5  >  Quartet ¥37.0   → Save ¥8.5, plus an extra item
Grilled Chicken Burger          Trio ¥34.5  >  Quartet ¥28.0   → Save ¥6.5
Big Mac                         Trio ¥36.5  >  Quartet ¥32.0   → Save ¥4.5
```

Looks like a menu loophole? **In all 8 cases, the quartet side requires McGold Card membership.**

People without the card can't get that price. So for them there's no "loophole" here —
only "with the card, you'd save ¥3–¥6.5 per order."

**This project recommends by default using "prices anyone can pay."** Member prices are included only when you explicitly ask for them.
The reason is simple: **every conclusion must hold for people without the card, too.**

---

## Installation

Three paths — pick the one that fits you. **If you want the live menu of your usual store, use Option 1 or 2; if you just want to see what it computes, Option 3 is the easiest.**

| What you want | Which option | What you need |
|---|---|---|
| Use it inside **WorkBuddy** | Option 1 | A WorkBuddy account + an MCP token |
| Use it in **Claude / Cursor / VS Code / Cline / Windsurf**, etc. | Option 2 | Any MCP-capable client + an MCP token |
| No AI client — just run commands yourself | Option 3 | Python (3.9+) |

---

**Do this first (required for Options 1 and 2)　Get a McDonald's MCP token**

Open the [McDonald's MCP Open Platform](https://open.mcd.cn/mcp) → sign in with your phone number → go to "Console" →
click "Activate" → copy the token (it's long, like `xxxxxxxx-xxxx-...`). It's free.

---

### Option 1 · Use it in WorkBuddy

**Step 2　Put the token into WorkBuddy**

Open WorkBuddy's [Connectors → Custom Connectors → Configure MCP],
paste the entire contents of [`mcp-config.example.json`](mcp-config.example.json) from the project,
and just replace `Bearer ${MCD_MCP_TOKEN}` with `Bearer <the token you just copied>`:

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

After saving, an `mcd-mcp` entry appears in the top-right of the connectors page. Click "**Trust**" next to it to enable it.

**Step 3　Install this skill**

Put the project folder into WorkBuddy's skills directory. On macOS / Linux, one command:

```bash
ln -s "$(pwd)" ~/.workbuddy/skills/mcd-meal-adviser
```

Windows users: copy the whole project folder to `%USERPROFILE%\.workbuddy\skills\mcd-meal-adviser`.

**Step 4　Start using it**

Once installed, you're ready. Go back to the chat window and say:
**"I want a Big Mac + fries + Coke — what's the cheapest way to order that?"**

The "How to use" section below lists more examples you can say directly.

> Installing with a symlink (`ln -s`) in the skills directory means that later `git pull` updates
> flow into the skill automatically — no second install needed.

---

### Option 2 · Use it in Claude / Cursor / VS Code, etc.

Get the token as described above first. They all install the same "data channel";
the only differences are **which file each client's config goes in and how the fields are named** — just find yours.

| Client | Where the config goes | How the field names differ |
|---|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`) | Top level is `mcpServers` |
| Claude Code | No file editing — run one command | N/A |
| Cursor | Global `~/.cursor/mcp.json`, or project `.cursor/mcp.json` | Only `url` + `headers` |
| VS Code (Copilot) | Project `.vscode/mcp.json` | Top level is `servers` (**not** `mcpServers`) |
| Cline | Fill in via the extension panel; no file editing | Type is `streamableHttp` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | Use `serverUrl` (**not** `url`) |

**Claude Desktop**

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamable-http",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

After editing, **quit completely and restart** (closing the window isn't enough; config is read only at startup).

If your version doesn't support the direct connection above, this "proxy" form works the same:

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.mcd.cn",
               "--header", "Authorization: Bearer YOUR_TOKEN"]
    }
  }
}
```

**Claude Code** — one command in the terminal:

```bash
claude mcp add --transport http mcd-mcp https://mcp.mcd.cn \
  --header "Authorization: Bearer YOUR_TOKEN"
```

**Cursor**

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

Put it in the global `~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`),
or in the project's `.cursor/mcp.json`. After saving, click refresh in the MCP panel.

**VS Code (Copilot)**

```json
{
  "servers": {
    "mcd-mcp": {
      "type": "http",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

Put it in the project's `.vscode/mcp.json`.

**Cline** — no file editing: open the extension's MCP Servers panel → Add Remote Server,
set the URL to `https://mcp.mcd.cn`, header name `Authorization`, header value `Bearer YOUR_TOKEN`.

**Windsurf**

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "serverUrl": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

Other clients (Gemini CLI, etc.) follow the same pattern: set the URL to `https://mcp.mcd.cn`,
then add an `Authorization: Bearer YOUR_TOKEN` request header.

**Step 3　Check that it's connected**

Just ask "List the McDonald's tools you can use." If it names a set of tools, you're connected.

**Step 4　Make it compute the way this project does**

What you installed above is only the "data channel." [`SKILL.md`](SKILL.md) in the same directory defines **how to compute**
(which data to fetch first, what the hard constraints are, which numbers must not be invented). Open the project directory as your working directory, then tell it:

> Read SKILL.md first, then follow its workflow strictly.

If you want it to read this automatically every time, put that sentence into the client's project rules file
(Claude Code uses `CLAUDE.md`, Cursor uses `.cursor/rules`, many other clients use `AGENTS.md`).

---

### Option 3 · No AI client — just run it

Only Python (3.9+) needed. **No token, no network, no account registration**:

```bash
git clone https://github.com/pandasir/mcd-value && cd mcd-value

python scripts/adviser.py --budget 45 --mode balanced   # a balanced meal for 45 yuan
python scripts/coupon_doctor.py --budget 45             # coupon wallet checkup + usage schedule
python demo.py                                          # the three examples above, seven scenarios in one run
python scripts/build_pages.py                           # pre-render comparisons into the web page (crawler-readable)
```

> The 12 lines of numbers in the web demo (`docs/index.html`) are **generated**; don't edit them by hand.
> After changing `data/`, run `build_demo.py` + `build_pages.py`; CI verifies both sides come from the same source.

It reads a **real store snapshot** bundled with the project (captured 2026-10-14, anonymized, containing no personal information).

> If your system only has `python3` and no `python` (the macOS default),
> replace `python` in the commands with `python3`.

Want to see your own usual store? After configuring the token (Option 1 or 2), just tell it, and it will fetch that store's live menu.
See [`docs/TOKEN_GUIDE.md`](docs/TOKEN_GUIDE.md) for the complete data-fetching steps.

---

## How to use

Just talk in plain language in the chat window — no commands to memorize:

**"I want a Big Mac + fries + Coke. What's the cheapest way to order that?"**
→ À la carte ¥48.5; this store's "Big Mac Trio" includes all three for ¥36.5, so you overpaid ¥12.0. With the card, it can go down to ¥32.0.

**"What can I eat at McDonald's for 30 yuan?"**
→ Several ways to order within a 30-yuan budget, with calories and protein for each, and where each is expensive or cheap.

**"I'm cutting fat, no beef and nothing fried, within 45 yuan."**
→ Dietary restrictions are genuinely excluded, not "avoided where possible." It returns a meal of 559 kcal, 20g protein, and 558mg sodium.

**"How should I use these coupons in the next few days?"**
→ The measured value of each coupon, ordered by your real ordering frequency, and a straight answer on which ones will go unused.

**"Four of us eating together, 150 yuan total."**
→ A meal plan for the table within the total budget.

---

## Why its numbers are trustworthy

Ask any AI the same question and you'll also get a professional-sounding answer.
The difference is that **the items, prices, and nutrition in those answers are mostly made up.**

| | Typical approach | McDonald's Ordering Strategist |
|---|---|---|
| Items | Generated from memory; names don't match the store | Real store menu; names and prices match |
| Prices | Estimated | Real store listed prices; re-checked again before ordering |
| Nutrition | Said from memory | Official nutrition database; combos derived from components, **and labeled as estimates** |
| Savings | Vague | States which kind of saving it is; **different bases are never added together** |
| Whether you can eat it | Model weighs it up itself | Budget, calories, protein, and restrictions are **hard constraints**; fail one and it's out |
| When it can't compute | Forces out a number | Says "unclear" directly |

**In one sentence: the AI understands your needs; the math is left to deterministic computation.**

### On "how much you saved" — bases are never mixed

The same meal can produce three different differences, and it's easy to blend them. Our rule:

- ✅ **Accepted**: money saved by buying the same items a different way. Both sides are real current prices at this store — **certain**.
- ✅ **Accepted**: money actually deducted by coupons. Measured by pricing the coupon at the store — **certain**, but subject to in-store verification.
- ⚠️ **Labeled separately, never added to the above**: the store's "struck-through price − current price."

Why isn't the third one counted? Because **you wouldn't have bought at the struck-through price anyway**.
Using the struck-through price as a baseline can make "savings" look impressive — but it's fake.

---

## Who it's for

- **Office workers / students** — a fixed daily budget; want to know the cheapest way to order this meal
- **People cutting fat or building muscle** — have calorie and protein targets; need combinations that actually deliver, not a feeling
- **People with dietary restrictions** — don't want to scroll the menu one by one checking for beef, spice, or caffeine
- **People with lots of coupons** — need to know which to use first and which won't get used
- **People ordering for a group** — need to feed a table within a total budget

---

## A few honest notes

- **Prices are a snapshot from that day.** Demo data comes from the 2026-10-14 store snapshot; actual prices and availability are subject to the store / app.
- **Nutrition involves estimates.** Nutrition for combo items is derived from components, and outputs clearly label it as an "estimate"; sauces and some new items have no nutrition data and are excluded.
- **Coupons have limits.** Very few coupons reveal their amount in the name; ones we can't infer are marked "unclear" rather than given a made-up number. Eligibility and stacking rules are subject to the store.
- **Spending analysis only looks at "how often and how much."** It doesn't analyze what you like, and it doesn't store your order details.
- **Not nutrition or medical advice.** Data and conclusions are for reference only.

---

## Found something that doesn't match?

Prices, combo composition, coupon amounts, nutrition values — if anything doesn't match what you see in the store, just say so.

Snapshots expire, stores change prices, and combos get restructured. Only real feedback can fix these.

- [Report a miscalculation](https://github.com/pandasir/mcd-value/issues/new?template=price-report.yml) — which store, which conclusion, and what you saw
- [I want my store](https://github.com/pandasir/mcd-value/issues/new?template=store-request.yml) — tell us the city and store; we'll prioritize adding it

---

## Disclaimer

This project is an entry for the "McDonald's Programmer Creative Development Contest," independently developed by the contestant, and is **not an official McDonald's product**.
Output is for reference only and does not constitute medical, nutritional, or other professional advice; item information, prices, and availability are subject to real-time results from official McDonald's channels.
Use of McDonald's MCP services is subject to its Terms of Use and McDonald's MCP Service Rules.

MIT License (see [LICENSE](LICENSE)).

**If it helps you save the price of a Coke, a star is the best feedback.** ⭐

---

[中文版 README](README.zh-CN.md)
