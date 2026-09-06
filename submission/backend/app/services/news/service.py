import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument
from app.models.news_article import NewsArticle
from app.schemas.news import RelevantNewsContext, RelevantNewsItem
from app.services.news.base import NewsArticleData, NewsProvider
from app.services.news.marketaux import MarketauxNewsProvider

logger = logging.getLogger(__name__)

NEWS_WINDOW_HOURS_BEFORE = 72
NEWS_WINDOW_HOURS_AFTER = 24
MAX_ARTICLES_PER_CHANGE = 3
MIN_RELEVANCE_THRESHOLD = 0.20


def compute_article_relevance(
    headline: str,
    summary: str | None,
    published_at: datetime,
    symbol: str,
    company_name: str,
    change_time: datetime,
    baseline_time: datetime | None = None,
    provider_match_score: float | None = None,
    provider_relevance_score: float | None = None,
) -> tuple[float, str, str]:
    head_low = headline.lower()
    sum_low = (summary or '').lower()
    sym_low = symbol.lower()
    comp_low = company_name.lower()

    if provider_match_score is not None:
        match = min(1.0, max(0.0, float(provider_match_score)))
    elif sym_low in head_low or (comp_low and comp_low in head_low):
        match = 0.90
    elif sym_low in sum_low or (comp_low and comp_low in sum_low):
        match = 0.65
    else:
        comp_parts = [p for p in comp_low.split() if len(p) > 3 and p not in ('limited', 'ltd', 'india', 'the', 'industries')]
        if any(part in head_low for part in comp_parts):
            match = 0.70
        elif any(part in sum_low for part in comp_parts):
            match = 0.50
        else:
            match = 0.25

    if published_at.tzinfo is None:
        pub_dt = published_at.replace(tzinfo=timezone.utc)
    else:
        pub_dt = published_at

    if change_time.tzinfo is None:
        c_dt = change_time.replace(tzinfo=timezone.utc)
    else:
        c_dt = change_time

    b_dt = baseline_time.replace(tzinfo=timezone.utc) if (baseline_time and baseline_time.tzinfo is None) else baseline_time

    diff_seconds = abs((pub_dt - c_dt).total_seconds())
    diff_hours = diff_seconds / 3600.0

    if b_dt and b_dt <= pub_dt <= c_dt:
        temporal = 1.0
        temporal_relation = 'Published during the observation window'
    elif diff_hours <= 12:
        temporal = 0.90
        temporal_relation = 'Published within hours of the detected move'
    elif diff_hours <= 24:
        temporal = 0.80
        temporal_relation = 'Published within 24 hours of the detected move'
    elif diff_hours <= 48:
        temporal = 0.60
        temporal_relation = 'Published within 2 days of the detected move'
    elif diff_hours <= 72:
        temporal = 0.40
        temporal_relation = 'Published within 3 days of the detected move'
    else:
        temporal = max(0.0, 1.0 - (diff_hours / 120.0))
        temporal_relation = 'Published around the time of the detected move'

    if provider_relevance_score is not None:
        rel = min(1.0, max(0.0, float(provider_relevance_score)))
    else:
        rel = 0.50

    composite = (0.45 * match) + (0.35 * temporal) + (0.20 * rel)
    match_tag = 'Direct ticker match' if match >= 0.8 else 'Company match'
    relevance_summary = f'{temporal_relation} · {match_tag}'

    return composite, temporal_relation, relevance_summary


async def persist_articles_idempotently(
    db: AsyncSession,
    instrument_id: int,
    provider_name: str,
    articles_data: list[NewsArticleData],
) -> list[NewsArticle]:
    if not articles_data:
        return []

    provider_ids = [a.provider_article_id for a in articles_data]
    stmt = select(NewsArticle).where(
        NewsArticle.instrument_id == instrument_id,
        NewsArticle.provider == provider_name,
        NewsArticle.provider_article_id.in_(provider_ids),
    )
    existing_records = (await db.execute(stmt)).scalars().all()
    existing_map = {rec.provider_article_id: rec for rec in existing_records}

    persisted: list[NewsArticle] = list(existing_records)
    new_records = []

    for art in articles_data:
        if art.provider_article_id not in existing_map:
            record = NewsArticle(
                instrument_id=instrument_id,
                provider=provider_name,
                provider_article_id=art.provider_article_id,
                headline=art.headline,
                source=art.source,
                url=art.url,
                summary=art.summary,
                published_at=art.published_at,
                retrieved_at=datetime.now(timezone.utc),
                relevance_score=art.relevance_score,
                match_score=art.match_score,
                sentiment_score=art.sentiment_score,
            )
            db.add(record)
            new_records.append(record)
            existing_map[art.provider_article_id] = record

    if new_records:
        try:
            await db.commit()
            for rec in new_records:
                await db.refresh(rec)
            persisted.extend(new_records)
        except Exception as exc:
            logger.warning('Error committing news articles: %s', exc)
            await db.rollback()

    return persisted


async def get_or_fetch_relevant_news(
    db: AsyncSession,
    instrument: Instrument,
    change_time: datetime,
    baseline_time: datetime | None = None,
    provider: NewsProvider | None = None,
    max_articles: int = MAX_ARTICLES_PER_CHANGE,
    min_score: float = MIN_RELEVANCE_THRESHOLD,
) -> RelevantNewsContext:
    window_start = (baseline_time or change_time) - timedelta(hours=NEWS_WINDOW_HOURS_BEFORE)
    window_end = change_time + timedelta(hours=NEWS_WINDOW_HOURS_AFTER)

    db_stmt = (
        select(NewsArticle)
        .where(
            NewsArticle.instrument_id == instrument.id,
            NewsArticle.published_at >= window_start,
            NewsArticle.published_at <= window_end,
        )
        .order_by(NewsArticle.published_at.desc())
        .limit(20)
    )
    existing_articles = (await db.execute(db_stmt)).scalars().all()
    all_articles: list[NewsArticle | NewsArticleData] = list(existing_articles)

    news_provider = provider or MarketauxNewsProvider()

    if not all_articles:
        if not news_provider.is_configured:
            return RelevantNewsContext(
                status='unavailable',
                articles=[],
                note='Marketaux news integration not configured.',
            )

        try:
            fetched_data = await news_provider.fetch_news_for_instrument(
                symbol=instrument.nse_symbol,
                company_name=instrument.company_name,
                published_after=window_start,
                published_before=window_end,
                limit=10,
            )
            if fetched_data:
                saved = await persist_articles_idempotently(
                    db=db,
                    instrument_id=instrument.id,
                    provider_name=news_provider.provider_name,
                    articles_data=fetched_data,
                )
                all_articles = saved if saved else fetched_data
        except Exception as exc:
            logger.warning('Error fetching news from provider: %s', exc)
            return RelevantNewsContext(
                status='unavailable',
                articles=[],
                note='News context is currently unavailable. Market signals remain unaffected.',
            )

    if not all_articles:
        return RelevantNewsContext(
            status='none_found',
            articles=[],
            note='No relevant news found around this change.',
        )

    scored_items: list[tuple[float, RelevantNewsItem]] = []

    for art in all_articles:
        score, temporal_rel, rel_summary = compute_article_relevance(
            headline=art.headline,
            summary=art.summary,
            published_at=art.published_at,
            symbol=instrument.nse_symbol,
            company_name=instrument.company_name,
            change_time=change_time,
            baseline_time=baseline_time,
            provider_match_score=art.match_score,
            provider_relevance_score=art.relevance_score,
        )

        if score >= min_score:
            art_id = getattr(art, 'id', None)
            item = RelevantNewsItem(
                id=art_id,
                provider_article_id=art.provider_article_id,
                headline=art.headline,
                source=art.source,
                url=art.url,
                published_at=art.published_at,
                summary=art.summary,
                relevance_score=art.relevance_score,
                match_score=art.match_score,
                sentiment_score=art.sentiment_score,
                temporal_relation=temporal_rel,
                relevance_summary=rel_summary,
            )
            scored_items.append((score, item))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = [it for _, it in scored_items[:max_articles]]

    if not top_items:
        return RelevantNewsContext(
            status='none_found',
            articles=[],
            note='No relevant news found around this change.',
        )

    return RelevantNewsContext(
        status='available',
        articles=top_items,
        note='',
    )
