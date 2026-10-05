# 数据类型②大宗交易 / ③融资融券 — 官方免费端点（Phase 0 已实测）

与①龙虎榜同架构：交易所官方为主源，TDX 免费版无此历史（仅快照）。
以下端点均于 2026-10-05 实测验证（2021-01 历史可达 + 当日数据正常）。

## ② 大宗交易（block trades）

### SSE（一天一发，买卖营业部内联）
```
GET http://query.sse.com.cn/commonQuery.do
    ?isPagination=true&pageHelp.pageSize=1000&pageHelp.pageNo=1
    &pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1
    &sqlId=COMMON_SSE_XXPL_JYXXPL_DZJYXX_L_1      # 股票/基金（L_2=债券）
    &stockId=&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
Headers: Referer: http://www.sse.com.cn/disclosure/diclosure/block/deal/dzjyxx/
```
- 日期格式 **带横线**（注意：与两融端点相反）。
- 行字段：`tradedate, stockid, abbrname, tradeprice(元), tradeamount(万元),
  tradeqty(万股/万份), branchbuy(买方营业部), branchsell(卖方营业部),
  ifZc(是否专场), NUM`
- 实测：2026-09-30 31 行；2021-01-05 100+ 行，单页 1000 行内一日取完。

### SZSE（日榜 + 个股明细钻取）
```
日榜   GET https://www.szse.cn/api/report/ShowReport/data
       ?SHOWTYPE=JSON&CATALOGID=1932_dzjyzqjy_after&TABKEY=tab1
       &txtStart=txtEnd=YYYY-MM-DD&PAGENO=N        # pagesize 固定 10
明细   同 API &CATALOGID=1265&txtkey2=<code>
       &txtKsrq=<start>&txtZzrq=<end>              # 参数取自日榜行 bz 链接
Headers: Referer: https://www.szse.cn/
```
- 日榜行：`dqrq, zqdm, zqjc, cjje(万元), cjsl(万股), phdj, hz`；2021-01-05
  ~50 行（3 页）。
- 明细行（每股可能多笔）：`cjrq, zqdh, zqjc, cjjg(元), cjgsnew(万股),
  cjjenew(万元), bxwmc(买方营业部), sxwmc(卖方营业部)` —— "机构专用"
  直接出现在买/卖方名称中。

## ③ 融资融券（margin，个股日度）

### SSE（一天 1-2 发，单位元，字段最全）
```
GET http://query.sse.com.cn/commonSoaQuery.do
    ?isPagination=true&pageHelp.pageSize=3000&pageHelp.pageNo=N
    &pageHelp.beginPage=N&pageHelp.cacheSize=1&pageHelp.endPage=N
    &sqlId=RZRQ_MX_INFO
    &beginDate=YYYYMMDD&endDate=YYYYMMDD
Headers: Referer: http://www.sse.com.cn/market/othersdata/margin/detail/
```
- 日期格式 **无横线紧凑**（YYYYMMDD；带横线返回空——坑）。
- 单页上限实测 2000 行；2026-09-30 共 2001 行（第 2 页补 1 行）；
  2021-01-05 全量 1090 行。
- 行字段（全为数值，**单位元/股**）：`opDate, stockCode, securityAbbr,
  rzye(融资余额), rzmre(融资买入额), rzche(融资偿还额),
  rqyl(融券余量), rqmcl(融券卖出量), rqchl(融券偿还量), rw`
- 汇总版 sqlId=RZRQ_HZ_INFO（市场合计，同参数）。

### SZSE（个股明细 = tab2，日期参数名不同）
```
GET https://www.szse.cn/api/report/ShowReport/data
    ?SHOWTYPE=JSON&CATALOGID=1837_xxpl&TABKEY=tab2
    &txtDate=YYYY-MM-DD&PAGENO=N
Headers: Referer: https://www.szse.cn/
```
- 日期参数名是 **txtDate**（txtStart/txtEnd 在此 catalog 无效——坑）。
- pagesize 固定 20：单日 ~920 只标的 ≈ 46 页。全历史回填成本
  ≈ 46 页 × 1393 天 ≈ 64k 请求（约 5h，隔夜任务）。
- 行字段：`zqdm, zqjc, jrrzmr(融资买入), jrrzye(融资余额), jrrjmc(融资偿还),
  jrrjyl(融券余量), jrrjye(融券余额), jrrzrjye(融资融券余额)`；
  单位待建管线时用 SSE 明细交叉核对钉死（SSE 侧单位已确认为元/股）。
- tab1=市场汇总历史（pagesize -1，4009 行无日期列，不适用）。

## 采集节奏（与①共用原则）

- SZSE 严禁多进程并发（见 LHB_PIPELINE.md 教训）；限速 ≥0.3s/请求。
- SSE 无此现象，但仍统一走 ThrottledClient。
- 断点续跑 + 状态合并写 + raw 只增不改，同①的 collector 框架复用。
