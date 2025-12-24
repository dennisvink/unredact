#!/usr/bin/env python3
import argparse
import os
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
from pypdf.generic import ArrayObject, NameObject


def _is_black(color):
    if color is None:
        return False
    try:
        return all(float(c) == 0.0 for c in color)
    except Exception:
        return False


def _looks_like_black_box(annot):
    subtype = annot.get("/Subtype")
    if subtype not in ("/Square", "/Polygon", "/Highlight", "/Ink", "/Stamp"):
        return False
    color = annot.get("/IC") or annot.get("/C")
    if not _is_black(color):
        return False
    opacity = annot.get("/CA", annot.get("/ca", 1))
    try:
        if float(opacity) < 0.9:
            return False
    except Exception:
        pass
    return True


def _remove_redaction_annots(page, aggressive=False):
    annots = page.get("/Annots")
    if not annots:
        return 0

    annots_obj = annots.get_object() if hasattr(annots, "get_object") else annots
    kept = ArrayObject()
    removed = 0

    for annot_ref in annots_obj:
        annot = annot_ref.get_object()
        subtype = annot.get("/Subtype")
        if subtype == "/Redact":
            removed += 1
            continue
        if aggressive and _looks_like_black_box(annot):
            removed += 1
            continue
        kept.append(annot_ref)

    if kept:
        page[NameObject("/Annots")] = kept
    else:
        page.pop("/Annots", None)
    return removed


def _is_black_color(color, tol=0.02):
    if not color:
        return False
    try:
        return all(float(c) <= tol for c in color)
    except Exception:
        return False


def _remove_black_rectangles(page, reader, aggressive=False, min_width=5.0, min_height=5.0):
    contents = page.get_contents()
    if contents is None:
        return 0

    content = ContentStream(contents, reader)
    operations = content.operations

    remove_indices = set()
    path_indices = []
    path_rects = []
    path_has_non_rect = False

    fill_color = (0.0, 0.0, 0.0)
    color_stack = [fill_color]

    def reset_path():
        nonlocal path_indices, path_rects, path_has_non_rect
        path_indices = []
        path_rects = []
        path_has_non_rect = False

    for idx, (operands, operator) in enumerate(operations):
        if operator == b"q":
            color_stack.append(fill_color)
        elif operator == b"Q":
            fill_color = color_stack.pop() if color_stack else (0.0, 0.0, 0.0)
        elif operator == b"g":
            gray = float(operands[0])
            fill_color = (gray, gray, gray)
        elif operator == b"rg":
            fill_color = (float(operands[0]), float(operands[1]), float(operands[2]))
        elif operator == b"re":
            path_indices.append(idx)
            try:
                _x, _y, w, h = map(float, operands)
                path_rects.append((w, h))
            except Exception:
                path_has_non_rect = True
        elif operator in (b"m", b"l", b"c", b"v", b"y", b"h"):
            path_indices.append(idx)
            path_has_non_rect = True
        elif operator in (b"f", b"f*", b"F", b"B", b"B*"):
            if path_indices:
                should_remove = False
                if not path_has_non_rect and _is_black_color(fill_color):
                    if aggressive:
                        should_remove = True
                    else:
                        should_remove = any(
                            w >= min_width and h >= min_height for w, h in path_rects
                        )
                if should_remove:
                    remove_indices.update(path_indices)
                    remove_indices.add(idx)
            reset_path()
        elif operator in (b"n", b"W", b"W*", b"S", b"s"):
            reset_path()

    if not remove_indices:
        return 0

    content.operations = [
        op for i, op in enumerate(operations) if i not in remove_indices
    ]
    page[NameObject("/Contents")] = content
    return len(remove_indices)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Remove PDF redaction annotations. This only removes overlay marks; "
            "it cannot recover content that was permanently redacted."
        )
    )
    parser.add_argument("pdf", help="Input PDF path")
    args = parser.parse_args()
    aggressive = True

    input_path = args.pdf
    if not os.path.isfile(input_path):
        print(f"File not found: {input_path}", file=sys.stderr)
        return 2

    base, _ext = os.path.splitext(input_path)
    output_path = f"{base}_unredacted.pdf"

    reader = PdfReader(input_path)
    writer = PdfWriter()
    total_removed = 0
    total_rect_ops = 0

    for page in reader.pages:
        total_removed += _remove_redaction_annots(page, aggressive=aggressive)
        total_rect_ops += _remove_black_rectangles(
            page, reader, aggressive=aggressive
        )
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

    print(
        f"Removed {total_removed} redaction annotations and "
        f"{total_rect_ops} rectangle ops -> {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
