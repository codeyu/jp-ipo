function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Design: an understated Japanese financial notebook. Snapshot-first chronology,
   source-separated opinions, locally stored personal tracking. No trade execution. */
const {
  useState,
  useEffect
} = React;
const srcName = {
  ipo96ut: '96ut',
  ipokiso: 'IPOkiso'
};
const stateNames = {
  all: '全部 IPO',
  open: '申购中',
  deadline: '截止日',
  purchase: '购买中',
  waiting: '待申购',
  listed: '已上市',
  closed: '待公布',
  saved: '我的关注'
};
const findField = (d, pattern) => Object.entries(d?.fields || {}).find(([k]) => pattern.test(k.replace(/\s/g, '')))?.[1] || '';
function dates(s) {
  return [...(s || '').matchAll(/(?:(20\d{2})[年/])?(\d{1,2})[月/](\d{1,2})/g)].map(m => `${m[1] || '2026'}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`);
}
function fmt(d) {
  return d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : '暂无数据';
}
function period(ds) {
  return ds.length > 1 ? `${fmt(ds[0])} — ${fmt(ds[1])}` : fmt(ds[0]);
}
function num(s) {
  return Number(String(s || '').replace(/,/g, '').match(/[\d.]+/)?.[0] || 0);
}
function prep(c) {
  const a = c.ipo96ut || {},
    b = c.ipokiso || {},
    ad = c.ipo96ut_detail || {},
    bd = c.ipokiso_detail || {};
  const bb = dates(b.application_period || findField(ad, /ＢＢ期間|BB期間/));
  const buy = dates(findField(bd, /購入申込期間/) || findField(ad, /購入申込期間/));
  const listing = dates(b.listing_date || a.listing_date)[0];
  const lottery = dates(findField(bd, /当選発表日/))[0];
  return {
    ...c,
    name: a.kabu_name || b.kabu_name,
    market: b.market || a.market,
    bb,
    buy,
    listing,
    lottery,
    rating96: a.rating || '-',
    ratingK: b.overall_rating || '-',
    range: b.provisional_range || a.provisional_range,
    expected: a.expected_price || b.expected_price,
    offer: b.offering_price || a.offering_price,
    website: bd.website || ad.website || '',
    business: ad.business || bd.business || ''
  };
}
function status(c, day) {
  if (c.listing && day >= c.listing) return 'listed';
  if (c.buy.length === 2 && day >= c.buy[0] && day <= c.buy[1]) return 'purchase';
  if (c.bb.length === 2) {
    if (day === c.bb[1]) return 'deadline';
    if (day >= c.bb[0] && day < c.bb[1]) return 'open';
    if (day < c.bb[0]) return 'waiting';
  }
  return 'closed';
}
function timelineStage(c, day) {
  const s = status(c, day);
  return s === 'listed' ? 3 : s === 'purchase' ? 2 : s === 'closed' ? 1 : s === 'waiting' ? -1 : 0;
}
function Rating({
  value
}) {
  const grade = /[SABCD]/.exec(value || '')?.[0] || '—';
  return /*#__PURE__*/React.createElement("span", {
    className: `rating ${grade === '—' ? 'none' : grade}`,
    title: value
  }, grade);
}
function Status({
  value
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: `badge ${value}`
  }, stateNames[value]);
}
function External({
  href,
  children,
  ...rest
}) {
  return href ? /*#__PURE__*/React.createElement("a", _extends({
    href: href,
    target: "_blank",
    rel: "noopener noreferrer"
  }, rest), children) : /*#__PURE__*/React.createElement("span", rest, children);
}
function SourceLink({
  c,
  source
}) {
  return /*#__PURE__*/React.createElement(External, {
    href: c[source + '_detail']?.url,
    className: "source-label"
  }, srcName[source], " \u2197");
}
function readLocal(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) || fallback;
  } catch {
    return fallback;
  }
}
function App() {
  const [data, setData] = useState(null),
    [error, setError] = useState('');
  const [saved, setSaved] = useState(() => readLocal('ipo-note-saved', []));
  const [filter, setFilter] = useState(new URLSearchParams(location.search).get('view') === 'saved' ? 'saved' : 'all'),
    [q, setQ] = useState(''),
    [market, setMarket] = useState('all'),
    [sort, setSort] = useState('deadline');
  const [toast, setToast] = useState('');
  useEffect(() => {
    fetch('data.json').then(r => {
      if (!r.ok) throw Error('读取数据失败');
      return r.json();
    }).then(d => setData({
      ...d,
      companies: d.companies.map(prep)
    })).catch(e => setError(e.message));
  }, []);
  useEffect(() => {
    localStorage.setItem('ipo-note-saved', JSON.stringify(saved));
  }, [saved]);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(''), 2400);
      return () => clearTimeout(t);
    }
  }, [toast]);
  const toggle = c => {
    setSaved(s => s.includes(c.code) ? s.filter(x => x !== c.code) : [...s, c.code]);
    setToast(saved.includes(c.code) ? '已取消关注' : '已加入关注 · 保存在此浏览器');
  };
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, error, "\u3002\u8BF7\u901A\u8FC7\u672C\u5730 HTTP \u670D\u52A1\u6253\u5F00\u9875\u9762\u3002");
  if (!data) return /*#__PURE__*/React.createElement("div", {
    className: "loading"
  }, "\u6B63\u5728\u8F7D\u5165 IPO \u6570\u636E\u2026");
  const detail = location.pathname.endsWith('detail.html');
  const code = new URLSearchParams(location.search).get('code') || '627A';
  const c = data.companies.find(x => x.code === code);
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("header", {
    className: "topbar"
  }, /*#__PURE__*/React.createElement("a", {
    href: "index.html?v=3",
    className: "brand"
  }, /*#__PURE__*/React.createElement("span", {
    className: "brand-mark"
  }, "i"), /*#__PURE__*/React.createElement("span", null, "IPO NOTE", /*#__PURE__*/React.createElement("small", null, "\u65E5\u672C\u65B0\u80A1\u89C2\u5BDF"))), /*#__PURE__*/React.createElement("nav", {
    className: "topnav",
    "aria-label": "\u4E3B\u5BFC\u822A"
  }, /*#__PURE__*/React.createElement("a", {
    className: !detail && filter !== 'saved' ? 'selected' : '',
    href: "index.html?v=3"
  }, "IPO \u4E00\u89C8"), /*#__PURE__*/React.createElement("a", {
    className: !detail && filter === 'saved' ? 'selected' : '',
    href: "index.html?v=3&view=saved"
  }, "\u6211\u7684\u5173\u6CE8 ", /*#__PURE__*/React.createElement("span", {
    className: "subtle"
  }, "\xA0", saved.length))), /*#__PURE__*/React.createElement("div", {
    className: "top-right"
  }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
    className: "dot"
  }), "\u53CC\u6765\u6E90\u6570\u636E"), /*#__PURE__*/React.createElement("span", {
    className: "avatar"
  }, "JP"))), /*#__PURE__*/React.createElement("main", {
    className: "shell"
  }, detail ? c ? /*#__PURE__*/React.createElement(Detail, {
    c: c,
    day: data.snapshot_date,
    saved: saved.includes(c.code),
    toggle: () => toggle(c),
    notify: setToast
  }) : /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "\u672A\u627E\u5230\u80A1\u7968\u4EE3\u7801 ", code, "\u3002", /*#__PURE__*/React.createElement("a", {
    href: "index.html?v=3"
  }, "\u8FD4\u56DE\u4E00\u89C8")) : /*#__PURE__*/React.createElement(Listing, {
    data: data,
    saved: saved,
    toggle: toggle,
    filter: filter,
    setFilter: setFilter,
    q: q,
    setQ: setQ,
    market: market,
    setMarket: setMarket,
    sort: sort,
    setSort: setSort
  }), /*#__PURE__*/React.createElement("footer", {
    className: "footer"
  }, /*#__PURE__*/React.createElement("span", null, "IPO NOTE \xB7 \u65E5\u672C\u65B0\u80A1\u89C2\u5BDF\u3000 /\u3000\u6570\u636E\u6765\u6E90\uFF1A96ut\u3001IPOkiso"), /*#__PURE__*/React.createElement("span", null, "\u5217\u8868\u5FEB\u7167 ", data.snapshot_date, " \xB7 \u65E5\u672C\u65F6\u95F4 JST \xB7 \u672C\u5730\u4EA4\u4E92\u539F\u578B"))), toast && /*#__PURE__*/React.createElement("div", {
    className: "toast",
    role: "status"
  }, toast));
}
function Listing({
  data,
  saved,
  toggle,
  filter,
  setFilter,
  q,
  setQ,
  market,
  setMarket,
  sort,
  setSort
}) {
  const day = data.snapshot_date,
    all = data.companies;
  const count = t => all.filter(c => t === 'open' ? ['open', 'deadline'].includes(status(c, day)) : status(c, day) === t).length;
  let rows = all.filter(c => (filter === 'all' || (filter === 'saved' ? saved.includes(c.code) : filter === 'open' ? ['open', 'deadline'].includes(status(c, day)) : status(c, day) === filter)) && (!q || `${c.name} ${c.code}`.toLowerCase().includes(q.toLowerCase())) && (market === 'all' || c.market.includes(market)));
  rows.sort((a, b) => {
    if (sort === 'listing') return (a.listing || '').localeCompare(b.listing || '');
    if (sort === 'price') return num(a.expected) - num(b.expected);
    const priority = c => ['deadline', 'open', 'purchase', 'waiting', 'closed', 'listed'].indexOf(status(c, day));
    return priority(a) - priority(b) || (a.bb[1] || '').localeCompare(b.bb[1] || '');
  });
  const events = all.filter(c => c.bb[1] >= day).sort((a, b) => a.bb[1].localeCompare(b.bb[1])).slice(0, 4);
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "IPO \u4E00\u89C8"
  }, /*#__PURE__*/React.createElement("div", {
    className: "heading"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow"
  }, "IPO WATCH / SEPTEMBER 2026"), /*#__PURE__*/React.createElement("h1", null, filter === 'saved' ? '我的关注' : '每一次申购，心中有数。'), /*#__PURE__*/React.createElement("p", null, "\u8FFD\u8E2A\u65E5\u672C\u65B0\u80A1\u65E5\u7A0B\uFF0C\u5BF9\u7167\u4E24\u7AD9\u89C2\u70B9\uFF0C\u628A\u63E1\u4E0B\u4E00\u6B65\u3002")), /*#__PURE__*/React.createElement("span", {
    className: "snapshot"
  }, "\u6570\u636E\u5FEB\u7167\u30002026.09.07 ", /*#__PURE__*/React.createElement("span", {
    className: "subtle"
  }, " / JST"))), /*#__PURE__*/React.createElement("div", {
    className: "stat-grid"
  }, /*#__PURE__*/React.createElement("button", {
    className: "stat green",
    onClick: () => setFilter('open')
  }, /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "\u6B63\u5728\u7533\u8D2D ", /*#__PURE__*/React.createElement("span", null, "\u2197")), /*#__PURE__*/React.createElement("strong", null, count('open').toString().padStart(2, '0')), /*#__PURE__*/React.createElement("small", null, "\u542B\u622A\u6B62\u65E5\u9879\u76EE")), /*#__PURE__*/React.createElement("button", {
    className: "stat urgent",
    onClick: () => setFilter('deadline')
  }, /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "\u5FEB\u7167\u65E5\u622A\u6B62 ", /*#__PURE__*/React.createElement("span", null, "\u2197")), /*#__PURE__*/React.createElement("strong", null, count('deadline').toString().padStart(2, '0')), /*#__PURE__*/React.createElement("small", null, "\u8BF7\u6838\u5BF9\u5404\u5238\u5546\u5177\u4F53\u622A\u6B62\u65F6\u523B")), /*#__PURE__*/React.createElement("button", {
    className: "stat",
    onClick: () => setFilter('purchase')
  }, /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "\u8FDB\u5165\u8D2D\u4E70\u671F ", /*#__PURE__*/React.createElement("span", null, "\u2197")), /*#__PURE__*/React.createElement("strong", null, count('purchase').toString().padStart(2, '0')), /*#__PURE__*/React.createElement("small", null, "\u4E2D\u7B7E\u540E\u8BB0\u5F97\u5B8C\u6210\u8D2D\u4E70")), /*#__PURE__*/React.createElement("button", {
    className: "stat",
    onClick: () => setFilter('waiting')
  }, /*#__PURE__*/React.createElement("span", {
    className: "label"
  }, "\u5373\u5C06\u5F00\u653E\u7533\u8D2D ", /*#__PURE__*/React.createElement("span", null, "\u2197")), /*#__PURE__*/React.createElement("strong", null, count('waiting').toString().padStart(2, '0')), /*#__PURE__*/React.createElement("small", null, "\u63D0\u524D\u4E86\u89E3\u516C\u53F8\u4E0E\u53D1\u884C\u4FE1\u606F"))), /*#__PURE__*/React.createElement("div", {
    className: "main-grid"
  }, /*#__PURE__*/React.createElement("section", {
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel-head"
  }, /*#__PURE__*/React.createElement("h2", null, "IPO \u65E5\u7A0B\u4E00\u89C8"), /*#__PURE__*/React.createElement("small", null, "9 \u2014 10 \u6708 \xB7 ", all.length, " \u5BB6\u516C\u53F8")), /*#__PURE__*/React.createElement("div", {
    className: "tabs"
  }, ['all', 'open', 'purchase', 'waiting', 'saved'].map(t => /*#__PURE__*/React.createElement("button", {
    key: t,
    className: filter === t ? 'on' : '',
    onClick: () => setFilter(t)
  }, stateNames[t], /*#__PURE__*/React.createElement("small", null, t === 'all' ? all.length : t === 'saved' ? saved.length : count(t)))), filter === 'deadline' && /*#__PURE__*/React.createElement("button", {
    className: "on"
  }, "\u622A\u6B62\u65E5 ", /*#__PURE__*/React.createElement("small", null, count('deadline')))), /*#__PURE__*/React.createElement("div", {
    className: "toolbar"
  }, /*#__PURE__*/React.createElement("label", {
    className: "search"
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true"
  }, "\u2315"), /*#__PURE__*/React.createElement("input", {
    "aria-label": "\u641C\u7D22\u516C\u53F8\u6216\u4EE3\u7801",
    placeholder: "\u641C\u7D22\u516C\u53F8\u540D\u79F0 / \u80A1\u7968\u4EE3\u7801",
    value: q,
    onChange: e => setQ(e.target.value)
  })), /*#__PURE__*/React.createElement("select", {
    "aria-label": "\u5E02\u573A\u7B5B\u9009",
    value: market,
    onChange: e => setMarket(e.target.value)
  }, /*#__PURE__*/React.createElement("option", {
    value: "all"
  }, "\u5168\u90E8\u5E02\u573A"), /*#__PURE__*/React.createElement("option", {
    value: "\u30B9\u30BF\u30F3\u30C0\u30FC\u30C9"
  }, "\u4E1C\u8BC1 Standard"), /*#__PURE__*/React.createElement("option", {
    value: "\u30B0\u30ED\u30FC\u30B9"
  }, "\u4E1C\u8BC1 Growth"), /*#__PURE__*/React.createElement("option", {
    value: "\u30CD\u30AF\u30B9\u30C8"
  }, "\u540D\u8BC1 Next")), /*#__PURE__*/React.createElement("select", {
    "aria-label": "\u6392\u5E8F",
    value: sort,
    onChange: e => setSort(e.target.value)
  }, /*#__PURE__*/React.createElement("option", {
    value: "deadline"
  }, "\u6309\u7533\u8D2D\u622A\u6B62\u6392\u5E8F"), /*#__PURE__*/React.createElement("option", {
    value: "listing"
  }, "\u6309\u4E0A\u5E02\u65E5\u6392\u5E8F"), /*#__PURE__*/React.createElement("option", {
    value: "price"
  }, "\u6309\u60F3\u5B9A\u4EF7\u6392\u5E8F"))), /*#__PURE__*/React.createElement("div", {
    className: "table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "list-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u516C\u53F8 / \u4EE3\u7801"), /*#__PURE__*/React.createElement("th", null, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u7533\u8D2D\u671F\u95F4"), /*#__PURE__*/React.createElement("th", null, "\u8D2D\u4E70\u671F\u95F4"), /*#__PURE__*/React.createElement("th", null, "\u4E0A\u5E02\u65E5"), /*#__PURE__*/React.createElement("th", {
    className: "ratings-cell"
  }, "96ut / IPOkiso"), /*#__PURE__*/React.createElement("th", null, "\u5173\u6CE8"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(c => /*#__PURE__*/React.createElement("tr", {
    key: c.code
  }, /*#__PURE__*/React.createElement("td", {
    className: "company-cell"
  }, /*#__PURE__*/React.createElement("a", {
    className: "company-name",
    href: `detail.html?v=3&code=${c.code}`,
    lang: "ja"
  }, c.name), /*#__PURE__*/React.createElement("span", {
    className: "code"
  }, c.code, " \xB7 ", c.market.replace('東証 ', '').replace('スタンダード', 'Standard').replace('グロース', 'Growth').replace('名証 ネクスト', '名证 Next'))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
    value: status(c, day)
  })), /*#__PURE__*/React.createElement("td", {
    className: "date"
  }, period(c.bb), /*#__PURE__*/React.createElement("small", {
    className: status(c, day) === 'deadline' ? 'soon' : ''
  }, status(c, day) === 'deadline' ? '快照日截止' : status(c, day) === 'waiting' ? '尚未开放' : '来源 IPOkiso')), /*#__PURE__*/React.createElement("td", {
    className: "date"
  }, period(c.buy), /*#__PURE__*/React.createElement("small", null, "\u6765\u6E90 IPOkiso / 96ut")), /*#__PURE__*/React.createElement("td", {
    className: "date"
  }, fmt(c.listing)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
    className: "rating-pair"
  }, /*#__PURE__*/React.createElement(Rating, {
    value: c.rating96
  }), /*#__PURE__*/React.createElement(Rating, {
    value: c.ratingK
  }))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("button", {
    className: `star ${saved.includes(c.code) ? 'saved' : ''}`,
    "aria-label": `${saved.includes(c.code) ? '取消关注' : '关注'} ${c.name}`,
    "aria-pressed": saved.includes(c.code),
    onClick: () => toggle(c)
  }, saved.includes(c.code) ? '★' : '☆')))))), !rows.length && /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "\u6CA1\u6709\u5339\u914D\u7684 IPO\u3002\u8BD5\u8BD5\u5176\u4ED6\u7B5B\u9009\u6761\u4EF6\u3002", /*#__PURE__*/React.createElement("br", null), /*#__PURE__*/React.createElement("button", {
    onClick: () => {
      setQ('');
      setMarket('all');
      setFilter('all');
    }
  }, "\u91CD\u7F6E\u7B5B\u9009"))), /*#__PURE__*/React.createElement("div", {
    className: "table-foot"
  }, /*#__PURE__*/React.createElement("span", null, "\u663E\u793A ", rows.length, " / ", all.length, " \u5BB6\u516C\u53F8"), /*#__PURE__*/React.createElement("span", null, "\u70B9\u51FB\u516C\u53F8\u540D\u79F0\u67E5\u770B\u8BE6\u60C5 \u2192")), /*#__PURE__*/React.createElement("div", {
    className: "list-header-note"
  }, "\u8BC4\u7EA7\u6CBF\u7528\u5217\u8868\u5FEB\u7167\uFF1B\u8D2D\u4E70\u65E5\u7A0B\u6765\u81EA\u8BE6\u60C5\u8865\u91C7\u3002\u72B6\u6001\u6309\u5FEB\u7167\u65E5\u7684\u65E5\u671F\u63A8\u7B97\uFF0C\u4E0D\u4EE3\u8868\u5F53\u524D\u53EF\u7533\u8D2D\u3002")), /*#__PURE__*/React.createElement("aside", {
    className: "aside list-aside"
  }, /*#__PURE__*/React.createElement("section", {
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "aside-kicker"
  }, "UP NEXT"), /*#__PURE__*/React.createElement("h3", null, "\u6700\u8FD1\u7533\u8D2D\u622A\u6B62"), events.map(c => /*#__PURE__*/React.createElement("div", {
    className: "event",
    key: c.code
  }, /*#__PURE__*/React.createElement("div", {
    className: `event-day ${c.bb[1] === day ? 'urgent' : ''}`
  }, Number(c.bb[1].slice(8)), /*#__PURE__*/React.createElement("small", null, "9 \u6708")), /*#__PURE__*/React.createElement("div", {
    className: "event-info"
  }, /*#__PURE__*/React.createElement("a", {
    href: `detail.html?v=3&code=${c.code}`
  }, /*#__PURE__*/React.createElement("strong", null, c.name)), /*#__PURE__*/React.createElement("p", null, c.code, " \xB7 \u7533\u8D2D\u622A\u6B62"), /*#__PURE__*/React.createElement("a", {
    href: `detail.html?v=3&code=${c.code}`
  }, "\u67E5\u770B\u65E5\u7A0B \u2197"))))), /*#__PURE__*/React.createElement("section", {
    className: "panel note"
  }, /*#__PURE__*/React.createElement("div", {
    className: "aside-kicker"
  }, "TWO PERSPECTIVES"), /*#__PURE__*/React.createElement("h3", null, "\u4E24\u4EFD\u8BC4\u7EA7\uFF0C\u72EC\u7ACB\u53C2\u8003\u3002"), /*#__PURE__*/React.createElement("p", null, "\u4E24\u7AD9\u5BF9\u540C\u4E00\u53EA\u80A1\u7968\u53EF\u80FD\u6709\u4E0D\u540C\u5224\u65AD\u3002\u8BE6\u60C5\u9875\u5C06\u8BC4\u7EA7\u3001\u521D\u503C\u9884\u6D4B\u4E0E\u8BC4\u4EF7\u539F\u6587\u5E76\u5217\u5C55\u793A\uFF0C\u4FDD\u7559\u5404\u81EA\u7684\u6765\u6E90\u3002"), /*#__PURE__*/React.createElement("a", {
    href: "detail.html?v=3&code=627A",
    className: "source-label"
  }, "\u770B\u770B akippa \u7684\u4E24\u7AD9\u89C2\u70B9 \u2192")), /*#__PURE__*/React.createElement("section", {
    className: "panel"
  }, /*#__PURE__*/React.createElement("h3", null, "\u6570\u636E\u6765\u6E90"), /*#__PURE__*/React.createElement("div", {
    className: "source-legend"
  }, /*#__PURE__*/React.createElement("span", null, "96ut ", /*#__PURE__*/React.createElement("small", null, "2026.09.07")), /*#__PURE__*/React.createElement("span", null, "IPOkiso ", /*#__PURE__*/React.createElement("small", null, "2026.09.07"))), /*#__PURE__*/React.createElement("p", {
    className: "mini-note"
  }, "\u5217\u8868\u5FEB\u7167\u4E0E\u8BE6\u60C5\u8865\u91C7\u65F6\u95F4\u5206\u522B\u4FDD\u7559\u3002\u672A\u83B7\u53D6\u7684\u503C\u4EE5\u201C\u6682\u65E0\u6570\u636E\u201D\u5448\u73B0\u3002")))));
}
function Review({
  c,
  source
}) {
  const [expanded, setExpanded] = useState(false);
  const d = c[source + '_detail'] || {};
  let content = (d.comments || []).map(x => x.text).join('\n\n');
  content = content.replace(/@ipokiso_com[\s\S]*$/, '').trim();
  if (source === 'ipo96ut' && content.includes('・新規承認時')) content = content.slice(content.indexOf('・新規承認時'));
  const forecast = findField(d, source === 'ipo96ut' ? /初値予想\(BB開始時\)/ : /初値予想/);
  return /*#__PURE__*/React.createElement("article", {
    className: `review ${expanded ? 'expanded' : ''}`
  }, /*#__PURE__*/React.createElement("div", {
    className: "review-top"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", null, srcName[source]), /*#__PURE__*/React.createElement("small", null, "\u7F51\u7AD9\u72EC\u7ACB\u8BC4\u7EA7 \xB7 \u5217\u8868\u5FEB\u7167")), /*#__PURE__*/React.createElement(Rating, {
    value: source === 'ipo96ut' ? c.rating96 : c.ratingK
  })), /*#__PURE__*/React.createElement("div", {
    className: "forecast"
  }, /*#__PURE__*/React.createElement("span", {
    className: "subtle"
  }, source === 'ipo96ut' ? '初值预测 · BB 开始时' : '初值预测 · 网站独自预测'), /*#__PURE__*/React.createElement("strong", null, forecast ? forecast.split(/[（(]/)[0] : '暂无数据'), forecast && /[（(]/.test(forecast) && /*#__PURE__*/React.createElement("small", null, forecast.slice(forecast.search(/[（(]/)))), /*#__PURE__*/React.createElement("p", {
    className: "review-body",
    lang: "ja"
  }, content || '暂无评价原文，请查看来源页面。'), /*#__PURE__*/React.createElement("div", {
    className: "review-actions"
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setExpanded(!expanded)
  }, expanded ? '收起评价 −' : '展开评价全文 +'), /*#__PURE__*/React.createElement(SourceLink, {
    c: c,
    source: source
  })), /*#__PURE__*/React.createElement("small", null, "\u8BE6\u60C5\u8865\u91C7\uFF1A", d.retrieved_at ? new Date(d.retrieved_at).toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Tokyo'
  }) : '暂无数据', " \xB7 \u65E5\u6587\u539F\u6587"));
}
function downloadCalendar(c) {
  const events = [['申购截止', c.bb[1]], ['购买开始', c.buy[0]], ['购买截止', c.buy[1]], ['上市日', c.listing]].filter(x => x[1]);
  const content = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//IPO NOTE//CN', 'CALSCALE:GREGORIAN', ...events.flatMap(([name, date], i) => ['BEGIN:VEVENT', `UID:${c.code}-${i}@ipo-note.local`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')}`, `DTSTART;VALUE=DATE:${date.replace(/-/g, '')}`, `SUMMARY:${c.name} ${c.code} ${name}`, 'DESCRIPTION:日期来自 IPO 快照；请在券商核对具体时间。', 'END:VEVENT']), 'END:VCALENDAR'].join('\r\n');
  const u = URL.createObjectURL(new Blob([content], {
    type: 'text/calendar;charset=utf-8'
  }));
  const a = document.createElement('a');
  a.href = u;
  a.download = `${c.code}-ipo.ics`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
function Detail({
  c,
  day,
  saved,
  toggle,
  notify
}) {
  const [checked, setChecked] = useState(() => readLocal('ipo-note-check-' + c.code, {}));
  const ad = c.ipo96ut_detail || {},
    bd = c.ipokiso_detail || {};
  const af = ad.fields || {},
    bf = bd.fields || {};
  const setCheck = k => setChecked(prev => {
    const next = {
      ...prev,
      [k]: !prev[k]
    };
    localStorage.setItem('ipo-note-check-' + c.code, JSON.stringify(next));
    return next;
  });
  const brokers = c.ipokiso?.target_securities || [];
  const docs = [...(ad.documents || []), ...(bd.documents || [])];
  const business = c.business.replace(/^.*?事業内容\s*[:：]?/, '').trim();
  return /*#__PURE__*/React.createElement("div", {
    "data-screen-label": "\u80A1\u7968\u8BE6\u60C5"
  }, /*#__PURE__*/React.createElement("div", {
    className: "breadcrumb"
  }, /*#__PURE__*/React.createElement("a", {
    href: "index.html?v=3"
  }, "IPO \u4E00\u89C8"), /*#__PURE__*/React.createElement("span", null, "/"), /*#__PURE__*/React.createElement("span", null, c.name, " \xB7 ", c.code)), /*#__PURE__*/React.createElement("div", {
    className: "detail-top"
  }, /*#__PURE__*/React.createElement("div", {
    className: "detail-heading"
  }, /*#__PURE__*/React.createElement("div", {
    className: "monogram"
  }, c.name.match(/[a-zA-Z]/)?.[0] || '株'), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    lang: "ja"
  }, c.name), /*#__PURE__*/React.createElement("div", {
    className: "detail-title-meta"
  }, /*#__PURE__*/React.createElement("span", null, c.code, " \xB7 ", c.market), /*#__PURE__*/React.createElement(Status, {
    value: status(c, day)
  })))), /*#__PURE__*/React.createElement("div", {
    className: "action-group"
  }, /*#__PURE__*/React.createElement("button", {
    onClick: toggle
  }, saved ? '★ 已关注' : '☆ 加入关注'), /*#__PURE__*/React.createElement("button", {
    className: "primary",
    onClick: () => {
      downloadCalendar(c);
      notify('IPO 日程已导出为日历文件');
    }
  }, "\uFF0B \u5BFC\u51FA IPO \u65E5\u7A0B"))), /*#__PURE__*/React.createElement("div", {
    className: "metric-strip"
  }, /*#__PURE__*/React.createElement("div", {
    className: "metric"
  }, /*#__PURE__*/React.createElement("span", null, "\u60F3\u5B9A\u4EF7\u683C"), /*#__PURE__*/React.createElement("strong", null, "\xA5 ", num(c.expected).toLocaleString()), /*#__PURE__*/React.createElement("small", null, "\u6765\u6E90 96ut / IPOkiso")), /*#__PURE__*/React.createElement("div", {
    className: "metric"
  }, /*#__PURE__*/React.createElement("span", null, "\u4EEE\u6761\u4EF6 \xB7 \u53D1\u884C\u4EF7\u683C\u533A\u95F4"), /*#__PURE__*/React.createElement("strong", null, c.range && c.range !== '-' ? `¥ ${c.range.replace(/円/g, '').replace(/～/g, '—')}` : '尚未公布'), /*#__PURE__*/React.createElement("small", null, "\u6765\u6E90 IPOkiso \xB7 \u6BCF\u80A1\u65E5\u5143")), /*#__PURE__*/React.createElement("div", {
    className: "metric"
  }, /*#__PURE__*/React.createElement("span", null, "\u516C\u52DF\u4EF7\u683C"), /*#__PURE__*/React.createElement("strong", null, c.offer && c.offer !== '-' ? `¥ ${num(c.offer).toLocaleString()}` : '尚未公布'), /*#__PURE__*/React.createElement("small", null, "\u6765\u6E90 IPOkiso")), /*#__PURE__*/React.createElement("div", {
    className: "metric"
  }, /*#__PURE__*/React.createElement("span", null, "\u4E0A\u5E02\u65E5\u671F"), /*#__PURE__*/React.createElement("strong", null, fmt(c.listing), " ", /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline',
      fontSize: 13
    }
  }, "2026")), /*#__PURE__*/React.createElement("small", null, c.market))), /*#__PURE__*/React.createElement("div", {
    className: "detail-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "detail-main"
  }, /*#__PURE__*/React.createElement("section", {
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel-head"
  }, /*#__PURE__*/React.createElement("h2", null, "\u7533\u8D2D\u5230\u4E0A\u5E02\uFF0C\u4E00\u6B65\u4E0D\u6F0F"), /*#__PURE__*/React.createElement("small", null, "\u65E5\u672C\u65F6\u95F4 \xB7 JST")), /*#__PURE__*/React.createElement("div", {
    className: "timeline"
  }, [['申购期间', period(c.bb), '截止后不可补报'], ['中签公布', fmt(c.lottery), '以券商账户结果为准'], ['购买期间', period(c.buy), '中签后完成购买'], ['上市交易', fmt(c.listing), '关注首日交易']].map(([title, value, note], i) => /*#__PURE__*/React.createElement("div", {
    key: title,
    className: `step ${i === timelineStage(c, day) ? 'current' : ''}`
  }, /*#__PURE__*/React.createElement("small", null, "0", i + 1, " / ", title), /*#__PURE__*/React.createElement("strong", null, value), /*#__PURE__*/React.createElement("span", null, note)))), /*#__PURE__*/React.createElement("p", {
    className: "disclaimer"
  }, "\u72B6\u6001\u57FA\u51C6\uFF1A", day, " \u5217\u8868\u5FEB\u7167\u3002\u65E5\u7A0B\u6765\u6E90 IPOkiso / 96ut\uFF1B\u5404\u5238\u5546\u5177\u4F53\u622A\u6B62\u65F6\u523B\u53EF\u80FD\u4E0D\u540C\u3002")), /*#__PURE__*/React.createElement("nav", {
    className: "section-nav",
    "aria-label": "\u8BE6\u60C5\u7AE0\u8282"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#company"
  }, "\u516C\u53F8\u6982\u51B5"), /*#__PURE__*/React.createElement("a", {
    href: "#opinions"
  }, "\u4E24\u7AD9\u8BC4\u4EF7"), /*#__PURE__*/React.createElement("a", {
    href: "#financials"
  }, "\u8D22\u52A1\u6570\u636E"), /*#__PURE__*/React.createElement("a", {
    href: "#brokers"
  }, "\u7533\u8D2D\u5238\u5546")), /*#__PURE__*/React.createElement("section", {
    id: "company",
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel-head"
  }, /*#__PURE__*/React.createElement("h2", null, "\u8FD9\u662F\u4E00\u5BB6\u600E\u6837\u7684\u516C\u53F8\uFF1F"), /*#__PURE__*/React.createElement(External, {
    href: c.website,
    className: "source-label"
  }, "\u516C\u53F8\u5B98\u7F51 \u2197")), /*#__PURE__*/React.createElement("div", {
    className: "section-content"
  }, /*#__PURE__*/React.createElement("p", {
    className: "business-text",
    lang: "ja"
  }, business || '暂无公司业务介绍。'), /*#__PURE__*/React.createElement("div", {
    className: "facts"
  }, [['公司成立', af['設立'] || bf['会社設立']], ['员工人数', af['従業員数']], ['主承销商', af['主幹事証券'] || bf['主幹事証券']], ['审计机构', af['監査法人']], ['公司所在地', af['所在地']], ['募集资金用途', af['IPOの資金用途']]].map(([k, v]) => /*#__PURE__*/React.createElement("div", {
    className: "fact",
    key: k
  }, /*#__PURE__*/React.createElement("span", null, k), /*#__PURE__*/React.createElement("strong", {
    lang: "ja"
  }, v || '暂无数据')))), /*#__PURE__*/React.createElement("p", {
    className: "mini-note"
  }, "\u8D44\u6599\u6765\u6E90\uFF1A96ut\uFF1B\u6210\u7ACB\u65F6\u95F4\u53CA\u4E3B\u627F\u9500\u5546\u7F3A\u5931\u65F6\u91C7\u7528 IPOkiso\u3002"))), /*#__PURE__*/React.createElement("section", {
    id: "opinions",
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel-head"
  }, /*#__PURE__*/React.createElement("h2", null, "\u4E24\u7AD9\u89C2\u70B9\uFF0C\u653E\u5728\u4E00\u8D77\u770B"), /*#__PURE__*/React.createElement("span", {
    className: "subtle",
    style: {
      fontSize: 11
    }
  }, "\u72EC\u7ACB\u8BC4\u7EA7 \xB7 \u4FDD\u7559\u539F\u6587")), /*#__PURE__*/React.createElement("div", {
    className: "analysis-grid"
  }, /*#__PURE__*/React.createElement(Review, {
    c: c,
    source: "ipo96ut"
  }), /*#__PURE__*/React.createElement(Review, {
    c: c,
    source: "ipokiso"
  })), /*#__PURE__*/React.createElement("p", {
    className: "disclaimer"
  }, "\u8BC4\u7EA7\u6CBF\u7528 2026.09.07 \u5217\u8868\u5FEB\u7167\uFF0C\u9884\u6D4B\u4E0E\u8BC4\u4EF7\u53D6\u81EA\u8BE6\u60C5\u8865\u91C7\u3002\u4E24\u7AD9\u8BC4\u7EA7\u53E3\u5F84\u4E0D\u540C\uFF0C\u4E0D\u505A\u5E73\u5747\u6216\u7EDF\u4E00\u6253\u5206\u3002")), /*#__PURE__*/React.createElement("section", {
    id: "financials",
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "panel-head"
  }, /*#__PURE__*/React.createElement("h2", null, "\u516C\u53F8\u8D22\u52A1"), /*#__PURE__*/React.createElement(SourceLink, {
    c: c,
    source: "ipokiso"
  })), bd.financials?.length ? /*#__PURE__*/React.createElement("div", {
    className: "table-wrap financial"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, bd.financials[0][0].map((v, i) => /*#__PURE__*/React.createElement("th", {
    key: i
  }, v || '财务指标')))), /*#__PURE__*/React.createElement("tbody", null, bd.financials[0].slice(1).map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, r.map((v, j) => /*#__PURE__*/React.createElement("td", {
    key: j,
    className: v.includes('△') ? 'urgent' : ''
  }, v))))))) : /*#__PURE__*/React.createElement("div", {
    className: "section-content subtle"
  }, "\u6682\u65E0\u5DF2\u83B7\u53D6\u8D22\u52A1\u6570\u636E\uFF0C\u8BF7\u53C2\u8003\u539F\u59CB\u62AB\u9732\u6587\u4EF6\u3002"), /*#__PURE__*/React.createElement("p", {
    className: "disclaimer",
    style: {
      paddingTop: 16
    }
  }, "\u4FDD\u7559\u539F\u8868\u5355\u4F4D\u53CA\u8D1F\u6570\u6807\u8BB0\uFF1B\u91D1\u989D\u3001\u6BCF\u80A1\u6307\u6807\u7684\u5355\u4F4D\u8BF7\u4EE5\u884C\u6807\u9898\u4E3A\u51C6\u3002"))), /*#__PURE__*/React.createElement("aside", {
    className: "aside detail-aside"
  }, /*#__PURE__*/React.createElement("section", {
    className: "panel check-panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "aside-kicker"
  }, "MY IPO NOTE"), /*#__PURE__*/React.createElement("h3", null, "\u6211\u7684\u7533\u8D2D\u5907\u5FD8"), /*#__PURE__*/React.createElement("p", {
    className: "subtle"
  }, "\u4EC5\u4FDD\u5B58\u5728\u6B64\u6D4F\u89C8\u5668\uFF0C\u4E0D\u4EE3\u8868\u5238\u5546\u72B6\u6001\u3002"), [['applied', '已向券商提交申购'], ['result', '已确认中签结果'], ['purchased', '已完成中签购买']].map(([k, label]) => /*#__PURE__*/React.createElement("label", {
    className: "checkline",
    key: k
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!checked[k],
    onChange: () => setCheck(k)
  }), label)), /*#__PURE__*/React.createElement("button", {
    className: "primary",
    onClick: () => document.getElementById('brokers').scrollIntoView({
      behavior: 'smooth'
    })
  }, "\u67E5\u770B\u7533\u8D2D\u5238\u5546 \u2193"), /*#__PURE__*/React.createElement("p", {
    className: "mini-note"
  }, "\u5B9E\u9645\u7533\u8D2D\u4E0E\u8D2D\u4E70\u8BF7\u5728\u5238\u5546\u8D26\u6237\u4E2D\u5B8C\u6210\u3002")), /*#__PURE__*/React.createElement("section", {
    className: "panel",
    id: "brokers"
  }, /*#__PURE__*/React.createElement("div", {
    className: "aside-kicker"
  }, "WHERE TO APPLY"), /*#__PURE__*/React.createElement("h3", null, "\u53EF\u7533\u8D2D\u5238\u5546"), brokers.map((b, i) => /*#__PURE__*/React.createElement("div", {
    className: "broker",
    key: i
  }, /*#__PURE__*/React.createElement(External, {
    href: b.url ? new URL(b.url, 'https://www.ipokiso.com').href : ''
  }, b.name, b.url ? ' ↗' : ''), /*#__PURE__*/React.createElement("small", null, b.role === '主' ? '主承销' : b.role === '副' ? '副承销' : '申购渠道'))), /*#__PURE__*/React.createElement("p", {
    className: "mini-note"
  }, "\u6765\u6E90 IPOkiso\u3002\u94FE\u63A5\u524D\u5F80\u5238\u5546\u4ECB\u7ECD\u9875\uFF0C\u53EF\u67E5\u627E\u5F00\u6237\u4E0E\u7533\u8D2D\u5165\u53E3\u3002")), /*#__PURE__*/React.createElement("section", {
    className: "panel"
  }, /*#__PURE__*/React.createElement("div", {
    className: "aside-kicker"
  }, "DOCUMENTS"), /*#__PURE__*/React.createElement("h3", null, "\u516C\u53F8\u62AB\u9732\u8D44\u6599"), docs.length ? docs.map((d, i) => /*#__PURE__*/React.createElement(External, {
    key: i,
    href: d.url,
    className: "document-link"
  }, /*#__PURE__*/React.createElement("span", null, d.title), /*#__PURE__*/React.createElement("span", null, "\u2197"))) : /*#__PURE__*/React.createElement("p", {
    className: "subtle"
  }, "\u6682\u65E0\u5DF2\u83B7\u53D6\u8D44\u6599\u3002")))));
}
ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(App, null));