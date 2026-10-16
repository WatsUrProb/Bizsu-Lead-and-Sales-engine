"""Bounded, staff-triggered lookup of public business email addresses."""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
USER_AGENT = "BizsuResearchPreview/1.0 (staff-triggered public contact lookup)"
MAX_PAGES = 4
MAX_BYTES = 350_000


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.fullmatch(value.strip())) and len(value) <= 254


def contact_type(address: str) -> str:
    local = address.split("@", 1)[0].lower()
    if any(word in local for word in ("sales", "business", "partnership")):
        return "sales"
    if any(word in local for word in ("info", "contact", "enquir", "inquir", "hello", "admin")):
        return "general"
    return "other"


def _public_host(host: str) -> bool:
    if not host or host in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


def _same_site(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").removeprefix("www.").lower() == host.removeprefix("www.").lower()


class ContactPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.mailtos: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        if href.lower().startswith("mailto:"):
            self.mailtos.append(unquote(href[7:].split("?", 1)[0]))
        elif href:
            self.links.append(href)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _read_page(client: httpx.Client, url: str) -> str | None:
    with client.stream("GET", url, follow_redirects=False) as response:
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", "").lower():
            return None
        chunks = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > MAX_BYTES:
                return None
            chunks.append(chunk)
        encoding = response.encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")


def discover_public_emails(website: str, source: str) -> list[dict]:
    """Read at most four same-host public pages; never follow redirects or guess addresses."""
    origin = urlparse(website)
    host = origin.hostname or ""
    if origin.scheme not in {"http", "https"} or not _public_host(host):
        return []
    base = f"{origin.scheme}://{origin.netloc}"
    pages = [website]
    if _same_site(source, host) and source != website:
        pages.append(source)
    pages.extend(urljoin(base, path) for path in ("/contact", "/contact-us", "/about"))
    found: dict[str, dict] = {}
    visited: set[str] = set()
    try:
        with httpx.Client(timeout=5.0, headers={"User-Agent": USER_AGENT}, trust_env=False) as client:
            robots_response = client.get(urljoin(base, "/robots.txt"), follow_redirects=False)
            if robots_response.status_code == 200:
                robots = RobotFileParser()
                robots.parse(robots_response.text.splitlines())
            elif robots_response.status_code == 404:
                robots = None
            else:
                return []
            while pages and len(visited) < MAX_PAGES:
                page_url = pages.pop(0)
                if page_url in visited or not _same_site(page_url, host):
                    continue
                visited.add(page_url)
                if robots and not robots.can_fetch(USER_AGENT, page_url):
                    continue
                try:
                    page = _read_page(client, page_url)
                except httpx.HTTPError:
                    continue
                if not page:
                    continue
                parser = ContactPage()
                parser.feed(page)
                visible_text = html.unescape(" ".join(parser.text))
                for address in EMAIL_RE.findall(" ".join(parser.mailtos) + " " + visible_text):
                    address = address.lower()
                    if not valid_email(address) or address.split("@", 1)[0] in {"noreply", "no-reply"}:
                        continue
                    position = visible_text.lower().find(address)
                    snippet = visible_text[max(0, position - 55):position + len(address) + 55].strip() if position >= 0 else "Public mailto link"
                    found[address] = {"email_address": address, "source_url": page_url,
                                      "contact_type": contact_type(address),
                                      "verification_status": "source-confirmed", "evidence_snippet": snippet[:180]}
                for link in parser.links:
                    linked = urljoin(page_url, link)
                    if _same_site(linked, host) and re.search(r"contact|about", urlparse(linked).path, re.I):
                        pages.append(linked)
    except httpx.HTTPError:
        return []
    return sorted(found.values(), key=lambda item: (item["contact_type"] not in {"general", "sales"}, item["email_address"]))
