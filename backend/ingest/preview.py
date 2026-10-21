"""Preview one Markdown filing locally; no embedding calls or database writes."""

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path, PureWindowsPath
from uuid import NAMESPACE_URL, uuid5

DATA = Path(__file__).resolve().parents[2] / "data"


def load_filing(source: Path, data: Path = DATA) -> dict:
    relative = source.resolve().relative_to((data / "markdown").resolve())
    if relative.suffix != ".md":
        raise ValueError("Select a Markdown file under data/markdown")
    manifest = json.loads(
        (data / "downloads/manifest.json").read_text(encoding="utf-8")
    )
    matches = [
        filing
        for filing in manifest["filings"]
        if Path(*PureWindowsPath(filing["local_path"]).parts).with_suffix(".md")
        == relative
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching manifest entry")
    filing = matches[0]
    for name in (
        "ticker",
        "cik",
        "form",
        "filing_date",
        "report_date",
        "accession_number",
        "primary_document",
        "source_url",
    ):
        if not isinstance(filing.get(name), str) or not filing[name].strip():
            raise ValueError(f"Missing manifest field: {name}")
    return {
        **filing,
        "document_id": str(
            uuid5(NAMESPACE_URL, "sec-edgar:" + filing["accession_number"])
        ),
        "corpus_year": int(relative.parts[0]),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def fit_chunk(chunk, chunker, encoding, max_tokens: int) -> list:
    """Split overflow without truncation; preserve every character of raw text."""
    contextualized = chunker.contextualize(chunk=chunk)
    if len(encoding.encode(contextualized, disallowed_special=())) <= max_tokens:
        return [chunk]
    if len(chunk.text) < 2:
        raise ValueError("Chunk context alone exceeds token budget")
    midpoint = len(chunk.text) // 2
    boundary = chunk.text.rfind(" ", 0, midpoint)
    cut = boundary + 1 if boundary >= midpoint // 2 else midpoint
    return [
        part
        for text in (chunk.text[:cut], chunk.text[cut:])
        for part in fit_chunk(
            chunk.model_copy(update={"text": text}), chunker, encoding, max_tokens
        )
    ]


def chunk_records(
    document, filing: dict, model: str, dimensions: int, max_tokens: int
) -> list[dict]:
    import tiktoken
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

    if model != "text-embedding-3-small" or dimensions != 1536:
        raise ValueError(
            "This preview is configured for text-embedding-3-small at 1536 dimensions"
        )
    if not 32 <= max_tokens <= 8191:
        raise ValueError("Chunk budget must be between 32 and 8191 tokens")
    encoding = tiktoken.get_encoding("cl100k_base")
    # Context serialization can tokenize differently from Docling's split estimates.
    tokenizer = OpenAITokenizer(tokenizer=encoding, max_tokens=max_tokens - 8)
    chunker = HybridChunker(
        tokenizer=tokenizer, merge_peers=True, repeat_table_header=True
    )
    records = []
    fitted = (
        part
        for chunk in chunker.chunk(dl_doc=document)
        for part in fit_chunk(chunk, chunker, encoding, max_tokens)
    )
    for index, chunk in enumerate(fitted):
        embedding_text = chunker.contextualize(chunk=chunk)
        count = len(encoding.encode(embedding_text, disallowed_special=()))
        if not embedding_text.strip() or count > max_tokens:
            raise ValueError(
                f"Chunk {index} is empty or exceeds the {max_tokens}-token budget ({count})"
            )
        headings = chunk.meta.headings or []
        records.append(
            {
                "id": str(
                    uuid5(NAMESPACE_URL, filing["document_id"] + f":chunk:{index}")
                ),
                "document_id": filing["document_id"],
                "chunk_index": index,
                "text": chunk.text,
                "embedding_text": embedding_text,
                "token_count": count,
                "section": " / ".join(headings) or None,
                "page": None,
                "metadata": {
                    "ticker": filing["ticker"],
                    "form": filing["form"],
                    "corpus_year": filing["corpus_year"],
                    "fiscal_year_verified": False,
                    "accession_number": filing["accession_number"],
                    "source_url": filing["source_url"],
                    "source_sha256": filing["source_sha256"],
                    "embedding_input_sha256": hashlib.sha256(
                        embedding_text.encode()
                    ).hexdigest(),
                    "model": model,
                    "dimensions": dimensions,
                    "tokenizer": "cl100k_base",
                    "max_tokens": max_tokens,
                    "docling_version": version("docling"),
                    "docling_core_version": version("docling-core"),
                    "headings": headings,
                    "item_refs": [item.self_ref for item in chunk.meta.doc_items],
                    "item_types": [item.label.value for item in chunk.meta.doc_items],
                    "citation_location_verified": False,
                },
            }
        )
    if not records:
        raise ValueError("No chunks were produced")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    from app.config import settings

    filing = load_filing(args.file)
    print(f"Parsing {args.file.name}", flush=True)
    document = (
        DocumentConverter(allowed_formats=[InputFormat.MD]).convert(args.file).document
    )
    records = chunk_records(
        document,
        filing,
        settings.openai_embedding_model,
        settings.openai_embedding_dimensions,
        settings.ingestion_chunk_tokens,
    )
    target = DATA / "chunks" / f"{filing['accession_number']}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".jsonl.tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )
    temporary.replace(target)
    total = sum(row["token_count"] for row in records)
    print(
        f"Preview: {len(records)} chunks, {total} embedding tokens; max {max(row['token_count'] for row in records)}"
    )
    print(f"Written: {target}")
    print("No embeddings requested; no database writes.")


if __name__ == "__main__":
    main()
