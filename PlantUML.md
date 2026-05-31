# Argus 系統手冊 PlantUML 圖碼

本檔集中保存 `專題文件/Argus_系統手冊.docx` 中系統架構、需求模型、設計模型、實作模型與資料庫設計相關圖形的 PlantUML 原始碼。圖碼以 Argus 目前實際架構為準：React SPA、Django REST API、Celery/Redis、Playwright、PostgreSQL、點數計費、授權合規、AdminAuditLog 與可選 Hermes-Agent。

## 圖 3-1-1　Argus SaaS 分層系統架構圖

```plantuml
@startuml
title Argus SaaS 分層系統架構圖
skinparam shadowing false
skinparam componentStyle rectangle
skinparam defaultFontName Microsoft JhengHei
skinparam packageStyle rectangle
skinparam ArrowColor #315a7d
skinparam rectangle {
  BackgroundColor #F8FBFF
  BorderColor #315a7d
}

actor "一般使用者 / Staff" as User

package "用戶端層" #EAF5FF {
  [React 18 SPA\n掃描工作區 / 後台 / PWA] as SPA
  [Zustand Store\nuser / wallet / scans] as Store
  [Axios API Client\nJWT + 401 interceptor] as Axios
}

package "反向代理層" #EEF7F2 {
  node "Nginx / frontend container" as Nginx {
    [Static assets\nfrontend/dist] as Static
    [Reverse Proxy\n/api/* -> web:8000] as Proxy
  }
}

package "應用程式層" #FFF4DF {
  node "Django 5 + DRF" as Django {
    [accounts\nGoogle OAuth / JWT] as Accounts
    [scans\nScanJob API / reports] as Scans
    [billing\nWallet / Order / Transaction] as Billing
    [reviews\nReview thread / helpful] as Reviews
    [content\nCMS public API] as Content
    [admin_api\nDashboard / Audit / CMS CRUD] as Admin
  }
}

package "非同步任務與掃描層" #F1EDFF {
  queue "Redis Broker" as Redis
  node "Celery Worker" as Worker {
    [tasks.py\n狀態機推進] as Tasks
    [Playwright Chromium\nBFS crawler] as Browser
    [scanners.py\nSEO / AEO / GEO / Security] as Scanner
    [active_probes.py\nActive 探針] as Active
    [agent runner\nHermes-Agent 可選] as Agent
  }
}

database "PostgreSQL" as DB {
  [User / ScanJob / Page / Finding]
  [CoinWallet / CoinTransaction / PurchaseOrder]
  [PlatformReview / AdminAuditLog / CMS]
}

cloud "授權網站\nsame-origin target" as Target

User --> SPA : 操作瀏覽器
SPA --> Store
SPA --> Axios
Axios --> Nginx : HTTPS / REST JSON
Nginx --> Django : /api/*
Scans --> Billing : 預扣 / 結算 / 退款
Scans --> Redis : enqueue ScanJob
Redis --> Worker : dispatch task
Tasks --> Browser : 啟動爬蟲
Browser --> Target : authorized HTTP requests
Tasks --> Scanner : 四維掃描
Tasks --> Active : scan_mode=active 才執行
Tasks --> Agent : ARGUS_AGENT_ENABLED 才執行
Django --> DB : ORM read/write
Worker --> DB : Page / Finding / progress
Admin --> DB : AdminAuditLog

note right of Scans
  掃描狀態只由 tasks.py 推進；
  crawler/scanners 不直接修改 ScanJob.status。
end note

note bottom of Billing
  CoinWallet 與 CoinTransaction
  寫入只能經 billing/services.py。
end note
@enduml
```

## 圖 3-1-2　掃描任務執行資料流圖

```plantuml
@startuml
title 掃描任務執行資料流圖 end title
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam activity {
  BackgroundColor #F8FBFF
  BorderColor #315a7d
  DiamondBackgroundColor #FFF4DF
}

start
:使用者輸入 URL、掃描模式、max_pages;
:前端檢查授權勾選與 Active 額外授權;
:POST /api/scans/;

if (URL 與授權檢查通過？) then (是)
  :Django Serializer 驗證 same-origin、第三方警示、max_pages;
else (否)
  :回傳 400 / UI 顯示原因;
  stop
endif

if (點數足夠？) then (是)
  :BillingService.hold_for_scan\n預扣 max_pages × 10 coin;
else (否)
  :回傳 coin 不足;
  stop
endif

:建立 ScanJob status=queued;
:Celery enqueue run_scan_job;
:Worker 設為 crawling\n並更新 progress;
:Playwright BFS 擷取 HTML、DOM、截圖、outgoing_links;

if (使用者取消？) then (是)
  :raise ScanCancelled;
  :refund_full_for_scan;
  :status=cancelled;
  stop
endif

:Worker 設為 scanning;
:執行 SEO / AEO / GEO / Passive Security scanners;

if (scan_mode == active 且已授權？) then (是)
  :執行 SQLi / admin path / directory listing\n無破壞性探針，RPS <= 2;
endif

if (ARGUS_AGENT_ENABLED？) then (是)
  :Worker 設為 agent_testing;
  :Hermes-Agent observe -> think -> act;
  :report_ux_issue 轉成 UX Finding;
endif

:寫入 Page、Finding、top_actions、category_scores;
:BillingService.settle_scan_actual\n依實際頁數退差額;
:status=completed 並清空 progress;
:前端顯示截圖高光、拓樸圖與 Word 報告下載;
stop
@enduml
```

## 圖 3-1-3　ScanJob 核心狀態與橫切機制圖

```plantuml
@startuml
title ScanJob 核心狀態與橫切機制圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam state {
  BackgroundColor #EAF5FF
  BorderColor #315a7d
}

[*] --> queued : POST /api/scans/
queued --> crawling : Celery worker start
crawling --> scanning : BFS completed
scanning --> agent_testing : ARGUS_AGENT_ENABLED
scanning --> completed : static scan completed
agent_testing --> completed : agent finished / skipped

queued --> cancelled : cancel request
crawling --> cancelled : cooperative cancel
scanning --> cancelled : cooperative cancel
agent_testing --> cancelled : cooperative cancel

queued --> failed : exception
crawling --> failed : crawler error
scanning --> failed : scanner error
agent_testing --> completed : agent warning only

completed --> [*]
cancelled --> [*]
failed --> [*]

note right of queued
  AuthorizationConsent
  user_id / IP / timestamp / user-agent
end note

note right of crawling
  same-origin
  max_depth / max_pages
  robots.txt
  blocked detection
end note

note right of scanning
  Passive 預設
  Active 需額外授權
  RPS <= 2
end note

note bottom of completed
  settle_scan_actual(actual_pages)
  Word report / topology / findings
end note

note bottom of cancelled
  refund_full_for_scan()
  冪等退款，可被 API 與 Worker 同時呼叫
end note

note left of failed
  error_message 保留診斷資訊
  refund_full_for_scan()
end note
@enduml
```

## 圖 5-2-1　使用個案圖（Use Case Diagram）

```plantuml
@startuml
title Argus 使用個案圖
left to right direction
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false

actor "訪客" as Guest
actor "一般使用者" as User
actor "Staff 管理員" as Staff
actor "Superuser" as Super
actor "Celery Worker" as Worker
actor "外部 OAuth / AI Provider" as Provider

rectangle "Argus 網站健檢 SaaS 平台" {
  usecase "瀏覽公開頁\n(project/team/purchase/download)" as UC_Public
  usecase "Google OAuth 登入" as UC_Login
  usecase "查看/購買點數" as UC_Billing
  usecase "提交掃描任務" as UC_Submit
  usecase "同意授權聲明" as UC_Consent
  usecase "啟用 Active 測試授權" as UC_ActiveConsent
  usecase "追蹤掃描進度" as UC_Progress
  usecase "取消掃描任務" as UC_Cancel
  usecase "查看互動報告" as UC_Report
  usecase "查看拓樸圖" as UC_Topology
  usecase "下載 Word 報告" as UC_Docx
  usecase "撰寫評論 / 回覆對話" as UC_Review
  usecase "管理使用者與點數" as UC_AdminUser
  usecase "管理掃描任務" as UC_AdminScan
  usecase "管理 CMS / 方案 / 訂單" as UC_CMS
  usecase "查看稽核紀錄" as UC_Audit
  usecase "執行 BFS 爬蟲與四維掃描" as UC_WorkerScan
  usecase "執行 Hermes-Agent UX 測試" as UC_Agent
}

Guest --> UC_Public
Guest --> UC_Login
User --> UC_Billing
User --> UC_Submit
User --> UC_Progress
User --> UC_Cancel
User --> UC_Report
User --> UC_Topology
User --> UC_Docx
User --> UC_Review
Staff --> UC_AdminUser
Staff --> UC_AdminScan
Staff --> UC_CMS
Super --> UC_Audit
Worker --> UC_WorkerScan
Worker --> UC_Agent
Provider --> UC_Login
Provider --> UC_Agent

UC_Submit ..> UC_Consent : <<include>>
UC_Submit ..> UC_ActiveConsent : <<extend>>\nscan_mode=active
UC_Report ..> UC_Docx : <<extend>>
Staff --|> User
Super --|> Staff
@enduml
```

## 圖 5-3-1　活動圖：提交掃描任務（Activity Diagram）

```plantuml
@startuml
title 活動圖：提交掃描任務
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false

|使用者|
start
:登入系統;
:輸入目標網址;
:選擇單頁/整站與 passive/active;
:勾選授權聲明;

|React SPA|
:估算預扣點數;
:送出 POST /api/scans/;

|Django API|
:驗證 JWT 與 request payload;
if (授權聲明有效？) then (是)
else (否)
  :回傳 400;
  |使用者|
  :修正授權勾選;
  stop
endif

if (URL 合規？\nsame-origin / third-party warning) then (是)
else (否)
  :回傳 URL 驗證錯誤;
  stop
endif

if (點數足夠？) then (是)
  :hold_for_scan();
else (否)
  :回傳 coin 不足;
  stop
endif

:建立 ScanJob queued;
:送入 Celery 佇列;

|Celery Worker|
:crawling;
:Playwright BFS 爬蟲;
if (使用者取消？) then (是)
  :refund_full_for_scan();
  :status=cancelled;
  stop
endif
:scanning;
:四維掃描產生 Finding;
if (Active 授權？) then (是)
  :執行無破壞性 Active probes;
endif
if (Agent 啟用？) then (是)
  :Hermes-Agent UX 測試;
endif
:settle_scan_actual();
:status=completed;

|React SPA|
:輪詢狀態完成;
:呈現截圖高光、拓樸圖、Word 報告下載;
stop
@enduml
```

## 圖 5-4-1　分析類別圖（Analysis Class Diagram）

```plantuml
@startuml
title 分析類別圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam classAttributeIconSize 0

class User {
  id
  username
  email
  is_staff
  is_superuser
}

class ScanJob {
  id
  original_url
  scan_mode
  status
  max_depth
  max_pages
  progress
  overall_score
}

class Page {
  id
  final_url
  status_code
  title
  depth
  screenshot
  outgoing_links
}

class Finding {
  id
  category
  severity
  title
  description
  remediation
  evidence
  selector
  bounding_box
}

class CoinWallet {
  id
  balance
  total_purchased_ntd
  total_scans_used
}

class CoinTransaction {
  id
  amount
  kind
  balance_after
  note
}

class PricingPlan {
  id
  name
  price_ntd
  coins
  is_active
}

class PurchaseOrder {
  id
  buyer_name
  buyer_email
  invoice_type
  carrier_type
  status
}

class PlatformReview {
  id
  rating
  content
  is_featured
}

class ReviewMessage {
  id
  body
  image
  is_admin
}

class AuthorizationConsent {
  id
  ip_address
  user_agent
  consent_text
  created_at
}

class AgentSession {
  id
  provider
  model
  total_tokens
  status
}

class AdminAuditLog {
  id
  action
  target_object_repr
  payload
  created_at
}

User "1" -- "1" CoinWallet
User "1" -- "0..*" ScanJob
User "1" -- "0..*" PurchaseOrder
User "1" -- "0..1" PlatformReview
User "1" -- "0..*" AuthorizationConsent
User "1" -- "0..*" AdminAuditLog : actor

ScanJob "1" -- "0..*" Page
ScanJob "1" -- "0..*" Finding
Page "1" -- "0..*" Finding
ScanJob "1" -- "0..*" AgentSession

CoinWallet "1" -- "0..*" CoinTransaction
CoinTransaction "0..1" -- "0..1" ScanJob
PurchaseOrder "0..1" -- "1" PricingPlan
PurchaseOrder "0..1" -- "0..1" CoinTransaction

PlatformReview "1" -- "0..*" ReviewMessage
@enduml
```

## 圖 6-1-1　掃描任務循序圖（Sequential Diagram）

```plantuml
@startuml
title 掃描任務循序圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
autonumber

actor User as "使用者"
participant SPA as "React SPA"
participant API as "Django DRF\nScanJobViewSet"
participant Billing as "BillingService"
queue Redis as "Redis / Celery Broker"
participant Worker as "Celery Worker\nrun_scan_job"
participant Browser as "Playwright\nChromium"
participant Scanner as "四維 Scanner\nSEO/AEO/GEO/Security"
participant Agent as "Hermes-Agent\n(optional)"
database DB as "PostgreSQL"

User -> SPA : 填寫 URL、掃描模式、授權勾選
SPA -> API : POST /api/scans/
API -> API : Serializer 驗證 URL / 授權 / Active / max_pages
API -> Billing : hold_for_scan(scan)
Billing -> DB : select_for_update wallet\ncreate CoinTransaction(hold)
API -> DB : create ScanJob(status=queued)\ncreate AuthorizationConsent
API -> Redis : enqueue run_scan_job(scan_id)
API --> SPA : 201 ScanJob

loop 前端輪詢
  SPA -> API : GET /api/scans/{id}/status/
  API --> SPA : status + progress
end

Redis -> Worker : dispatch task
Worker -> DB : status=crawling\nprogress.phase=crawling
Worker -> Browser : crawl_site(original_url)
Browser -> DB : save Page(html/dom/screenshot/links)
Worker -> DB : status=scanning
Worker -> Scanner : scan pages
Scanner -> DB : create Finding\nupdate scores/top_actions

alt scan_mode=active
  Worker -> Scanner : run active_probes(RPS <= 2)
  Scanner -> DB : create security Findings
end

alt ARGUS_AGENT_ENABLED
  Worker -> DB : status=agent_testing
  Worker -> Agent : observe -> think -> act
  Agent -> Browser : click/type/scroll/screenshot tools
  Agent -> DB : persist UX Finding
end

Worker -> Billing : settle_scan_actual(actual_pages)
Billing -> DB : create settle transaction\nupdate wallet
Worker -> DB : status=completed\nprogress={}
SPA -> API : GET findings/pages/report
API -> DB : read Page/Finding
API --> SPA : interactive report / docx blob
@enduml
```

## 圖 6-2-1　設計類別圖（Design Class Diagram）

```plantuml
@startuml
title 設計類別圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam classAttributeIconSize 0

class ScanJobViewSet <<DRF ViewSet>> {
  +create(request)
  +status(request, pk)
  +cancel(request, pk)
  +topology(request, pk)
  +report(request, pk)
}

class ScanJobCreateSerializer <<Serializer>> {
  +validate(attrs)
  +create(validated_data)
}

class RunScanJobTask <<Celery Task>> {
  +run_scan_job(scan_id)
  -_write_progress(scan_id, done, total, phase)
}

class Crawler <<module>> {
  +crawl_site(url, max_depth, max_pages, progress_callback)
}

class StaticScanners <<module>> {
  +run_scanners(page)
  +build_site_findings(scan)
}

class ActiveProbes <<module>> {
  +run_active_probes(scan)
}

class AgentRunner <<module>> {
  +run_agent_for_scan(scan)
  +persist_agent_issues(session, issues)
}

class BillingService <<service>> {
  +hold_for_scan(scan)
  +settle_scan_actual(scan, actual_pages)
  +refund_full_for_scan(scan)
  +grant_monthly_bonus(user)
  +purchase_coins(user, plan, order)
  +adjust_coin_manual(wallet, delta, note, actor)
}

class ReportBuilder <<service>> {
  +build_scan_report(scan)
}

class AdminAuditService <<service>> {
  +record(action, actor, target, payload)
}

ScanJobViewSet --> ScanJobCreateSerializer
ScanJobViewSet --> BillingService : create/cancel
ScanJobViewSet --> ReportBuilder
ScanJobCreateSerializer --> BillingService : hold_for_scan
ScanJobViewSet --> RunScanJobTask : enqueue
RunScanJobTask --> Crawler
RunScanJobTask --> StaticScanners
RunScanJobTask --> ActiveProbes : active only
RunScanJobTask --> AgentRunner : optional
RunScanJobTask --> BillingService : settle/refund
BillingService --> AdminAuditService : admin adjust
@enduml
```

## 圖 7-1-1　Docker Compose 佈署圖（Deployment Diagram）

```plantuml
@startuml
title Docker Compose 佈署圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false

node "User Browser" as Browser

node "Docker Host" {
  node "frontend\nnginx:1.26-alpine" as Frontend {
    artifact "frontend/dist" as Dist
  }

  node "web\nDjango + DRF\nport 8000" as Web {
    artifact "backend/config"
    artifact "backend/apps"
  }

  node "worker\nCelery + Playwright" as Worker {
    artifact "Chromium runtime"
  }

  database "db\nPostgreSQL:5432" as DB
  queue "redis\nRedis:6379" as Redis
}

cloud "Authorized target site" as Target
cloud "Google OAuth / AI Providers" as Provider

Browser --> Frontend : HTTP/HTTPS
Frontend --> Web : /api/* -> web:8000
Web --> DB : ORM
Web --> Redis : enqueue task
Worker --> Redis : consume task
Worker --> DB : Page / Finding / progress
Worker --> Target : Playwright HTTP
Web --> Provider : OAuth token verify
Worker --> Provider : optional Agent API

note bottom of Worker
  Playwright browser 必須在容器或專案 .ms-playwright，
  不使用使用者層級瀏覽器快取。
end note
@enduml
```

## 圖 7-2-1　套件架構圖（Package Diagram）

```plantuml
@startuml
title Django 後端套件架構圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam packageStyle rectangle

package "backend/config" as Config {
  [settings.py]
  [urls.py]
  [celery.py]
}

package "apps.accounts" as Accounts
package "apps.scans" as Scans
package "apps.billing" as Billing
package "apps.reviews" as Reviews
package "apps.content" as Content
package "apps.admin_api" as Admin
package "apps.agent" as Agent
package "apps.insights" as Insights

Accounts ..> Config
Scans ..> Config
Billing ..> Config
Reviews ..> Config
Content ..> Config
Admin ..> Config
Agent ..> Config
Insights ..> Config

Scans --> Billing : hold / settle / refund
Scans --> Agent : optional UX test
Admin --> Billing : manual adjustment
Admin --> Reviews : admin reply
Admin --> Content : CMS CRUD
Billing --> Accounts : User wallet
Reviews --> Accounts : reviewer / message author
Scans --> Accounts : scan owner

note right of Billing
  services.py 是錢包唯一寫入入口
end note

note right of Scans
  tasks.py 是 ScanJob 狀態機唯一推進處
end note
@enduml
```

## 圖 7-3-1　系統元件圖（Component Diagram）

```plantuml
@startuml
title 系統元件圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
skinparam componentStyle rectangle

component "React SPA" as SPA {
  [ScanForm]
  [FindingsWorkspace]
  [TopologyPage]
  [BillingWizard]
  [AdminDashboard]
}

component "Django REST API" as API {
  [Auth API]
  [Scans API]
  [Billing API]
  [Reviews API]
  [Admin API]
  [Content API]
}

component "Domain Services" as Services {
  [BillingService]
  [ReportBuilder]
  [AdminAuditLog]
}

component "Scan Runtime" as Runtime {
  [Celery Task]
  [Playwright Crawler]
  [Static Scanners]
  [Active Probes]
  [Hermes-Agent]
}

database "PostgreSQL" as DB
queue "Redis" as Redis
cloud "Authorized Website" as Target
cloud "OAuth / AI APIs" as External

SPA --> API : REST / JSON
API --> Services
API --> Redis : enqueue
Runtime --> Redis : consume
Runtime --> Target : browser automation
Runtime --> Services : settle/refund/report
Runtime --> External : optional AI tool calling
API --> DB
Services --> DB
Runtime --> DB
@enduml
```

## 圖 7-4-1　ScanJob 狀態機圖（State Machine）

```plantuml
@startuml
title ScanJob 狀態機圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false

[*] --> queued : create ScanJob\nhold_for_scan
queued --> crawling : worker starts
crawling --> scanning : crawl_site completed
scanning --> agent_testing : agent enabled
scanning --> completed : static scan done
agent_testing --> completed : agent finished or skipped

queued --> cancelled : cancel API
crawling --> cancelled : ScanCancelled
scanning --> cancelled : ScanCancelled
agent_testing --> cancelled : ScanCancelled

queued --> failed : exception
crawling --> failed : browser / network error
scanning --> failed : scanner error

completed : settle_scan_actual(actual_pages)
completed : progress = {}
cancelled : refund_full_for_scan()
cancelled : error_message = 使用者已終止掃描
failed : refund_full_for_scan()
failed : error_message = exception summary

completed --> [*]
cancelled --> [*]
failed --> [*]
@enduml
```

## 圖 8-1-1　資料庫 ER 圖（Entity-Relationship Diagram）

```plantuml
@startuml
title Argus 資料庫 ER 圖
skinparam defaultFontName Microsoft JhengHei
skinparam shadowing false
hide circle

entity "auth_user" as user {
  * id : int <<PK>>
  --
  username : varchar
  email : varchar
  is_staff : bool
  is_superuser : bool
}

entity "scans_scanjob" as scan {
  * id : uuid <<PK>>
  --
  user_id : int <<FK>>
  original_url : text
  status : varchar
  scan_mode : varchar
  progress : json
}

entity "scans_page" as page {
  * id : int <<PK>>
  --
  scan_id : uuid <<FK>>
  final_url : text
  title : varchar
  screenshot : file
  outgoing_links : json
}

entity "scans_finding" as finding {
  * id : int <<PK>>
  --
  scan_id : uuid <<FK>>
  page_id : int <<FK nullable>>
  category : varchar
  severity : varchar
  evidence : text
}

entity "billing_coinwallet" as wallet {
  * id : int <<PK>>
  --
  user_id : int <<FK unique>>
  balance : int
  total_purchased_ntd : int
}

entity "billing_cointransaction" as tx {
  * id : int <<PK>>
  --
  wallet_id : int <<FK>>
  scan_job_id : uuid <<FK nullable>>
  amount : int
  kind : varchar
  balance_after : int
}

entity "billing_pricingplan" as plan {
  * id : int <<PK>>
  --
  name : varchar
  price_ntd : int
  coins : int
}

entity "billing_purchaseorder" as order {
  * id : uuid <<PK>>
  --
  user_id : int <<FK>>
  plan_id : int <<FK>>
  transaction_id : int <<FK nullable>>
  status : varchar
}

entity "reviews_platformreview" as review {
  * id : int <<PK>>
  --
  user_id : int <<FK unique>>
  rating : int
  content : text
}

entity "reviews_reviewmessage" as msg {
  * id : int <<PK>>
  --
  review_id : int <<FK>>
  author_id : int <<FK>>
  is_admin : bool
  body : text
}

entity "admin_api_adminauditlog" as audit {
  * id : int <<PK>>
  --
  actor_id : int <<FK>>
  action : varchar
  payload : json
}

user ||--o{ scan
scan ||--o{ page
scan ||--o{ finding
page ||--o{ finding
user ||--|| wallet
wallet ||--o{ tx
scan ||--o{ tx
user ||--o{ order
plan ||--o{ order
tx ||--o{ order
user ||--o| review
review ||--o{ msg
user ||--o{ msg
user ||--o{ audit
@enduml
```
