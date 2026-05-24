import { useEffect, useMemo, useRef, useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import {
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";

import { api } from "./api";
import { useArgusStore } from "./store";

// ============================================================
// 常數
// ============================================================

const CATEGORY_FILTERS = [
  { value: "all", label: "全部分類" },
  { value: "seo", label: "SEO" },
  { value: "aeo", label: "AEO" },
  { value: "geo", label: "GEO" },
  { value: "security", label: "資安" },
  { value: "ux", label: "UX" },
];

const SEVERITY_FILTERS = [
  { value: "all", label: "全部嚴重度" },
  { value: "critical", label: "嚴重" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" },
  { value: "info", label: "資訊" },
];

const STATUS_LABELS = {
  queued: { label: "等待中", tone: "slate", emoji: "⏳" },
  crawling: { label: "爬取中", tone: "blue", emoji: "🕷️" },
  scanning: { label: "掃描中", tone: "blue", emoji: "🔍" },
  agent_testing: { label: "Agent 測試中", tone: "blue", emoji: "🤖" },
  completed: { label: "完成", tone: "emerald", emoji: "✓" },
  failed: { label: "失敗", tone: "red", emoji: "✗" },
};

const IN_PROGRESS_STATUSES = ["queued", "crawling", "scanning", "agent_testing"];

function isInProgress(status) {
  return IN_PROGRESS_STATUSES.includes(status);
}

// ============================================================
// 視覺化元件（純 SVG / CSS，無 chart 套件）
// ============================================================

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];
const SEVERITY_COLOR = {
  critical: "#dc2626",
  high: "#f97316",
  medium: "#facc15",
  low: "#38bdf8",
  info: "#94a3b8",
};
const SEVERITY_LABEL = {
  critical: "嚴重",
  high: "高",
  medium: "中",
  low: "低",
  info: "資訊",
};
const CATEGORY_COLOR = {
  security: "#ef4444",
  seo: "#6366f1",
  aeo: "#a855f7",
  geo: "#06b6d4",
  ux: "#10b981",
};

// 數字遞增動畫（適可而止：300ms 線性 ease-out）
function CountUp({ value, duration = 600, suffix = "" }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const target = Number(value) || 0;
    if (target === 0) {
      setDisplay(0);
      return undefined;
    }
    const start = performance.now();
    let frameId = 0;
    const tick = (now) => {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(target * eased);
      if (progress < 1) {
        frameId = requestAnimationFrame(tick);
      } else {
        setDisplay(target);
      }
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [value, duration]);
  const rounded = Number.isInteger(value) ? Math.round(display) : Math.round(display * 10) / 10;
  return (
    <span>
      {rounded}
      {suffix}
    </span>
  );
}

// 水平堆疊比例條：data = [{label, value, color}]，按比例填色
function StackedBar({ data, height = 14 }) {
  const total = data.reduce((sum, item) => sum + (item.value || 0), 0);
  if (total === 0) {
    return <div className="stacked-bar empty" style={{ height }} />;
  }
  return (
    <div className="stacked-bar-wrap">
      <div className="stacked-bar" style={{ height }}>
        {data.map((item) => {
          const pct = (item.value / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              className="stacked-bar-seg"
              key={item.label}
              style={{ width: `${pct}%`, background: item.color }}
              title={`${item.label}: ${item.value} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      <div className="stacked-bar-legend">
        {data.map((item) => {
          if (!item.value) return null;
          const pct = (item.value / total) * 100;
          return (
            <div key={item.label} className="stacked-bar-legend-item">
              <span
                className="stacked-bar-swatch"
                style={{ background: item.color }}
                aria-hidden="true"
              />
              <span className="stacked-bar-legend-label">{item.label}</span>
              <span className="stacked-bar-legend-value">{Math.round(pct)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// 嚴重度長條圖（水平、按 SEVERITY_ORDER）
function SeverityBarChart({ severityTotals, title = "Findings 嚴重度分佈" }) {
  const max = Math.max(
    ...SEVERITY_ORDER.map((s) => severityTotals?.[s] || 0),
    1,
  );
  const totalFindings = SEVERITY_ORDER.reduce(
    (sum, s) => sum + (severityTotals?.[s] || 0),
    0,
  );
  return (
    <div className="bar-chart">
      <div className="bar-chart-header">
        <h4>{title}</h4>
        <span className="bar-chart-total">共 {totalFindings}</span>
      </div>
      <div className="bar-chart-rows">
        {SEVERITY_ORDER.map((sev) => {
          const count = severityTotals?.[sev] || 0;
          const pct = (count / max) * 100;
          return (
            <div key={sev} className="bar-chart-row">
              <span className={`bar-chart-label severity ${sev}`}>
                {SEVERITY_LABEL[sev]}
              </span>
              <div className="bar-chart-track">
                <div
                  className="bar-chart-fill"
                  style={{
                    width: `${pct}%`,
                    background: SEVERITY_COLOR[sev],
                    boxShadow: `0 0 8px ${SEVERITY_COLOR[sev]}66`,
                  }}
                />
              </div>
              <span className="bar-chart-count">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// 折線圖：分數趨勢（含座標軸、點標註）
// data = [{label, value}]（按時間舊→新排序）
function LineChart({ data, width = 320, height = 110, ariaLabel }) {
  if (!data || data.length === 0) {
    return <div className="line-chart-empty">無資料</div>;
  }
  const padding = { top: 12, right: 12, bottom: 22, left: 30 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const values = data.map((d) => d.value).filter((v) => typeof v === "number");
  if (values.length === 0) {
    return <div className="line-chart-empty">無有效分數</div>;
  }
  const minV = 0;
  const maxV = 100;
  const stepX = data.length > 1 ? plotW / (data.length - 1) : 0;
  const yFor = (v) => padding.top + plotH - ((v - minV) / (maxV - minV)) * plotH;
  const xFor = (i) => padding.left + i * stepX;

  const linePoints = data
    .map((d, i) => (typeof d.value === "number" ? `${xFor(i)},${yFor(d.value)}` : null))
    .filter(Boolean)
    .join(" ");

  const yTicks = [0, 50, 100];
  return (
    <svg
      className="line-chart"
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel || "分數趨勢"}
    >
      {/* Y 軸格線與刻度 */}
      {yTicks.map((tick) => (
        <g key={tick}>
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={yFor(tick)}
            y2={yFor(tick)}
            className="line-chart-grid"
          />
          <text
            x={padding.left - 6}
            y={yFor(tick) + 3}
            className="line-chart-axis-label"
            textAnchor="end"
          >
            {tick}
          </text>
        </g>
      ))}
      {/* 折線 */}
      <polyline points={linePoints} className="line-chart-line" fill="none" />
      {/* 資料點 */}
      {data.map((d, i) => {
        if (typeof d.value !== "number") return null;
        return (
          <g key={i}>
            <circle
              cx={xFor(i)}
              cy={yFor(d.value)}
              r="3.5"
              className="line-chart-dot"
            />
            <text
              x={xFor(i)}
              y={yFor(d.value) - 7}
              className="line-chart-value"
              textAnchor="middle"
            >
              {d.value}
            </text>
          </g>
        );
      })}
      {/* X 軸標籤：只顯示首末，避免擠 */}
      {data.length > 0 && (
        <>
          <text
            x={xFor(0)}
            y={height - 6}
            className="line-chart-axis-label"
            textAnchor="start"
          >
            {data[0].label}
          </text>
          {data.length > 1 && (
            <text
              x={xFor(data.length - 1)}
              y={height - 6}
              className="line-chart-axis-label"
              textAnchor="end"
            >
              {data[data.length - 1].label}
            </text>
          )}
        </>
      )}
    </svg>
  );
}

// 進行中時的 polling 間隔（毫秒）
const SCAN_POLL_INTERVAL_MS = 2000;
const LIST_POLL_INTERVAL_MS = 3000;

// localStorage 暫存表單草稿的 key
const SCAN_DRAFT_KEY = "argus_scan_draft_v1";

// ============================================================
// 通用小元件
// ============================================================

function ScanStatusBadge({ status }) {
  const meta = STATUS_LABELS[status] || { label: status, tone: "slate", emoji: "?" };
  const pulse = isInProgress(status) ? "animate-pulse" : "";
  return (
    <span className={`status-badge status-${meta.tone} ${pulse}`}>
      <span aria-hidden="true">{meta.emoji}</span>
      <span>{meta.label}</span>
    </span>
  );
}

function ScoreBadge({ score }) {
  if (score === null || score === undefined) {
    return <span className="score-badge muted">尚無分數</span>;
  }
  const tone = score >= 80 ? "good" : score >= 60 ? "medium" : "bad";
  return <span className={`score-badge ${tone}`}>{score}</span>;
}

// ============================================================
// 登入相關
// ============================================================

function LoginForm() {
  const setToken = useArgusStore((state) => state.setToken);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");
  const clientId = import.meta.env.GOOGLE_OAUTH_CLIENT_ID || "";

  // 被 401 interceptor 踢回登入頁時保留 next，登入成功後回到原頁面（含 deep link 與 query）
  function nextDestination() {
    const next = searchParams.get("next");
    if (next && next.startsWith("/")) {
      return next;
    }
    return "/scans";
  }

  async function handleGoogleSuccess(credentialResponse) {
    setError("");
    try {
      const response = await api.post("/auth/google/", {
        credential: credentialResponse.credential,
      });
      setToken(response.data.access);
      navigate(nextDestination(), { replace: true });
    } catch (errorResponse) {
      const data = errorResponse.response?.data;
      setError(
        (data && (data.credential || data.config)) || "Google 登入失敗,請稍後再試。",
      );
    }
  }

  // DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING
  async function handleDevLogin() {
    setError("");
    try {
      const response = await api.post("/auth/dev-login/", {});
      setToken(response.data.access);
      navigate(nextDestination(), { replace: true });
    } catch (errorResponse) {
      setError(
        errorResponse.response?.data?.detail ||
          "Dev login 失敗,後端可能不在 DEBUG 模式或 bootstrap 帳號不存在。",
      );
    }
  }

  return (
    <section className="panel space-y-4">
      <div>
        <p className="eyebrow">登入 / 註冊</p>
        <h2 className="section-title">使用 Argus</h2>
        <p className="mt-2 text-sm text-slate-600">
          使用 Google 帳號登入或註冊；首次使用會自動建立對應帳號。
        </p>
      </div>
      {!clientId ? (
        <p className="error-text">
          尚未設定 <code>GOOGLE_OAUTH_CLIENT_ID</code>，請在專案根目錄 .env
          填入後重新啟動前端。
        </p>
      ) : (
        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError("Google 登入流程被中斷或失敗。")}
          />
        </div>
      )}
      {error && <p className="error-text">{error}</p>}

      {/* DEV LOGIN BACKDOOR — REMOVE WHEN GOOGLE OAUTH IS FULLY WORKING */}
      <div className="mt-2 border-t border-slate-200 pt-3">
        <button
          className="secondary-button w-full"
          type="button"
          onClick={handleDevLogin}
        >
          🛠️ 跳過 Google 登入（開發用，待移除）
        </button>
        <p className="mt-2 text-xs text-slate-500">
          僅在後端 <code>DEBUG=true</code> 時生效，以 bootstrap superuser
          (<code>1124</code>) 登入。
          Google OAuth 的 Authorized origins 生效後，請依 code 內
          <code> DEV LOGIN BACKDOOR </code>註解移除整塊。
        </p>
      </div>

      <p className="text-xs text-slate-500">
        系統管理員仍透過 <code>/admin/</code> 以 username/password 登入。
      </p>
    </section>
  );
}

function AccountBar() {
  const { accessToken, setToken } = useArgusStore();
  const navigate = useNavigate();
  if (!accessToken) {
    return null;
  }
  function handleLogout() {
    setToken(null);
    navigate("/login");
  }
  return (
    <div className="account-bar">
      <span className="text-sm text-slate-600">已登入</span>
      <button className="secondary-button" type="button" onClick={handleLogout}>
        登出
      </button>
    </div>
  );
}

// ============================================================
// 建立掃描表單（含 F5 防丟失與草稿持久化）
// ============================================================

function loadScanDraft() {
  try {
    const raw = window.localStorage.getItem(SCAN_DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveScanDraft(draft) {
  try {
    window.localStorage.setItem(SCAN_DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // localStorage 滿了或被禁用時，安靜失敗
  }
}

function clearScanDraft() {
  window.localStorage.removeItem(SCAN_DRAFT_KEY);
}

function ScanJobForm({ onCreated }) {
  // 從 localStorage 還原草稿，避免 F5 後重打網址
  const initial = loadScanDraft() || {};
  const [url, setUrl] = useState(initial.url || "");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(
    initial.authorizationConfirmed || false,
  );
  const [thirdPartyReconfirmed, setThirdPartyReconfirmed] = useState(
    initial.thirdPartyReconfirmed || false,
  );
  const [activeMode, setActiveMode] = useState(initial.activeMode || false);
  const [activeAuthorized, setActiveAuthorized] = useState(initial.activeAuthorized || false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 任何欄位改變都即時存草稿，使用者真的不小心 F5 也不會白打
  useEffect(() => {
    saveScanDraft({
      url,
      authorizationConfirmed,
      thirdPartyReconfirmed,
      activeMode,
      activeAuthorized,
    });
  }, [url, authorizationConfirmed, thirdPartyReconfirmed, activeMode, activeAuthorized]);

  // 提交中時，瀏覽器原生攔截 F5 / 關閉分頁
  useEffect(() => {
    if (!submitting) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [submitting]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await api.post("/scans/", {
        url,
        authorization_confirmed: authorizationConfirmed,
        third_party_reconfirmed: thirdPartyReconfirmed,
        scan_mode: activeMode ? "active" : "passive",
        active_testing_authorized: activeMode && activeAuthorized,
      });
      // 成功後清空欄位與草稿
      setUrl("");
      setAuthorizationConfirmed(false);
      setThirdPartyReconfirmed(false);
      setActiveMode(false);
      setActiveAuthorized(false);
      clearScanDraft();
      onCreated(response.data);
    } catch (errorResponse) {
      setError(JSON.stringify(errorResponse.response?.data || "建立掃描失敗。"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="panel space-y-4" onSubmit={handleSubmit}>
      <div>
        <p className="eyebrow">新增任務</p>
        <h2 className="section-title">建立授權掃描</h2>
        <p className="mt-1 text-xs text-slate-500">
          表單會自動存草稿；F5 或不小心關閉分頁後再回來，欄位會保留。
        </p>
      </div>
      <input
        className="input"
        placeholder="https://example.com/"
        value={url}
        onChange={(event) => setUrl(event.target.value)}
      />
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={authorizationConfirmed}
          onChange={(event) => setAuthorizationConfirmed(event.target.checked)}
        />
        我擁有此網站或已獲得書面授權測試。
      </label>
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={thirdPartyReconfirmed}
          onChange={(event) => setThirdPartyReconfirmed(event.target.checked)}
        />
        若此網站看似第三方或敏感產業，我已再次確認授權。
      </label>
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={activeMode}
          onChange={(event) => setActiveMode(event.target.checked)}
        />
        啟用主動式資安測試模式。
      </label>
      {activeMode && (
        <label className="checkbox-row warning">
          <input
            type="checkbox"
            checked={activeAuthorized}
            onChange={(event) => setActiveAuthorized(event.target.checked)}
          />
          我同意進行侵入式測試，並理解系統會限制 RPS ≤ 2。
        </label>
      )}
      {error && <p className="error-text">{error}</p>}
      <button className="primary-button" type="submit" disabled={submitting}>
        {submitting ? "送出中... (請勿關閉視窗)" : "建立掃描"}
      </button>
    </form>
  );
}

// ============================================================
// 掃描列表
// ============================================================

function ScanList({ scans, onRefresh }) {
  const navigate = useNavigate();
  const { scanId } = useParams();
  const activeId = scanId ? Number(scanId) : null;
  const inProgressCount = scans.filter((scan) => isInProgress(scan.status)).length;

  // 每個 origin 上一次的分數，用來算 delta（同 origin 的 scans 已按 -created_at 排序）
  const previousByOrigin = useMemo(() => {
    const seen = new Map();
    const result = new Map();
    for (const scan of scans) {
      if (scan.overall_score === null || scan.overall_score === undefined) continue;
      if (seen.has(scan.origin)) {
        // 第二次見到此 origin，視為「上一次分數」對應第一次見到的那筆
        const firstScanId = seen.get(scan.origin);
        if (!result.has(firstScanId)) {
          result.set(firstScanId, scan.overall_score);
        }
      } else {
        seen.set(scan.origin, scan.id);
      }
    }
    return result;
  }, [scans]);

  return (
    <section className="panel space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="eyebrow">任務</p>
          <h2 className="section-title">掃描列表</h2>
          {inProgressCount > 0 && (
            <p className="mt-1 text-xs text-blue-600">
              🔄 {inProgressCount} 個進行中，畫面每 {LIST_POLL_INTERVAL_MS / 1000} 秒自動更新
            </p>
          )}
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh}>
          重新整理
        </button>
      </div>
      <div className="space-y-2">
        {scans.map((scan) => {
          const tone =
            scan.overall_score === null || scan.overall_score === undefined
              ? "muted"
              : scan.overall_score >= 80
                ? "good"
                : scan.overall_score >= 60
                  ? "medium"
                  : "bad";
          const previous = previousByOrigin.get(scan.id);
          const delta =
            previous !== undefined &&
            scan.overall_score !== null &&
            scan.overall_score !== undefined
              ? scan.overall_score - previous
              : null;
          return (
            <button
              className={`scan-card tone-${tone} ${activeId === scan.id ? "active" : ""}`}
              key={scan.id}
              type="button"
              onClick={() => navigate(`/scans/${scan.id}`)}
            >
              <span className={`scan-card-stripe tone-${tone}`} aria-hidden="true" />
              <div className="scan-card-body">
                <p className="scan-card-origin" title={scan.origin}>
                  {scan.origin.replace(/^https?:\/\//, "")}
                </p>
                <div className="scan-card-meta">
                  <ScanStatusBadge status={scan.status} />
                  {delta !== null && delta !== 0 && (
                    <span
                      className={`scan-card-delta tone-${delta > 0 ? "good" : "bad"}`}
                      title="與該網址上一次分數比較"
                    >
                      {delta > 0 ? `▲ +${delta}` : `▼ ${delta}`}
                    </span>
                  )}
                </div>
              </div>
              <ScoreBadge score={scan.overall_score} />
            </button>
          );
        })}
        {!scans.length && <p className="hint-text">尚無掃描任務。</p>}
      </div>
    </section>
  );
}

// ============================================================
// Findings 分組列表（同分類、同標題的 finding 合併為一群組，例如 11 個「頁面未使用 HTTPS」併成一筆，展開後列出每個頁面）
// ============================================================

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function buildFindingGroups(findings) {
  const groupMap = new Map();
  for (const finding of findings) {
    const key = `${finding.category}::${finding.title}`;
    let group = groupMap.get(key);
    if (!group) {
      group = {
        key,
        category: finding.category,
        title: finding.title,
        severity: finding.severity,
        description: finding.description,
        remediation: finding.remediation,
        items: [],
      };
      groupMap.set(key, group);
    }
    group.items.push(finding);
    // 群組嚴重度取群內最高
    if (SEVERITY_RANK[finding.severity] < SEVERITY_RANK[group.severity]) {
      group.severity = finding.severity;
    }
  }
  return Array.from(groupMap.values()).sort((a, b) => {
    const sev = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
    if (sev !== 0) return sev;
    if (a.category !== b.category) return a.category.localeCompare(b.category);
    return b.items.length - a.items.length;
  });
}

function FindingsGroupList({
  findings,
  pages,
  scanStatus,
  totalFindings,
  selectedFinding,
  onSelectFinding,
}) {
  const groups = useMemo(() => buildFindingGroups(findings), [findings]);
  const pageMap = useMemo(() => {
    const map = new Map();
    for (const page of pages) {
      map.set(page.id, page);
    }
    return map;
  }, [pages]);

  // 自動展開包含目前 selectedFinding 的群組，並把該群組滾到視野中
  const [expanded, setExpanded] = useState(() => new Set());
  const groupRefs = useRef({});
  useEffect(() => {
    if (!selectedFinding) return;
    const key = `${selectedFinding.category}::${selectedFinding.title}`;
    setExpanded((prev) => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    // 反向跳轉用：當截圖紅框被點時，selectedFinding 變化，把對應建議按鈕滾到視野中央
    const el = groupRefs.current[key];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedFinding]);

  function toggle(key) {
    const wasExpanded = expanded.has(key);
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
    // 從關閉變展開時，同步選中該群組第一個 finding，
    // 讓使用者點一次群組標題就能同時看到紅色高光框與右側內容，不必再點子項。
    if (!wasExpanded) {
      const group = groups.find((g) => g.key === key);
      if (group && group.items.length > 0) {
        onSelectFinding(group.items[0]);
      }
    }
  }

  if (!groups.length) {
    return (
      <p className="hint-text">
        {totalFindings
          ? "沒有符合篩選條件的項目。"
          : isInProgress(scanStatus)
            ? "尚未發現任何項目，掃描進行中..."
            : "尚無 findings。"}
      </p>
    );
  }

  return (
    <div className="max-h-[520px] space-y-2 overflow-auto pr-1">
      {groups.map((group) => {
        const isExpanded = expanded.has(group.key);
        const containsSelected =
          selectedFinding &&
          selectedFinding.category === group.category &&
          selectedFinding.title === group.title;
        return (
          <div
            key={group.key}
            ref={(el) => {
              if (el) groupRefs.current[group.key] = el;
            }}
            className={`finding-group ${containsSelected ? "active" : ""}`}
          >
            <button
              className="finding-group-header"
              type="button"
              onClick={() => toggle(group.key)}
            >
              <span className={`severity ${group.severity}`}>{group.severity}</span>
              <span className={`category-pill cat-${group.category}`}>
                {group.category.toUpperCase()}
              </span>
              <span className="finding-group-title">{group.title}</span>
              <span className="finding-group-count">{group.items.length}</span>
              <span className="finding-group-chevron" aria-hidden="true">
                {isExpanded ? "▾" : "▸"}
              </span>
            </button>
            {isExpanded && (
              <ul className="finding-group-items">
                {group.items.map((finding) => {
                  const page = finding.page ? pageMap.get(finding.page) : null;
                  const label =
                    page?.url || page?.final_url || "（站台層級）";
                  const isSelected = selectedFinding?.id === finding.id;
                  return (
                    <li key={finding.id}>
                      <button
                        className={`finding-item ${isSelected ? "active" : ""}`}
                        type="button"
                        onClick={() => onSelectFinding(finding)}
                        title={label}
                      >
                        <span className="finding-item-url">{label}</span>
                        {finding.evidence && (
                          <span className="finding-item-evidence">
                            {finding.evidence}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// 截圖畫布（接 selectedFinding 為 prop，以對應 URL 來源）
// ============================================================

function ScreenshotCanvas({ scan, targetPage, findings, selectedFinding, onSelectFinding }) {
  const [imageUrl, setImageUrl] = useState("");
  const [scale, setScale] = useState(1);
  const imageRef = useRef(null);

  useEffect(() => {
    let objectUrl = "";
    async function loadScreenshot() {
      if (!scan || !targetPage) {
        setImageUrl("");
        return;
      }
      try {
        const response = await api.get(
          `/scans/${scan.id}/pages/${targetPage.id}/screenshot/`,
          { responseType: "blob" },
        );
        objectUrl = URL.createObjectURL(response.data);
        setImageUrl(objectUrl);
      } catch {
        // 該頁面尚未產生截圖（爬蟲還沒跑到、或被 robots 擋）靜默失敗
        setImageUrl("");
      }
    }
    loadScreenshot();
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [scan, targetPage]);

  function syncScale() {
    const image = imageRef.current;
    if (image && image.naturalWidth) {
      setScale(image.clientWidth / image.naturalWidth);
    }
  }

  useEffect(() => {
    window.addEventListener("resize", syncScale);
    return () => window.removeEventListener("resize", syncScale);
  }, []);

  // 高光框：選中的 finding 在當前頁面且有座標時，畫紅色高光框
  const overlayFindings = findings.filter(
    (finding) => finding.bounding_box && finding.page === targetPage?.id,
  );

  // 站台層級或無 bounding_box 的 finding → 在截圖頂部畫紅色 banner（讓使用者知道「有反應，但不是元素級」）
  const showSiteBanner =
    selectedFinding && !selectedFinding.bounding_box;

  // 確保「按了一定有反應」：沒 bounding_box 時退化為整頁紅色 pulse 外框；
  // 或選的是別頁的 finding（page 對不上 targetPage）也畫整頁外框提示。
  const showWholePageHighlight =
    selectedFinding &&
    (!selectedFinding.bounding_box ||
      (selectedFinding.page && selectedFinding.page !== targetPage?.id));

  return (
    <div className="screenshot-shell">
      {targetPage && (
        <div className="screenshot-caption-row">
          <p className="screenshot-caption">
            📷 {targetPage.title || targetPage.url}
          </p>
          <a
            className="screenshot-open-link"
            href={targetPage.final_url || targetPage.url}
            target="_blank"
            rel="noopener noreferrer"
            title="在新分頁開啟原網站（可實際互動，但會脫離 Argus 的紅框跳轉）"
          >
            🔗 在新分頁開啟原網站
          </a>
        </div>
      )}
      {!imageUrl && (
        <p className="hint-text">
          {isInProgress(scan?.status)
            ? "正在爬取頁面...截圖完成後會顯示在此。"
            : targetPage
              ? "此頁面沒有可用截圖（可能被 robots.txt 阻擋或回 4xx/5xx）。"
              : "掃描完成並產生截圖後會顯示在此。"}
        </p>
      )}
      {imageUrl && (
        <div className="relative inline-block">
          <img
            alt="頁面截圖"
            className="screenshot-image"
            ref={imageRef}
            src={imageUrl}
            onLoad={syncScale}
          />
          {showSiteBanner && (
            <div className="site-banner-overlay">
              <span className={`severity ${selectedFinding.severity}`}>
                {selectedFinding.severity}
              </span>
              <span className={`category-pill cat-${selectedFinding.category}`}>
                {selectedFinding.category.toUpperCase()}
              </span>
              <span className="site-banner-title">
                ⚠ {selectedFinding.title}
              </span>
            </div>
          )}
          {showWholePageHighlight && (
            <div className="whole-page-highlight pointer-events-none" aria-hidden="true" />
          )}
          <div className="pointer-events-none absolute inset-0">
            {overlayFindings.map((finding) => {
              const box = finding.bounding_box;
              const active = selectedFinding?.id === finding.id;
              // 紅框變可點：點下去自動選中對應 finding，達成「截圖 → 建議按鈕」反向跳轉。
              // 外層 div 保留 pointer-events-none 不擋截圖右鍵；個別 highlight-box 在 CSS 中設 pointer-events-auto。
              return (
                <div
                  className={`highlight-box ${active ? "active" : ""}`}
                  key={finding.id}
                  role="button"
                  tabIndex={0}
                  title={`${finding.severity.toUpperCase()} / ${finding.category.toUpperCase()}：${finding.title}（點擊跳到建議）`}
                  onClick={() => onSelectFinding?.(finding)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectFinding?.(finding);
                    }
                  }}
                  style={{
                    left: `${box.x * scale}px`,
                    top: `${box.y * scale}px`,
                    width: `${box.width * scale}px`,
                    height: `${box.height * scale}px`,
                  }}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// 互動報告（含進度提示、URL-driven 選擇）
// ============================================================

function FindingsWorkspace({ scan }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [findings, setFindings] = useState([]);
  const [pages, setPages] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  // findings 與 pages 在 scan 物件更新時跟著刷新（polling 改變 scan 後 findings_count 變動會觸發）
  useEffect(() => {
    async function loadDetails() {
      const [findingsResponse, pagesResponse] = await Promise.all([
        api.get(`/findings/?scan_id=${scan.id}`),
        api.get(`/pages/?scan_id=${scan.id}`),
      ]);
      setFindings(findingsResponse.data.results || findingsResponse.data);
      setPages(pagesResponse.data.results || pagesResponse.data);
    }
    loadDetails();
  }, [scan.id, scan.findings_count, scan.pages_count, scan.status]);

  // 選中的 finding 由 URL search param 決定，F5 後仍能還原
  const selectedFindingId = searchParams.get("finding");
  const selectedFinding = findings.find((f) => String(f.id) === selectedFindingId) || null;

  // 當前 page tab；URL param `page=<id>` 或 `page=all`；預設 all
  const pageTabParam = searchParams.get("page") || "all";

  function setPageTab(value) {
    const params = new URLSearchParams(searchParams);
    if (value === "all") {
      params.delete("page");
    } else {
      params.set("page", String(value));
    }
    setSearchParams(params, { replace: false });
  }

  function selectFinding(finding) {
    const params = new URLSearchParams(searchParams);
    params.set("finding", String(finding.id));
    // 點 finding 時自動切到對應頁面 tab（站台層級 finding 切到「全站」）
    if (finding.page) {
      params.set("page", String(finding.page));
    } else {
      params.delete("page");
    }
    setSearchParams(params, { replace: false });
  }

  async function downloadReport() {
    const response = await api.get(`/scans/${scan.id}/report/`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `argus-scan-${scan.id}-report.docx`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  // page tab 過濾：「all」顯示全部、某 page id 顯示該頁與站台級 finding
  const pageFiltered =
    pageTabParam === "all"
      ? findings
      : findings.filter(
          (f) => String(f.page) === pageTabParam || f.page === null,
        );

  const filteredFindings = pageFiltered.filter(
    (finding) =>
      (categoryFilter === "all" || finding.category === categoryFilter) &&
      (severityFilter === "all" || finding.severity === severityFilter),
  );

  // 截圖目標 page：page tab 指定為某 page → 用它；tab=all → 用 selectedFinding 的 page 或 pages[0]
  const targetPage =
    pageTabParam !== "all"
      ? pages.find((p) => String(p.id) === pageTabParam)
      : (selectedFinding?.page &&
          pages.find((p) => p.id === selectedFinding.page)) ||
        pages[0] ||
        null;

  // 計算每個 page 下的 finding 數，給 page tab 顯示徽章
  const findingsPerPage = useMemo(() => {
    const counts = new Map();
    let siteLevel = 0;
    for (const f of findings) {
      if (f.page === null || f.page === undefined) {
        siteLevel += 1;
      } else {
        counts.set(f.page, (counts.get(f.page) || 0) + 1);
      }
    }
    return { perPage: counts, siteLevel };
  }, [findings]);

  // 嚴重度統計（給長條圖）
  const severityTotals = useMemo(() => {
    const totals = {};
    for (const f of findings) {
      totals[f.severity] = (totals[f.severity] || 0) + 1;
    }
    return totals;
  }, [findings]);

  // 各類別 finding 數（給 Top Actions 堆疊比例條）
  const categoryTotals = useMemo(() => {
    const totals = {};
    for (const f of findings) {
      totals[f.category] = (totals[f.category] || 0) + 1;
    }
    return totals;
  }, [findings]);

  const completed = scan.status === "completed";

  return (
    <section className="panel lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="eyebrow">互動報告</p>
          <h2 className="section-title">{scan.origin}</h2>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
            <ScanStatusBadge status={scan.status} />
            <span>頁面: {scan.pages_count ?? 0}</span>
            <span>Findings: {scan.findings_count ?? 0}</span>
            {scan.overall_score !== null && scan.overall_score !== undefined && (
              <span>分數: {scan.overall_score}</span>
            )}
          </div>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={downloadReport}
          disabled={!completed}
        >
          匯出 Word{!completed && "（完成後可用）"}
        </button>
      </div>

      {isInProgress(scan.status) && (
        <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          🔄 掃描進行中，畫面每 {SCAN_POLL_INTERVAL_MS / 1000} 秒自動更新。
          可以離開此頁、切換到其他掃描或登出，背景作業會繼續執行。
          <p className="mt-1 text-xs">
            ℹ️ 為避免無意義的建議，後台路徑（/admin、/wp-admin、/dashboard 等）會跳過 SEO/AEO/GEO 評分（安全頭部與 CSRF 仍會檢查）；
            .apk、.zip、.pdf、圖片等下載連結不會列入頁面分析。
          </p>
          {scan.warning_summary && scan.warning_summary.blocked_urls?.length > 0 && (
            <p className="mt-1 text-xs">
              已偵測到 {scan.warning_summary.blocked_urls.length} 個被阻擋的 URL（403/429/robots.txt）。
            </p>
          )}
        </div>
      )}

      {scan.status === "failed" && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          ✗ 掃描失敗：{scan.error_message || "未知錯誤"}
        </div>
      )}

      {/* 頁面 tabs：依不同頁面切換中間截圖區與右側 findings 範圍 */}
      {pages.length > 0 && (
        <div className="page-tabs">
          <button
            type="button"
            className={`page-tab ${pageTabParam === "all" ? "active" : ""}`}
            onClick={() => setPageTab("all")}
          >
            <span className="page-tab-label">全站</span>
            <span className="page-tab-count">{findings.length}</span>
          </button>
          {pages.map((page) => {
            const isHome = page.depth === 0;
            const label = isHome
              ? "首頁"
              : page.title?.slice(0, 14) ||
                page.url?.replace(scan.origin, "").slice(0, 18) ||
                `Page ${page.id}`;
            const cnt = findingsPerPage.perPage.get(page.id) || 0;
            return (
              <button
                key={page.id}
                type="button"
                className={`page-tab ${String(page.id) === pageTabParam ? "active" : ""}`}
                onClick={() => setPageTab(page.id)}
                title={page.url}
              >
                <span className="page-tab-label">{label}</span>
                <span className="page-tab-count">{cnt}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* 整體 viz：嚴重度長條 + 各類別佔比堆疊條 — 完成或進行中皆顯示（進行中是部分資料） */}
      {findings.length > 0 && (
        <div className="report-viz">
          <div className="report-viz-block">
            <SeverityBarChart severityTotals={severityTotals} />
          </div>
          <div className="report-viz-block">
            <h4 className="bar-chart-header-h4">各類別 finding 佔比</h4>
            <StackedBar
              data={Object.keys(CATEGORY_LABELS).map((cat) => ({
                label: CATEGORY_LABELS[cat],
                value: categoryTotals[cat] || 0,
                color: CATEGORY_COLOR[cat],
              }))}
            />
          </div>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <ScreenshotCanvas
          findings={filteredFindings}
          targetPage={targetPage}
          scan={scan}
          selectedFinding={selectedFinding}
          onSelectFinding={selectFinding}
        />
        <div className="space-y-3">
          <div className="top-actions-box">
            <p className="top-actions-title">⚡ Top Actions</p>
            {(scan.top_actions || []).map((action, idx) => (
              <button
                className="top-action-row"
                type="button"
                key={`${action.category}-${action.title}-${idx}`}
                onClick={() => {
                  // 試著從現有 findings 找符合的 finding 自動選中
                  const matched = findings.find(
                    (f) =>
                      f.category === action.category && f.title === action.title,
                  );
                  if (matched) selectFinding(matched);
                }}
              >
                <span className={`severity ${action.severity}`}>{action.severity}</span>
                <span className={`category-pill cat-${action.category}`}>
                  {action.category.toUpperCase()}
                </span>
                <span className="top-action-title">{action.title}</span>
              </button>
            ))}
            {!(scan.top_actions && scan.top_actions.length) && (
              <p className="mt-2 text-sm text-slate-400">
                {isInProgress(scan.status) ? "尚未產生（掃描完成後出現）" : "—"}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <select
              className="input"
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
            >
              {CATEGORY_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              className="input"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
            >
              {SEVERITY_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <FindingsGroupList
            findings={filteredFindings}
            pages={pages}
            scanStatus={scan.status}
            totalFindings={findings.length}
            selectedFinding={selectedFinding}
            onSelectFinding={selectFinding}
          />
          {selectedFinding && (
            <div className="finding-detail">
              <h3 className="font-semibold text-slate-900">{selectedFinding.title}</h3>
              <p>{selectedFinding.description}</p>
              <p className="font-semibold">修補方向</p>
              <p>{selectedFinding.remediation}</p>
              <button
                className="primary-button"
                type="button"
                onClick={() => navigator.clipboard.writeText(selectedFinding.ai_handoff_prompt)}
              >
                複製問題 Prompt
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ============================================================
// 路由保護與版面
// ============================================================

function RequireAuth({ children }) {
  const accessToken = useArgusStore((state) => state.accessToken);
  if (accessToken) {
    return children;
  }
  // 使用者直接輸入 /scans/123 之類 deep link 但未登入時，帶 next 讓登入後跳回
  const next = encodeURIComponent(
    window.location.pathname + window.location.search,
  );
  return <Navigate to={`/login?next=${next}`} replace />;
}

// ScanLayout 改為 parent route + Outlet：sidebar（表單 + 列表）只 mount 一次，
// `/scans` ↔ `/scans/:id` 切換只重渲染右側 Outlet，避免每次按「建立掃描」
// 版面整個 unmount 再 remount 造成的跳動。
//
// 兩種模式：
//   list-mode（/scans）：sidebar inline 在左邊，固定 360px。
//   detail-mode（/scans/:id）：sidebar 縮為 drawer overlay，主內容拿到全寬讓截圖變大。
function ScanLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { scanId } = useParams();
  const isDetailPage = Boolean(scanId);
  const isTopologyPage = isDetailPage && location.pathname.endsWith("/topology");
  const [scans, setScans] = useState([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  async function loadScans() {
    try {
      const response = await api.get("/scans/");
      setScans(response.data.results || response.data);
    } catch {
      // 401 之類靜默失敗，store 變動會自動導回 /login
    }
  }

  useEffect(() => {
    loadScans();
  }, []);

  // 從詳情頁切回列表頁時，自動關閉 drawer 避免 inline sidebar 與 drawer 同時出現
  useEffect(() => {
    if (!isDetailPage) setDrawerOpen(false);
  }, [isDetailPage]);

  // 有任何進行中的 scan 時，自動 polling 列表
  const hasInProgress = scans.some((scan) => isInProgress(scan.status));
  useEffect(() => {
    if (!hasInProgress) return undefined;
    const timer = setInterval(loadScans, LIST_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [hasInProgress]);

  function handleScanCreated(newScan) {
    loadScans();
    setDrawerOpen(false);
    navigate(`/scans/${newScan.id}`);
  }

  return (
    <div
      className={`scan-layout ${isDetailPage ? "detail-mode" : "list-mode"} ${
        drawerOpen ? "drawer-open" : ""
      }`}
    >
      <aside className="scan-sidebar">
        <ScanJobForm onCreated={handleScanCreated} />
        <ScanList scans={scans} onRefresh={loadScans} />
      </aside>
      {isDetailPage && drawerOpen && (
        <button
          type="button"
          className="scan-sidebar-backdrop"
          aria-label="關閉列表"
          onClick={() => setDrawerOpen(false)}
        />
      )}
      <div className="scan-content">
        {isDetailPage && (
          <div className="scan-content-toolbar">
            <button
              type="button"
              className="drawer-toggle"
              onClick={() => setDrawerOpen((open) => !open)}
              aria-expanded={drawerOpen}
            >
              <span aria-hidden="true">☰</span>
              <span>{drawerOpen ? "收起列表" : "展開列表 / 建立掃描"}</span>
            </button>
            <button
              type="button"
              className="back-to-list-button"
              onClick={() => navigate("/scans")}
            >
              ← 回到掃描列表
            </button>
            {isTopologyPage ? (
              <button
                type="button"
                className="back-to-list-button"
                onClick={() => navigate(`/scans/${scanId}`)}
              >
                📋 回詳情報告
              </button>
            ) : (
              <button
                type="button"
                className="back-to-list-button"
                onClick={() => navigate(`/scans/${scanId}/topology`)}
              >
                🌐 拓撲圖
              </button>
            )}
          </div>
        )}
        <Outlet />
      </div>
    </div>
  );
}

function LoginPage() {
  const accessToken = useArgusStore((state) => state.accessToken);
  const [searchParams] = useSearchParams();
  if (accessToken) {
    const next = searchParams.get("next");
    const target = next && next.startsWith("/") ? next : "/scans";
    return <Navigate to={target} replace />;
  }
  return (
    <div className="mx-auto max-w-md">
      <LoginForm />
    </div>
  );
}

function shortenUrl(url) {
  try {
    const u = new URL(url);
    const tail = (u.pathname + u.search) || "/";
    return tail.length > 28 ? `${tail.slice(0, 25)}...` : tail;
  } catch {
    return url.slice(0, 28);
  }
}

function TopologyPage() {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/scans/${scanId}/topology/`)
      .then((r) => {
        if (!cancelled) setData(r.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError("無法載入拓撲資料，可能掃描尚未完成或無權限。");
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    const byDepth = {};
    data.nodes.forEach((n) => {
      const d = n.depth ?? 0;
      if (!byDepth[d]) byDepth[d] = [];
      byDepth[d].push(n);
    });
    const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b);
    const rfNodes = [];
    depths.forEach((d) => {
      const layer = byDepth[d];
      layer.forEach((n, i) => {
        rfNodes.push({
          id: String(n.id),
          position: { x: d * 260, y: i * 110 - ((layer.length - 1) * 110) / 2 },
          data: {
            label: (
              <div className={`topology-node tone-${n.tone}`}>
                <div className="topology-node-url" title={n.url}>
                  {shortenUrl(n.url)}
                </div>
                <div className="topology-node-meta">
                  {n.blocked
                    ? "⛔ 被阻擋"
                    : n.finding_count > 0
                      ? `${n.finding_count} 個 finding · ${n.max_severity}`
                      : "✓ 無 finding"}
                </div>
              </div>
            ),
          },
          className: `topology-rf-node tone-${n.tone}`,
        });
      });
    });
    const rfEdges = data.edges.map((e, i) => ({
      id: `e${i}-${e.source}-${e.target}`,
      source: String(e.source),
      target: String(e.target),
      type: "smoothstep",
      animated: false,
    }));
    return { nodes: rfNodes, edges: rfEdges };
  }, [data]);

  function handleNodeClick(_, node) {
    navigate(`/scans/${scanId}?page=${node.id}`);
  }

  if (loadError) {
    return (
      <section className="panel">
        <p className="error-text">{loadError}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="panel">
        <p className="hint-text">載入拓撲資料中...</p>
      </section>
    );
  }
  if (data.nodes.length === 0) {
    return (
      <section className="panel">
        <p className="hint-text">本次掃描沒有可顯示的頁面節點（爬蟲未產生任何 Page）。</p>
      </section>
    );
  }

  return (
    <section className="topology-panel">
      <header className="topology-header">
        <h2>掃描拓撲圖</h2>
        <p className="hint-text">
          節點 = 頁面（顏色按該頁 finding 嚴重度），邊 = 頁面間連結。
          點任一節點可跳回詳情報告該頁。
        </p>
        <div className="topology-legend">
          <span className="legend-chip tone-good">✓ 無問題</span>
          <span className="legend-chip tone-medium">中度問題</span>
          <span className="legend-chip tone-bad">高/嚴重問題</span>
        </div>
      </header>
      <div className="topology-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodeClick={handleNodeClick}
          fitView
          nodesDraggable
          minZoom={0.2}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
        >
          <Controls />
          <Background gap={24} size={1} />
        </ReactFlow>
      </div>
    </section>
  );
}

function ScansPlaceholder() {
  return (
    <section className="panel">
      <p className="hint-text">請從左側選擇一個掃描任務查看互動報告。</p>
    </section>
  );
}

function ScanDetailPage() {
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [scan, setScan] = useState(null);
  const [loadError, setLoadError] = useState("");

  // 首次載入
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await api.get(`/scans/${scanId}/`);
        if (!cancelled) {
          setScan(response.data);
          setLoadError("");
        }
      } catch {
        if (!cancelled) setLoadError("無法載入掃描資料，可能不存在或無權限。");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  // 進行中時自動 polling
  const inProgress = scan && isInProgress(scan.status);
  useEffect(() => {
    if (!inProgress) return undefined;
    const timer = setInterval(async () => {
      try {
        const response = await api.get(`/scans/${scanId}/`);
        setScan(response.data);
      } catch {
        // 暫時失敗繼續嘗試
      }
    }, SCAN_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [inProgress, scanId]);

  if (loadError) {
    return (
      <section className="panel">
        <p className="error-text">{loadError}</p>
        <button
          className="secondary-button mt-3"
          type="button"
          onClick={() => navigate("/scans")}
        >
          回到掃描列表
        </button>
      </section>
    );
  }
  if (scan) {
    return <FindingsWorkspace scan={scan} />;
  }
  return (
    <section className="panel">
      <p className="hint-text">載入掃描資料中...</p>
    </section>
  );
}

// ============================================================
// 頂部深色 Navigation（高科技 dashboard 感）
// ============================================================

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", emoji: "📊" },
  { to: "/scans", label: "掃描", emoji: "🔍" },
  { to: "/history", label: "歷史", emoji: "📈" },
  { to: "/audit", label: "活動", emoji: "🧾" },
  { to: "/categories", label: "分類", emoji: "🗂️" },
  { to: "/settings", label: "設定", emoji: "⚙️" },
];

function TopNav() {
  const accessToken = useArgusStore((state) => state.accessToken);
  if (!accessToken) return null;
  return (
    <nav className="argus-nav">
      <div className="argus-nav-inner">
        <div className="argus-brand">
          <span className="argus-brand-glyph">⟡</span>
          <span>
            <span className="argus-brand-title">ARGUS</span>
            <span className="argus-brand-sub">AI 網站健檢平台</span>
          </span>
        </div>
        <div className="argus-nav-links">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `argus-nav-link ${isActive ? "active" : ""}`
              }
            >
              <span aria-hidden="true">{item.emoji}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
        <AccountBar />
      </div>
    </nav>
  );
}

// ============================================================
// Dashboard 頁
// ============================================================

const CATEGORY_LABELS = {
  seo: "SEO",
  aeo: "AEO",
  geo: "GEO",
  security: "資安",
  ux: "UX",
};

function ScoreRing({ value, label, size = 96 }) {
  const display = value === null || value === undefined ? "—" : Math.round(value);
  const pct = typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
  const tone = pct >= 80 ? "good" : pct >= 60 ? "medium" : "bad";
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  return (
    <div className={`score-ring tone-${tone}`} style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth="8"
          className="ring-track"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="none"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="ring-progress"
        />
      </svg>
      <div className="score-ring-text">
        <span className="score-ring-value">{display}</span>
        {label && <span className="score-ring-label">{label}</span>}
      </div>
    </div>
  );
}

function StatTile({ label, value, hint, tone = "neutral", animateValue }) {
  return (
    <div className={`stat-tile tone-${tone}`}>
      <p className="stat-tile-label">{label}</p>
      <p className="stat-tile-value">
        {typeof animateValue === "number" ? <CountUp value={animateValue} /> : value}
      </p>
      {hint && <p className="stat-tile-hint">{hint}</p>}
    </div>
  );
}

function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [categoriesData, setCategoriesData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.get("/dashboard/"), api.get("/findings-by-category/")])
      .then(([dashRes, catRes]) => {
        if (cancelled) return;
        setData(dashRes.data);
        setCategoriesData(catRes.data);
      })
      .catch(() => {
        if (!cancelled) setError("無法載入 Dashboard 資料。");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <section className="panel">
        <p className="error-text">{error}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="panel">
        <p className="hint-text">載入 Dashboard 中...</p>
      </section>
    );
  }

  const { quota } = data;
  const quotaPct =
    quota.monthly_limit > 0
      ? Math.min(100, (quota.used_this_month / quota.monthly_limit) * 100)
      : 0;
  const totalFindings = Object.values(data.severity_totals || {}).reduce(
    (sum, n) => sum + n,
    0,
  );

  return (
    <div className="dashboard-grid">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow text-cyan-300">總覽</p>
          <h2 className="dashboard-hero-title">
            你已執行 <span>{data.total_scans}</span> 次健檢
          </h2>
          <p className="dashboard-hero-sub">
            完成 {data.completed_scans}・失敗 {data.failed_scans}・本月剩餘配額{" "}
            {quota.remaining}/{quota.monthly_limit}
          </p>
        </div>
        <ScoreRing value={data.average_score} label="平均分" size={120} />
      </div>

      <div className="stat-grid">
        <StatTile
          label="掃描總數"
          animateValue={data.total_scans}
          hint="所有狀態合計"
          tone="cyan"
        />
        <StatTile
          label="本月已用"
          value={`${quota.used_this_month} / ${quota.monthly_limit}`}
          hint={`使用率 ${Math.round(quotaPct)}%`}
          tone="violet"
        />
        <StatTile
          label="累計 Findings"
          animateValue={totalFindings}
          hint="跨所有完成掃描"
          tone="amber"
        />
        <StatTile
          label="高/嚴重"
          animateValue={
            (data.severity_totals?.critical || 0) +
            (data.severity_totals?.high || 0)
          }
          hint="critical + high"
          tone="rose"
        />
      </div>

      <div className="panel dashboard-panel">
        <div className="dashboard-panel-header">
          <h3>Findings 嚴重度分佈</h3>
          <span className="hint-text-sm">跨所有掃描</span>
        </div>
        <SeverityBarChart
          severityTotals={data.severity_totals}
          title=""
        />
      </div>

      <div className="panel dashboard-panel">
        <div className="dashboard-panel-header">
          <h3>各類別 finding 佔比</h3>
          <span className="hint-text-sm">哪一類問題最多</span>
        </div>
        <StackedBar
          data={Object.keys(CATEGORY_LABELS).map((cat) => ({
            label: CATEGORY_LABELS[cat],
            value: categoriesData?.categories?.[cat]?.total_findings || 0,
            color: CATEGORY_COLOR[cat],
          }))}
        />
      </div>

      <div className="panel dashboard-panel">
        <div className="dashboard-panel-header">
          <h3>各類別平均</h3>
          <span className="hint-text-sm">基於完成的掃描</span>
        </div>
        <div className="category-rings">
          {Object.keys(CATEGORY_LABELS).map((cat) => (
            <div className="category-ring-item" key={cat}>
              <ScoreRing
                value={data.category_averages?.[cat] ?? null}
                size={84}
              />
              <span className={`category-pill cat-${cat}`}>
                {CATEGORY_LABELS[cat]}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="panel dashboard-panel">
        <div className="dashboard-panel-header">
          <h3>最近掃描</h3>
          <button
            className="secondary-button"
            type="button"
            onClick={() => navigate("/scans")}
          >
            前往掃描頁
          </button>
        </div>
        <ul className="recent-list">
          {data.recent_scans.length === 0 && (
            <li className="text-sm text-slate-400">尚無掃描紀錄。</li>
          )}
          {data.recent_scans.map((scan) => (
            <li key={scan.id}>
              <button
                className="recent-row"
                type="button"
                onClick={() => navigate(`/scans/${scan.id}`)}
              >
                <span className="recent-origin">{scan.origin}</span>
                <ScanStatusBadge status={scan.status} />
                <ScoreBadge score={scan.overall_score} />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ============================================================
// History 頁（同網址歷次分數）
// ============================================================

function Sparkline({ values }) {
  if (!values.length) return <span className="text-slate-400">—</span>;
  const w = 120;
  const h = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length > 1 ? w / (values.length - 1) : 0;
  const points = values
    .map((v, i) => `${i * step},${h - ((v - min) / range) * (h - 6) - 3}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="sparkline">
      <polyline points={points} fill="none" strokeWidth="2" />
    </svg>
  );
}

function HistoryPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get("/history/")
      .then((r) => !cancelled && setData(r.data))
      .catch(() => !cancelled && setError("無法載入歷史資料。"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <section className="panel"><p className="error-text">{error}</p></section>;
  if (!data) return <section className="panel"><p className="hint-text">載入中...</p></section>;

  return (
    <section className="panel">
      <div className="dashboard-panel-header">
        <h3>同網址分數歷史</h3>
        <span className="hint-text-sm">每個 origin 的歷次健檢</span>
      </div>
      {data.origins.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">尚無紀錄。</p>
      )}
      <div className="history-grid">
        {data.origins.map((origin) => {
          const chronological = origin.scans
            .filter((s) => s.overall_score !== null && s.overall_score !== undefined)
            .slice()
            .reverse();
          const chartData = chronological.map((s) => ({
            label: new Date(s.created_at).toLocaleDateString("zh-Hant", {
              month: "numeric",
              day: "numeric",
            }),
            value: s.overall_score,
          }));
          const deltaLabel =
            origin.delta === null || origin.delta === undefined
              ? null
              : origin.delta > 0
                ? `▲ +${origin.delta}`
                : origin.delta < 0
                  ? `▼ ${origin.delta}`
                  : "—";
          const deltaTone =
            origin.delta === null || origin.delta === undefined
              ? "neutral"
              : origin.delta >= 0
                ? "good"
                : "bad";
          return (
            <div key={origin.origin} className="history-card">
              <div className="history-card-head">
                <span className="history-origin">{origin.origin}</span>
                <span className="hint-text-sm">{origin.total_scans} 次</span>
              </div>
              <div className="history-card-mid">
                <ScoreBadge score={origin.latest_score} />
                {deltaLabel && (
                  <span className={`history-delta tone-${deltaTone}`}>{deltaLabel}</span>
                )}
              </div>
              {chartData.length > 0 && (
                <div className="history-chart">
                  <LineChart data={chartData} ariaLabel={`${origin.origin} 分數趨勢`} />
                </div>
              )}
              <ul className="history-list">
                {origin.scans.slice(0, 5).map((s) => (
                  <li key={s.id}>
                    <button
                      className="history-row"
                      type="button"
                      onClick={() => navigate(`/scans/${s.id}`)}
                    >
                      <span className="text-xs text-slate-500">
                        {new Date(s.created_at).toLocaleString("zh-Hant")}
                      </span>
                      <ScanStatusBadge status={s.status} />
                      <ScoreBadge score={s.overall_score} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ============================================================
// Audit log 頁
// ============================================================

const AUDIT_TYPE_META = {
  scan_created: { label: "建立掃描", tone: "blue", emoji: "🔍" },
  scan_completed: { label: "完成掃描", tone: "emerald", emoji: "✓" },
  scan_failed: { label: "掃描失敗", tone: "red", emoji: "✗" },
  authorization: { label: "授權確認", tone: "slate", emoji: "🛡️" },
};

function AuditPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get("/audit/")
      .then((r) => !cancelled && setData(r.data))
      .catch(() => !cancelled && setError("無法載入活動紀錄。"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <section className="panel"><p className="error-text">{error}</p></section>;
  if (!data) return <section className="panel"><p className="hint-text">載入中...</p></section>;

  return (
    <section className="panel">
      <div className="dashboard-panel-header">
        <h3>活動紀錄</h3>
        <span className="hint-text-sm">{data.events.length} 筆事件</span>
      </div>
      {data.events.length === 0 && (
        <p className="mt-3 text-sm text-slate-500">尚無活動。</p>
      )}
      <ol className="timeline">
        {data.events.map((event, idx) => {
          const meta = AUDIT_TYPE_META[event.type] || { label: event.type, tone: "slate", emoji: "•" };
          return (
            <li className="timeline-item" key={`${event.type}-${event.timestamp}-${idx}`}>
              <span className={`timeline-marker tone-${meta.tone}`}>{meta.emoji}</span>
              <div className="timeline-body">
                <div className="timeline-row">
                  <span className="timeline-label">{meta.label}</span>
                  <span className="timeline-time">
                    {new Date(event.timestamp).toLocaleString("zh-Hant")}
                  </span>
                </div>
                <p className="timeline-message">{event.message}</p>
                {event.scan_id && (
                  <button
                    className="link-button"
                    type="button"
                    onClick={() => navigate(`/scans/${event.scan_id}`)}
                  >
                    查看掃描 #{event.scan_id}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// ============================================================
// Categories 頁（跨掃描 finding 分類聚合）
// ============================================================

function CategoriesPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState("security");

  useEffect(() => {
    let cancelled = false;
    api
      .get("/findings-by-category/")
      .then((r) => !cancelled && setData(r.data))
      .catch(() => !cancelled && setError("無法載入分類資料。"));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <section className="panel"><p className="error-text">{error}</p></section>;
  if (!data) return <section className="panel"><p className="hint-text">載入中...</p></section>;

  const categories = Object.keys(CATEGORY_LABELS);
  const current = data.categories[active] || { total_findings: 0, items: [] };

  return (
    <section className="panel">
      <div className="dashboard-panel-header">
        <h3>跨掃描分類彙總</h3>
        <span className="hint-text-sm">同類問題重複出現的次數</span>
      </div>
      <div className="category-tabs">
        {categories.map((cat) => {
          const stats = data.categories[cat];
          return (
            <button
              key={cat}
              className={`category-tab cat-${cat} ${active === cat ? "active" : ""}`}
              type="button"
              onClick={() => setActive(cat)}
            >
              <span className="category-tab-label">{CATEGORY_LABELS[cat]}</span>
              <span className="category-tab-count">{stats?.total_findings || 0}</span>
            </button>
          );
        })}
      </div>
      <ul className="category-issue-list">
        {current.items.length === 0 && (
          <li className="hint-text">此分類目前沒有 finding。</li>
        )}
        {current.items.map((item) => (
          <li key={`${active}-${item.title}`} className="category-issue-row">
            <span className={`severity ${item.severity}`}>{item.severity}</span>
            <span className="category-issue-title">{item.title}</span>
            <span className="category-issue-count">×{item.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ============================================================
// Settings 頁
// ============================================================

function SettingsPage() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/").then((r) => setData(r.data)).catch(() => {});
  }, []);

  const quotaUsed = data?.quota?.used_this_month || 0;
  const quotaLimit = data?.quota?.monthly_limit || 1;
  const quotaPct = Math.min(100, (quotaUsed / quotaLimit) * 100);
  const quotaTone = quotaPct >= 80 ? "bad" : quotaPct >= 50 ? "medium" : "good";

  const totalFindings = data
    ? Object.values(data.severity_totals || {}).reduce((sum, n) => sum + n, 0)
    : 0;

  return (
    <section className="panel space-y-4">
      <div>
        <p className="eyebrow">設定</p>
        <h2 className="section-title">帳號與系統</h2>
      </div>

      {/* 本月配額：大塊進度條 */}
      <div className="quota-panel">
        <div className="quota-panel-head">
          <div>
            <p className="quota-label">本月配額使用率</p>
            {data ? (
              <p className="quota-value">
                <span className="quota-used">
                  <CountUp value={quotaUsed} />
                </span>
                <span className="quota-divider">/</span>
                <span className="quota-limit">{quotaLimit}</span>
                <span className="quota-unit">次</span>
              </p>
            ) : (
              <p className="text-sm text-slate-400">載入中...</p>
            )}
          </div>
          <span className={`quota-tone-badge tone-${quotaTone}`}>
            {Math.round(quotaPct)}%
          </span>
        </div>
        <div className="quota-progress">
          <div
            className={`quota-progress-fill tone-${quotaTone}`}
            style={{ width: `${quotaPct}%` }}
          />
        </div>
        <p className="settings-card-hint">每月 1 日重設</p>
      </div>

      <div className="settings-grid">
        <div className="settings-card stat-card-glow">
          <p className="settings-card-label">累計掃描</p>
          <p className="settings-card-value">
            <CountUp value={data?.total_scans || 0} />
          </p>
          <p className="settings-card-hint">所有狀態合計</p>
        </div>
        <div className="settings-card stat-card-glow">
          <p className="settings-card-label">累計 Findings</p>
          <p className="settings-card-value">
            <CountUp value={totalFindings} />
          </p>
          <p className="settings-card-hint">跨所有完成掃描</p>
        </div>
        <div className="settings-card">
          <p className="settings-card-label">登入方式</p>
          <p className="settings-card-value text-base">Google OAuth</p>
          <p className="settings-card-hint">DEBUG=true 時可走 dev-login 後門</p>
        </div>
        <div className="settings-card">
          <p className="settings-card-label">資料夾位置</p>
          <p className="settings-card-value text-base">Docker volume</p>
          <p className="settings-card-hint">media_data（截圖與報告）</p>
        </div>
        <div className="settings-card">
          <p className="settings-card-label">技術棧</p>
          <p className="settings-card-value text-base">Django 5 · React 18</p>
          <p className="settings-card-hint">Playwright · Celery · Postgres</p>
        </div>
        <div className="settings-card">
          <p className="settings-card-label">版本</p>
          <p className="settings-card-value text-base">Argus MVP</p>
          <p className="settings-card-hint">授權式網站健檢平台</p>
        </div>
      </div>

      <div className="settings-about">
        <h3 className="text-base font-bold text-slate-900">關於 Argus</h3>
        <p>授權式 AI 網站健檢平台。同網域爬蟲、SEO/AEO/GEO/被動資安檢查、互動式報告、Word 匯出。</p>
        <p className="text-xs text-slate-500">
          所有掃描必須先勾選授權；明顯第三方需再次確認。掃描歷史與授權紀錄可在「活動」頁查看。
        </p>
      </div>
    </section>
  );
}

export default function App() {
  const accessToken = useArgusStore((state) => state.accessToken);
  return (
    <div className="argus-app">
      <TopNav />
      <main className={`argus-main ${accessToken ? "with-nav" : ""}`}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <DashboardPage />
              </RequireAuth>
            }
          />
          <Route
            element={
              <RequireAuth>
                <ScanLayout />
              </RequireAuth>
            }
          >
            <Route path="/scans" element={<ScansPlaceholder />} />
            <Route path="/scans/:scanId" element={<ScanDetailPage />} />
            <Route path="/scans/:scanId/topology" element={<TopologyPage />} />
          </Route>
          <Route
            path="/history"
            element={
              <RequireAuth>
                <HistoryPage />
              </RequireAuth>
            }
          />
          <Route
            path="/audit"
            element={
              <RequireAuth>
                <AuditPage />
              </RequireAuth>
            }
          />
          <Route
            path="/categories"
            element={
              <RequireAuth>
                <CategoriesPage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
