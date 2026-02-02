#!/usr/bin/env python3
"""
News Fetcher Module
Fetches financial news from various sources for sentiment analysis
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Represents a single news article"""
    headline: str
    source: str
    timestamp: datetime
    url: str = ""
    summary: str = ""
    symbols: List[str] = field(default_factory=list)
    sentiment: Optional[str] = None  # bullish, bearish, neutral
    sentiment_score: float = 0.0  # -1 to 1
    impact: str = "medium"  # low, medium, high

    def to_dict(self) -> Dict:
        return {
            'headline': self.headline,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'url': self.url,
            'summary': self.summary,
            'symbols': self.symbols,
            'sentiment': self.sentiment,
            'sentiment_score': self.sentiment_score,
            'impact': self.impact
        }


class NewsFetcher:
    """
    Fetches financial news from multiple sources

    Supported sources:
    - NewsAPI (newsapi.org)
    - Alpha Vantage News
    - Finnhub
    - RSS Feeds (Reuters, Bloomberg, etc.)
    """

    def __init__(self):
        self.newsapi_key = os.getenv('NEWSAPI_KEY', '')
        self.alphavantage_key = os.getenv('ALPHAVANTAGE_KEY', '')
        self.finnhub_key = os.getenv('FINNHUB_KEY', '')

        self.cache = {}
        self.cache_duration = timedelta(minutes=5)

        # Keywords for futures trading
        self.keywords = [
            'futures', 'S&P 500', 'ES futures', 'Nasdaq', 'NQ futures',
            'Fed', 'Federal Reserve', 'interest rate', 'inflation',
            'CPI', 'jobs report', 'unemployment', 'GDP',
            'treasury', 'bonds', 'yields', 'economic',
            'stock market', 'equity', 'trading'
        ]

        # High impact keywords
        self.high_impact_keywords = [
            'fed', 'fomc', 'rate decision', 'emergency',
            'crash', 'surge', 'plunge', 'crisis', 'war',
            'cpi', 'inflation', 'jobs report', 'gdp'
        ]

    def fetch_all(self, limit: int = 20) -> List[NewsArticle]:
        """Fetch news from all available sources"""
        all_news = []

        # Try each source
        if self.newsapi_key:
            all_news.extend(self.fetch_from_newsapi(limit))

        if self.alphavantage_key:
            all_news.extend(self.fetch_from_alphavantage(limit))

        if self.finnhub_key:
            all_news.extend(self.fetch_from_finnhub(limit))

        # Always try free RSS feeds
        all_news.extend(self.fetch_from_rss(limit))

        # Remove duplicates based on headline similarity
        unique_news = self._deduplicate(all_news)

        # Sort by timestamp (newest first)
        unique_news.sort(key=lambda x: x.timestamp, reverse=True)

        return unique_news[:limit]

    def fetch_from_newsapi(self, limit: int = 10) -> List[NewsArticle]:
        """Fetch from NewsAPI.org"""
        if not self.newsapi_key:
            return []

        cache_key = f"newsapi_{limit}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data

        articles = []
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'apiKey': self.newsapi_key,
                'q': 'futures OR "S&P 500" OR "stock market" OR "Federal Reserve"',
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': limit
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data.get('articles', []):
                article = NewsArticle(
                    headline=item.get('title', ''),
                    source=item.get('source', {}).get('name', 'NewsAPI'),
                    timestamp=datetime.fromisoformat(
                        item.get('publishedAt', '').replace('Z', '+00:00')
                    ),
                    url=item.get('url', ''),
                    summary=item.get('description', ''),
                    impact=self._determine_impact(item.get('title', ''))
                )
                articles.append(article)

            self.cache[cache_key] = (datetime.now(), articles)

        except Exception as e:
            logger.error(f"NewsAPI fetch error: {e}")

        return articles

    def fetch_from_alphavantage(self, limit: int = 10) -> List[NewsArticle]:
        """Fetch from Alpha Vantage News Sentiment API"""
        if not self.alphavantage_key:
            return []

        cache_key = f"alphavantage_{limit}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data

        articles = []
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'SPY,QQQ',
                'apikey': self.alphavantage_key,
                'limit': limit
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data.get('feed', []):
                # Alpha Vantage provides sentiment scores
                sentiment_score = float(item.get('overall_sentiment_score', 0))

                article = NewsArticle(
                    headline=item.get('title', ''),
                    source=item.get('source', 'Alpha Vantage'),
                    timestamp=datetime.strptime(
                        item.get('time_published', '')[:15],
                        '%Y%m%dT%H%M%S'
                    ) if item.get('time_published') else datetime.now(),
                    url=item.get('url', ''),
                    summary=item.get('summary', ''),
                    symbols=[t.get('ticker', '') for t in item.get('ticker_sentiment', [])],
                    sentiment_score=sentiment_score,
                    sentiment=self._score_to_sentiment(sentiment_score),
                    impact=self._determine_impact(item.get('title', ''))
                )
                articles.append(article)

            self.cache[cache_key] = (datetime.now(), articles)

        except Exception as e:
            logger.error(f"Alpha Vantage fetch error: {e}")

        return articles

    def fetch_from_finnhub(self, limit: int = 10) -> List[NewsArticle]:
        """Fetch from Finnhub"""
        if not self.finnhub_key:
            return []

        cache_key = f"finnhub_{limit}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data

        articles = []
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {
                'category': 'general',
                'token': self.finnhub_key
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data[:limit]:
                article = NewsArticle(
                    headline=item.get('headline', ''),
                    source=item.get('source', 'Finnhub'),
                    timestamp=datetime.fromtimestamp(item.get('datetime', 0)),
                    url=item.get('url', ''),
                    summary=item.get('summary', ''),
                    impact=self._determine_impact(item.get('headline', ''))
                )
                articles.append(article)

            self.cache[cache_key] = (datetime.now(), articles)

        except Exception as e:
            logger.error(f"Finnhub fetch error: {e}")

        return articles

    def fetch_from_rss(self, limit: int = 10) -> List[NewsArticle]:
        """Fetch from free RSS feeds"""
        import xml.etree.ElementTree as ET

        cache_key = f"rss_{limit}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_data

        rss_feeds = [
            ('https://feeds.finance.yahoo.com/rss/2.0/headline?s=ES=F&region=US&lang=en-US', 'Yahoo Finance'),
            ('https://www.investing.com/rss/news.rss', 'Investing.com'),
        ]

        articles = []

        for feed_url, source_name in rss_feeds:
            try:
                response = requests.get(feed_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                })

                if response.status_code == 200:
                    root = ET.fromstring(response.content)

                    for item in root.findall('.//item')[:limit // len(rss_feeds)]:
                        title = item.find('title')
                        pub_date = item.find('pubDate')
                        link = item.find('link')
                        description = item.find('description')

                        if title is not None:
                            # Parse date
                            try:
                                timestamp = datetime.strptime(
                                    pub_date.text[:25] if pub_date is not None else '',
                                    '%a, %d %b %Y %H:%M:%S'
                                )
                            except:
                                timestamp = datetime.now()

                            article = NewsArticle(
                                headline=title.text or '',
                                source=source_name,
                                timestamp=timestamp,
                                url=link.text if link is not None else '',
                                summary=description.text if description is not None else '',
                                impact=self._determine_impact(title.text or '')
                            )
                            articles.append(article)

            except Exception as e:
                logger.warning(f"RSS feed error ({source_name}): {e}")

        self.cache[cache_key] = (datetime.now(), articles)
        return articles

    def _determine_impact(self, headline: str) -> str:
        """Determine news impact level based on headline"""
        headline_lower = headline.lower()

        for keyword in self.high_impact_keywords:
            if keyword in headline_lower:
                return 'high'

        # Medium impact for market-moving terms
        medium_keywords = ['earnings', 'profit', 'revenue', 'forecast', 'outlook']
        for keyword in medium_keywords:
            if keyword in headline_lower:
                return 'medium'

        return 'low'

    def _score_to_sentiment(self, score: float) -> str:
        """Convert numeric score to sentiment label"""
        if score > 0.2:
            return 'bullish'
        elif score < -0.2:
            return 'bearish'
        return 'neutral'

    def _deduplicate(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles based on headline similarity"""
        seen_headlines = set()
        unique = []

        for article in articles:
            # Normalize headline for comparison
            normalized = article.headline.lower()[:50]
            if normalized not in seen_headlines:
                seen_headlines.add(normalized)
                unique.append(article)

        return unique

    def get_market_summary(self) -> Dict:
        """Get a summary of market news sentiment"""
        articles = self.fetch_all(limit=20)

        if not articles:
            return {
                'article_count': 0,
                'avg_sentiment': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'high_impact_count': 0
            }

        sentiments = [a.sentiment_score for a in articles if a.sentiment_score != 0]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        return {
            'article_count': len(articles),
            'avg_sentiment': avg_sentiment,
            'bullish_count': sum(1 for a in articles if a.sentiment == 'bullish'),
            'bearish_count': sum(1 for a in articles if a.sentiment == 'bearish'),
            'neutral_count': sum(1 for a in articles if a.sentiment == 'neutral'),
            'high_impact_count': sum(1 for a in articles if a.impact == 'high')
        }
