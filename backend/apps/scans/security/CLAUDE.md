# scans/security 子模組規則

Claude 操作 `backend/apps/scans/security/` 時，本檔在 `scans/CLAUDE.md` 之後自動載入。

---

## 職責定義

此 sub-package 負責**深度主動式資安檢查**，與 `scanners.py` 的被動式基本檢查嚴格分離。

| 位置 | 負責什麼 | 不負責什麼 |
|---|---|---|
| `scanners.py` → `analyze_security()` | HTTPS 判斷、安全 header 存在性、CSRF token 偵測（被動、已有的） | 任何深度分析 |
| `scanners.py` → `analyze_data_exposure()` | PII 偵測（被動、已有的） | 主動掃描 |
| **此 sub-package（security/）** | SSL/TLS 深度、Cookie 旗標、CORS/CSP 品質、OWASP 對映、Kali 呼叫 | 修改 ScanJob.status、呼叫 billing |

**規則：** 凡是「被動讀取已有 response headers/HTML」的安全性判斷留在 `scanners.py`；凡是「需要額外連線、工具呼叫、或深度解析」的放進此 sub-package。

---

## 檔案規劃

| 檔案 | 職責（待建） | 狀態 |
|---|---|---|
| `ssl_scanner.py` | SSL/TLS 深度分析：憑證到期、弱 cipher、過期協議（TLS 1.0/1.1）| 已建 |
| `cookie_scanner.py` | Cookie 安全旗標：Secure、HttpOnly、SameSite | 已建 |
| `header_scanner.py` | 資訊洩露標頭（Server/X-Powered-By）、CORS 設定、CSP 品質分析 | 已建 |
| `owasp_mapper.py` | Finding 對映 OWASP Top 10（A01~A10）與 CWE 編號（`tag()` + `backfill()`） | 已建 |
| `kali_tools.py` | Hermes-Agent 呼叫 Kali container 的工具（SQLMap、Metasploit 等） | 待建 |

---

## 整合規則

- **所有 scanner 函式回傳 `list[dict]`**，格式與 `scanners.py` 的 `make_finding()` 相同
- **不直接寫入 DB**：回傳 findings list，由 `tasks.py` 統一寫入
- **呼叫點在 `tasks.py`**：在 Nuclei 掃描完成後，`tasks.py` 依序呼叫此 sub-package 的各 scanner
- **Kali 工具呼叫順序**：Nuclei 偵測完成 → Hermes-Agent 判斷 → `kali_tools.py` 執行，不可與 Nuclei 同時對同一目標打

---

## SSL Scanner 設計原則

```python
# ssl_scanner.py 的函式簽名
def analyze_ssl(hostname: str, port: int = 443, scan_job_id: int = 0) -> list[dict]:
    """連線取得憑證資訊，回傳 Finding list。任何例外 silent-fail 回傳 []。"""
```

- 使用 Python 內建 `ssl` 模組，不依賴外部 binary
- 憑證到期 ≤ 30 天 → HIGH；≤ 7 天 → CRITICAL
- 協議版本低於 TLS 1.2 → HIGH
- 弱 cipher（RC4、DES、3DES）→ HIGH

---

## Cookie Scanner 設計原則

```python
# cookie_scanner.py 的函式簽名
def analyze_cookies(cookies: list[dict], url: str) -> list[dict]:
    """接收 Playwright 的 context.cookies()，回傳 Finding list。"""
```

- Secure flag 缺失且 URL 為 HTTPS → MEDIUM
- HttpOnly flag 缺失 → LOW
- SameSite 為 None 且無 Secure → MEDIUM

---

## Kali Tools 設計原則

```python
# kali_tools.py 的函式簽名
def run_sqlmap(target_url: str, scan_job_id: int) -> dict:
    """docker exec argus-kali-1 sqlmap ...，回傳 stdout/returncode。"""

def run_metasploit(module: str, options: dict, scan_job_id: int) -> dict:
    """docker exec argus-kali-1 msfconsole -x ...，回傳執行結果。"""
```

- **只在 `ARGUS_AGENT_ENABLED=true` 且 `scan_mode=active` 且 `active_testing_authorized=True` 時才可呼叫**
- 任何例外 silent-fail，不影響主掃描流程
- 所有呼叫都記錄進 `scan_logger.append_log`
- 呼叫前確認 `argus-kali-1` container 存在：`docker inspect argus-kali-1`

---

## 禁止事項

| 禁止 | 原因 |
|---|---|
| `kali_tools.py` 在 passive mode 執行 | 未授權主動攻擊 |
| 任何函式直接寫入 Finding model | 職責分離，DB 寫入只在 tasks.py |
| 修改 `ScanJob.status` | 狀態機只在 tasks.py 管理 |
| Kali 工具與 Nuclei 同時對同一目標執行 | 目標可能因流量異常封鎖 IP |

---

## 長遠遷移計畫（專題後）

目前 `scanners.py` 的 `analyze_security()` 和 `analyze_data_exposure()` 仍留在原處（被動式）。
專題結束後可將這兩個函式移至此 sub-package 的 `passive_scanner.py`，同時將 `nuclei_scanner.py`
和 `katana_scanner.py` 也移進來，使資安邏輯完全集中。遷移不涉及 model 或 migration 變更，
只需更新 `tasks.py` 的 import 路徑。
