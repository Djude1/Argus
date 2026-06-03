# Nuclei 整合設計文件

**日期**：2026-06-03
**狀態**：待實作
**範疇**：Phase 1 快速掃描（免費層）

---

## 背景與目標

Argus 目前的資安掃描涵蓋：被動 header 檢查、PII 偵測、Katana JS 秘鑰分析，以及 active_probes（admin 路徑枚舉、SQLi boolean、開放目錄）。覆蓋範圍有限，缺少 XSS、CORS、CVE、JWT、SSRF 等常見漏洞類別。

本次整合目標：
- 引入 **Nuclei**（29k stars，ProjectDiscovery）補強資安偵測廣度
- 將 Katana 從 Docker 改為本機 binary，消除 Docker 啟動 overhead
- 以 **並行執行** 控制總掃描時間（快速掃描優先）
- 刪除 `active_probes.py`，由 Nuclei 取代其功能並大幅擴展

---

## 商業分層設計

| 層級 | 觸發條件 | 包含內容 |
|---|---|---|
| **免費（快速掃描）** | 所有使用者，預設 | crawl + 四維 scan + Katana binary + Nuclei 精選模板（5 分鐘上限） |
| **付費（深度掃描）** | `active_testing_authorized=True`，未來實作 | 免費全部 + Nuclei 完整模板 + 更長 timeout + 額外工具（dalfox/sqlmap）|

Phase 1 只實作免費層。`ScanJob` schema 不變，`active` mode gate 保留作為付費功能預留位置。

---

## 架構變動

### 流程對比

```
改前：
crawl → scan → katana(Docker) → site_signals → active_probes → agent

改後：
crawl → scan → ┌ katana(binary)  ┐ ThreadPoolExecutor 並行
               └ nuclei(binary)  ┘
               → merge findings → site_signals → agent
```

### 檔案異動清單

| 動作 | 檔案 | 說明 |
|---|---|---|
| 新增 | `apps/scans/nuclei_scanner.py` | Nuclei subprocess 封裝 |
| 修改 | `apps/scans/katana_scanner.py` | Docker → binary |
| 修改 | `apps/scans/tasks.py` | 並行執行 + 移除 active_probes 呼叫 |
| 刪除 | `apps/scans/active_probes.py` | Nuclei 已完整取代 |
| 刪除 | `apps/scans/tests_active_probes.py` | 對應測試一併移除 |
| 新增 | `apps/scans/tests_nuclei_scanner.py` | Nuclei 模組單元測試 |

---

## nuclei_scanner.py 設計

### 執行參數

```bash
nuclei \
  -u <target_url> \
  -tags cves,vulnerabilities,misconfigurations,exposures,default-logins \
  -timeout 15 \
  -c 25 \
  -j \
  -o /tmp/nuclei_<scan_id>.jsonl \
  -silent
```

- `-tags`：精選五類高價值模板，排除 `fuzzing`（太慢）和 `helpers`（非漏洞）
- `-timeout 15`：每個 HTTP request 連線等待上限 15 秒（Nuclei 內部預設 5 秒）
- `-c 25`：25 執行緒並行，平衡速度與靶機壓力
- `-j`：JSONL 格式輸出，每行一筆 finding
- 外層 subprocess timeout：360 秒（6 分鐘硬性上限，超時 kill process）

### Binary 偵測（silent-fail）

```python
def run_nuclei(url: str, scan_job_id: int) -> list[dict]:
    if not shutil.which("nuclei"):
        append_log(scan_job_id, "Nuclei binary 未安裝，略過", level="warn")
        return []
    # ... 執行 subprocess
```

### Finding Mapping

| Nuclei JSON 欄位 | Finding 欄位 | 備註 |
|---|---|---|
| `info.name` | `title` | 直接對應 |
| `info.severity` | `severity` | critical/high/medium/low 已相容 |
| `info.description` | `description` | |
| `info.remediation` | `remediation` | 空時填「請參考官方修補建議」|
| `matched-at` | `evidence` | 命中 URL |
| `extracted-results` | `evidence`（附加） | 額外證據字串 |
| 固定 `"security"` | `category` | 所有 Nuclei finding 歸入 security |
| 固定 `None` | `page` | 不綁定特定頁面（同 Katana） |
| 依 severity | `priority_score` | critical=90, high=75, medium=55, low=30 |
| 固定 `0.85` | `confidence` | 社群驗證模板，預設高信心值 |

### 去重邏輯

同一 `(template-id, matched-at)` 組合在 parse 階段用 `set` 去重，不依賴 DB constraint。

---

## katana_scanner.py 變動

移除 `docker run projectdiscovery/katana ...`，改為直接呼叫本機 `katana` binary：

```bash
katana -u <url> -d <depth> -jc -jsl -td -json-output /tmp/katana_<id>.json
```

同樣加上 `shutil.which("katana")` 偵測，binary 不存在則 silent-fail。

---

## tasks.py 並行段落

```python
import threading
from concurrent.futures import ThreadPoolExecutor

# scanning 主迴圈結束後
cancel_event = threading.Event()

def _watch_cancel(scan_job_id: int, event: threading.Event) -> None:
    while not event.wait(timeout=5):
        if is_cancelled(scan_job_id):
            event.set()

watcher = threading.Thread(
    target=_watch_cancel, args=(scan_job_id, cancel_event), daemon=True
)
watcher.start()

try:
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_katana = executor.submit(run_katana, scan_job.normalized_url,
                                   scan_job.max_depth, scan_job.max_pages,
                                   cancel_event)
        f_nuclei = executor.submit(run_nuclei, scan_job.normalized_url, scan_job_id,
                                   cancel_event)

    katana_findings, katana_tech = f_katana.result()
    nuclei_findings = f_nuclei.result()
finally:
    cancel_event.set()  # 確保 watcher thread 退出

for finding in katana_findings + nuclei_findings:
    Finding.objects.create(scan_job=scan_job, page=None, **finding)
```

---

## 錯誤處理

| 情境 | 處理方式 |
|---|---|
| Binary 不存在 | silent-fail，`append_log` warn，回傳空 list |
| Subprocess timeout（360s） | `proc.kill()`，silent-fail |
| JSON parse 錯誤（單筆） | 跳過該筆，記錄 warn，繼續處理其他結果 |
| 使用者取消 | `cancel_event.set()` 通知兩個 subprocess terminate |
| 兩個 thread 都失敗 | 主流程繼續（site_signals、agent 不受影響） |

---

## 測試策略

### 新增：`tests_nuclei_scanner.py`

| 測試案例 | Mock 方式 | 驗證重點 |
|---|---|---|
| Binary 不存在 | `shutil.which` 回傳 None | 回傳 `[]`，不拋例外 |
| 正常 JSON 輸出解析 | mock subprocess stdout | Finding dict 欄位正確 |
| severity → priority_score mapping | 各 severity 值逐一測 | critical=90, high=75... |
| 重複結果去重 | 兩筆相同 template-id + matched-at | 只產出一筆 |
| Subprocess timeout | mock `subprocess.run` raise TimeoutExpired | silent-fail，回傳 `[]` |

### 修改：現有測試

- `tests_active_probes.py`：整個刪除
- Katana 相關 mock：更新 mock target 從 `docker run` 改為 `katana` binary 路徑

### 手動整合驗證

對 DVWA 或 OWASP Juice Shop 靶機執行完整掃描，確認：
1. scan log 出現「Nuclei 完成：N 項發現」
2. `Finding` 表有 `category=security` 的 Nuclei 結果
3. 總掃描時間 < 10 分鐘

---

## 未來展望（Phase 2，付費功能）

- `active` mode + `active_testing_authorized=True` 時：移除 `-tags` 限制，跑全部模板
- 加入 **dalfox**（XSS 深度掃描）、**sqlmap**（完整 SQLi）
- Nuclei `-c` 提升至 50，timeout 延長至 600 秒
- 考慮將 Nuclei 和其他工具全部並行化（Approach B 進化版）

---

## 安裝需求

```powershell
# Nuclei
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
nuclei -update-templates

# Katana（取代現有 Docker image）
go install github.com/projectdiscovery/katana/cmd/katana@latest
```

或透過 Docker Desktop 內已有的 Go 環境，或直接下載 release binary。
