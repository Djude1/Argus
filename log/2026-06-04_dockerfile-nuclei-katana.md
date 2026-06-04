# Dockerfile 加入 Nuclei + Katana binary 安裝

**日期**：2026-06-04
**操作者**：Claude

## 變更內容

- 修改 `Dockerfile`：在 Python/Playwright base image 中新增安裝步驟
  - apt 安裝 `unzip`、`wget`
  - 從 GitHub releases 下載 `nuclei_3.8.0_linux_amd64.zip` 並安裝到 `/usr/local/bin/`
  - 從 GitHub releases 下載 `katana_1.1.2_linux_amd64.zip` 並安裝到 `/usr/local/bin/`
  - 執行 `nuclei -update-templates` 預先下載 templates（加速首次掃描）
  - 使用 `ARG NUCLEI_VERSION` / `ARG KATANA_VERSION` 固定版本，方便未來升級

## 原因

Docker worker 容器執行 Celery 掃描任務，但先前未安裝 nuclei/katana binary，導致 `shutil.which()` 回傳 None，Nuclei/Katana 掃描靜默略過（silent-fail）。需在 image 內預裝 binary 才能讓 Docker 部署享有完整資安掃描能力。

## 影響範圍

- Docker worker 容器現在可執行完整 Nuclei + Katana 掃描
- 免費模式（passive）：log 顯示「Nuclei（快速免費）」
- 付費模式（active + authorized）：log 顯示「Nuclei（深度付費）」
- Docker image build 時間增加約 2-3 分鐘（下載 binary + templates）

## 驗證方式

- `docker exec argus-worker-1 nuclei -version` → `v3.8.0` ✅
- `docker exec argus-worker-1 katana -version` → 正常輸出 ✅
- 透過 Argus UI（localhost:8080）建立掃描：
  - passive 掃描（#15）：log 顯示「Nuclei（快速免費）」，完成 ✅
  - active+authorized 掃描（#14）：log 顯示「Nuclei（深度付費）」，完成 ✅
