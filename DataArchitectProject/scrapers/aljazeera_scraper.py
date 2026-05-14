from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class AlJazeeraScraper(BaseScraper):

    def __init__(self):
        super().__init__(
            source_name="aljazeera",
            base_url="https://www.aljazeera.com",
            rate_limit_seconds=2.5,
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        news_url = f"{self.base_url}/news"
        html = self._fetch_with_retries(news_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            absolute_url = self.make_absolute_url(href)

            # Filter articles: contain /news/ followed by a date segment
            is_article = (
                "/news/" in absolute_url
                and absolute_url.count("/") >= 5
                and "/news/liveblog/" not in absolute_url
                and "/news/longform/" not in absolute_url
                and absolute_url != f"{self.base_url}/news"
            )

            if is_article and absolute_url not in urls:
                urls.append(absolute_url)

        self.logger.info({"count": len(urls)}, "Al Jazeera URLs found")
        return urls[:20]

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:
        article = {}

        # --- Title ---
        title_tag = (
            soup.find("h1", class_="article-header") or soup.find("h1")
        )
        if not title_tag:
            return None
        article["title"] = self.clean_text(title_tag.get_text())

        # --- Author ---
        author_tag = (
            soup.find("div", class_="article-author-name")
            or soup.find("a", class_="author-link")
            or soup.find("span", class_="author")
        )
        if author_tag:
            text = self.clean_text(author_tag.get_text())
            article["author"] = text.replace("By ", "").strip()
        else:
            article["author"] = None

        # --- Date ---
        date_tag = (
            soup.find("time")
            or soup.find("span", class_="date-simple")
        )
        article["published_date"] = (
            date_tag.get("datetime") or self.clean_text(date_tag.get_text())
            if date_tag else None
        )

        # --- Category ---
        # Al Jazeera places the section in the breadcrumb or Open Graph metadata
        og_section = soup.find("meta", property="article:section")
        if og_section:
            article["category"] = og_section.get("content")
        else:
            tag_link = soup.find("a", class_="article-heading-tag")
            article["category"] = (
                self.clean_text(tag_link.get_text()) if tag_link else "News"
            )

        # --- Content ---
        content_div = (
            soup.find("div", class_="wysiwyg")
            or soup.find("div", class_="article-p-wrapper")
            or soup.find("main")
        )
        if content_div:
            for tag in content_div.find_all(["script", "style", "iframe", "figure"]):
                tag.decompose()
            paragraphs = [
                self.clean_text(p.get_text())
                for p in content_div.find_all("p")
                if p.get_text().strip()
            ]
            article["content"] = "\n".join(paragraphs)
        else:
            article["content"] = ""

        return article
