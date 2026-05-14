from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class HespressScraper(BaseScraper):

    def __init__(self):
        super().__init__(
            source_name="hespress",
            base_url="https://fr.hespress.com",
            rate_limit_seconds=2.0,
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        html = self._fetch_with_retries(self.base_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")

        # Hespress uses cards with links in the news sections.
        # We look for all links that point to individual articles.
        article_links = soup.find_all("a", href=True)

        for link in article_links:
            href = link["href"]
            # Filter: only URLs that look like individual articles.
            # Hespress articles typically have a long slug in the URL.
            is_article = (
                href.startswith("https://fr.hespress.com/")
                and href != self.base_url
                and len(href) > 40
                and not href.endswith("/category/")
                and "/author/" not in href
                and "/page/" not in href
                and "/tag/" not in href
            )

            if is_article and href not in urls:
                urls.append(href)

        self.logger.info("Hespress URLs found: %d", len(urls))
        return urls[:20]  # Limit to 20 articles per run

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:

        article = {}

        # --- Title ---
        title_tag = soup.find("h1", class_="post-title") or soup.find("h1")
        if title_tag:
            article["title"] = self.clean_text(title_tag.get_text())
        else:
            return None  # No title = invalid article

        # --- Author ---
        author_tag = (
            soup.find("span", class_="author-name")
            or soup.find("a", rel="author")
            or soup.find("span", class_="post-author")
        )
        article["author"] = (
            self.clean_text(author_tag.get_text()) if author_tag else None
        )

        # --- Publication date ---
        date_tag = (
            soup.find("time")
            or soup.find("span", class_="post-date")
            or soup.find("span", class_="date")
        )
        article["published_date"] = (
            date_tag.get("datetime") or self.clean_text(date_tag.get_text())
            if date_tag
            else None
        )

        # --- Category ---
        category_tag = (
            soup.find("span", class_="category")
            or soup.find("a", class_="post-cat")
        )
        # Also try breadcrumbs as a fallback
        if not category_tag:
            breadcrumb = soup.find("nav", class_="breadcrumb")
            if breadcrumb:
                crumbs = breadcrumb.find_all("a")
                if len(crumbs) >= 2:
                    category_tag = crumbs[-1]

        article["category"] = (
            self.clean_text(category_tag.get_text()) if category_tag else None
        )

        # --- Article content ---
        content_div = (
            soup.find("div", class_="article-content")
            or soup.find("div", class_="post-content")
            or soup.find("div", class_="entry-content")
            or soup.find("article")
        )

        if content_div:
            # Remove scripts and styles from the content block
            for tag in content_div.find_all(["script", "style", "iframe", "aside"]):
                tag.decompose()

            paragraphs = content_div.find_all("p")
            content_text = "\n".join(
                self.clean_text(p.get_text()) for p in paragraphs if p.get_text().strip()
            )
            article["content"] = content_text
        else:
            article["content"] = ""

        return article
