import json
import subprocess
from datetime import datetime
from typing import Final

from services.graduate_student_briefing_service import GraduateStudentBriefingService


RunnerType = object


class OpenClawNotifier:
    binary_path: Final[str]
    session_key: Final[str]
    timeout_seconds: Final[int]
    enable_graduate_student_briefing: Final[bool]

    def __init__(
        self,
        binary_path: str,
        session_key: str,
        timeout_seconds: int,
        enable_graduate_student_briefing: bool = False,
        runner=subprocess.run,
    ):
        self.binary_path = binary_path
        self.session_key = session_key
        self.timeout_seconds = timeout_seconds
        self.enable_graduate_student_briefing = enable_graduate_student_briefing
        self.runner = runner
        self.briefing_service = GraduateStudentBriefingService() if enable_graduate_student_briefing else None

    def build_session_lookup_command(self) -> list[str]:
        return [self.binary_path, "sessions", "--json"]

    def build_send_command(self, content: str, session_id: str) -> list[str]:
        return [
            self.binary_path,
            "agent",
            "--session-id",
            session_id,
            "--message",
            content,
            "--timeout",
            str(self.timeout_seconds),
        ]

    def _run_command(self, command: list[str]):
        return self.runner(
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )

    def resolve_session_id(self) -> str | None:
        result = self._run_command(self.build_session_lookup_command())
        if getattr(result, "returncode", 1) != 0:
            return None

        try:
            payload = json.loads(getattr(result, "stdout", "") or "{}")
        except json.JSONDecodeError:
            return None

        sessions = payload.get("sessions", [])
        if not isinstance(sessions, list):
            return None

        exact_matches: list[str] = []
        alias_matches: list[str] = []
        for session in sessions:
            if not isinstance(session, dict):
                continue

            session_id = session.get("sessionId")
            session_key = session.get("key")
            if not isinstance(session_id, str) or not session_id:
                continue

            if session_id == self.session_key or session_key == self.session_key:
                exact_matches.append(session_id)
                continue

            if (
                isinstance(session_key, str)
                and ":" not in self.session_key
                and session_key.endswith(f":{self.session_key}")
            ):
                alias_matches.append(session_id)

        if exact_matches:
            return exact_matches[0]
        if alias_matches:
            return alias_matches[0]
        return None

    def render_digest(self, papers: list[dict[str, object]]) -> str:
        if not self.enable_graduate_student_briefing:
            return self._render_standard_digest(papers)

        assert self.briefing_service is not None
        enriched_papers = self.briefing_service.enrich_papers(papers)
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"# 📚 Graduate Student Briefing | {today}", "", "---", ""]
        for index, paper in enumerate(enriched_papers, start=1):
            title = str(paper.get("TitleCN") or paper.get("Title") or "未命名论文")
            title_en = str(paper.get("Title") or title)
            stars = paper.get("Stars", 0)
            reason = str(paper.get("RelevanceReason") or "暂无推荐理由")
            help_text = str(paper.get("PotentialHelp") or "暂无帮助说明")
            author = str(paper.get("Author") or "未知作者")
            affiliation = str(
                paper.get("BriefingInstitutions") or paper.get("Affiliation") or "未知单位"
            )
            abstract_cn = str(paper.get("AbstractCN") or paper.get("Abstract") or "暂无摘要")
            contribution_points = self._normalize_points(
                paper.get("BriefingContributionPoints"),
                "暂无核心贡献总结",
            )
            conclusion_points = self._normalize_points(
                paper.get("BriefingConclusionPoints"),
                "暂无主要结论总结",
            )
            experiment_points = self._normalize_points(
                paper.get("BriefingExperimentPoints"),
                "暂无实验结果总结",
            )
            importance = str(paper.get("BriefingImportance") or help_text)

            lines.extend(
                [
                    f"## {index}. {title}",
                    "",
                    f"**标题:** {title_en}",
                    f"**作者:** {author}",
                    f"**机构:** {affiliation}",
                    "",
                    f"**📊 相关度评分**: {stars}分/100",
                    "",
                    f"**💡 推荐理由**: {reason}",
                    "",
                    f"**🎯 对我的帮助**: {help_text}",
                    "",
                    "### 摘要",
                    "",
                    abstract_cn,
                    "",
                    "### 核心贡献",
                ]
            )
            lines.extend(
                [f"{point_index}. {point}" for point_index, point in enumerate(contribution_points, start=1)]
            )
            lines.extend(["", "### 主要结论"])
            lines.extend(
                [f"{point_index}. {point}" for point_index, point in enumerate(conclusion_points, start=1)]
            )
            lines.extend(["", "### 实验结果"])
            lines.extend([f"- {point}" for point in experiment_points])
            lines.extend(["", "### Graduate Student 笔记", "", f"- 重要性: {importance}"])
            if paper.get("Link"):
                lines.extend([f"- arXiv: {paper['Link']}"])
            lines.extend(["", "---", ""])
        return "\n".join(lines)

    def _render_standard_digest(self, papers: list[dict[str, object]]) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"# 📚 今日arXiv论文推送 - {today}", ""]
        for index, paper in enumerate(papers, start=1):
            title = paper.get("TitleCN") or paper.get("Title") or "未命名论文"
            stars = paper.get("Stars", 0)
            reason = paper.get("RelevanceReason") or "暂无推荐理由"
            help_text = paper.get("PotentialHelp") or "暂无帮助说明"
            author = paper.get("Author") or "未知作者"
            affiliation = paper.get("Affiliation") or "未知单位"
            abstract_cn = paper.get("AbstractCN") or paper.get("Abstract") or "暂无摘要"

            lines.extend(
                [
                    f"## {index}. {title}",
                    "",
                    f"**📊 相关度评分**: {stars}分/100",
                    "",
                    f"**💡 推荐理由**: {reason}",
                    "",
                    f"**🎯 对我的帮助**: {help_text}",
                    "",
                    f"**👥 作者**: {author}",
                    "",
                    f"**🏛️ 单位**: {affiliation}",
                    "",
                    f"**📝 摘要**: {abstract_cn}",
                ]
            )
            if paper.get("Link"):
                lines.extend(["", f"**🔗 链接**: {paper['Link']}"])
            lines.extend(["", "---", ""])
        return "\n".join(lines)

    def _normalize_points(self, value: object, fallback: str) -> list[str]:
        if isinstance(value, list):
            normalized = [str(item).strip() for item in value if str(item).strip()]
            if normalized:
                return normalized
        return [fallback]

    def send_papers(self, papers: list[dict[str, object]]) -> bool:
        content = self.render_digest(papers)
        session_id = self.resolve_session_id()
        if not session_id:
            return False

        command = self.build_send_command(content, session_id)
        result = self._run_command(command)
        return getattr(result, "returncode", 1) == 0
