"""PDF ingestion. Day 1: `inventory()` (which pages have a text layer). Day 3: statement reading.

Day 3 contract (tasks/sprint.md), so the rest of the pipeline can be built against it now:

    read_package(deal_dir) -> ReadResult
        statements:   list[schemas.Statement]   every value with a SourceRef (document, page, method)
        addbacks:     list[schemas.AddBack]     the seller's add-back schedule, descriptions verbatim
        unread_pages: list[(document, page, why)]  pages neither the parser nor Claude could read
        warnings:     list[str]

Order of attempts per page: text layer and table parsing (pdfplumber; camelot for ruled tables)
-> registered use ingest.page_extraction for pages with no text layer or no readable table ->
the page is listed in unread_pages for keying in on review. Every statement then goes through
validate.check_statement before any figure is used.
"""
from .inventory import PageInfo, inventory

__all__ = ["inventory", "PageInfo"]
