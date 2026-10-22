"""Store each filing's fiscal year as the filing itself declares it.

Every 10-K's inline XBRL tags its fiscal year (`dei:DocumentFiscalYearFocus`).
Ingestion left source_documents.fiscal_year NULL because the corpus year (the
download folder) is not proof of a fiscal year, so citations read "fiscal year
unverified" and fiscal-year filters matched nothing. The tag is kept only when
it equals the year the reporting period ended, the convention of all five
companies; a filing that names its year differently stays NULL. Offline;
--write updates the database.

    uv run python -m ingest.fiscal_years            # report only
    uv run python -m ingest.fiscal_years --write    # update the database
"""

import argparse
import re
from datetime import date

from ingest.pages import decode, filing_pairs

FISCAL_YEAR_TAG = re.compile(
    r'name="dei:DocumentFiscalYearFocus"[^>]*>\s*(?:<[^>]+>\s*)*(\d{4})'
)


def declared_fiscal_year(raw_html: str, report_date: date | None) -> int | None:
    match = FISCAL_YEAR_TAG.search(raw_html)
    if not match or report_date is None:
        return None
    year = int(match[1])
    return year if year == report_date.year else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    import psycopg
    from psycopg.rows import dict_row

    from app.config import settings

    with psycopg.connect(
        str(settings.database_url),
        connect_timeout=10,
        prepare_threshold=None,
        row_factory=dict_row,
    ) as connection:
        updates = []
        for chunk_file, html_file in filing_pairs():
            row = connection.execute(
                "SELECT id, ticker, report_date FROM public.source_documents WHERE accession_number = %s",
                (chunk_file.stem,),
            ).fetchone()
            if row is None:
                continue
            year = declared_fiscal_year(
                decode(html_file.read_bytes()), row["report_date"]
            )
            print(f"{row['ticker']} {row['report_date']}: fiscal year {year}")
            updates.append((year, row["id"]))
        print(f"Verified {sum(y is not None for y, _ in updates)}/{len(updates)}")
        if args.write:
            with connection.cursor() as cursor:
                cursor.executemany(
                    "UPDATE public.source_documents SET fiscal_year = %s WHERE id = %s",
                    updates,
                )
            connection.commit()
            print(f"Updated {len(updates)} filings")


if __name__ == "__main__":
    main()
