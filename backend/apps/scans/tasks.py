import asyncio

from asgiref.sync import sync_to_async
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.scans.active_probes import run_active_probes
from apps.scans.crawler import crawl_site
from apps.scans.models import Finding, Page, ScanJob
from apps.scans.scanners import (
    PageAnalysisInput,
    analyze_page,
    analyze_site_signals,
    calculate_scores,
)


def _write_progress(
    scan_job_id: int, *, phase: str, done: int, total: int, phase_started_at: str
) -> None:
    """寫 ScanJob.progress；用 filter().update() 避免覆蓋其他欄位且 race-safe。"""
    ScanJob.objects.filter(id=scan_job_id).update(
        progress={
            "pages_done": done,
            "pages_total": max(total, 1),  # 避免除以 0
            "phase": phase,
            "phase_started_at": phase_started_at,
        }
    )


@shared_task(bind=True)
def run_scan_job(self, scan_job_id: int) -> dict:
    scan_job = ScanJob.objects.get(id=scan_job_id)
    now = timezone.now()
    crawl_phase_started = now.isoformat()
    scan_job.status = ScanJob.Status.CRAWLING
    scan_job.started_at = now
    scan_job.progress = {
        "pages_done": 0,
        "pages_total": 1,
        "phase": "crawling",
        "phase_started_at": crawl_phase_started,
    }
    scan_job.save(update_fields=["status", "started_at", "progress", "updated_at"])

    try:
        # crawler callback：在 async loop 內透過 sync_to_async 寫 DB，每爬完一頁就更新
        async def _crawl_progress(done: int, total: int) -> None:
            await sync_to_async(_write_progress, thread_sensitive=True)(
                scan_job_id, phase="crawling", done=done, total=total,
                phase_started_at=crawl_phase_started,
            )

        crawled_pages, warnings, site_signals = asyncio.run(
            crawl_site(
                start_url=scan_job.normalized_url,
                origin=scan_job.origin,
                scan_job_id=scan_job.id,
                scan_mode=scan_job.scan_mode,
                max_depth=scan_job.max_depth,
                max_pages=scan_job.max_pages,
                respect_robots=scan_job.respect_robots,
                progress_callback=_crawl_progress,
            )
        )
        scan_phase_started = timezone.now().isoformat()
        scan_job.status = ScanJob.Status.SCANNING
        scan_job.warning_summary = warnings
        scan_job.progress = {
            "pages_done": 0,
            "pages_total": max(len(crawled_pages), 1),
            "phase": "scanning",
            "phase_started_at": scan_phase_started,
        }
        scan_job.save(update_fields=["status", "warning_summary", "progress", "updated_at"])

        all_findings: list[dict] = []
        scanning_total = max(len(crawled_pages), 1)
        for scanned_idx, page_data in enumerate(crawled_pages, start=1):
            page = Page.objects.create(
                scan_job=scan_job,
                url=page_data["url"],
                final_url=page_data["final_url"],
                origin=page_data["origin"],
                status_code=page_data["status_code"],
                title=page_data["title"],
                html=page_data["html"],
                rendered_dom=page_data["rendered_dom"],
                html_only_text=page_data["html_only"],
                screenshot_path=page_data["screenshot_path"],
                load_time_ms=page_data["load_time_ms"],
                depth=page_data["depth"],
                blocked_reason=page_data["blocked_reason"],
                outgoing_links=page_data["outgoing_links"],
                headers=page_data["headers"],
                element_boxes=page_data["element_boxes"],
            )
            # 被阻擋的頁面內容是錯誤頁，不進行四維掃描，僅保留紀錄與警告
            if not page_data["blocked_reason"]:
                page_findings = analyze_page(
                    PageAnalysisInput(
                        url=page.url,
                        final_url=page.final_url,
                        title=page.title,
                        html=page.html,
                        headers=page_data["headers"],
                        element_boxes=page_data["element_boxes"],
                        html_only=page_data["html_only"],
                    )
                )
                all_findings.extend(page_findings)
                for finding in page_findings:
                    Finding.objects.create(scan_job=scan_job, page=page, **finding)
            # 不論是否被阻擋，已處理一頁就更新 progress
            _write_progress(
                scan_job.id,
                phase="scanning",
                done=scanned_idx,
                total=scanning_total,
                phase_started_at=scan_phase_started,
            )

        # 站台層級的 GEO FAST 檢查（llms.txt、AI 爬蟲可存取性）
        site_findings = analyze_site_signals(site_signals)
        for finding in site_findings:
            Finding.objects.create(scan_job=scan_job, page=None, **finding)
        all_findings.extend(site_findings)

        # T14 主動式資安：只在 active 模式 + 額外授權下執行；RPS 限制由 RateLimitedClient 強制
        if (
            scan_job.scan_mode == ScanJob.ScanMode.ACTIVE
            and scan_job.active_testing_authorized
        ):
            active_findings = run_active_probes(
                origin=scan_job.origin,
                pages=scan_job.pages.all(),
            )
            for finding in active_findings:
                Finding.objects.create(scan_job=scan_job, page=None, **finding)
            all_findings.extend(active_findings)

        # Phase 2：可選的 Hermes-Agent 動態 UX 測試
        # 預設 ARGUS_AGENT_ENABLED=False；只在使用者明確啟用時才跑，避免每次掃描都消耗 LLM token。
        agent_meta = {}
        if settings.ARGUS_AGENT_ENABLED:
            agent_phase_started = timezone.now().isoformat()
            scan_job.status = ScanJob.Status.AGENT_TESTING
            scan_job.progress = {
                "pages_done": 0,
                "pages_total": settings.ARGUS_AGENT_MAX_STEPS,
                "phase": "agent_testing",
                "phase_started_at": agent_phase_started,
            }
            scan_job.save(update_fields=["status", "progress", "updated_at"])
            try:
                from apps.agent.runner import run_agent_for_scan

                agent_result = asyncio.run(run_agent_for_scan(scan_job))
                if agent_result:
                    agent_meta = {
                        "status": agent_result.status,
                        "steps": agent_result.steps,
                        "tokens": agent_result.total_tokens,
                        "issues_reported": len(agent_result.issues),
                        "error": agent_result.error,
                    }
                    _write_progress(
                        scan_job.id,
                        phase="agent_testing",
                        done=agent_result.steps,
                        total=settings.ARGUS_AGENT_MAX_STEPS,
                        phase_started_at=agent_phase_started,
                    )
                    for issue in agent_result.issues:
                        all_findings.append(
                            {
                                "category": "ux",
                                "severity": issue.get("severity", "low"),
                                "title": issue.get("title", ""),
                            }
                        )
            except Exception as exc:  # noqa: BLE001 — agent 失敗不應讓整個掃描失敗
                agent_meta = {"status": "error", "error": exc.__class__.__name__}

        overall_score, category_scores, top_actions = calculate_scores(all_findings)
        scan_job.status = ScanJob.Status.COMPLETED
        scan_job.overall_score = overall_score
        scan_job.category_scores = category_scores
        scan_job.top_actions = top_actions
        if agent_meta:
            warning_summary = dict(scan_job.warning_summary or {})
            warning_summary["agent"] = agent_meta
            scan_job.warning_summary = warning_summary
        scan_job.progress = {}  # 完成後清空，前端不再顯示進行中動畫
        scan_job.completed_at = timezone.now()
        scan_job.save(
            update_fields=[
                "status",
                "overall_score",
                "category_scores",
                "top_actions",
                "warning_summary",
                "progress",
                "completed_at",
                "updated_at",
            ]
        )
        return {
            "status": scan_job.status,
            "pages": len(crawled_pages),
            "findings": len(all_findings),
            "agent": agent_meta,
        }
    except Exception as exc:
        scan_job.status = ScanJob.Status.FAILED
        # 只存類別名（"Error"）會讓使用者在 UI 看到「掃描失敗：Error」，無法診斷。
        # 帶上 str(exc) 截斷至 500 字（避免完整 traceback 灌爆欄位、洩漏內部路徑）。
        detail = str(exc).strip()[:500]
        class_name = exc.__class__.__name__
        scan_job.error_message = f"{class_name}: {detail}" if detail else class_name
        scan_job.completed_at = timezone.now()
        scan_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        raise
