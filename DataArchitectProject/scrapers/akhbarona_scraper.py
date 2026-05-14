from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class AkhbaronaScraper(BaseScraper):


    def __init__(self):
        super().__init__(
            source_name="akhbarona",
            base_url="https://www.akhbarona.com",
            rate_limit_seconds=2.0,
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        html = self._fetch_with_retries(self.base_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")
        article_links = soup.find_all("a", href=True)

        for link in article_links:
            href = link["href"]
            absolute_url = self.make_absolute_url(href)

            is_article = (
                "akhbarona.com" in absolute_url
                and any(char.isdigit() for char in absolute_url.split("/")[-1])
                and len(absolute_url) > 35
                and "/category/" not in absolute_url
                and "/tag/" not in absolute_url
                and "/page/" not in absolute_url
                and "/author/" not in absolute_url
            )

            if is_article and absolute_url not in urls:
                urls.append(absolute_url)

        self.logger.info({"count": len(urls)}, "Akhbarona URLs found")
        return urls[:20]

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:
        """Extracts data from an Akhbarona article."""
        article = {}

        # --- Title ---
        title_tag = soup.find("h1", class_="post-title") or soup.find("h1")
        if not title_tag:
            return None
        article["title"] = self.clean_text(title_tag.get_text())

        # --- Author ---
        author_tag = (
            soup.find("span", class_="author")
            or soup.find("a", rel="author")
        )
        article["author"] = (
            self.clean_text(author_tag.get_text()) if author_tag else None
        )

        # --- Date ---
        date_tag = soup.find("time") or soup.find("span", class_="date")
        article["published_date"] = (
            date_tag.get("datetime") or self.clean_text(date_tag.get_text())
            if date_tag else None
        )

        # --- Category ---
        cat_tag = soup.find("span", class_="category") or soup.find("a", class_="cat")
        if not cat_tag:
            breadcrumb = soup.find("div", class_="breadcrumb")
            if breadcrumb:
                crumbs = breadcrumb.find_all("a")
                cat_tag = crumbs[-1] if len(crumbs) >= 2 else None
        article["category"] = (
            self.clean_text(cat_tag.get_text()) if cat_tag else None
        )

        # --- Content ---
        content_div = (
            soup.find("div", class_="entry-content")
            or soup.find("div", class_="post-content")
            or soup.find("article")
        )
        if content_div:
            for tag in content_div.find_all(["script", "style", "iframe", "aside"]):
                tag.decompose()
            paragraphs = content_div.find_all("p")
            article["content"] = "\n".join(
                self.clean_text(p.get_text()) for p in paragraphs if p.get_text().strip()
            )
        else:
            article["content"] = ""

        return article
