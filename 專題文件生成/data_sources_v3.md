# Argus 系統手冊 v3 — 真實可引用資料來源

> 原則：禁止估算/猜測。所有數據必須真實存在、可引用，並附「標題＋連結」。
> 本檔記錄 v3 文件中所有對外引用數據的出處，供查核與參考資料章節使用。
> 查證日期：2026-05-29

---

## 1. 競品定價（圖 2-1-1 主要競品月費比較）

| 工具 | 方案 | 官方定價 | 換算 NT$/月 | 來源 |
|---|---|---|---|---|
| Argus（本系統） | 按需點數 | 單次掃描最低約 NT$300 | 300 | 本系統定價（自有產品，非外部引用） |
| Google Search Console | — | 免費 | 0 | https://search.google.com/search-console/about |
| Screaming Frog SEO Spider | 授權 | €245／年／使用者 | 714（€245÷12×35） | https://www.screamingfrog.co.uk/seo-spider/pricing/ |
| Ahrefs | Starter | US$29／月 | 928（×32） | https://ahrefs.com/pricing |
| SEMrush | Pro | US$139.95／月 | 4,478（×32） | https://www.semrush.com/pricing/seo/ |

**匯率來源**：台灣銀行牌告匯率 https://rate.bot.com.tw/xrt
約 1 USD≈NT$32、1 EUR≈NT$35（匯率每日浮動，數值僅供比較參考）。

備註：原 v2 圖內標題重複「圖 2-1-1」前綴已移除（標號由 caption 提供）；
圖內中文以標楷體（kaiu.ttf）繪製，解決亂碼；配色改淺色系。

---

## 1b. 第 1 章 表 1-2-1（主流網站分析 SaaS 平台功能特性比較表）

> 修訂原因：原 v3 表 1-2-1 將 Argus 與單一用途命令列工具（Nmap、Dirsearch、Katana 等）
> 並列比較，比較基準不對等。改以「同屬雲端 SaaS 網站分析平台」之主流商業產品作對等比較，
> 凸顯 Argus「AEO/GEO + 一站式四維整合」之差異化定位。

| 平台 | 定位 | 方案 | 官方定價 | 換算 NT$/月 | 來源 |
|---|---|---|---|---|---|
| Argus（本系統） | 四維網站健檢 SaaS | 按需點數 | 最低約 NT$300 起 | 300 | 本系統定價（自有產品，系統實測 2026） |
| SEMrush | SEO／數位行銷套件 | Pro | US$139.95／月 | 4,478（×32） | https://www.semrush.com/pricing/seo/ |
| Ahrefs | SEO／外鏈分析 | Starter | US$29／月 | 928（×32） | https://ahrefs.com/pricing |
| Moz Pro | SEO 分析平台 | Starter | US$49／月 | 1,568（×32） | https://moz.com/products/pro/pricing |
| Sucuri | 網站資安防護 | Basic Platform | US$199.99／年 | 533（US$199.99÷12×32） | https://sucuri.net/website-security-platform/signup/ |

**匯率來源**：台灣銀行牌告匯率 https://rate.bot.com.tw/xrt 約 1 USD≈NT$32（每日浮動，僅供比較參考）。
查證日期：2026-05。

差異化重點：四大 SEO 平台（SEMrush／Ahrefs／Moz Pro）皆無 AEO/GEO 與資安掃描；
Sucuri 僅資安、無 SEO/AEO/GEO；唯 Argus 一站式整合 SEO+AEO+GEO+資安四維。

---

## 2. 市場規模（取代 v2 估算數字）

- **台灣中小企業家數**：逾 167.4 萬家（2023 年），占全體企業 98% 以上。
  - 來源：經濟部《2024 年中小企業白皮書》
    https://www.sme.gov.tw/article-tw-2853-13097
- v2 的「35 萬家中小企業電商網站（資策會 MIC）」「1% 滲透率 → 年收入 NT$2,100 萬」
  等推估數字**已移除**，改為可引用的官方統計 + 質化敘述。
- v2 的「目標市場區隔分布（估計）」圓餅圖**已刪除**（查無可引用之區隔比例，
  依規範移除，2-1 改以質化敘述 + 競品月費（真實）佐證）。

---

## 3. 技術棧版本（第 3 章）

各技術之官方文件連結（參考資料章節列出）：

| 技術 | 版本 | 官方來源 |
|---|---|---|
| Django | 5.1 | https://www.djangoproject.com/ |
| Django REST Framework | 3.15 | https://www.django-rest-framework.org/ |
| React | 18 | https://react.dev/ |
| Vite | 5 | https://vitejs.dev/ |
| Playwright | 1.45 | https://playwright.dev/ |
| Celery | 5.4 | https://docs.celeryq.dev/ |
| Redis | 7.2 | https://redis.io/ |
| PostgreSQL | 16 | https://www.postgresql.org/ |
| Docker | 26 | https://www.docker.com/ |
| Nginx | 1.26 | https://nginx.org/ |
| PlantUML | 1.2024.x | https://plantuml.com/ |

---

## 4. 待後續任務補齊的引用

- OWASP Top 10（資安掃描章節背景）：https://owasp.org/Top10/
- AI 搜尋／AEO/GEO 趨勢背景統計：Task 9 參考資料時補真實來源。
- 第 1 章 表 1-2-1 競品比較之來源欄：Task 10 真實化。
