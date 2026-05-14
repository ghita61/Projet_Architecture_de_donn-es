from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class CNNScraper(BaseScraper):

    def __init__(self):
        super().__init__(
            source_name="cnn",
            base_url="https://edition.cnn.com",
            rate_limit_seconds=2.5,
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        html = self._fetch_with_retries(self.base_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            absolute_url = self.make_absolute_url(href)

            # CNN article URLs always contain a date and end with index.html
            is_article = (
                "cnn.com/" in absolute_url
                and "/index.html" in absolute_url
                and "/video/" not in absolute_url
                and "/gallery/" not in absolute_url
                and "/live-news/" not in absolute_url
            )

            if is_article and absolute_url not in urls:
                urls.append(absolute_url)

        self.logger.info({"count": len(urls)}, "CNN URLs found")
        return urls[:20]

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:
        """Extracts data from a CNN article."""
        article = {}

        # --- Title ---
        title_tag = (
            soup.find("h1", class_="headline__text")
            or soup.find("h1", id="maincontent")
            or soup.find("h1")
        )
        if not title_tag:
            return None
        article["title"] = self.clean_text(title_tag.get_text())

        # --- Author ---
        author_tag = (
            soup.find("span", class_="byline__name")
            or soup.find("div", class_="byline__names")
        )
        if author_tag:
            text = self.clean_text(author_tag.get_text())
            # CNN uses "By Name, CNN" format — strip the suffix
            article["author"] = text.replace("By ", "").split(",")[0].strip()
        else:
            article["author"] = None

        # --- Date ---
        date_tag = (
            soup.find("div", class_="timestamp")
            or soup.find("time")
        )
        if date_tag:
            article["published_date"] = (
                date_tag.get("datetime")
                or self.clean_text(date_tag.get_text())
            )
        else:
            article["published_date"] = None

        # --- Category ---
        # CNN stores the section in the breadcrumb or Open Graph metadata
        og_section = soup.find("meta", property="article:section")
        if og_section:
            article["category"] = og_section.get("content")
        else:
            section_tag = soup.find("a", class_="header__link")
            article["category"] = (
                self.clean_text(section_tag.get_text()) if section_tag else None
            )

        # --- Content ---
        content_div = (
            soup.find("div", class_="article__content")
            or soup.find("section", id="body-text")
            or soup.find("article")
        )
        if content_div:
            for tag in content_div.find_all(["script", "style", "aside", "figure"]):
                tag.decompose()
            paragraphs = [
                self.clean_text(p.get_text())
                for p in content_div.find_all("p")
                if p.get_text().strip() and len(p.get_text().strip()) > 20
            ]
            article["content"] = "\n".join(paragraphs)
        else:
            article["content"] = ""

        return article
