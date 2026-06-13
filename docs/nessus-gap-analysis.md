# Nessus vs Argus 差距分析

**建立日期：** 2026-06-07
**用途：** 專題初審參考資料、後續補齊功能的優先順序依據

> 實作優先順序與完整攻擊鏈架構見 [`docs/capstone-roadmap.md`](capstone-roadmap.md)

---

## Argus 目前掃描能力全覽

| 模組 | 能力 |
|---|---|
| **Playwright 爬蟲** | BFS 多頁爬取、JS 渲染後 HTML |
| **Katana** | JS 端點挖掘、秘鑰偵測（API key/token/private key）、Tech stack 識別、Vite dev server 暴露 |
| **Nuclei** | CVE、vulnerabilities、misconfigs、exposures、default-logins（fast/deep 雙模式） |
| **Security（rule-based）** | HTTPS 檢查、HSTS/CSP 存在性/X-Frame-Options/X-Content-Type-Options、CSRF token、PII 偵測 |
| **SEO** | meta title/description、H1、圖片 alt、canonical URL |
| **AEO** | FAQPage/HowTo Schema 偵測 |
| **GEO** | JSON-LD 結構化資料、JS 渲染差距、llms.txt、robots.txt AI 爬蟲封鎖 |
| **免費工具** | 測速、釣魚 URL 分析、釣魚郵件分析 |

---

## 與 Nessus 的差距分析

### 完全缺少（Web 層面，補起來最有價值）

| # | 功能 | Nessus 做什麼 | Argus 現況 | 補齊難度 |
|---|---|---|---|---|
| 1 | **SSL/TLS 深度分析** | 憑證到期日、自簽憑證、弱加密套件（RC4/3DES）、過期協議（TLS 1.0/1.1）、憑證鏈完整性 | 只判斷 scheme 是否為 HTTPS | 低（Python `ssl` 模組） |
| 2 | **Cookie 安全旗標** | Secure、HttpOnly、SameSite 屬性逐一檢查 | 完全沒有 | 低（Playwright 可直接讀 cookies） |
| 3 | **資訊洩露標頭** | Server 版本洩露（`Apache/2.4.x`）、`X-Powered-By`、`X-Generator`、`X-AspNet-Version` | 完全沒有 | 低（分析 response headers） |
| 4 | **SRI 缺失** | 外部 CDN `<script>/<link>` 缺少 `integrity` hash | 完全沒有 | 低（HTML parser 已有基礎） |
| 5 | **CORS 設定分析** | `Access-Control-Allow-Origin: *` 過寬、credentials + wildcard 錯誤組合 | 完全沒有 | 低（分析 CORS headers） |
| 6 | **CSP 品質分析** | `unsafe-inline`、`unsafe-eval`、wildcard source 偵測 | 只偵測有無 CSP header | 中（需解析 CSP policy 字串） |
| 7 | **DNS / 郵件安全** | SPF record、DKIM 設定、DMARC 政策、DNSSEC | 無（免費工具釣魚郵件分析中只解析 header，未做 DNS 查詢） | 中（需 `dnspython`） |
| 8 | **OWASP Top 10 對映** | 每個 finding 標記對應的 OWASP 分類（A01~A10）、CWE 編號 | finding 有 category/impact_area，但沒有 OWASP/CWE 對映 | 低（報告層面加標籤） |

### 部分覆蓋（Nuclei 有幫忙，但不完整）

| # | 功能 | Nessus 做什麼 | Argus 現況 | 差距 |
|---|---|---|---|---|
| 9 | **敏感路徑暴露** | `/.git/HEAD`、`/.env`、`/phpinfo.php`、備份檔（`.bak/.old`）、目錄列舉 | Nuclei `exposures` tag 有部分覆蓋 | Nuclei 模板不一定全裝，且沒有客製整合 |
| 10 | **第三方 JS 庫漏洞** | jQuery/Bootstrap/lodash 舊版本比對 CVE | Katana 識別 tech stack，但無版本→CVE 對比 | 缺 version-to-CVE 資料庫整合 |
| 11 | **預設憑證測試** | 廣泛的預設帳密嘗試清單 | Nuclei `default-logins` 模板有基本涵蓋 | 覆蓋率依模板安裝狀況而異 |

### Nessus 有但 Argus 不適合做（架構差異太大）

| # | 功能 | 說明 |
|---|---|---|
| 12 | **Port / 網路層掃描** | Nessus 用 nmap 做 TCP/UDP port scan、service fingerprinting；Argus 定位是 Web scanner，網路層超出範疇 |
| 13 | **主機 / OS 層掃描** | patch level、OS 配置審計；需要 agent 安裝或 SSH 存取，與 Argus 純 Web 架構不相容 |
| 14 | **認證掃描（Authenticated Scan）** | 提供帳密後登入再掃內部頁面；需要大幅架構改動（目前 Argus 只掃公開頁面） |
| 15 | **合規性稽核（PCI DSS / CIS / HIPAA）** | 需要整套基礎設施存取；Web-only 工具無法達到 Nessus 的合規深度 |

---

## 補齊優先順序建議

依「視覺衝擊 × 實作容易度」排序：

### 第一優先（低成本高回報，適合 1-2 週衝刺）

| 功能 | 預估工時 | 實作方向 |
|---|---|---|
| SSL/TLS 深度分析 | 1-2 天 | Python `ssl` 模組連線取得憑證資訊；`requests` 取 cipher suite |
| Cookie 安全旗標 | 半天 | Playwright `context.cookies()` 讀取後逐項檢查旗標 |
| 資訊洩露標頭偵測 | 半天 | 掃描 `Server`、`X-Powered-By`、`X-Generator` 等 response headers |
| OWASP Top 10 對映 | 1 天 | 在 `make_finding()` 或 Finding model 加入 `owasp_category`、`cwe_id` 欄位 |

### 第二優先（中等成本）

| 功能 | 預估工時 | 實作方向 |
|---|---|---|
| CORS 設定分析 | 1 天 | 分析 `Access-Control-*` headers，主動送 OPTIONS 探測 |
| CSP 品質分析 | 1-2 天 | 解析 CSP policy 字串，偵測 `unsafe-inline`、`unsafe-eval`、wildcard |
| SRI 缺失偵測 | 半天 | HTML parser 已有基礎，新增偵測外部 `<script>/<link>` 缺少 `integrity` |

### 第三優先（視時間而定）

| 功能 | 預估工時 | 實作方向 |
|---|---|---|
| DNS/郵件安全（SPF/DKIM/DMARC） | 2 天 | `uv add dnspython`，查詢目標網域的 TXT records |
| 第三方 JS 庫 CVE 對比 | 3-5 天 | 需要整合 OSS Index 或 Retire.js 的版本→CVE 資料庫 |

---

## 定位說明（可直接用於簡報）

> Argus 定位是「Web 應用層安全 + 內容品質」一站式掃描器；Nessus 則是「網路/主機/應用」全層次企業弱點管理平台。
>
> 兩者在 Web 應用層有重疊，但：
> - **Argus 的獨特優勢**：SEO / AEO / GEO 三個維度是 Nessus 完全沒有的
> - **Nessus 的明顯優勢**：SSL 深度分析、Cookie 旗標、網路層掃描、合規性稽核
>
> 補齊第一優先項目後，Argus 在純 Web 掃描範疇的能力可達到 Nessus Web Plugin 子集的 70%+。
