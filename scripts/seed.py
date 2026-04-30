"""
Seed the corpus with opinions from CourtListener.

Default: 50 SCOTUS opinions, ordered most recently created. Each opinion's
plain_text is written into a synthesized multi-page PDF (PyMuPDF) so the
existing pipeline runs unchanged: PDF parse → eyecite → embed.

Usage:
    python scripts/seed.py                                  # 50 SCOTUS
    python scripts/seed.py --count 500                      # 500 SCOTUS
    python scripts/seed.py --court ca9 --count 100          # 9th Circuit
    python scripts/seed.py --topic "establishment clause" --count 100
    python scripts/seed.py --after-date 2018-01-01 --count 200

Flags:
    --count N         Target number of opinions. Capped at 500 to avoid
                      pulling the entire CourtListener catalog by accident.
                      (Aliased as --limit for backward compatibility.)
    --court SLUG      CourtListener court slug (scotus, ca1..ca11, dcd, ...).
    --topic TEXT      Free-text query against CourtListener's full-text
                      search.
    --after-date DATE ISO date "YYYY-MM-DD"; restrict to filings after this.

Idempotent on two levels:
    - SHA-256 of the plain_text body (content fingerprint) — primary dedupe.
    - source_url match against documents.source_url — catches CourtListener
      republishing the same opinion under a new ID with edited text.

Auth: set COURTLISTENER_API_KEY for higher rate limits. The 429 backoff in
backend.courtlistener.list_opinions() applies; this script does not need
extra throttling beyond that.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
import uuid
from datetime import datetime
from typing import Optional

import fitz  # PyMuPDF
import structlog

# Allow running via `python scripts/seed.py` from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings

from backend.config import settings
from backend.courtlistener import (
    fetch_cluster,
    fetch_opinion,
    find_cluster_by_name,
    list_opinions,
)
from backend.database import AsyncSessionLocal
from backend.models import Document

logger = structlog.get_logger()

MAX_COUNT = 500


def _safe_filename(stub: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in stub)[:80]


def _build_pdf(path: str, title: str, body: str) -> None:
    """
    Render plain text to a multi-page PDF so PyMuPDF + eyecite can read it.

    Slice the body into ~2800-char chunks (one page each at 10pt with
    standard margins). Avoids the prior `insert_textbox` rc-misinterpretation
    that could loop on long opinions.
    """
    doc = fitz.open()
    text = f"{title}\n\n{body}".strip()
    chunk_size = 2800

    cursor = 0
    while cursor < len(text):
        page = doc.new_page()
        rect = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
        chunk = text[cursor : cursor + chunk_size]
        page.insert_textbox(rect, chunk, fontsize=10, fontname="helv")
        cursor += chunk_size

    if doc.page_count == 0:
        doc.new_page()

    doc.save(path)
    doc.close()


async def _existing_state(session) -> tuple[set[str], set[str]]:
    """Return (existing_fingerprints, existing_source_urls)."""
    fp_rows = await session.execute(select(Document.fingerprint))
    url_rows = await session.execute(
        select(Document.source_url).where(Document.source_url.isnot(None))
    )
    return (
        {fp for (fp,) in fp_rows.all()},
        {url for (url,) in url_rows.all() if url},
    )


async def _ingest_opinion(
    opinion: dict,
    storage_dir: str,
    fingerprints: set[str],
    source_urls: set[str],
    court_label: str,
) -> Optional[str]:
    """Returns the new document id or None if skipped."""
    body = (opinion.get("plain_text") or "").strip()
    if not body:
        return None

    cluster_url = opinion.get("cluster")
    cluster = await fetch_cluster(cluster_url) if cluster_url else None

    case_name = (cluster or {}).get("case_name") or f"Opinion {opinion.get('id')}"
    date_filed = (cluster or {}).get("date_filed")
    year = None
    if date_filed:
        try:
            year = int(str(date_filed)[:4])
        except ValueError:
            year = None

    fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if fingerprint in fingerprints:
        logger.info("Skip duplicate fingerprint", case=case_name, fingerprint=fingerprint[:12])
        return None

    source_url = opinion.get("absolute_url")
    if source_url and source_url in source_urls:
        logger.info("Skip duplicate source_url", case=case_name, url=source_url)
        return None

    pdf_name = f"seed_{_safe_filename(case_name)}_{fingerprint[:8]}.pdf"
    pdf_path = os.path.join(storage_dir, pdf_name)
    _build_pdf(pdf_path, case_name, body)

    document = Document(
        id=str(uuid.uuid4()),
        title=case_name,
        fingerprint=fingerprint,
        source_path=pdf_path,
        source_url=source_url,
        court=court_label,
        year=year,
        docket=(cluster or {}).get("docket_number"),
        full_text=body,
        created_at=datetime.utcnow(),
    )

    async with AsyncSessionLocal() as session:
        session.add(document)
        await session.commit()
        await session.refresh(document)
        fingerprints.add(fingerprint)
        if source_url:
            source_urls.add(source_url)

    return document.id


# 40 SCOTUS landmark cases — chosen for breadth across constitutional
# subject-areas and across the 1800s–2010s timeline. Each pair is
# `(case_name_for_icontains_search, year_filed)`. `find_cluster_by_name`
# does a partial case-name match scoped to the year, so common shortenings
# (e.g. "Brown v. Board" rather than the full "Brown v. Board of Education
# of Topeka") still resolve. When CourtListener republishes a case under
# multiple clusters we take the first result returned, which is typically
# the canonical opinion.
LANDMARK_CASES: list[tuple[str, int]] = [
    ("Marbury v. Madison", 1803),
    ("McCulloch v. Maryland", 1819),
    ("Dred Scott v. Sandford", 1857),
    ("Plessy v. Ferguson", 1896),
    ("Lochner v. New York", 1905),
    ("Schenck v. United States", 1919),
    ("Korematsu v. United States", 1944),
    ("Brown v. Board of Education", 1954),
    ("Mapp v. Ohio", 1961),
    ("Engel v. Vitale", 1962),
    ("Gideon v. Wainwright", 1963),
    ("New York Times Co. v. Sullivan", 1964),
    ("Griswold v. Connecticut", 1965),
    ("Miranda v. Arizona", 1966),
    ("Loving v. Virginia", 1967),
    ("Tinker v. Des Moines", 1969),
    ("Brandenburg v. Ohio", 1969),
    ("New York Times Co. v. United States", 1971),
    ("Lemon v. Kurtzman", 1971),
    ("Roe v. Wade", 1973),
    ("United States v. Nixon", 1974),
    ("Buckley v. Valeo", 1976),
    ("Regents of the University of California v. Bakke", 1978),
    ("Chevron", 1984),
    ("Texas v. Johnson", 1989),
    ("Planned Parenthood v. Casey", 1992),
    ("Daubert v. Merrell Dow", 1993),
    ("Bush v. Gore", 2000),
    ("Apprendi v. New Jersey", 2000),
    ("Lawrence v. Texas", 2003),
    ("Crawford v. Washington", 2004),
    ("District of Columbia v. Heller", 2008),
    ("Citizens United v. Federal Election Commission", 2010),
    ("National Federation of Independent Business v. Sebelius", 2012),
    ("Riley v. California", 2014),
    ("Obergefell v. Hodges", 2015),
    ("Carpenter v. United States", 2018),
    ("Erie Railroad v. Tompkins", 1938),
    ("Wickard v. Filburn", 1942),
    ("Youngstown Sheet & Tube Co. v. Sawyer", 1952),
]


_COURT_LABELS = {
    "scotus": "U.S. Supreme Court",
    "ca1": "First Circuit",
    "ca2": "Second Circuit",
    "ca3": "Third Circuit",
    "ca4": "Fourth Circuit",
    "ca5": "Fifth Circuit",
    "ca6": "Sixth Circuit",
    "ca7": "Seventh Circuit",
    "ca8": "Eighth Circuit",
    "ca9": "Ninth Circuit",
    "ca10": "Tenth Circuit",
    "ca11": "Eleventh Circuit",
    "cadc": "D.C. Circuit",
    "cafc": "Federal Circuit",
}


async def _seed_spread(args: argparse.Namespace) -> None:
    """Spread the corpus across decades for a richer Timeline scrubber.

    Default behaviour (no --year-min/--year-max) walks 1900 → present in
    decade-sized windows, fetching `count // n_decades` opinions per
    decade. The user can narrow the range with --year-min / --year-max.

    Why per-decade walks instead of one big query: CourtListener orders
    results by ingestion id by default, which clusters newer opinions at
    the top. Walking decade by decade with `before_date`/`after_date`
    yields broader coverage without paginating through tens of thousands
    of results.
    """
    storage_dir = settings.pdf_storage_path
    os.makedirs(storage_dir, exist_ok=True)

    if not settings.courtlistener_api_key:
        logger.warning(
            "COURTLISTENER_API_KEY not set — historical spread makes one "
            "API request per decade window; expect rate limiting"
        )

    year_min = args.year_min if args.year_min is not None else 1900
    year_max = args.year_max if args.year_max is not None else datetime.utcnow().year
    if year_min >= year_max:
        logger.error("year-min must be < year-max", year_min=year_min, year_max=year_max)
        return

    total = min(max(args.count, 1), MAX_COUNT)

    # Build decade buckets covering the requested span. We anchor on
    # decade boundaries so the histogram in the Timeline scrubber lines
    # up cleanly.
    start_decade = (year_min // 10) * 10
    end_decade = ((year_max - 1) // 10) * 10
    decades = list(range(start_decade, end_decade + 10, 10))
    per_decade = max(1, total // len(decades))

    logger.info(
        "Historical spread plan",
        year_min=year_min,
        year_max=year_max,
        decades=len(decades),
        per_decade=per_decade,
        total_target=total,
    )

    async with AsyncSessionLocal() as session:
        fingerprints, source_urls = await _existing_state(session)

    court_label = _COURT_LABELS.get(args.court, args.court.upper())
    new_ids: list[str] = []

    for decade in decades:
        after = f"{max(decade, year_min)}-01-01"
        before = f"{min(decade + 9, year_max)}-12-31"
        try:
            opinions = await list_opinions(
                court=args.court,
                page_size=20,
                max_results=per_decade,
                topic=args.topic,
                after_date=after,
                before_date=before,
                # Oldest first within the decade — keeps the spread
                # representative even when CourtListener's default
                # ordering would over-sample modern slip opinions.
                order_by="cluster__date_filed",
            )
        except Exception as e:
            logger.warning("Decade fetch failed", decade=decade, error=str(e))
            continue

        if not opinions:
            logger.info("Decade returned no opinions", decade=decade)
            continue

        for op in opinions:
            try:
                new_id = await _ingest_opinion(
                    op, storage_dir, fingerprints, source_urls, court_label
                )
                if new_id is not None:
                    new_ids.append(new_id)
            except Exception as e:
                logger.warning("Failed to ingest opinion", error=str(e))

        if len(new_ids) >= total:
            break

    if not new_ids:
        logger.info("Spread seed: nothing new (all duplicates or empty fetch)")
        return

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        for doc_id in new_ids:
            await pool.enqueue_job("process_pdf_job", doc_id)
    finally:
        await pool.close()

    logger.info(
        "Spread seed complete",
        new_documents=len(new_ids),
        decades_covered=len(decades),
    )


async def _seed_landmarks(args: argparse.Namespace) -> None:
    """Seed the curated SCOTUS landmark list.

    For each `(case_name, year)` tuple, resolve to a CourtListener cluster
    via partial case-name match within the year, fetch the lead opinion's
    plain_text, and ingest through the same path as the regular seed.
    Failures (cluster not found, opinion empty) log + continue — the goal
    is best-effort coverage of the canon, not an all-or-nothing run.

    Output: roughly 35–40 ingested documents. A handful regularly fail to
    resolve cleanly (cluster name mismatches, slip-opinion text quirks)
    and that's fine — the seed just needs to give the graph enough
    structure to look populated.
    """
    storage_dir = settings.pdf_storage_path
    os.makedirs(storage_dir, exist_ok=True)

    if not settings.courtlistener_api_key:
        logger.warning(
            "COURTLISTENER_API_KEY not set — landmark resolution makes ~40 "
            "API calls, expect rate limiting without a key"
        )

    async with AsyncSessionLocal() as session:
        fingerprints, source_urls = await _existing_state(session)

    new_ids: list[str] = []
    resolved = 0
    skipped = 0

    for case_name, year in LANDMARK_CASES:
        try:
            cluster = await find_cluster_by_name(case_name, year, court="scotus")
        except Exception as e:
            logger.warning("Landmark search failed", case=case_name, error=str(e))
            skipped += 1
            continue

        if not cluster:
            logger.warning("Landmark not found", case=case_name, year=year)
            skipped += 1
            continue

        sub_opinions = cluster.get("sub_opinions") or []
        if not sub_opinions:
            logger.warning("Landmark cluster has no sub_opinions", case=case_name)
            skipped += 1
            continue

        # Lead opinion is always sub_opinions[0]; concurrences/dissents
        # come after. We only ingest the lead — that's enough text to
        # produce a useful node and matches what the regular seed does.
        opinion = await fetch_opinion(sub_opinions[0])
        if not opinion or not (opinion.get("plain_text") or "").strip():
            logger.warning("Landmark opinion empty", case=case_name)
            skipped += 1
            continue

        resolved += 1
        try:
            new_id = await _ingest_opinion(
                opinion, storage_dir, fingerprints, source_urls, "U.S. Supreme Court"
            )
            if new_id is not None:
                new_ids.append(new_id)
                logger.info("Landmark ingested", case=case_name, year=year)
        except Exception as e:
            logger.warning("Landmark ingest failed", case=case_name, error=str(e))

    logger.info(
        "Landmark resolution summary",
        total=len(LANDMARK_CASES),
        resolved=resolved,
        ingested=len(new_ids),
        skipped=skipped,
    )

    if not new_ids:
        logger.info("Nothing new to seed (all duplicates or no matches)")
        return

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        for doc_id in new_ids:
            await pool.enqueue_job("process_pdf_job", doc_id)
    finally:
        await pool.close()

    logger.info("Landmark seed complete", new_documents=len(new_ids))


async def _seed(args: argparse.Namespace) -> None:
    storage_dir = settings.pdf_storage_path
    os.makedirs(storage_dir, exist_ok=True)

    if not settings.courtlistener_api_key:
        logger.warning(
            "COURTLISTENER_API_KEY not set — falling back to anonymous; "
            "expect heavy rate limiting on >100 fetches"
        )

    count = min(max(args.count, 1), MAX_COUNT)
    if args.count > MAX_COUNT:
        logger.warning("Capped --count to MAX_COUNT", requested=args.count, capped=MAX_COUNT)

    logger.info(
        "Fetching opinions",
        court=args.court,
        topic=args.topic,
        after_date=args.after_date,
        count=count,
    )
    opinions = await list_opinions(
        court=args.court,
        page_size=20,
        max_results=count,
        topic=args.topic,
        after_date=args.after_date,
    )
    if not opinions:
        logger.error("No opinions returned from CourtListener")
        return

    async with AsyncSessionLocal() as session:
        fingerprints, source_urls = await _existing_state(session)

    court_label = _COURT_LABELS.get(args.court, args.court.upper())

    new_ids: list[str] = []
    for op in opinions:
        try:
            new_id = await _ingest_opinion(
                op, storage_dir, fingerprints, source_urls, court_label
            )
            if new_id is not None:
                new_ids.append(new_id)
        except Exception as e:
            logger.warning("Failed to ingest opinion", error=str(e))

    if not new_ids:
        logger.info("Nothing new to seed (all duplicates)")
        return

    logger.info("Enqueuing process_pdf_job for new documents", count=len(new_ids))
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        for doc_id in new_ids:
            await pool.enqueue_job("process_pdf_job", doc_id)
    finally:
        await pool.close()

    logger.info("Seed complete", new_documents=len(new_ids))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count",
        "--limit",
        dest="count",
        type=int,
        default=50,
        help=f"target number of opinions (max {MAX_COUNT})",
    )
    parser.add_argument("--court", type=str, default="scotus")
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--after-date", dest="after_date", type=str, default=None)
    parser.add_argument(
        "--landmarks",
        action="store_true",
        help="Seed the curated SCOTUS landmark list (~40 cases). "
        "Ignores --count/--court/--topic/--after-date.",
    )
    parser.add_argument(
        "--spread",
        action="store_true",
        help="Walk decade-sized year windows from --year-min to --year-max "
        "to spread the corpus across history. Defaults to 1900–present.",
    )
    parser.add_argument(
        "--year-min",
        dest="year_min",
        type=int,
        default=None,
        help="Earliest year to include with --spread (default 1900).",
    )
    parser.add_argument(
        "--year-max",
        dest="year_max",
        type=int,
        default=None,
        help="Latest year to include with --spread (default = current year).",
    )
    args = parser.parse_args()

    if args.landmarks:
        asyncio.run(_seed_landmarks(args))
    elif args.spread:
        asyncio.run(_seed_spread(args))
    else:
        asyncio.run(_seed(args))


if __name__ == "__main__":
    main()
