from app.services.news.base import NewsArticleData, NewsProvider
from app.services.news.marketaux import MarketauxNewsProvider
from app.services.news.service import (
    compute_article_relevance,
    get_or_fetch_relevant_news,
    persist_articles_idempotently,
)

__all__ = [
    'NewsArticleData',
    'NewsProvider',
    'MarketauxNewsProvider',
    'compute_article_relevance',
    'get_or_fetch_relevant_news',
    'persist_articles_idempotently',
]
