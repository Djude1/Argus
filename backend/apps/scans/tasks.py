import asyncio

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.scans.crawler import crawl_site
from apps.scans.models import Finding, Page, ScanJob
from apps.scans.scanners import (
    PageAnalysisInput,
    analyze_page,
    analyze_site_signals,
    calculate_scores,
)


@shared_task(bind=True)
def run_scan_job(self, scan_job_id: int) -> dict:
    scan_job = ScanJob.objects.get(id=scan_job_id)
    scan_job.status = ScanJob.Status.CRAWLING
    scan_job.started_at = timezone.now()
    scan_job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        crawled_pages, warnings, site_signals = asyncio.run(
            crawl_site(
                start_url=scan_job.normalized_url,
                origin=scan_job.origin,
                scan_job_id=scan_job.id,
                scan_mode=scan_job.scan_mode,
                max_depth=scan_job.max_depth,
                max_pages=scan_job.max_pages,
                respect_robots=scan_job.respect_robots,
            )
        )
        scan_job.status = ScanJob.Status.SCANNING
        scan_job.warning_summary = warnings
        scan_job.save(update_fields=["status", "warning_summary", "updated_at"])

        all_findings: list[dict] = []
        for page_data in crawled_pages:
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
            if page_data["blocked_reason"]:
                continue
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

        # 站台層級的 GEO FAST 檢查（llms.txt、AI 爬蟲可存取性）
        site_findings = analyze_site_signals(site_signals)
        for finding in site_findings:
            Finding.objects.create(scan_job=scan_job, page=None, **finding)
        all_findings.extend(site_findings)

        # Phase 2：可選的 Hermes-Agent 動態 UX 測試
        # 預設 ARGUS_AGENT_ENABLED=False；只在使用者明確啟用時才跑，避免每次掃描都消耗 LLM token。
        agent_meta = {}
        if settings.ARGUS_AGENT_ENABLED:
            scan_job.status = ScanJob.Status.AGENT_TESTING
            scan_job.save(update_fields=["status", "updated_at"])
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
        scan_job.completed_at = timezone.now()
        scan_job.save(
            update_fields=[
                "status",
                "overall_score",
                "category_scores",
                "top_actions",
                "warning_summary",
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
