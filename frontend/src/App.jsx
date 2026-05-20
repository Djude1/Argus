import { useEffect, useRef, useState } from "react";

import { api } from "./api";
import { useArgusStore } from "./store";

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

function LoginPanel() {
  const { accessToken, setToken } = useArgusStore();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("login");
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      if (mode === "register") {
        await api.post("/auth/register/", { username, email, password });
      }
      const response = await api.post("/auth/token/", { username, password });
      setToken(response.data.access);
    } catch {
      setError(mode === "register" ? "註冊失敗，請檢查欄位。" : "登入失敗，請確認帳號密碼。");
    }
  }

  if (accessToken) {
    return (
      <section className="panel">
        <div>
          <p className="eyebrow">已登入</p>
          <p className="text-sm text-slate-600">可建立授權掃描任務。</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => setToken(null)}>
          登出
        </button>
      </section>
    );
  }

  return (
    <form className="panel space-y-3" onSubmit={handleSubmit}>
      <div>
        <p className="eyebrow">{mode === "login" ? "登入" : "註冊"}</p>
        <h2 className="section-title">使用 Argus 前台</h2>
      </div>
      <input
        className="input"
        placeholder="帳號"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />
      {mode === "register" && (
        <input
          className="input"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      )}
      <input
        className="input"
        placeholder="密碼"
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {error && <p className="error-text">{error}</p>}
      <button className="primary-button" type="submit">
        {mode === "login" ? "登入" : "註冊並登入"}
      </button>
      <button
        className="text-sm font-semibold text-blue-700"
        type="button"
        onClick={() => setMode(mode === "login" ? "register" : "login")}
      >
        {mode === "login" ? "沒有帳號？切換到註冊" : "已有帳號？切換到登入"}
      </button>
    </form>
  );
}

function ScanJobForm({ onCreated }) {
  const [url, setUrl] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [thirdPartyReconfirmed, setThirdPartyReconfirmed] = useState(false);
  const [activeMode, setActiveMode] = useState(false);
  const [activeAuthorized, setActiveAuthorized] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
      setUrl("");
      setAuthorizationConfirmed(false);
      setThirdPartyReconfirmed(false);
      setActiveMode(false);
      setActiveAuthorized(false);
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
        {submitting ? "送出中..." : "建立掃描"}
      </button>
    </form>
  );
}

function ScoreBadge({ score }) {
  if (score === null || score === undefined) {
    return <span className="score-badge muted">尚無分數</span>;
  }
  const tone = score >= 80 ? "good" : score >= 60 ? "medium" : "bad";
  return <span className={`score-badge ${tone}`}>{score}</span>;
}

function ScanList({ scans, onRefresh }) {
  const { selectedScan, setSelectedScan } = useArgusStore();

  return (
    <section className="panel space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="eyebrow">任務</p>
          <h2 className="section-title">掃描列表</h2>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh}>
          重新整理
        </button>
      </div>
      <div className="space-y-2">
        {scans.map((scan) => (
          <button
            className={`scan-card ${selectedScan?.id === scan.id ? "active" : ""}`}
            key={scan.id}
            type="button"
            onClick={() => setSelectedScan(scan)}
          >
            <div>
              <p className="font-medium text-slate-900">{scan.origin}</p>
              <p className="text-xs text-slate-500">{scan.status}</p>
            </div>
            <ScoreBadge score={scan.overall_score} />
          </button>
        ))}
        {!scans.length && <p className="text-sm text-slate-500">尚無掃描任務。</p>}
      </div>
    </section>
  );
}

function ScreenshotCanvas({ scan, pages, findings }) {
  const firstPage = pages[0];
  const selectedFinding = useArgusStore((state) => state.selectedFinding);
  const [imageUrl, setImageUrl] = useState("");
  const [scale, setScale] = useState(1);
  const imageRef = useRef(null);

  useEffect(() => {
    let objectUrl = "";
    async function loadScreenshot() {
      if (!scan || !firstPage) {
        setImageUrl("");
        return;
      }
      const response = await api.get(`/scans/${scan.id}/pages/${firstPage.id}/screenshot/`, {
        responseType: "blob",
      });
      objectUrl = URL.createObjectURL(response.data);
      setImageUrl(objectUrl);
    }
    loadScreenshot();
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [scan, firstPage]);

  // 截圖以 max-width 縮放顯示，需依「顯示寬度 / 原始寬度」換算高光框座標才能對齊
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

  return (
    <div className="screenshot-shell">
      {!imageUrl && <p className="text-sm text-slate-500">掃描完成並產生截圖後會顯示在此。</p>}
      {imageUrl && (
        <div className="relative inline-block">
          <img
            alt="頁面截圖"
            className="screenshot-image"
            ref={imageRef}
            src={imageUrl}
            onLoad={syncScale}
          />
          <div className="pointer-events-none absolute inset-0">
            {findings
              .filter((finding) => finding.bounding_box)
              .map((finding) => {
                const box = finding.bounding_box;
                const active = selectedFinding?.id === finding.id;
                return (
                  <div
                    className={`highlight-box ${active ? "active" : ""}`}
                    key={finding.id}
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

function FindingsWorkspace() {
  const { selectedScan, selectedFinding, setSelectedFinding } = useArgusStore();
  const [findings, setFindings] = useState([]);
  const [pages, setPages] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  useEffect(() => {
    async function loadDetails() {
      if (!selectedScan) {
        return;
      }
      const [findingsResponse, pagesResponse] = await Promise.all([
        api.get(`/findings/?scan_id=${selectedScan.id}`),
        api.get(`/pages/?scan_id=${selectedScan.id}`),
      ]);
      setFindings(findingsResponse.data.results || findingsResponse.data);
      setPages(pagesResponse.data.results || pagesResponse.data);
    }
    loadDetails();
  }, [selectedScan]);

  async function downloadReport() {
    const response = await api.get(`/scans/${selectedScan.id}/report/`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `argus-scan-${selectedScan.id}-report.docx`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const filteredFindings = findings.filter(
    (finding) =>
      (categoryFilter === "all" || finding.category === categoryFilter) &&
      (severityFilter === "all" || finding.severity === severityFilter),
  );

  if (!selectedScan) {
    return (
      <section className="panel lg:col-span-2">
        <p className="text-sm text-slate-500">請先選擇一個掃描任務。</p>
      </section>
    );
  }

  return (
    <section className="panel lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">互動報告</p>
          <h2 className="section-title">{selectedScan.origin}</h2>
        </div>
        <button className="secondary-button" type="button" onClick={downloadReport}>
          匯出 Word
        </button>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <ScreenshotCanvas findings={filteredFindings} pages={pages} scan={selectedScan} />
        <div className="space-y-3">
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-700">Top Actions</p>
            {(selectedScan.top_actions || []).map((action) => (
              <p className="mt-2 text-sm text-slate-600" key={`${action.category}-${action.title}`}>
                {action.severity} / {action.category}：{action.title}
              </p>
            ))}
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
          <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
            {filteredFindings.map((finding) => (
              <button
                className={`finding-card ${selectedFinding?.id === finding.id ? "active" : ""}`}
                key={finding.id}
                type="button"
                onClick={() => setSelectedFinding(finding)}
              >
                <span className={`severity ${finding.severity}`}>{finding.severity}</span>
                <span>{finding.title}</span>
              </button>
            ))}
            {!filteredFindings.length && (
              <p className="text-sm text-slate-500">
                {findings.length ? "沒有符合篩選條件的項目。" : "尚無 findings。"}
              </p>
            )}
          </div>
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

export default function App() {
  const accessToken = useArgusStore((state) => state.accessToken);
  const [scans, setScans] = useState([]);

  async function loadScans() {
    if (!accessToken) {
      setScans([]);
      return;
    }
    const response = await api.get("/scans/");
    setScans(response.data.results || response.data);
  }

  useEffect(() => {
    loadScans();
  }, [accessToken]);

  return (
    <main className="min-h-screen bg-slate-100 p-4 text-slate-800 md:p-8">
      <header className="mx-auto mb-8 max-w-7xl">
        <p className="eyebrow">Argus</p>
        <h1 className="text-3xl font-bold text-slate-950 md:text-5xl">AI 網站健檢平台</h1>
        <p className="mt-3 max-w-3xl text-slate-600">
          授權式同網域爬蟲、SEO/AEO/GEO/被動資安掃描、互動式報告與 Word 匯出。
        </p>
      </header>
      <div className="mx-auto grid max-w-7xl gap-4 lg:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <LoginPanel />
          {accessToken && <ScanJobForm onCreated={loadScans} />}
          {accessToken && <ScanList onRefresh={loadScans} scans={scans} />}
        </div>
        {accessToken ? <FindingsWorkspace /> : <section className="panel">請先登入。</section>}
      </div>
    </main>
  );
}
