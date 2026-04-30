"""
Async wrapper around DocumentProcessor.

For now this delegates the CPU/IO-bound work (PyMuPDF + eyecite + DB writes)
to a thread via `asyncio.to_thread`, so background workers can `await` it
without blocking the event loop. A fully native async port can replace this
later without changing the worker contract.
"""
from __future__ import annotations

import asyncio
from typing import Dict

from backend.document_processor import DocumentProcessor


async def process_document_async(document_id: str) -> Dict:
    processor = DocumentProcessor()
    return await asyncio.to_thread(processor.process_document, document_id)


async def process_all_documents_async() -> Dict:
    processor = DocumentProcessor()
    return await asyncio.to_thread(processor.process_all_documents)
