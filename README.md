# Daily Financial Report

一个最小可实施的静态理财日报站点。

## 结构

- `index.html`：最新日报入口
- `reports/YYYY-MM-DD.html`：每日归档
- `assets/style.css`：页面样式

## GitHub Pages

在 GitHub 仓库中打开：

`Settings -> Pages -> Build and deployment -> Deploy from a branch -> main / root`

打开后，访问地址通常是：

`https://jianinggaga.github.io/Daily-Financial-Report/`

## 更新日报

运行脚本生成首页和当天归档：

```bash
python3 scripts/generate_report.py --date 2026-06-01 --time 14:30
```

脚本会抓取公开行情代理数据，生成：

- `index.html`
- `reports/YYYY-MM-DD.html`

基金涨跌是代理估算，不是官方净值。QDII 主要参考隔夜美股/港股和汇率，A 股基金参考指数、行业或相关股票代理。
