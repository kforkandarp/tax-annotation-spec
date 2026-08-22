"""PDF rendering engine for drawing processed annotation fields onto PDF templates."""

from pathlib import Path
from typing import Iterable, Union
import fitz  # PyMuPDF - the library we're using to open and modify PDFs.

from src.models import TextAlignment
from src.processor import ProcessedField

# PyMuPDF alignment mapping: 0=left, 1=center, 2=right
ALIGNMENT_MAP = {
    TextAlignment.LEFT: 0,
    TextAlignment.CENTER: 1,
    TextAlignment.RIGHT: 2,
}

DEFAULT_FONT_SIZE = 10.0


class RendererError(Exception):
    """Base exception for PDF rendering failures."""


# ProcessedField(): # The final package of information that the renderer needs.
#     annotation_id: str
#     label: str
#     page: int
#     box: BoundingBox
#     formatted_value: str
#     style: Style # alignment and font size


def render_fields(
    template_path: Union[str, Path],
    fields: Iterable[ProcessedField],
    output_path: Union[str, Path],
) -> None:
    """Render a sequence of ProcessedField items onto an existing PDF template.

    Coordinates and Geometry:
    - Coordinates are measured in PDF points (1/72 inch).
    - Origin (0,0) is at the top-left corner of the page.
    - x increases to the right, y increases downward.
    - BoundingBox (x, y, width, height) converts to fitz.Rect(x, y, x + width, y + height).

    Page Numbering:
    - Annotation page numbers are 1-based (page 1 is the first page).
    - PyMuPDF page indices are 0-based (page 1 -> index 0).

    Args:
        template_path: File path to the existing PDF template.
        fields: Iterable of render-ready ProcessedField objects.
        output_path: Destination file path for the annotated PDF.

    Raises:
        RendererError: If the template cannot be loaded, a page is out of bounds,
                       or drawing onto the PDF fails.
    """
    template_file = Path(template_path)
    output_file = Path(output_path)

    if not template_file.exists():
        raise RendererError(f"Template PDF not found at '{template_file}'")

    try:
        doc = fitz.open(template_file)
    except Exception as e:
        raise RendererError(f"Failed to open template PDF '{template_file}': {e}") from e

    try:
        total_pages = len(doc)

        for field in fields:
            # 1-based page to 0-based index
            page_index = field.page - 1
            if page_index < 0 or page_index >= total_pages:
                raise RendererError(
                    f"Annotation '{field.annotation_id}' targets page {field.page}, "
                    f"but template has {total_pages} page(s) (valid range: 1 to {total_pages})"
                )

            page = doc[page_index]
            box = field.box
            rect = fitz.Rect(box.x, box.y, box.x + box.width, box.y + box.height)

            # Determine styling
            font_size = field.style.font_size if field.style.font_size is not None else DEFAULT_FONT_SIZE
            align = ALIGNMENT_MAP.get(field.style.alignment, 0)

            # Draw text inside bounding box
            rc = page.insert_textbox(
                rect,
                field.formatted_value,
                fontsize=font_size,
                align=align,
                fontname="helv",  # Standard standard-14 Helvetica
            )
            if rc < 0:
                # Negative return indicates text could not fit inside the specified rect
                raise RendererError(
                    f"Formatted value '{field.formatted_value}' does not fit in box for "
                    f"annotation '{field.annotation_id}' at page {field.page} {rect}"
                )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_file))
    except Exception as e:
        if isinstance(e, RendererError):
            raise
        raise RendererError(f"Error during PDF rendering: {e}") from e
    finally:
        doc.close()