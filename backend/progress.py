"""
Pipeline progress logging.

Why a dedicated module: the worker output is the single place a user can
tell whether ingest is making progress or stuck. structlog's default
key=value lines get drowned out by ARQ's hash-prefixed job lines, and
without a uniform "stage X starting / stage X done" pattern there's no
way to skim.

Every stage should emit ONE start line and ONE end line, both with the
same `stage=` tag. Read the result with:

    docker compose logs worker | grep ' stage='

Format chosen for greppability: short fixed-width prefixes, lower-snake
identifiers, all values as key=value so it survives copy-paste. Example
output (5-doc seed):

    [pipeline] start  doc=8d0a stage=process       title="Roe v. Wade"
    [pipeline] step   doc=8d0a stage=parse_pdf     pages=14 chars=42100 elapsed=0.41s
    [pipeline] step   doc=8d0a stage=parse_cites   found=82 elapsed=0.18s
    [pipeline] step   doc=8d0a stage=store_cites   stored=80 dropped=2
    [pipeline] step   doc=8d0a stage=link_cites    linked=43 unresolved=37 elapsed=0.07s
    [pipeline] done   doc=8d0a stage=process       elapsed=0.74s
    [pipeline] start  doc=8d0a stage=embed
    [pipeline] step   doc=8d0a stage=embed_text    chunks=4 dim=768 elapsed=2.10s
    [pipeline] step   doc=8d0a stage=neighbors     k=25 written=50 elapsed=0.31s
    [pipeline] done   doc=8d0a stage=embed         elapsed=2.49s

The `stage()` context manager bookends a stage with its start/end lines
and tracks elapsed time for the user. Inner steps inside a stage are
emitted via `stage.step(name, **kwargs)`.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator, Optional

import structlog

logger = structlog.get_logger()


def _shortid(value: Optional[str]) -> str:
    """Truncate UUIDs to 4 chars for human-skimmable log lines."""
    if not value:
        return "-"
    return value.replace("-", "")[:4]


def _format_kv(kwargs: dict) -> str:
    """Render key=value pairs in insertion order, quoting strings with spaces."""
    parts = []
    for k, v in kwargs.items():
        if v is None:
            continue
        if isinstance(v, float):
            parts.append(f"{k}={v:.2f}")
        elif isinstance(v, str) and (" " in v or "\t" in v):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return " ".join(parts)


def step(stage_name: str, *, doc: Optional[str] = None, **kwargs) -> None:
    """Log a within-stage progress step.

    Use this for fine-grained progress inside a `with stage(...)` block:
    e.g. "embed_text chunks=4 dim=768 elapsed=2.10s".
    """
    line = f"[pipeline] step   doc={_shortid(doc)} stage={stage_name}"
    extras = _format_kv(kwargs)
    if extras:
        line = f"{line} {extras}"
    logger.info(line)


class _StageContext:
    """Returned by `stage(...)` so callers can `.step(...)` inside it."""

    def __init__(self, name: str, doc: Optional[str]) -> None:
        self.name = name
        self.doc = doc
        self.started_at: float = 0.0

    def step(self, sub_name: str, **kwargs) -> None:
        step(sub_name, doc=self.doc, **kwargs)


@contextmanager
def stage(name: str, *, doc: Optional[str] = None, **kwargs) -> Iterator[_StageContext]:
    """Bookend a stage with start + done log lines (and elapsed time on done).

    Usage:
        with stage("embed", doc=doc_id) as s:
            s.step("embed_text", chunks=4, elapsed=2.1)
            s.step("neighbors", k=25, written=50)

    On exception, emits a `fail` line with the exception type. The
    exception is re-raised so the caller's error handling still runs.
    """
    ctx = _StageContext(name=name, doc=doc)
    ctx.started_at = time.perf_counter()
    start_line = f"[pipeline] start  doc={_shortid(doc)} stage={name}"
    extras = _format_kv(kwargs)
    if extras:
        start_line = f"{start_line} {extras}"
    logger.info(start_line)
    try:
        yield ctx
    except Exception as e:
        elapsed = time.perf_counter() - ctx.started_at
        logger.error(
            f"[pipeline] fail   doc={_shortid(doc)} stage={name} "
            f"error={type(e).__name__} elapsed={elapsed:.2f}s msg={str(e)[:120]!r}"
        )
        raise
    else:
        elapsed = time.perf_counter() - ctx.started_at
        logger.info(
            f"[pipeline] done   doc={_shortid(doc)} stage={name} elapsed={elapsed:.2f}s"
        )
