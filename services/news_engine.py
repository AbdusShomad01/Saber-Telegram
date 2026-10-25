"""
IDX AI Signal Bot - News Engine
Fetches and analyzes financial news for Indonesian stocks.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A single news article."""
    title: str
    source: str = ""
    url: str = ""
    published_at: Optional[datetime] = None
    sentiment: str = "neutral"  # positive, neutral, negative
    summary: str = ""
    ticker: str = ""


class NewsEngine:
    """
    Fetches financial news from Indonesian sources.
    In MVP: returns mock/placeholder news.
    In production: scrapes from Bisnis.com, CNBC Indonesia, Kontan.
    """

    # Known Indonesian financial news sources
    SOURCES = [
        {"name": "Bisnis.com", "base_url": "https://market.bisnis.com"},
        {"name": "CNBC Indonesia", "base_url": "https://www.cnbcindonesia.com"},
        {"name": "Kontan", "base_url": "https://investasi.kontan.co.id"},
        {"name": "IDX Channel", "base_url": "https://www.idxchannel.com"},
    ]

    async def fetch_news(self, ticker: str, limit: int = 5) -> List[NewsItem]:
        """
        Fetch recent news for a specific ticker.
        In production, this would scrape actual news sites.
        """
        try:
            return await self._fetch_from_api(ticker, limit)
        except Exception as e:
            logger.warning(f"News fetch failed for {ticker}: {e}")
            return self._generate_placeholder_news(ticker, limit)

    async def _fetch_from_api(self, ticker: str, limit: int) -> List[NewsItem]:
        """
        Fetch news from Google News RSS for the given ticker.
        """
        import httpx
        import xml.etree.ElementTree as ET
        from datetime import datetime
        import email.utils

        url = f"https://news.google.com/rss/search?q=saham+{ticker}&hl=id&gl=ID&ceid=ID:id"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
            root = ET.fromstring(response.text)
            items = root.findall('.//item')
            
            news_list = []
            now = datetime.now()
            
            for item in items:
                if len(news_list) >= limit:
                    break
                
                _title_el = item.find('title')
                title = (_title_el.text if _title_el is not None else None) or ""
                _link_el = item.find('link')
                link = (_link_el.text if _link_el is not None else None) or ""
                source_elem = item.find('source')
                source = (source_elem.text if source_elem is not None else None) or "Google News"
                _pubdate_el = item.find('pubDate')
                pub_date_str = (_pubdate_el.text if _pubdate_el is not None else None) or ""
                published_at = None
                if pub_date_str:
                    try:
                        parsed_tuple = email.utils.parsedate_tz(pub_date_str)
                        if parsed_tuple:
                            published_at = datetime.fromtimestamp(email.utils.mktime_tz(parsed_tuple))
                    except:
                        pass
                
                # Skip if news is older than 30 days
                if published_at:
                    try:
                        if published_at.tzinfo:
                            from datetime import timezone
                            days_old = (datetime.now(timezone.utc) - published_at).days
                        else:
                            days_old = (now - published_at).days
                            
                        if days_old > 30:
                            continue
                    except Exception:
                        pass

                # Simple keyword-based sentiment detection
                title_lower = (title or "").lower()
                positive_words = ["lonjak", "naik", "cuan", "rebound", "borong", "laba", "untung", "melesat", "menguat"]
                negative_words = ["anjlok", "turun", "rugi", "jual", "koreksi", "arb", "jeblok", "melemah"]
                
                sentiment = "neutral"
                if any(w in title_lower for w in positive_words):
                    sentiment = "positive"
                elif any(w in title_lower for w in negative_words):
                    sentiment = "negative"

                news_list.append(NewsItem(
                    title=title or "",
                    source=source or "",
                    url=link or "",
                    published_at=published_at,
                    sentiment=sentiment,
                    summary=title or "",
                    ticker=ticker
                ))
            
            if not news_list:
                return self._generate_placeholder_news(ticker, limit)
                
            return news_list
            
        except Exception as e:
            logger.error(f"Google News RSS fetch failed for {ticker}: {e}")
            return self._generate_placeholder_news(ticker, limit)

    def _generate_placeholder_news(self, ticker: str, limit: int) -> List[NewsItem]:
        """Return a notification that no recent news was found."""
        return [
            NewsItem(
                title=f"Tidak ada berita mengenai saham ini sebulan terakhir",
                source="System",
                sentiment="neutral",
                summary=f"Tidak ada berita mengenai saham {ticker} dalam 30 hari terakhir.",
                ticker=ticker
            )
        ]

    def analyze_sentiment(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """Aggregate news sentiment."""
        if not news_items:
            return {
                "news_count": 0,
                "sentiment_score": 0,
                "sentiment_label": "neutral",
                "headlines": [],
            }

        sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
        scores = [sentiment_map.get(n.sentiment, 0) for n in news_items]
        avg_score = sum(scores) / len(scores)

        if avg_score > 0.3:
            label = "positive"
        elif avg_score < -0.3:
            label = "negative"
        else:
            label = "neutral"

        return {
            "news_count": len(news_items),
            "sentiment_score": round(avg_score, 2),
            "sentiment_label": label,
            "headlines": [n.title for n in news_items[:3]],
        }
