import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
import httpx

from app.config import settings
from app.services.news.base import NewsArticleData, NewsProvider

logger = logging.getLogger(__name__)


class MarketauxNewsProvider(NewsProvider):
    provider_name: str = 'marketaux'

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        self.api_token = api_token if api_token is not None else settings.marketaux_api_token
        self.base_url = (base_url or settings.marketaux_base_url).rstrip('/')
        self.timeout = timeout or settings.marketaux_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token and self.api_token.strip())

    async def fetch_news_for_instrument(
        self,
        symbol: str,
        company_name: str,
        published_after: datetime | None = None,
        published_before: datetime | None = None,
        limit: int = 10,
    ) -> list[NewsArticleData]:
        if not self.is_configured:
            logger.info('MarketauxNewsProvider: API token not configured; skipping external fetch.')
            return []

        endpoint = f'{self.base_url}/news/all'
        params: dict[str, Any] = {
            'api_token': self.api_token,
            'symbols': f'{symbol},{symbol}.NS',
            'language': 'en',
            'limit': min(max(limit, 1), 10),
        }
        if published_after:
            params['published_after'] = published_after.strftime('%Y-%m-%dT%H:%M:%S')
        if published_before:
            params['published_before'] = published_before.strftime('%Y-%m-%dT%H:%M:%S')

        headers = {
            'User-Agent': 'SmartMarketWatchlist/1.0',
            'Accept': 'application/json',
        }

        attempts = 0
        max_attempts = 2
        last_response: httpx.Response | None = None

        while attempts < max_attempts:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(endpoint, params=params, headers=headers)
                    last_response = resp

                if resp.status_code == 200:
                    break
                elif resp.status_code in (401, 403):
                    logger.warning('MarketauxNewsProvider: authorization failed (HTTP %s).', resp.status_code)
                    return []
                elif resp.status_code == 429:
                    logger.warning('MarketauxNewsProvider: rate limit exceeded (HTTP 429).')
                    return []
                elif resp.status_code >= 500:
                    logger.warning('MarketauxNewsProvider: server error (HTTP %s, attempt %d/%d).', resp.status_code, attempts, max_attempts)
                    if attempts < max_attempts:
                        await asyncio.sleep(0.5)
                        continue
                    return []
                else:
                    logger.warning('MarketauxNewsProvider: unexpected HTTP status %s.', resp.status_code)
                    return []
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning('MarketauxNewsProvider: network/timeout error on attempt %d/%d: %s', attempts, max_attempts, type(exc).__name__)
                if attempts < max_attempts:
                    await asyncio.sleep(0.5)
                    continue
                return []
            except Exception as exc:
                logger.error('MarketauxNewsProvider: unexpected error fetching news: %s', type(exc).__name__)
                return []

        if not last_response or last_response.status_code != 200:
            return []

        try:
            payload = last_response.json()
        except Exception:
            logger.warning('MarketauxNewsProvider: failed to parse JSON response.')
            return []

        raw_articles = payload.get('data')
        if not isinstance(raw_articles, list):
            return []

        return self.normalize_articles(raw_articles, symbol=symbol, company_name=company_name)

    def normalize_articles(
        self,
        raw_articles: list[dict[str, Any]],
        symbol: str,
        company_name: str,
    ) -> list[NewsArticleData]:
        normalized: list[NewsArticleData] = []
        sym_upper = symbol.strip().upper()
        comp_lower = company_name.strip().lower()

        for item in raw_articles:
            if not isinstance(item, dict):
                continue

            uuid = item.get('uuid')
            title = item.get('title')
            url = item.get('url')
            if not uuid or not title or not url:
                continue

            pub_raw = item.get('published_at')
            if pub_raw:
                try:
                    pub_dt = datetime.fromisoformat(str(pub_raw).replace('Z', '+00:00'))
                except Exception:
                    pub_dt = datetime.now(timezone.utc)
            else:
                pub_dt = datetime.now(timezone.utc)

            source = item.get('source') or 'Marketaux'
            summary = item.get('description') or item.get('snippet')

            entities = item.get('entities') or []
            matched_entity = None
            for ent in entities:
                ent_sym = (ent.get('symbol') or '').upper()
                ent_name = (ent.get('name') or '').lower()
                if ent_sym in (sym_upper, f'{sym_upper}.NS') or (comp_lower and comp_lower in ent_name):
                    matched_entity = ent
                    break

            match_score: float | None = None
            sentiment_score: float | None = None
            if matched_entity:
                raw_match = matched_entity.get('match_score')
                if raw_match is not None:
                    try:
                        val = float(raw_match)
                        match_score = val / 100.0 if val > 1.0 else val
                    except (ValueError, TypeError):
                        match_score = None
                raw_sentiment = matched_entity.get('sentiment_score')
                if raw_sentiment is not None:
                    try:
                        sentiment_score = float(raw_sentiment)
                    except (ValueError, TypeError):
                        sentiment_score = None

            rel_score_raw = item.get('relevance_score')
            relevance_score: float | None = None
            if rel_score_raw is not None:
                try:
                    relevance_score = float(rel_score_raw)
                except (ValueError, TypeError):
                    relevance_score = None

            normalized.append(
                NewsArticleData(
                    provider_article_id=str(uuid),
                    headline=str(title).strip(),
                    source=str(source).strip(),
                    url=str(url).strip(),
                    published_at=pub_dt,
                    summary=str(summary).strip() if summary else None,
                    relevance_score=relevance_score,
                    match_score=match_score,
                    sentiment_score=sentiment_score,
                    raw_data=item,
                )
            )

        return normalized
