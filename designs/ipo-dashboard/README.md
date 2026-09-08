# IPO NOTE — 设计原型

方向：浅色、紧凑、日式金融工具。桌面优先，兼容移动端。

- `index.html`：IPO 一览，搜索、状态/市场筛选、排序、关注。
- `detail.html?code=627A`：公司详情，双来源评级与原文评价、财务、申购备忘、日历导出。
- `data.json`：列表源于仓库 2026-09-07 快照。购买日程和评论等详情为补采数据，每站记录 `retrieved_at`；评级与状态按列表快照呈现。
- 收藏和备忘仅写入此浏览器 localStorage；没有交易或推送功能。日历仅记录日期，不臆造券商截止时刻。
- 未合并两站观点，不将 96ut 读者预测作为作者初值预测。

从仓库启动：`python -m http.server 4311 --bind 127.0.0.1 --directory designs`

打开 `http://localhost:4311/ipo-dashboard/index.html`。

React 18.3.1 与 Babel 7.29.0 固定版本保存在 vendor，运行不依赖外部 CDN。
`build_data.py` 可重新读取仓库列表并补采详情，网络访问由调用环境授权。
