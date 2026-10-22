from datetime import date

from ingest.fiscal_years import declared_fiscal_year

TAG = '<ix:nonNumeric contextRef="c-1" name="dei:DocumentFiscalYearFocus">{}</ix:nonNumeric>'


def test_the_filings_own_tag_names_the_fiscal_year():
    # NVIDIA's fiscal 2025 ended in January 2025.
    assert declared_fiscal_year(TAG.format(2025), date(2025, 1, 26)) == 2025


def test_a_tag_wrapped_in_formatting_is_read():
    raw = '<ix:nonNumeric name="dei:DocumentFiscalYearFocus"><span>2024</span></ix:nonNumeric>'
    assert declared_fiscal_year(raw, date(2024, 6, 30)) == 2024


def test_a_year_that_differs_from_the_period_end_stays_unverified():
    # Some retailers name fiscal 2024 after the year it starts (ends Feb 2025).
    assert declared_fiscal_year(TAG.format(2024), date(2025, 2, 1)) is None


def test_a_filing_without_the_tag_stays_unverified():
    assert declared_fiscal_year("<p>Annual report</p>", date(2025, 9, 27)) is None
