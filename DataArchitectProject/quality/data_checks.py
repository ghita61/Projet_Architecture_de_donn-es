import re
import logging
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger("data_checks")


class DataQualityChecker:

    # Minimum character threshold for valid content
    MIN_CONTENT_LENGTH = 100

    def check_article(self, article: dict) -> dict:

        issues = []
        issues.extend(self._check_completeness(article))
        issues.extend(self._check_coherence(article))
        issues.extend(self._check_validity(article))

        # Score: 100 minus a penalty for each issue found
        penalty_per_issue = 15
        score = max(0, 100 - len(issues) * penalty_per_issue)

        return {
            "url": article.get("url", "unknown"),
            "source": article.get("source", "unknown"),
            "quality_score": score,
            "issues": issues,
            "is_valid": len(issues) == 0,
        }

    def check_batch(self, articles: list[dict]) -> dict:

        reports = [self.check_article(a) for a in articles]

        valid_count = sum(1 for r in reports if r["is_valid"])
        total = len(reports)
        avg_score = sum(r["quality_score"] for r in reports) / total if total else 0

        # Group issues by type
        issue_counts = {}
        for report in reports:
            for issue in report["issues"]:
                issue_type = issue["type"]
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        summary = {
            "total_articles": total,
            "valid_articles": valid_count,
            "invalid_articles": total - valid_count,
            "average_quality_score": round(avg_score, 1),
            "issue_breakdown": issue_counts,
            "quarantine_candidates": [
                r["url"] for r in reports if r["quality_score"] < 40
            ],
        }

        logger.info(
            {"valid": valid_count, "total": total, "avg_score": avg_score},
            "Quality check completed"
        )
        return summary

    # --- Completeness ---

    def _check_completeness(self, article: dict) -> list[dict]:
        issues = []
        if not article.get("title"):
            issues.append({"type": "missing_title", "dimension": "completeness",
                           "message": "Article has no title"})
        if not article.get("published_date"):
            issues.append({"type": "missing_date", "dimension": "completeness",
                           "message": "Publication date is missing"})
        if not article.get("content"):
            issues.append({"type": "missing_content", "dimension": "completeness",
                           "message": "Content is empty"})
        return issues

    # --- Coherence ---

    def _check_coherence(self, article: dict) -> list[dict]:
        issues = []
        date_str = article.get("published_date", "")
        if date_str:
            try:
                pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if pub_date > datetime.now(pub_date.tzinfo):
                    issues.append({"type": "future_date", "dimension": "coherence",
                                   "message": "Publication date is in the future"})
            except (ValueError, TypeError):
                issues.append({"type": "invalid_date_format", "dimension": "coherence",
                               "message": "Invalid date format"})
        return issues

    # --- Validity ---

    def _check_validity(self, article: dict) -> list[dict]:
        issues = []
        content = article.get("content", "")
        if content and len(content) < self.MIN_CONTENT_LENGTH:
            issues.append({"type": "short_content", "dimension": "validity",
                           "message": f"Content < {self.MIN_CONTENT_LENGTH} characters"})
        url = article.get("url", "")
        if url:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                issues.append({"type": "invalid_url", "dimension": "validity",
                               "message": "URL has an invalid format"})
        return issues
