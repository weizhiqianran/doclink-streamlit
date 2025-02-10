import logging
import validators

from requests_html import HTMLSession
from urllib.parse import urlparse
from ratelimit import limits, sleep_and_retry
from bs4 import BeautifulSoup
from typing import Optional, Tuple


class Webscraper:
    def __init__(self):
        self.session = HTMLSession()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.unwanted_tags = [
            "nav",
            "header",
            "footer",
            "aside",
            "script",
            "style",
            "noscript",
            "iframe",
            "advertisement",
            "banner",
            "cookie-banner",
            "social-media",
            "comments",
            '[class*="ad-"]',
            '[class*="advertisement"]',
            '[class*="banner"]',
            '[class*="social"]',
            '[class*="footer"]',
            '[class*="header-nav"]',
            '[class*="cookie"]',
            '[class*="popup"]',
            '[class*="modal"]',
            '[class*="newsletter"]',
        ]

    @sleep_and_retry
    @limits(calls=30, period=60)
    def request_creator(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.html.html
        except Exception as e:
            self.logger.error(f"Error making request to {url}: {e}")
            return None

    def url_validator(self, url: str) -> bool:
        try:
            if not validators.url(url):
                return False

            parsed = urlparse(url)

            return parsed.scheme in ["https", "http"]
        except Exception as e:
            self.logger.error(f"URL validation error: {str(e)}")
            return False

    def html_parser(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "html.parser")

            for selector in self.unwanted_tags:
                for element in soup.select(selector):
                    element.decompose()

            main_content = None
            main_tags = ["article", "main", "div"]

            for tag in main_tags:
                if tag == "div":
                    for element in soup.find_all(tag, class_=True):
                        class_name = str(element.get("class", ""))
                        if any(
                            pattern in class_name.lower()
                            for pattern in ["content", "article", "post", "entry"]
                        ):
                            main_content = element
                            break
                else:
                    main_content = soup.find(tag)

                if main_content:
                    break
            if not main_content:
                main_content = soup.body

            return str(main_content) if main_content else str(soup)

        except Exception as e:
            self.logger.error(f"Error cleaning HTML: {str(e)}")
            return html

    def scraper(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.url_validator(url):
            return None, "Invalid Format"

        html = self.request_creator(url)
        if not html:
            return None, "Failed to fetch URL"

        try:
            parsed_html = self.html_parser(html=html)
            return parsed_html, None
        except Exception as e:
            self.logger.error(f"Error processing URL {url}: {str(e)}")
            return None, f"Error processing URL {str(e)}"
