# cn_stock — China A-Share Market Data

Tool package providing real-time and historical market data for Chinese A-shares
(Shanghai / Shenzhen / Beijing exchanges), backed by [akshare](https://akshare.akfamily.xyz/).

## Tools

| Tool | Purpose |
|---|---|
| `get_quote` | Real-time spot quote for one or more A-shares (price, change %, volume, P/E, P/B, market cap). |
| `get_kline` | Daily / weekly / monthly OHLCV bars for a single A-share, with forward/back adjustment. |
| `get_index` | Spot value (and optional 30-day history) for major Chinese stock indices (上证, 深证, 创业板, 沪深300, ...). |
| `get_board` | Industry / concept board snapshot ranked by intraday % change. |
| `get_capital_flow` | Net capital inflow/outflow for an individual stock or the whole market. |
| `get_news` | Recent news for a specific A-share, or top macro financial headlines. |
| `get_announcement` | Listed-company announcements (公告) for a given trading day. |
| `get_financials` | Key financial metrics (EPS, ROE, revenue, margins) by reporting period. |
| `is_trading_day` | Whether a given calendar date is an A-share trading day. Always call at the start of a scheduled task — cron triggers do not skip holidays. |

## Operational notes

- All akshare calls are blocking; the base class wraps them in `asyncio.to_thread`.
- Results are short-TTL cached in Redis (5–60s for live quotes, longer for kline/financials)
  to absorb retry storms — akshare scrapes free public endpoints which rate-limit by IP.
- A category-level global rate limit of 60 calls/min protects shared infrastructure.
- Stock codes are normalized: accepts `600519`, `sh600519`, `SH600519`, `600519.SH`.
- Symbols not yet listed or recently delisted may return empty data; tools raise
  `ToolException` with a clear message rather than silently returning empty results.

## Composition

These tools are designed to be used by **leaf** public agents (one per data domain),
which a team-built monitor agent can orchestrate via `lead_call_agent`. See the
public-agent YAMLs in `public_agents/base/cn-*.yaml` for working examples.
