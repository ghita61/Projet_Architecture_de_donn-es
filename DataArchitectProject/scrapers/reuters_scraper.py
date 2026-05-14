
from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class ReutersScraper(BaseScraper):


    def __init__(self):
        super().__init__(
            source_name="reuters",
            base_url="https://www.reuters.com",
            rate_limit_seconds=3.0,  # Reuters enforces strict rate limits
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        world_url = f"{self.base_url}/world/"
        html = self._fetch_with_retries(world_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            absolute_url = self.make_absolute_url(href)

            # Reuters article URLs follow a section/slug pattern
            is_article = (
                "reuters.com/" in absolute_url
                and any(
                    section in absolute_url
                    for section in ["/world/", "/business/", "/markets/", "/technology/"]
                )
                and absolute_url.count("/") >= 4
                and not absolute_url.endswith("/world/")
                and not absolute_url.endswith("/business/")
                and "/video/" not in absolute_url
            )

            if is_article and absolute_url not in urls:
                urls.append(absolute_url)

        self.logger.info({"count": len(urls)}, "Reuters URLs found")
        return urls[:20]

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:
        """Extracts data from a Reuters article."""
        article = {}

        # --- Title ---
        title_tag = (
            soup.find("h1", attrs={"data-testid": "Heading"})
            or soup.find("h1")
        )
        if not title_tag:
            return None
        article["title"] = self.clean_text(title_tag.get_text())

        # --- Author ---
        author_tag = (
            soup.find("a", attrs={"data-testid": "AuthorName"})
            or soup.find("span", class_="byline__author")
        )
        if author_tag:
            text = self.clean_text(author_tag.get_text())
            article["author"] = text.replace("By ", "").strip()
        else:
            article["author"] = None

        # --- Date ---
        time_tag = (
            soup.find("time", attrs={"data-testid": "DatePublished"})
            or soup.find("time")
        )
        article["published_date"] = (
            time_tag.get("datetime") or self.clean_text(time_tag.get_text())
            if time_tag else None
        )

        # --- Category ---
        og_section = soup.find("meta", property="article:section")
        if og_section:
            article["category"] = og_section.get("content")
        else:
            # Reuters breadcrumbs contain the section name
            breadcrumb = soup.find("nav", attrs={"aria-label": "Breadcrumb"})
            if breadcrumb:
                crumbs = breadcrumb.find_all("a")
                article["category"] = (
                    self.clean_text(crumbs[-1].get_text()) if crumbs else None
                )
            else:
                article["category"] = None

        # --- Content ---
        # Reuters uses data-testid attributes to identify article paragraphs
        paragraphs_tags = soup.find_all(
            "p", attrs={"data-testid": lambda v: v and "paragraph" in v.lower()}
        ) if soup.find("p", attrs={"data-testid": True}) else []

        if paragraphs_tags:
            article["content"] = "\n".join(
                self.clean_text(p.get_text()) for p in paragraphs_tags
                if p.get_text().strip()
            )
        else:
            # Fallback: search in the generic article container
            article_body = (
                soup.find("div", class_="article-body__content")
                or soup.find("article")
            )
            if article_body:
                for tag in article_body.find_all(["script", "style", "aside"]):
                    tag.decompose()
                article["content"] = "\n".join(
                    self.clean_text(p.get_text())
                    for p in article_body.find_all("p")
                    if p.get_text().strip()
                )
            else:
                article["content"] = ""

        return article
