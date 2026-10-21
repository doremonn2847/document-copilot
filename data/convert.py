"""Convert downloaded SEC HTML filings to Markdown with Docling."""

import argparse
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

DATA = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite", action="store_true", help="Reconvert existing Markdown"
    )
    args = parser.parse_args()
    sources = sorted((DATA / "downloads").rglob("*.htm"))
    if not sources:
        raise SystemExit("No .htm files found in data/downloads.")
    converter = DocumentConverter(allowed_formats=[InputFormat.HTML])
    converted = skipped = 0
    for source in sources:
        target = (
            DATA
            / "markdown"
            / source.relative_to(DATA / "downloads").with_suffix(".md")
        )
        if target.exists() and not args.overwrite:
            skipped += 1
            continue
        markdown = converter.convert(source).document.export_to_markdown()
        if not markdown.strip():
            raise RuntimeError(f"Empty conversion: {source.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".md.tmp")
        temporary.write_text(markdown, encoding="utf-8")
        temporary.replace(target)
        converted += 1
        print(f"Converted {converted}: {target.relative_to(DATA)}", flush=True)
    print(f"Done: {converted} converted, {skipped} skipped, {len(sources)} total.")


if __name__ == "__main__":
    main()
