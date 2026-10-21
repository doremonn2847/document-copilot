"""Restore verbatim table layout from the already-stored, hash-verified source.

Indexed chunk text and vectors remain unchanged. Context is original Markdown,
not a reconstruction of missing cells or a declaration of financial periods.
"""

import hashlib
import re

TABLES = re.compile(r"(?m)^\|[^\n]*\n(?:\|[^\n]*(?:\n|$))+")
FISCAL_HEADING = re.compile(
    r"(?im)^Fiscal Year \d{4} Compared with Fiscal Year \d{4}[^\n]*"
)


def original_table_context(
    markdown: str | None, metadata: dict, text: str
) -> list[str]:
    refs = [
        int(m[1])
        for ref in metadata.get("item_refs", [])
        if (m := re.fullmatch(r"#/tables/(\d+)", ref))
    ]
    if not refs or not markdown:
        return []
    # Ingestion hashes file bytes but stores read_text() output. Account only for
    # that known Windows newline translation, not arbitrary content changes.
    source = markdown.replace("\r\n", "\n")
    hashes = {
        hashlib.sha256(value.encode()).hexdigest()
        for value in (source, source.replace("\n", "\r\n"))
    }
    if metadata.get("source_sha256") not in hashes:
        raise ValueError("Original table source hash does not match indexed provenance")
    tables = list(TABLES.finditer(source))
    contexts = []
    for index in dict.fromkeys(refs):
        if index >= len(tables):
            raise ValueError("Original table reference is outside the verified source")
        match = tables[index]
        table = match.group().rstrip()
        # A positional reference must also share a meaningful cell with this
        # chunk. Do not guess a different table when conversion orders differ.
        cells = [
            cell.strip()
            for line in table.splitlines()
            for cell in line.strip("|").split("|")
        ]
        if not any(
            len(cell) >= 4 and cell in text for cell in cells if re.search(r"\w", cell)
        ):
            continue
        before = source[: match.start()].rstrip().split("\n\n")[-1]
        if before and len(before) <= 200 and not before.startswith("|"):
            contexts.append(before)
        after = source[match.end() : match.end() + 8000]
        header_years = set(
            re.findall(r"\b20\d{2}\b", "\n".join(table.splitlines()[:4]))
        )
        for heading in FISCAL_HEADING.finditer(after):
            if set(re.findall(r"\b20\d{2}\b", heading.group())) == header_years:
                contexts.append(heading.group())
                break
        else:
            for heading in re.finditer(
                r"(?im)^For the Fiscal Year Ended [^\n]{1,80}", source
            ):
                if set(re.findall(r"\b20\d{2}\b", heading.group())) & header_years:
                    contexts.append(heading.group())
                    break
        # Keep the body rows: the first 1,600 characters of a padded table held
        # only its headers. Exposure picks header and relevant rows to fit each
        # target's share. Never cut through a row.
        if len(table) > 20000:
            end = table.rfind("\n", 0, 20000)
            table = table[:end] if end > 0 else ""
        if table:
            contexts.append(table)
    return list(dict.fromkeys(contexts))
