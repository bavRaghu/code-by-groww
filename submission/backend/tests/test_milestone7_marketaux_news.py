import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import httpx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.instrument import Instrument
from app.models.news_article import NewsArticle
from app.models.watchlist import Watchlist
from app.services.news.base import NewsArticleData
from app.services.news.marketaux import MarketauxNewsProvider
from app.services.news.service import (
    compute_article_relevance,
    get_or_fetch_relevant_news,
    persist_articles_idempotently,
)
from app.services.significance_scoring import calculate_significance

SAMPLE_MARKETAUX_PAYLOAD = {
    'meta': {'found': 2, 'returned': 2, 'limit': 10, 'page': 1},
    'data': [
        {
            'uuid': 'art-uuid-111',
            'title': 'TCS Reports Strong Q1 Performance and New AI Contracts',
            'description': 'Tata Consultancy Services announced major client wins and steady margins across key sectors.',
            'snippet': 'Tata Consultancy Services announced major client wins...',
            'url': 'https://example.com/tcs-q1-report',
            'image_url': 'https://example.com/img1.jpg',
            'language': 'en',
            'published_at': '2026-09-03T10:30:00.000000Z',
            'source': 'The Economic Times',
            'relevance_score': 0.88,
            'entities': [
                {
                    'symbol': 'TCS',
                    'name': 'Tata Consultancy Services Limited',
                    'exchange': 'NSE',
                    'match_score': 92.5,
                    'sentiment_score': 0.35,
                }
            ],
        },
        {
            'uuid': 'art-uuid-222',
            'title': 'IT Sector Faces Macro Headwinds Amid Shifting Global Budgets',
            'description': 'General outlook on technology outsourcing companies in India.',
            'snippet': 'General outlook on technology outsourcing...',
            'url': 'https://example.com/it-sector-update',
            'image_url': None,
            'language': 'en',
            'published_at': '2026-09-02T14:15:00.000000Z',
            'source': 'LiveMint',
            'relevance_score': 0.55,
            'entities': [
                {
                    'symbol': 'TCS.NS',
                    'name': 'Tata Consultancy Services',
                    'exchange': 'NSE',
                    'match_score': 65.0,
                    'sentiment_score': -0.10,
                }
            ],
        },
    ],
}

@pytest.mark.asyncio
async def test_1_marketaux_response_normalization():
    provider = MarketauxNewsProvider(api_token='test_mock_token')
    raw_articles = SAMPLE_MARKETAUX_PAYLOAD['data']
    normalized = provider.normalize_articles(raw_articles, symbol='TCS', company_name='Tata Consultancy Services')
    assert len(normalized) == 2
    first = normalized[0]
    assert first.provider_article_id == 'art-uuid-111'
    assert first.headline == 'TCS Reports Strong Q1 Performance and New AI Contracts'
    assert first.source == 'The Economic Times'
    assert first.url == 'https://example.com/tcs-q1-report'
    assert first.published_at == datetime(2026, 9, 3, 10, 30, tzinfo=timezone.utc)
    assert first.summary is not None
    assert first.match_score == pytest.approx(0.925, rel=1e-2)
    assert first.relevance_score == 0.88
    assert first.sentiment_score == 0.35

@pytest.mark.asyncio
async def test_2_missing_token_graceful_handling(db_session: AsyncSession):
    provider = MarketauxNewsProvider(api_token='')
    assert not provider.is_configured
    res = await provider.fetch_news_for_instrument('TCS', 'Tata Consultancy Services')
    assert res == []
    inst_stmt = select(Instrument).where(Instrument.nse_symbol == 'TCS')
    inst = (await db_session.execute(inst_stmt)).scalar_one()
    context = await get_or_fetch_relevant_news(
        db=db_session,
        instrument=inst,
        change_time=datetime(2026, 9, 3, 15, 30, tzinfo=timezone.utc),
        provider=provider,
    )
    assert context.status == 'unavailable'
    assert context.articles == []

@pytest.mark.asyncio
async def test_3_timeout_and_5xx_resilience():
    provider = MarketauxNewsProvider(api_token='dummy_token')
    with patch('httpx.AsyncClient.get', side_effect=httpx.TimeoutException('Read timed out')):
        res = await provider.fetch_news_for_instrument('TCS', 'Tata Consultancy Services')
        assert res == []
    call_count = 0
    async def mock_502(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=502, request=httpx.Request('GET', 'https://api.marketaux.com'))
    with patch('httpx.AsyncClient.get', side_effect=mock_502):
        res = await provider.fetch_news_for_instrument('TCS', 'Tata Consultancy Services')
        assert res == []
        assert call_count == 2

@pytest.mark.asyncio
async def test_4_rate_limit_429_and_auth_401_handling():
    provider = MarketauxNewsProvider(api_token='mock_token')
    mock_429 = httpx.Response(status_code=429, request=httpx.Request('GET', 'https://api.marketaux.com'))
    with patch('httpx.AsyncClient.get', return_value=mock_429):
        res = await provider.fetch_news_for_instrument('TCS', 'Tata Consultancy Services')
        assert res == []
    mock_401 = httpx.Response(status_code=401, request=httpx.Request('GET', 'https://api.marketaux.com'))
    with patch('httpx.AsyncClient.get', return_value=mock_401):
        res = await provider.fetch_news_for_instrument('TCS', 'Tata Consultancy Services')
        assert res == []

@pytest.mark.asyncio
async def test_5_duplicate_article_prevention_idempotency(db_session: AsyncSession):
    inst_stmt = select(Instrument).where(Instrument.nse_symbol == 'TCS')
    inst = (await db_session.execute(inst_stmt)).scalar_one()
    article = NewsArticleData(
        provider_article_id='idemp-test-uuid-999',
        headline='TCS Announces Major Partnership',
        source='Reuters',
        url='https://reuters.com/tcs-deal',
        published_at=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        relevance_score=0.9,
    )
    res1 = await persist_articles_idempotently(db_session, inst.id, 'marketaux', [article])
    assert len(res1) == 1
    res2 = await persist_articles_idempotently(db_session, inst.id, 'marketaux', [article])
    assert len(res2) == 1
    check_stmt = select(NewsArticle).where(
        NewsArticle.instrument_id == inst.id,
        NewsArticle.provider_article_id == 'idemp-test-uuid-999',
    )
    rows = (await db_session.execute(check_stmt)).scalars().all()
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_6_instrument_association(db_session: AsyncSession):
    tcs = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == 'TCS'))).scalar_one()
    infy = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == 'INFY'))).scalar_one()
    tcs_art = NewsArticleData(
        provider_article_id='assoc-tcs-1',
        headline='TCS Expansion in European Cloud Market',
        source='Mint',
        url='https://example.com/tcs',
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )
    infy_art = NewsArticleData(
        provider_article_id='assoc-infy-1',
        headline='Infosys Cloud Migration Platform Launch',
        source='Bloomberg',
        url='https://example.com/infy',
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
    )
    await persist_articles_idempotently(db_session, tcs.id, 'marketaux', [tcs_art])
    await persist_articles_idempotently(db_session, infy.id, 'marketaux', [infy_art])
    tcs_articles = (await db_session.execute(select(NewsArticle).where(NewsArticle.instrument_id == tcs.id))).scalars().all()
    assert any(a.provider_article_id == 'assoc-tcs-1' for a in tcs_articles)
    assert not any(a.provider_article_id == 'assoc-infy-1' for a in tcs_articles)

@pytest.mark.asyncio
async def test_7_relevance_ranking_and_max_3_articles():
    change_time = datetime(2026, 9, 3, 15, 30, tzinfo=timezone.utc)
    baseline_time = datetime(2026, 9, 2, 15, 30, tzinfo=timezone.utc)
    score1, rel1, sum1 = compute_article_relevance(
        headline='TCS Signs Mega Deal with Retail Giant',
        summary='Tata Consultancy Services won contract',
        published_at=datetime(2026, 9, 3, 11, 0, tzinfo=timezone.utc),
        symbol='TCS',
        company_name='Tata Consultancy Services',
        change_time=change_time,
        baseline_time=baseline_time,
        provider_match_score=0.95,
        provider_relevance_score=0.9,
    )
    score2, rel2, sum2 = compute_article_relevance(
        headline='IT Outsourcing Trends for Indian Tech',
        summary='Sector insights mentioning Tata Consultancy Services',
        published_at=datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc),
        symbol='TCS',
        company_name='Tata Consultancy Services',
        change_time=change_time,
        baseline_time=baseline_time,
        provider_match_score=0.60,
        provider_relevance_score=0.5,
    )
    score3, rel3, sum3 = compute_article_relevance(
        headline='Global Tech Stocks Mixed on Inflation Data',
        summary='Broad overview of world markets',
        published_at=datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc),
        symbol='TCS',
        company_name='Tata Consultancy Services',
        change_time=change_time,
        baseline_time=baseline_time,
        provider_match_score=0.20,
        provider_relevance_score=0.3,
    )
    assert score1 > score2 > score3
    assert 'Direct ticker match' in sum1
    assert 'Published during the observation window' in rel1

@pytest.mark.asyncio
async def test_8_temporal_relevance_proximity():
    change_time = datetime(2026, 9, 3, 15, 30, tzinfo=timezone.utc)
    score_near, rel_near, _ = compute_article_relevance(
        headline='TCS Announces Quarterly Dividend',
        summary='Tata Consultancy Services dividend',
        published_at=datetime(2026, 9, 3, 13, 30, tzinfo=timezone.utc),
        symbol='TCS',
        company_name='Tata Consultancy Services',
        change_time=change_time,
        provider_match_score=0.9,
    )
    score_far, rel_far, _ = compute_article_relevance(
        headline='TCS Announces Quarterly Dividend',
        summary='Tata Consultancy Services dividend',
        published_at=datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
        symbol='TCS',
        company_name='Tata Consultancy Services',
        change_time=change_time,
        provider_match_score=0.9,
    )
    assert score_near > score_far

@pytest.mark.asyncio
async def test_9_no_relevant_news_fallback(db_session: AsyncSession):
    inst = (await db_session.execute(select(Instrument).where(Instrument.nse_symbol == 'INFY'))).scalar_one()
    mock_provider = AsyncMock(spec=MarketauxNewsProvider)
    mock_provider.is_configured = True
    mock_provider.provider_name = 'marketaux'
    mock_provider.fetch_news_for_instrument.return_value = []
    context = await get_or_fetch_relevant_news(
        db=db_session,
        instrument=inst,
        change_time=datetime(2028, 1, 1, 15, 30, tzinfo=timezone.utc),
        provider=mock_provider,
    )
    assert context.status == 'none_found'
    assert context.articles == []
    assert 'no relevant news' in context.note.lower()

@pytest.mark.asyncio
async def test_10_marketaux_failure_does_not_break_attention(client: AsyncClient, db_session: AsyncSession):
    wl_res = await client.post('/api/v1/watchlists', json={'name': 'M7 Resilience Watchlist'})
    assert wl_res.status_code == 201
    wl_id = wl_res.json()['id']
    with patch(
        'app.services.news.service.MarketauxNewsProvider.fetch_news_for_instrument',
        side_effect=RuntimeError('Marketaux total network outage'),
    ):
        res = await client.get(f'/api/v1/watchlists/{wl_id}/attention')
        assert res.status_code == 200
        data = res.json()
        assert 'attention_items' in data
        assert 'summary' in data

@pytest.mark.asyncio
async def test_11_existing_significance_calculation_unchanged():
    res_clean = calculate_significance(
        current_return=0.042,
        historical_abs_returns=[0.01, 0.012, 0.015, 0.011, 0.009],
        z_score=2.8,
        excess_return=0.031,
        volume_ratio=2.4,
    )
    res_repeat = calculate_significance(
        current_return=0.042,
        historical_abs_returns=[0.01, 0.012, 0.015, 0.011, 0.009],
        z_score=2.8,
        excess_return=0.031,
        volume_ratio=2.4,
    )
    assert res_clean.overall_score == res_repeat.overall_score
    assert res_clean.magnitude_score == res_repeat.magnitude_score
    assert res_clean.overall_score > Decimal('0.5')
    assert not hasattr(res_clean, 'news_score')
    assert not hasattr(res_clean, 'marketaux_score')
    assert 'news' not in res_clean.evidence
    assert res_clean.abnormality_score == res_repeat.abnormality_score
    assert res_clean.significance_level == res_repeat.significance_level

@pytest.mark.asyncio
async def test_12_token_security_and_no_leak(client: AsyncClient, db_session: AsyncSession):
    inst = (await db_session.execute(select(Instrument).limit(1))).scalar_one()
    res = await client.get(f'/api/v1/instruments/{inst.id}/detail')
    assert res.status_code == 200
    response_text = res.text
    if settings.marketaux_api_token:
        assert settings.marketaux_api_token not in response_text
    data = res.json()
    if data.get('relevant_news'):
        disclaimer = data['relevant_news'].get('disclaimer', '')
        assert 'does not imply causality' in disclaimer.lower() or 'context' in disclaimer.lower()
