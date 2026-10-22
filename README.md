<div align="center">

# McDonald's Ordering Strategist

The same meal can cost a dozen yuan more depending on how you order it.

Say you want a Big Mac, fries, and a Coke. Ordered the obvious way it costs ¥48.5. Ordered a different way it costs ¥36.5, so you overpaid ¥12.0.

![Same intent, two ways to buy: obvious order ¥48.5, better order ¥36.5](assets/demo-dual-view.svg)

The items are identical: the same fries and the same Coke.

<a href="https://github.com/pandasir/mcd-value/stargazers"><img src="https://img.shields.io/badge/%E2%AD%90_Star-this_repo-DA291C?style=for-the-badge&logo=github&logoColor=white" alt="Star this repo" height="28"></a> · <a href="https://pandasir.github.io/mcd-value/">Live demo (no token)</a>

</div>

---

<div align="center">

Tell it what you want to eat, your budget, and whether you are cutting fat or avoiding certain ingredients, in plain language. It lists every way to buy that meal at this store and shows which one is cheaper, where you are overpaying, and how your coupons apply.

![tests](https://github.com/pandasir/mcd-value/actions/workflows/tests.yml/badge.svg)
![license](https://img.shields.io/badge/license-MIT-green)
![mcp](https://img.shields.io/badge/MCP-mcd.cn-DA291C)

[Live demo](https://pandasir.github.io/mcd-value/) · [What it is](#what-it-is) · [How much you can save](#three-places-you-overpay-every-day) · [Install](#installation) · [How to use](#how-to-use) · [Who it's for](#who-its-for) · [Caveats](#caveats)

<sub>Entry for the McDonald's Programmer Creative Development Contest · Not an official McDonald's product · MIT</sub>

</div>

---

## What it is

It is a McDonald's ordering strategist. You tell it, "I want a Big Mac, fries, and a Coke. What is the cheapest way to order that?" and it does three things:

1. It pulls the real menu for your store, so the prices are that store's prices for that day rather than items recalled from memory.
2. It puts every way to buy the same items side by side, including à la carte, combos, and bundles, so you can see which is cheaper.
3. It factors in the coupons you already have: what each is worth, which to use first, and which will expire unused.

It does not guess or estimate. If it cannot compute something, it says so.

> Also known as: McDonald's Ordering Strategist / McDonald's Savings Assistant / Fat-loss Ordering Helper / MCD Value Strategist.

---

## Three places you overpay every day

The three examples below come from the real menu snapshot of one store, Shenzhen Tongfang Information Port, captured on 2026-10-14. The numbers are that store's listed prices.

### Same items, bought a different way, save ¥12.0

```
À la carte    Big Mac ¥25.5 + Fries ¥13.5 + Coke ¥9.5   = ¥48.5
Other way     "Big Mac Trio" ×1                         = ¥36.5
                                                        ─────────
You overpaid                                            ¥12.0
```

People who order the trio pay 12 yuan less and get exactly the same three items.

The menu has 12 verified comparisons between a single burger and its matching trio, and every trio costs exactly ¥12.0 less. The combo discount is fixed at this store regardless of the item:

```
Spicy Chicken Burger Trio      Combo ¥33.5  <  Items separately ¥45.5   → Save ¥12.0
Double Beef Burger Trio        Combo ¥37.5  <  Items separately ¥49.5   → Save ¥12.0
Big Mac Trio                   Combo ¥36.5  <  Items separately ¥48.5   → Save ¥12.0
Bacon Veggie Double Beef Trio  Combo ¥35.5  <  Items separately ¥47.5   → Save ¥12.0
```

### Your coupons expire before you can use them

A coupon is money with an expiration date.

Coupon names often do not state an amount. The name "Ace Snack Platter" says nothing about value, and the menu has no such item. The only way to measure the coupon's face value is to price it at the store.

For one account, the measurement came out like this:

```
[Ready to use]  Medium fries buy-one-get-one    worth ¥13.5 · 3 days left
[Ready to use]  13.9 Rich Dark Chocolate        worth ¥7.1  · 6 days left
[Ready to use]  Ace Snack Platter               worth ¥6.1  · 3 days left
[Unclear]       6 breakfast coupons             amount can't be inferred from names, so we don't guess

Nominal total ¥26.7, all achievable at your spending level, so it looks good.

But look at your ordering habits: 8 orders over 212 days, average ticket ¥23.6, 0.26 orders/week.
These coupons expire in 6 days, meaning you'll likely place only 1 more order.

The coupon wallet can deliver ¥26.7, but you only have enough opportunities to use ¥13.5.
The remaining ¥13.2 is guaranteed to expire unused. Wasted.
```

The useful distinction is between what a coupon is worth and whether you will use it. An assistant that sums only the face value tells you that you have ¥26.7 in coupons. This one tells you that you can use ¥13.5 and that the other ¥13.2 will go to waste.

> The ordering frequency comes from your own order history of 8 real orders, not from an assumption. If we assumed three orders a week, the conclusion would change from "waste ¥13.2" to "almost no waste." A wrong assumption produces wrong advice.

### "More portions for less money" comes with conditions

The menu has 8 cases where the trio costs more than the quartet:

```
Bacon Angus Thick Beef Burger   Trio ¥45.5  >  Quartet ¥37.0   → Save ¥8.5, plus an extra item
Grilled Chicken Burger          Trio ¥34.5  >  Quartet ¥28.0   → Save ¥6.5
Big Mac                         Trio ¥36.5  >  Quartet ¥32.0   → Save ¥4.5
```

In all 8 cases, the quartet price requires McGold Card membership.

People without the card cannot get that price, so for them there is no loophole, only a saving of ¥3 to ¥6.5 per order with the card.

By default the project recommends using prices anyone can pay. Member prices are included only when you ask for them, because every conclusion should hold for people without the card too.

---

## Installation

There are three installation paths. Use Option 1 or 2 if you want the live menu of your usual store. Option 3 is the quickest way to see what the project computes.

| What you want | Which option | What you need |
|---|---|---|
| Use it inside **WorkBuddy** | Option 1 | A WorkBuddy account + an MCP token |
| Use it in **Claude / Cursor / VS Code / Cline / Windsurf**, etc. | Option 2 | Any MCP-capable client + an MCP token |
| No AI client, just run commands yourself | Option 3 | Python (3.9+) |

---

Get a McDonald's MCP token first (required for Options 1 and 2).

Open the [McDonald's MCP Open Platform](https://open.mcd.cn/mcp), sign in with your phone number, and go to "Console". Click "Activate" and copy the token, which is a long string like `xxxxxxxx-xxxx-...`. It is free.

---

### Option 1 · Use it in WorkBuddy

Step 2: Put the token into WorkBuddy

Open WorkBuddy's [Connectors → Custom Connectors → Configure MCP] and paste the contents of [`mcp-config.example.json`](mcp-config.example.json). Replace `Bearer ${MCD_MCP_TOKEN}` with `Bearer <the token you copied>`:

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

After you save, an `mcd-mcp` entry appears in the top right of the connectors page. Click "Trust" next to it to enable it.

Step 3: Install this skill

Put the project folder in WorkBuddy's skills directory. On macOS or Linux, run:

```bash
ln -s "$(pwd)" ~/.workbuddy/skills/mcd-meal-adviser
```

Windows users: copy the whole project folder to `%USERPROFILE%\.workbuddy\skills\mcd-meal-adviser`.

Step 4: Start using it

Once it is installed, go back to the chat window and say, "I want a Big Mac, fries, and a Coke. What is the cheapest way to order that?"

The "How to use" section below lists more examples you can say directly.

> If you install with a symlink (`ln -s`), later `git pull` updates reach the skill automatically, so you do not install it again.

---

### Option 2 · Use it in Claude / Cursor / VS Code, etc.

Get the token first. Every client uses the same data channel; only the config file and the field names differ. Find your client in the table.

| Client | Where the config goes | How the field names differ |
|---|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`) | Top level is `mcpServers` |
| Claude Code | No file editing, run one command | N/A |
| Cursor | Global `~/.cursor/mcp.json`, or project `.cursor/mcp.json` | Only `url` + `headers` |
| VS Code (Copilot) | Project `.vscode/mcp.json` | Top level is `servers`, not `mcpServers` |
| Cline | Fill in via the extension panel; no file editing | Type is `streamableHttp` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | Use `serverUrl`, not `url` |

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

After editing, quit the app completely and restart it. Closing the window is not enough, because the config is read only at startup.

If your version does not support the direct connection above, this proxy form works the same way:

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

**Claude Code**: run one command in the terminal:

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

Put it in the global `~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`), or in the project's `.cursor/mcp.json`. After saving, click refresh in the MCP panel.

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

**Cline**: no file editing. Open the extension's MCP Servers panel, choose Add Remote Server, set the URL to `https://mcp.mcd.cn`, the header name to `Authorization`, and the header value to `Bearer YOUR_TOKEN`.

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

Other clients (Gemini CLI, etc.) follow the same pattern: set the URL to `https://mcp.mcd.cn`, then add an `Authorization: Bearer YOUR_TOKEN` request header.

Step 3: Check the connection

Ask "List the McDonald's tools you can use." If it names a set of tools, the connection works.

Step 4: Make it compute the way this project does

What you installed is only the data channel. [`SKILL.md`](SKILL.md) in the same directory defines how to compute: which data to fetch first, what the hard constraints are, and which numbers must not be invented. Open the project directory as your working directory, then tell it:

> Read SKILL.md first, then follow its workflow strictly.

If you want it to read this automatically every time, put that sentence into the client's project rules file (Claude Code uses `CLAUDE.md`, Cursor uses `.cursor/rules`, many other clients use `AGENTS.md`).

---

### Option 3 · No AI client, just run it

You need only Python 3.9 or later. No token, network access, or account registration is required:

```bash
git clone https://github.com/pandasir/mcd-value && cd mcd-value

python scripts/adviser.py --budget 45 --mode balanced   # a balanced meal for 45 yuan
python scripts/coupon_doctor.py --budget 45             # coupon wallet checkup + usage schedule
python demo.py                                          # the three examples above, seven scenarios in one run
python scripts/build_pages.py                           # pre-render comparisons into the web page (crawler-readable)
```

> The 12 lines of numbers in the web demo (`docs/index.html`) are generated. Don't edit them by hand. After changing `data/`, run `build_demo.py` and `build_pages.py`. CI checks that both sides come from the same source.

It reads a real store snapshot bundled with the project, captured on 2026-10-14 and anonymized. The snapshot contains no personal information.

> If your system only has `python3` and no `python` (the macOS default), replace `python` in the commands with `python3`.

To use your own usual store, configure the token with Option 1 or 2 and tell the assistant which store you want. It will fetch that store's live menu. See [`docs/TOKEN_GUIDE.md`](docs/TOKEN_GUIDE.md) for the full data-fetching steps.

---

## How to use

Talk in plain language in the chat window. There are no commands to memorize.

"I want a Big Mac, fries, and a Coke. What is the cheapest way to order that?"

À la carte the three items cost ¥48.5. This store's "Big Mac Trio" includes all three for ¥36.5, so you overpaid ¥12.0. With the card, the price can go down to ¥32.0.

"What can I eat at McDonald's for 30 yuan?"

It returns several ways to order within a 30-yuan budget, with calories and protein for each, and notes where each is expensive or cheap.

"I'm cutting fat, no beef and nothing fried, within 45 yuan."

It excludes the restricted ingredients rather than trying to avoid them. The result is a meal of 559 kcal, 20g protein, and 558mg sodium.

"How should I use these coupons in the next few days?"

It measures what each coupon is worth, orders them by your real ordering frequency, and says which ones will go unused.

"Four of us eating together, 150 yuan total."

It returns a meal plan for the table within the total budget.

---

## Why its numbers are trustworthy

Any AI can give a professional-sounding answer to the same question. In most such answers the items, prices, and nutrition are made up.

| | Typical approach | McDonald's Ordering Strategist |
|---|---|---|
| Items | Generated from memory; names don't match the store | Real store menu; names and prices match |
| Prices | Estimated | Real store listed prices; re-checked again before ordering |
| Nutrition | Said from memory | Official nutrition database; combos derived from components and labeled as estimates |
| Savings | Vague | States which kind of saving it is; different bases are never added together |
| Whether you can eat it | Model weighs it up itself | Budget, calories, protein, and restrictions are hard constraints; fail one and the item is out |
| When it can't compute | Forces out a number | Says "unclear" directly |

The AI handles the language. A deterministic calculation handles the money.

### How "how much you saved" is counted

The same meal can produce three different figures, and they are easy to blend. The rule is:

- Accepted: money saved by buying the same items a different way. Both sides are real current prices at this store, so the figure is certain.
- Accepted: money actually deducted by coupons. This is measured by pricing the coupon at the store. It is certain, but subject to verification in the store.
- Labeled separately and never added to the figures above: the store's struck-through price minus the current price.

The third figure is not counted because you would not have bought at the struck-through price anyway. Using that price as a baseline makes the saving look larger than it is.

---

## Who it's for

Office workers and students on a fixed daily budget want the cheapest way to order this meal. People cutting fat or building muscle have calorie and protein targets and need combinations that meet them. People with dietary restrictions do not want to check the menu item by item for beef, spice, or caffeine. People with many coupons need to know which to use first and which will go unused. Anyone ordering for a group needs to feed a table within a total budget.

---

## Caveats

- Prices are a snapshot from that day. Demo data comes from the 2026-10-14 store snapshot; actual prices and availability are subject to the store or app.
- Nutrition involves estimates. Nutrition for combo items is derived from components, and the output labels it as an estimate. Sauces and some new items have no nutrition data and are excluded.
- Coupons have limits. Few coupons reveal their amount in the name; ones we cannot infer are marked "unclear" rather than given a made-up number. Eligibility and stacking rules are subject to the store.
- Spending analysis looks only at how often you order and how much you spend. It does not analyze what you like, and it does not store your order details.
- This is not nutrition or medical advice. Data and conclusions are for reference only.

---

## Found something that doesn't match?

If a price, combo composition, coupon amount, or nutrition value does not match what you see in the store, say so.

Snapshots expire, stores change prices, and combos get restructured, so these reports are the only way to fix them.

- [Report a miscalculation](https://github.com/pandasir/mcd-value/issues/new?template=price-report.yml): which store, which conclusion, and what you saw
- [I want my store](https://github.com/pandasir/mcd-value/issues/new?template=store-request.yml): tell us the city and store, and we will prioritize adding it

---

## Disclaimer

This project is an entry for the "McDonald's Programmer Creative Development Contest," independently developed by the contestant, and is not an official McDonald's product.
Output is for reference only and does not constitute medical, nutritional, or other professional advice; item information, prices, and availability are subject to real-time results from official McDonald's channels.
Use of McDonald's MCP services is subject to its Terms of Use and McDonald's MCP Service Rules.

MIT License (see [LICENSE](LICENSE)).

If it saves you the price of a Coke, a star is welcome.

---

[中文版 README](README.zh-CN.md)
