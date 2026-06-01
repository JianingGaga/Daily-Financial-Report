#!/usr/bin/env python3
"""Generate the static daily financial report.

The estimates are proxy based. They are useful for an intraday read, not
official fund NAVs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SINA_REFERER = {"Referer": "https://finance.sina.com.cn"}

STOCKS = [
    {"name": "招商银行", "symbol": "600036.SH", "sina": "sh600036", "bucket": "持仓", "bias": "核心金融仓，继续持有，不因小波动操作。"},
    {"name": "工商银行", "symbol": "601398.SH", "sina": "sh601398", "bucket": "持仓", "bias": "防守高股息，继续持有。"},
    {"name": "广发证券", "symbol": "000776.SZ", "sina": "sz000776", "bucket": "持仓", "bias": "持有观察，券商急涨不追。"},
    {"name": "中国能建", "symbol": "601868.SH", "sina": "sh601868", "bucket": "持仓", "bias": "低弹性仓位，持有观察，避免继续占用过多现金。"},
    {"name": "中远海发", "symbol": "601866.SH", "sina": "sh601866", "bucket": "持仓", "bias": "周期仓，反弹时看是否降风险。"},
    {"name": "中天科技", "symbol": "600522.SH", "sina": "sh600522", "bucket": "已清仓观察", "bias": "不急接回；等 20 日线走平/上行且 5 日线上穿 20 日线。"},
    {"name": "长电科技", "symbol": "600584.SH", "sina": "sh600584", "bucket": "观察", "bias": "半导体高波动，只等低吸条件，不追高。"},
    {"name": "华工科技", "symbol": "000988.SZ", "sina": "sz000988", "bucket": "观察", "bias": "AI/光模块方向，强势只观察，回调到支撑再评估。"},
    {"name": "蔚蓝锂芯", "symbol": "002245.SZ", "sina": "sz002245", "bucket": "观察", "bias": "观察趋势和量能，暂不追涨。"},
    {"name": "南方航空", "symbol": "600029.SH", "sina": "sh600029", "bucket": "观察", "bias": "看油价、汇率和出行数据，低位企稳再考虑。"},
    {"name": "中国移动", "symbol": "600941.SH", "sina": "sh600941", "bucket": "观察", "bias": "稳健候选，估值和位置合适再低吸。"},
    {"name": "沃格光电", "symbol": "603773.SH", "sina": "sh603773", "bucket": "高风险观察", "bias": "高风险观察股；若急涨或涨停，今天只看不追，必须有止损条件。"},
    {"name": "美的集团", "symbol": "000333.SZ", "sina": "sz000333", "bucket": "观察", "bias": "偏稳健候选，等估值和回调位置；20 日线走强再看 520 信号。"},
]

PROXIES = {
    "CSI300": "s_sh000300",
    "CSI500": "s_sh000905",
    "CSI1000": "s_sh000852",
    "CHINEXT": "s_sz399006",
    "SHCOMP": "s_sh000001",
    "SZCOMP": "s_sz399001",
    "NASDAQ": "gb_ixic",
    "SP500": "gb_inx",
    "HSI": "hkHSI",
    "USDCNH": "fx_susdcnh",
}

FUNDS = [
    {
        "name": "易方达全球成长精选混合(QDII)C",
        "code": "012922",
        "amount": 5503.18,
        "weight": 13.69,
        "confidence": "中",
        "proxies": {"NASDAQ": 0.45, "SP500": 0.25, "USDCNH": 0.10},
        "bias": "持有，保留小额定投；涨幅过大时不追加。",
    },
    {
        "name": "易方达信息产业混合A",
        "code": "001513",
        "amount": 7618.10,
        "weight": 18.96,
        "confidence": "低",
        "proxies": {"CHINEXT": 0.35, "SEMIS": 0.30, "SZCOMP": 0.15},
        "bias": "持有，不追涨；若单日大涨优先观察而非加仓。",
    },
    {
        "name": "华夏磐泰混合(LOF)A",
        "code": "160323",
        "amount": 8486.25,
        "weight": 21.12,
        "confidence": "低",
        "proxies": {"CSI300": 0.30, "CSI1000": 0.20},
        "bias": "持有；看估值和仓位，不因单日波动调整。",
    },
    {
        "name": "广发纳斯达克100ETF联接(QDII)C",
        "code": "006479",
        "amount": 1860.62,
        "weight": 4.63,
        "confidence": "中",
        "proxies": {"NASDAQ": 0.85, "USDCNH": 0.10},
        "bias": "保留小额定投；若纳指高位急涨，不额外手动加仓。",
    },
    {
        "name": "国泰海通中证500指数增强C",
        "code": "014156",
        "amount": 972.32,
        "weight": 2.42,
        "confidence": "高",
        "proxies": {"CSI500": 0.90},
        "bias": "保留小额周定投；市场冲高时不放大扣款。",
    },
    {
        "name": "天弘纳斯达克100指数(QDII)A",
        "code": "018043",
        "amount": 1240.34,
        "weight": 3.09,
        "confidence": "中",
        "proxies": {"NASDAQ": 0.85, "USDCNH": 0.10},
        "bias": "持有；与其他纳指基金合并看总敞口。",
    },
    {
        "name": "大成纳斯达克100ETF联接(QDII)A",
        "code": "000834",
        "amount": 3112.64,
        "weight": 7.75,
        "confidence": "中",
        "proxies": {"NASDAQ": 0.85, "USDCNH": 0.10},
        "bias": "重点观察；日定投金额偏大，纳指过热时优先考虑降额。",
    },
    {
        "name": "摩根标普500指数(QDII)A",
        "code": "017641",
        "amount": 803.00,
        "weight": 2.00,
        "confidence": "中",
        "proxies": {"SP500": 0.90, "USDCNH": 0.10},
        "bias": "持有；若美股估值偏热，可考虑降低日扣金额。",
    },
    {
        "name": "博时标普500ETF联接(QDII)A",
        "code": "050025",
        "amount": 151.46,
        "weight": 0.38,
        "confidence": "中",
        "proxies": {"SP500": 0.90, "USDCNH": 0.10},
        "bias": "小仓持有，不需要单独操作。",
    },
    {
        "name": "国泰纳斯达克100指数(QDII)",
        "code": "160213",
        "amount": 300.80,
        "weight": 0.75,
        "confidence": "中",
        "proxies": {"NASDAQ": 0.85, "USDCNH": 0.10},
        "bias": "小仓持有，不追加。",
    },
    {
        "name": "华夏中证5G通信主题ETF联接A",
        "code": "008086",
        "amount": 19.98,
        "weight": 0.05,
        "confidence": "低",
        "proxies": {"CHINEXT": 0.35, "SZCOMP": 0.25},
        "bias": "极小仓，定投金额不放大。",
    },
    {
        "name": "华夏恒生ETF联接(QDII)C",
        "code": "000948",
        "amount": 1592.22,
        "weight": 3.96,
        "confidence": "中",
        "proxies": {"HSI": 0.85, "USDCNH": 0.05},
        "bias": "持有观察；港股波动大，不追涨。",
    },
]


def fetch_sina(codes: list[str]) -> str:
    url = "https://hq.sinajs.cn/list=" + ",".join(codes)
    req = urllib.request.Request(url, headers=SINA_REFERER)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("gb18030", errors="replace")


def parse_lines(raw: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for key, value in re.findall(r"hq_str_([^=]+)=\"([^\"]*)\"", raw):
        parsed[key] = value.split(",")
    return parsed


def parse_stock_quotes(parsed: dict[str, list[str]]) -> tuple[list[dict[str, object]], str]:
    rows = []
    latest_time = ""
    for item in STOCKS:
        values = parsed.get(item["sina"], [])
        price = pct = "-"
        quote_time = ""
        if len(values) >= 32 and values[0]:
            prev_close = to_float(values[2])
            current = to_float(values[3])
            if current is not None:
                price = f"{current:.2f}"
            if prev_close and current is not None:
                pct = f"{(current - prev_close) / prev_close * 100:+.2f}%"
            quote_time = " ".join(part for part in values[30:32] if part)
            latest_time = quote_time or latest_time
        rows.append({**item, "price": price, "pct": pct, "quote_time": quote_time})
    return rows, latest_time


def parse_proxies(parsed: dict[str, list[str]], stock_rows: list[dict[str, object]]) -> dict[str, float]:
    proxies: dict[str, float] = {}
    for name, code in PROXIES.items():
        values = parsed.get(code, [])
        pct = None
        if code.startswith("s_") and len(values) >= 4:
            pct = to_float(values[3])
        elif code.startswith("gb_") and len(values) >= 3:
            pct = to_float(values[2])
        elif code == "hkHSI" and len(values) >= 9:
            pct = to_float(values[8])
        elif code == "fx_susdcnh" and len(values) >= 12:
            pct = to_float(values[11])
        if pct is not None:
            proxies[name] = pct

    semi_names = {"长电科技", "华工科技"}
    semi_pcts = []
    for row in stock_rows:
        if row["name"] in semi_names and isinstance(row["pct"], str) and row["pct"].endswith("%"):
            semi_pcts.append(float(row["pct"].replace("%", "")))
    if semi_pcts:
        proxies["SEMIS"] = sum(semi_pcts) / len(semi_pcts)
    return proxies


def estimate_funds(proxies: dict[str, float]) -> list[dict[str, object]]:
    rows = []
    for fund in FUNDS:
        total = 0.0
        used = []
        missing = []
        for symbol, weight in fund["proxies"].items():
            if symbol in proxies:
                total += proxies[symbol] * weight
                used.append(f"{symbol} {proxies[symbol]:+.2f}% x {weight:.0%}")
            else:
                missing.append(symbol)
        confidence = fund["confidence"]
        if missing and confidence == "高":
            confidence = "中"
        elif missing:
            confidence = "低"
        rows.append({
            **fund,
            "estimate_pct": total,
            "drivers": "；".join(used) if used else "暂无可用代理",
            "missing": "、".join(missing),
            "confidence": confidence,
        })
    return rows


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_class(pct: object) -> str:
    if isinstance(pct, (int, float)):
        return "up" if pct >= 0 else "down"
    if isinstance(pct, str) and pct.startswith("+"):
        return "up"
    if isinstance(pct, str) and pct.startswith("-"):
        return "down"
    return ""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fund_rows_html(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        pct = row["estimate_pct"]
        pct_text = f"{pct:+.2f}%"
        missing = f"<br><span class=\"note\">缺少代理：{esc(row['missing'])}</span>" if row["missing"] else ""
        body.append(
            "<tr>"
            f"<td>{esc(row['name'])}</td>"
            f"<td>{esc(row['code'])}</td>"
            f"<td>{float(row['amount']):.2f}</td>"
            f"<td>{float(row['weight']):.2f}%</td>"
            f"<td class=\"{pct_class(pct)}\">{pct_text}</td>"
            f"<td>{esc(row['confidence'])}</td>"
            f"<td>{esc(row['drivers'])}{missing}</td>"
            f"<td>{esc(row['bias'])}</td>"
            "</tr>"
        )
    return "\n".join(body)


def stock_rows_html(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{esc(row['name'])}</td>"
            f"<td>{esc(row['symbol'])}</td>"
            f"<td>{esc(row['bucket'])}</td>"
            f"<td>{esc(row['price'])}</td>"
            f"<td class=\"{pct_class(row['pct'])}\">{esc(row['pct'])}</td>"
            f"<td>{esc(row['bias'])}</td>"
            "</tr>"
        )
    return "\n".join(body)


def render_page(date_text: str, time_text: str, fund_rows: list[dict[str, object]], stock_rows: list[dict[str, object]], css_prefix: str) -> str:
    fund_note = "基金今日涨跌为代理估算，QDII 使用隔夜美股/港股与汇率，A 股基金使用指数或行业代理；不是官方净值。"
    stock_note = f"股票行情时间：{time_text or date_text}；数据用于日报展示，最终交易以券商 App 实时报价为准。"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>理财日报 - {esc(date_text)}</title>
  <link rel="stylesheet" href="{css_prefix}assets/style.css">
</head>
<body>
  <main>
    <header>
      <h1>理财日报</h1>
      <p class="meta">{esc(date_text)} 更新 · 最新日报</p>
    </header>

    <div class="grid" aria-label="账户概览">
      <div class="card"><p class="card-title">账户快照</p><p class="card-value">约 4.84 万</p></div>
      <div class="card"><p class="card-title">股票市值</p><p class="card-value">约 3.82 万</p></div>
      <div class="card"><p class="card-title">现金底线</p><p class="card-value">8k-12k</p></div>
    </div>

    <section>
      <h2>今日行动总结</h2>
      <p><span class="tag">建议</span>以观察为主。当前权益仓位偏高，先保留现金，不主动追高半导体、AI、纳指和高波动题材。</p>
    </section>

    <section>
      <h2>基金</h2>
      <p class="note">{esc(fund_note)}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>名称</th><th>代码</th><th>金额</th><th>占比</th><th>预估今日涨跌</th><th>置信度</th><th>估算依据</th><th>操作偏向</th></tr>
          </thead>
          <tbody>
{fund_rows_html(fund_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>股票</h2>
      <p class="note">{esc(stock_note)}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>名称</th><th>代码</th><th>分组</th><th>现价</th><th>涨跌幅</th><th>操作偏向</th></tr>
          </thead>
          <tbody>
{stock_rows_html(stock_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>风险提醒</h2>
      <ul>
        <li><span class="warn">现金纪律：</span>尽量保留 8000-12000 元现金，避免满仓。</li>
        <li><span class="warn">520 规则：</span>只看 5 日线和 20 日线；20 日线下行时，忽略假金叉。</li>
        <li><span class="warn">基金加仓：</span>大跌后先等 MACD 或趋势企稳，不急着抄底。</li>
      </ul>
    </section>

    <p class="footer">归档：<a href="{css_prefix}reports/{esc(date_text[:10])}.html">{esc(date_text[:10])}</a></p>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--time", default=dt.datetime.now().strftime("%H:%M"))
    args = parser.parse_args()

    codes = [stock["sina"] for stock in STOCKS] + list(PROXIES.values())
    raw = fetch_sina(codes)
    parsed = parse_lines(raw)
    stock_rows, quote_time = parse_stock_quotes(parsed)
    proxies = parse_proxies(parsed, stock_rows)
    fund_rows = estimate_funds(proxies)

    date_text = f"{args.date} {args.time}"
    report_html = render_page(date_text, quote_time, fund_rows, stock_rows, "../")
    index_html = render_page(date_text, quote_time, fund_rows, stock_rows, "")

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")
    (reports_dir / f"{args.date}.html").write_text(report_html, encoding="utf-8")
    print(f"generated index.html and reports/{args.date}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
