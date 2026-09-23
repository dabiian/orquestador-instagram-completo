"""HTML chunking utility for breaking large documents into manageable pieces.

The chunker tries to preserve complete HTML tags instead of cutting the
document at arbitrary character positions. This produces more useful
context for the locator-healing LLM.
"""

from __future__ import annotations


def _find_safe_split(
    html: str,
    start: int,
    target_end: int,
) -> int:
    """
    Find a safe HTML split position near target_end.

    The returned position will preferably be outside an HTML tag and will
    try to split at whitespace or between HTML elements.

    Args:
        html:
            Complete HTML string.

        start:
            Beginning of the current chunk.

        target_end:
            Desired end position.

    Returns:
        A split position greater than start.
    """
    length = len(html)

    if target_end >= length:
        return length

    if target_end <= start:
        return min(
            start + 1,
            length,
        )

    # --------------------------------------------------------------
    # First preference: find the end of the current HTML tag.
    # --------------------------------------------------------------

    in_tag = False
    quote: str | None = None
    last_tag_end = -1

    index = start

    while index < length and index <= target_end:
        char = html[index]

        if quote is not None:
            if char == quote:
                quote = None

            index += 1
            continue

        if in_tag:
            if char in {"'", '"'}:
                quote = char
            elif char == ">":
                in_tag = False
                last_tag_end = index + 1

        elif char == "<":
            in_tag = True

        index += 1

    if last_tag_end > start:
        # Only use the tag boundary if it is reasonably close to the
        # requested chunk size. This prevents a very large tag from
        # creating unexpectedly tiny chunks.
        distance = abs(last_tag_end - target_end)

        if distance <= max(
            256,
            (target_end - start) // 3,
        ):
            return last_tag_end

    # --------------------------------------------------------------
    # Second preference: whitespace immediately before target_end.
    # --------------------------------------------------------------

    whitespace_position = html.rfind(
        " ",
        start,
        target_end,
    )

    if whitespace_position > start:
        return whitespace_position + 1

    # --------------------------------------------------------------
    # Third preference: HTML element boundary.
    # --------------------------------------------------------------

    closing_boundary = html.rfind(
        ">",
        start,
        target_end,
    )

    if closing_boundary > start:
        return closing_boundary + 1

    # --------------------------------------------------------------
    # Last resort: hard split.
    # --------------------------------------------------------------

    return min(
        target_end,
        length,
    )


def chunk_html(
    html: str,
    chunk_size_kb: int = 50,
) -> list[str]:
    """
    Divide HTML into manageable chunks while preserving HTML boundaries.

    The function attempts to avoid splitting inside HTML tags. Chunk sizes
    are approximate because an individual HTML tag or element may be larger
    than the configured target size.

    Args:
        html:
            HTML string to chunk.

        chunk_size_kb:
            Approximate size of each chunk in kilobytes.

    Returns:
        List of HTML chunks. If html is empty, returns [].

    Raises:
        ValueError:
            If chunk_size_kb is not a positive integer.
    """
    if not html:
        return []

    if isinstance(chunk_size_kb, bool):
        raise ValueError(
            "chunk_size_kb must be a positive integer"
        )

    try:
        chunk_size_kb = int(chunk_size_kb)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "chunk_size_kb must be a positive integer"
        ) from exc

    if chunk_size_kb <= 0:
        raise ValueError(
            "chunk_size_kb must be positive"
        )

    if not isinstance(html, str):
        html = str(html)

    chunk_size_bytes = chunk_size_kb * 1024

    # Small documents do not need chunking.
    if len(html) <= chunk_size_bytes:
        return [html]

    chunks: list[str] = []

    start = 0
    length = len(html)

    while start < length:
        target_end = min(
            start + chunk_size_bytes,
            length,
        )

        if target_end >= length:
            end = length
        else:
            end = _find_safe_split(
                html,
                start,
                target_end,
            )

        # Defensive protection against an invalid split position.
        if end <= start:
            end = min(
                start + chunk_size_bytes,
                length,
            )

        chunk = html[start:end]

        if chunk:
            chunks.append(chunk)

        start = end

    return chunks
