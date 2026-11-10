from urllib.request import Request, urlopen
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def fetch_page(url: str, timeout: int = 30) -> str:
    """Download a page and return its HTML content."""
    request = Request(
        url,
        headers={"User-Agent": "AI-agents-learning/0.1"},
    )

    with urlopen(request, timeout=timeout) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(encoding)

    return html

def extract_opportunities(html: str, base_url: str) -> list[dict]:
    """Extract opportunity titles and links from a PCI listing."""
    soup = BeautifulSoup(html, "html.parser")

    opportunities = []
    seen_urls = set()

    for link in soup.select("a.noticia_desc[href]"):
        title = link.get_text(" ", strip=True)
        href = link["href"].strip()

        if not title or not href:
            continue

        url = urljoin(base_url, href)

        if url in seen_urls:
            continue

        opportunities.append({
            "title": title,
            "url": url,
        })
        seen_urls.add(url)

    return opportunities

def extract_article_text(html: str) -> str:
    """Extract the headline and main text from a PCI article."""
    soup = BeautifulSoup(html, "html.parser")

    article = soup.select_one("article#noticia")

    if article is None:
        raise ValueError("The article container was not found.")

    body = article.select_one('[itemprop="articleBody"]')

    if body is None:
        raise ValueError("The article body was not found.")

    # Remove promotional paragraphs found in the inspected page.
    for link in body.select('a[href*="/apostilas/"], a.link-podcast'):
        paragraph = link.find_parent("p")

        if paragraph is not None:
            paragraph.decompose()

    sections = []

    headline = article.select_one("h1")

    if headline is not None:
        sections.append(headline.get_text(" ", strip=True))

    for element in body.select("p, li"):
        text = element.get_text(" ", strip=True)

        if text:
            sections.append(text)

    if not sections or not body.get_text(strip=True):
        raise ValueError("The article text is empty.")

    return "\n\n".join(sections)