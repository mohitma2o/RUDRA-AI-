"""Bounded text chunking for document summarization."""


def chunk_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in text.splitlines(keepends=True):
        if len(paragraph) > max_chars:
            if current:
                chunks.append("".join(current))
                current = []
                current_length = 0
            chunks.extend(
                paragraph[index : index + max_chars]
                for index in range(0, len(paragraph), max_chars)
            )
            continue
        if current and current_length + len(paragraph) > max_chars:
            chunks.append("".join(current))
            current = []
            current_length = 0
        current.append(paragraph)
        current_length += len(paragraph)

    if current:
        chunks.append("".join(current))
    return chunks
