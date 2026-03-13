import logging
from collections.abc import Callable
from typing import cast

from delivery.openclaw_notifier import OpenClawNotifier
from services import (
    ArxivService,
    LLMFilterService,
    PaperQueueService,
    TranslationService,
    get_unprocessed_raw_papers,
    get_unpushed_papers,
    mark_papers_as_processed,
    mark_papers_as_pushed,
    save_relevant_papers_to_mysql,
)

from core.runtime_config import get_config


PaperRecord = dict[str, object]
WorkflowResult = dict[str, object]
ConfigMap = dict[str, object]
SearchPapersCallable = Callable[[], list[PaperRecord]]


def _get_logger(logger: logging.Logger | None = None) -> logging.Logger:
    return logger or logging.getLogger("app")


def _to_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def run_fetch_papers(logger: logging.Logger | None = None) -> WorkflowResult:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始执行论文获取任务")
    active_logger.info("=" * 60)

    try:
        arxiv_config = get_config("arxiv", logger=active_logger)
        llm_config = get_config("llm_filter", logger=active_logger)
        min_stars = _to_int(llm_config.get("min_stars", 3), 3)

        llm_service = (
            LLMFilterService(config=llm_config)
            if llm_config.get("enable", True)
            else None
        )
        translation_service = (
            TranslationService(config=llm_config)
            if llm_config.get("enable", True)
            else None
        )
        queue_service = PaperQueueService()
        arxiv_service = ArxivService(config=arxiv_config)
        processed_count = 0

        def _process_batch(batch: list[PaperRecord]) -> None:
            nonlocal processed_count

            active_logger.info(f"📝 新抓到 {len(batch)} 篇论文，立即开始解析...")

            try:
                if llm_service:
                    filtered, failed_papers = llm_service.filter_papers(batch)
                    qualified = [
                        paper
                        for paper in filtered
                        if paper.get("Stars", 0) >= min_stars
                    ]
                    if failed_papers:
                        active_logger.warning(
                            f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态"
                        )
                else:
                    filtered = batch
                    qualified = batch

                for index, paper in enumerate(qualified, start=1):
                    try:
                        active_logger.info(
                            f"  [{index}/{len(qualified)}] 翻译: {str(paper.get('Title', ''))[:50]}..."
                        )
                        translated = (
                            cast(PaperRecord, translation_service.translate_paper(paper))
                            if translation_service
                            else paper
                        )
                        _ = save_relevant_papers_to_mysql([translated])
                        translated["ID"] = translated.get("DOI", "")
                        _ = queue_service.enqueue_papers([translated])
                        processed_count += 1
                        active_logger.info(
                            f"  [{index}/{len(qualified)}] 已保存 (总计 {processed_count} 篇)"
                        )
                    except Exception as exc:
                        active_logger.error(f"  [{index}/{len(qualified)}] 处理失败: {exc}")

                successfully_processed = [
                    str(paper.get("DOI"))
                    for paper in (filtered if llm_service else batch)
                    if paper.get("DOI")
                ]
                if successfully_processed:
                    _ = mark_papers_as_processed(successfully_processed)
                    active_logger.info(f"✅ 已标记 {len(successfully_processed)} 篇为已处理")

            except Exception as exc:
                active_logger.error(f"解析批次出错: {exc}")

        active_logger.info("🚀 开始获取新论文...，将在整批论文筛选并翻译完成后将相关论文存入papers_relevant表中。")
        all_papers = arxiv_service.search_papers(batch_callback=_process_batch)

        if all_papers:
            active_logger.info(f"✅ 共获取 {len(all_papers)} 篇新论文，处理了 {processed_count} 篇相关论文")
        else:
            active_logger.info("没有找到新论文")

        return {
            "status": "success",
            "message": f"获取了 {len(all_papers) if all_papers else 0} 篇新论文，处理了 {processed_count} 篇相关论文",
            "count": processed_count,
        }
    except Exception as exc:
        active_logger.error(f"论文获取任务失败: {exc}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "message": str(exc), "count": 0}

def run_delivery(logger: logging.Logger | None = None) -> WorkflowResult:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始执行论文投递任务")
    active_logger.info("=" * 60)

    try:
        push_config = cast(
            ConfigMap,
            get_config("schedule", logger=active_logger).get("push_papers", {}),
        )
        max_papers = _to_int(push_config.get("max_papers_per_push", 5), 5)

        unpushed = get_unpushed_papers(limit=100)
        if unpushed:
            active_logger.info(f"发现 {len(unpushed)} 篇未投递的论文，加入投递队列")
            _ = PaperQueueService().enqueue_papers(unpushed)

        queue_service = PaperQueueService()
        papers = queue_service.dequeue_papers(max_papers)
        if not papers:
            active_logger.info("队列中没有待投递的论文")
            return {"status": "success", "message": "队列为空", "count": 0}

        delivery_config = get_config("openclaw", logger=active_logger)
        notifier = OpenClawNotifier(
            binary_path=_to_str(
                delivery_config.get("binary_path", "openclaw"), "openclaw"
            ),
            session_key=_to_str(delivery_config.get("session_key", "main"), "main"),
        timeout_seconds=_to_int(delivery_config.get("timeout_seconds", 300), 300),
        )
        success = notifier.send_papers(papers)

        if success:
            dois = [paper.get("DOI") for paper in papers if paper.get("DOI")]
            if dois:
                _ = mark_papers_as_pushed([str(doi) for doi in dois])

            active_logger.info(f"成功投递 {len(papers)} 篇论文")
            return {
                "status": "success",
                "message": f"投递了 {len(papers)} 篇论文",
                "count": len(papers),
            }

        active_logger.warning("部分论文投递失败")
        return {
            "status": "partial",
            "message": "部分论文投递失败",
            "count": len(papers),
        }
    except Exception as exc:
        active_logger.error(f"论文投递任务失败: {exc}")
        return {"status": "error", "message": str(exc), "count": 0}


def process_unprocessed_papers(logger: logging.Logger | None = None) -> None:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始处理未解析的论文")
    active_logger.info("=" * 60)

    try:
        process_config = cast(
            ConfigMap,
            get_config("schedule", logger=active_logger).get("process_papers", {}),
        )
        batch_size = _to_int(process_config.get("batch_size", 100), 100)

        unprocessed = get_unprocessed_raw_papers(limit=batch_size)
        total = len(unprocessed)
        if total == 0:
            active_logger.info("没有未处理的论文")
            return

        active_logger.info(f"找到 {total} 篇未处理的论文（配置限制：{batch_size}篇）")

        llm_config = get_config("llm_filter", logger=active_logger)
        min_stars = _to_int(llm_config.get("min_stars", 3), 3)
        llm_service = (
            LLMFilterService(config=llm_config)
            if llm_config.get("enable", True)
            else None
        )
        translation_service = (
            TranslationService(config=llm_config)
            if llm_config.get("enable", True)
            else None
        )
        queue_service = PaperQueueService()

        processed_count = 0
        relevant_count = 0
        failed_papers = []

        if llm_service:
            active_logger.info(f"开始LLM筛选 {total} 篇论文...")
            filtered, failed_papers = llm_service.filter_papers(unprocessed)
            qualified = [
                paper for paper in filtered if paper.get("Stars", 0) >= min_stars
            ]
        else:
            filtered = unprocessed
            qualified = unprocessed

        active_logger.info(
            f"筛选完成: {len(qualified)}/{total} 篇论文达到 {min_stars}星及以上"
        )

        if qualified:
            for index, paper in enumerate(qualified, start=1):
                try:
                    action_label = "翻译" if translation_service else "保存"
                    active_logger.info(
                        f"  [{index}/{len(qualified)}] {action_label}: {str(paper.get('Title', ''))[:50]}..."
                    )
                    translated = (
                        cast(PaperRecord, translation_service.translate_paper(paper))
                        if translation_service
                        else paper
                    )
                    _ = save_relevant_papers_to_mysql([translated])
                    translated["ID"] = translated.get("DOI", "")
                    _ = queue_service.enqueue_papers([translated])
                    relevant_count += 1
                    active_logger.info(
                        f"  [{index}/{len(qualified)}] 已保存 (总计 {relevant_count} 篇)"
                    )
                except Exception as exc:
                    active_logger.error(f"  [{index}/{len(qualified)}] 处理失败: {exc}")

        successfully_processed = [
            paper.get("DOI")
            for paper in (filtered if llm_service else unprocessed)
            if paper.get("DOI")
        ]
        if successfully_processed:
            _ = mark_papers_as_processed([str(doi) for doi in successfully_processed])
            processed_count = len(successfully_processed)

        if failed_papers:
            active_logger.warning(
                f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态，等待重新评估"
            )

        active_logger.info("=" * 60)
        active_logger.info(
            f"处理完成: 共处理 {processed_count} 篇，相关 {relevant_count} 篇"
        )
        active_logger.info("=" * 60)
    except Exception as exc:
        active_logger.error(f"处理未解析论文失败: {exc}")
        import traceback

        active_logger.error(traceback.format_exc())
