"""Katana 補充型爬蟲整合。

透過 Docker 執行 projectdiscovery/katana，提供：
- JS 秘鑰偵測（-kb-secrets）
- 技術棧識別（-td）
- JS 端點挖掘（-jc）

設計原則：
- Docker 不可用或 Katana 失敗時靜默回傳空結果，不影響主掃描流程。
- Tech stack 以獨立列表回傳，由 tasks.py 存入 warning_summary。
- 所有 security finding 的 page=None（Finding FK 已是 nullable）。
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# 秘鑰類型嚴重度映射
_SECRET_SEVERITY: dict[str, str] = {
    "aws": "critical",
    "google": "critical",
    "gcp": "critical",
    "github": "critical",
    "gitlab": "critical",
    "stripe": "critical",
    "twilio": "critical",
    "sendgrid": "critical",
    "openai": "critical",
    "anthropic": "critical",
    "jwt": "high",
    "private key": "critical",
    "rsa": "critical",
    "password": "high",
    "secret": "high",
    "token": "high",
    "api_key": "high",
    "apikey": "high",
}


def run_katana(
    url: str,
    max_depth: int = 3,
    max_pages: int = 50,
) -> tuple[list[dict], list[str]]:
    """以 Docker 執行 Katana 並回傳 (findings, tech_stack)。

    任何錯誤（Docker 不可用、timeout、parse 失敗）皆靜默回傳 ([], [])。
    """
    image = getattr(settings, "KATANA_DOCKER_IMAGE", "projectdiscovery/katana:latest")
    timeout = getattr(settings, "KATANA_TIMEOUT", 90)

    cmd = [
        "docker", "run", "--rm",
        image,
        "-u", url,
        "-d", str(max_depth),
        "-jc",
        "-td",
        "-kb-secrets",
        "-j",
        "-silent",
        "-timeout", "10",
        "-rl", "10",
        "-c", "5",
        "-p", "1",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        logger.warning("katana_scanner: docker 指令不存在，略過 Katana 掃描")
        return [], []
    except subprocess.TimeoutExpired:
        logger.warning("katana_scanner: Katana 超時（%ds），略過", timeout)
        return [], []
    except Exception as exc:  # noqa: BLE001
        logger.warning("katana_scanner: 執行失敗 %s，略過", exc.__class__.__name__)
        return [], []

    if result.returncode != 0 and not result.stdout.strip():
        logger.warning(
            "katana_scanner: exit=%d stderr=%s",
            result.returncode,
            result.stderr[:200],
        )
        return [], []

    return _parse_jsonl_lines(result.stdout.splitlines())


def _parse_jsonl_lines(lines: list[str]) -> tuple[list[dict], list[str]]:
    """解析 Katana JSONL 輸出，回傳 (findings, tech_stack)。"""
    findings: list[dict] = []
    tech_set: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        # 技術棧識別
        for tech in _extract_technologies(record):
            tech_set.add(tech)

        # 秘鑰 findings
        findings.extend(_extract_secret_findings(record))

        # JS 端點 findings
        endpoint_finding = _extract_endpoint_finding(record)
        if endpoint_finding:
            findings.append(endpoint_finding)

    return findings, sorted(tech_set)


def _extract_technologies(record: dict[str, Any]) -> list[str]:
    """從 JSONL 記錄提取技術棧清單。"""
    techs: list[str] = []
    response = record.get("response") or {}

    # Katana -td 輸出：response.technologies 為字串列表
    raw = response.get("technologies") or []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                techs.append(item.strip())
    return techs


def _extract_secret_findings(record: dict[str, Any]) -> list[dict]:
    """從 JSONL 記錄提取秘鑰 finding。

    Katana -kb-secrets 可能將秘鑰放在以下欄位之一（版本差異）：
    - record["knowledge_base"]["secrets"]
    - record["secrets"]
    - record["response"]["body_parsed"]["secrets"]
    """
    findings: list[dict] = []
    endpoint = (record.get("request") or {}).get("endpoint", "")

    # 嘗試多個可能的秘鑰欄位路徑
    candidates: list[Any] = []

    kb = record.get("knowledge_base") or {}
    if isinstance(kb, dict):
        s = kb.get("secrets") or []
        if isinstance(s, list):
            candidates.extend(s)

    s = record.get("secrets") or []
    if isinstance(s, list):
        candidates.extend(s)

    response = record.get("response") or {}
    body_parsed = response.get("body_parsed") or {}
    if isinstance(body_parsed, dict):
        s = body_parsed.get("secrets") or []
        if isinstance(s, list):
            candidates.extend(s)

    for secret in candidates:
        if not isinstance(secret, dict):
            continue
        finding = _build_secret_finding(secret, endpoint)
        if finding:
            findings.append(finding)

    return findings


def _build_secret_finding(secret: dict[str, Any], endpoint: str) -> dict | None:
    """將單筆 secret 記錄轉為 Argus finding dict。"""
    secret_type = str(secret.get("type") or secret.get("name") or "secret").strip()
    match_val = str(secret.get("match") or secret.get("value") or "").strip()
    line_no = secret.get("line") or ""

    if not secret_type and not match_val:
        return None

    # 依類型決定嚴重度
    severity = "high"
    for keyword, sev in _SECRET_SEVERITY.items():
        if keyword in secret_type.lower() or keyword in match_val.lower():
            severity = sev
            break

    # 遮罩敏感值（只保留前 6 字元）
    masked = (match_val[:6] + "…") if len(match_val) > 6 else match_val

    evidence_parts = [f"來源：{endpoint}"]
    if line_no:
        evidence_parts.append(f"行號：{line_no}")
    evidence_parts.append(f"比對值（遮罩）：{masked}")

    return {
        "category": "security",
        "severity": severity,
        "title": f"JS 檔案含硬編碼秘鑰：{secret_type}",
        "description": (
            f"在 {endpoint} 偵測到疑似硬編碼的 {secret_type}。"
            "硬編碼秘鑰一旦被搜尋引擎或工具掃描到，攻擊者可直接利用，"
            "無需進一步滲透即可存取對應服務。"
        ),
        "remediation": (
            "立即撤銷（revoke）該秘鑰並重新產生。"
            "改用環境變數或密鑰管理服務（Vault、AWS Secrets Manager 等）注入，"
            "確保秘鑰絕不進入版本控制或前端打包產物。"
        ),
        "evidence": "；".join(evidence_parts),
        "selector": "",
        "bounding_box": None,
        "impact_area": "secret_disclosure",
        "confidence": 0.85,
        "priority_score": 90.0 if severity == "critical" else 75.0,
        "ai_handoff_prompt": (
            "我網站的前端 JS 檔案中偵測到硬編碼秘鑰，請協助分析風險與修復方向：\n"
            f"- 秘鑰類型：{secret_type}\n"
            f"- 偵測位置：{endpoint}\n"
            "請提供：1) 立即應對步驟 2) 長期防範架構建議 3) 如何確認秘鑰未被惡意使用。"
            "不要輸出完整修復程式碼。"
        ),
    }


def _extract_endpoint_finding(record: dict[str, Any]) -> dict | None:
    """偵測可疑的隱藏 JS 端點（API 路由、內部路徑）。"""
    request = record.get("request") or {}
    endpoint = request.get("endpoint", "")
    response = record.get("response") or {}
    status = response.get("status_code", 0)

    if not endpoint:
        return None

    # 只關注從 JS 解析出來的（非 HTML 連結）且回應成功的端點
    source = request.get("source", "")
    is_js_discovered = "js" in source.lower() if isinstance(source, str) else False
    if not is_js_discovered:
        return None

    # 過濾掉靜態資源
    low = endpoint.lower()
    if any(low.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2")):
        return None

    # 只回報回應 200-299 的可疑路徑（避免大量 404 雜訊）
    if not (200 <= int(status) < 300):
        return None

    return {
        "category": "security",
        "severity": "medium",
        "title": f"JS 中發現隱藏端點：{endpoint}",
        "description": (
            f"Katana 從 JavaScript 原始碼中解析出端點 {endpoint}，"
            "且該端點回應 HTTP {status}。此類端點可能是未公開的 API 路由或內部服務，"
            "若缺乏適當的存取控制，可能成為攻擊面。"
        ).format(status=status),
        "remediation": (
            "確認此端點是否需要對公開網路開放；若否，加上認證中介軟體或 IP 白名單。"
            "建議將敏感端點路徑避免直接寫入前端 JS，改為後端動態產生。"
        ),
        "evidence": f"Katana JS 解析：{endpoint} → HTTP {status}",
        "selector": "",
        "bounding_box": None,
        "impact_area": "exposed_endpoints",
        "confidence": 0.7,
        "priority_score": 55.0,
        "ai_handoff_prompt": (
            "我網站的 JS 檔案中發現隱藏端點，請協助評估風險：\n"
            f"- 端點：{endpoint}\n"
            f"- HTTP 狀態：{status}\n"
            "請說明此類端點的常見攻擊向量與防護方式。"
        ),
    }
