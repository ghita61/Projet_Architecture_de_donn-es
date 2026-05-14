from typing import Optional

from bs4 import BeautifulSoup

from base_scraper import BaseScraper


class BBCScraper(BaseScraper):

    def __init__(self):
        super().__init__(
            source_name="bbc",
            base_url="https://www.bbc.com",
            rate_limit_seconds=2.5,  # BBC is stricter with rate limits
        )

    def get_article_urls(self) -> list[str]:

        urls = []
        news_url = f"{self.base_url}/news"
        html = self._fetch_with_retries(news_url)

        if html is None:
            return urls

        soup = BeautifulSoup(html, "lxml")
        article_links = soup.find_all("a", href=True)

        for link in article_links:
            href = link["href"]
            absolute_url = self.make_absolute_url(href)

            # Filter: only URLs that are BBC News articles
            is_article = (
                "/news/articles/" in absolute_url
                or ("/news/" in absolute_url and absolute_url[-8:].isdigit())
            )
            # Exclude section landing pages and navigation pages
            is_not_section = (
                "/news/topics/" not in absolute_url
                and "/news/live/" not in absolute_url
                and "/news/av/" not in absolute_url
            )

            if is_article and is_not_section and absolute_url not in urls:
                urls.append(absolute_url)

        self.logger.info({"count": len(urls)}, "BBC URLs found")
        return urls[:20]  # Limit to 20 articles per run

    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:

        article = {}

        # --- Title ---
        title_tag = soup.find("h1")
        if title_tag:
            article["title"] = self.clean_text(title_tag.get_text())
        else:
            return None  # No title = not a valid article

        # --- Author ---
        # BBC places the author in a div/span with data-testid attributes
        author_tag = (
            soup.find("div", attrs={"data-testid": "byline-new-contributors"})
            or soup.find("span", class_="byline__name")
            or soup.find("p", class_="byline")
        )
        if author_tag:
            # Strip "By " prefix if present
            author_text = self.clean_text(author_tag.get_text())
            article["author"] = author_text.replace("By ", "").strip()
        else:
            article["author"] = None

        # --- Publication date ---
        time_tag = soup.find("time")
        if time_tag:
            article["published_date"] = (
                time_tag.get("datetime")
                or self.clean_text(time_tag.get_text())
            )
        else:
            article["published_date"] = None

        # --- Category ---
        # BBC stores section metadata in the navigation area
        category_tag = (
            soup.find("a", attrs={"data-testid": "undefined-section-label"})
            or soup.find("span", class_="topic-tag")
        )
        # Fallback: try Open Graph meta tags
        if not category_tag:
            og_section = soup.find("meta", property="article:section")
            if og_section:
                article["category"] = og_section.get("content")
            else:
                article["category"] = None
        else:
            article["category"] = self.clean_text(category_tag.get_text())

        # --- Article content ---
        # BBC uses text blocks tagged with data-component="text-block"
        text_blocks = soup.find_all(
            "div", attrs={"data-component": "text-block"}
        )

        if text_blocks:
            paragraphs = []
            for block in text_blocks:
                for p in block.find_all("p"):
                    text = self.clean_text(p.get_text())
                    if text:
                        paragraphs.append(text)
            article["content"] = "\n".join(paragraphs)
        else:
            # Fallback: search inside a generic article tag
            article_tag = soup.find("article")
            if article_tag:
                for tag in article_tag.find_all(["script", "style", "aside", "nav"]):
                    tag.decompose()
                paragraphs = [
                    self.clean_text(p.get_text())
                    for p in article_tag.find_all("p")
                    if p.get_text().strip()
                ]
                article["content"] = "\n".join(paragraphs)
            else:
                article["content"] = ""

        return article
