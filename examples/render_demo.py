"""Runnable demonstration of the declarative PDF tax annotation pipeline."""

import json
from pathlib import Path
import fitz  # PyMuPDF

from src.models import AnnotationDocument
from src.pipeline import render_document

BASE_DIR = Path(__file__).parent.parent
SAMPLE_DATA_FILE = BASE_DIR / "examples" / "sample_data.json"
ANNOTATIONS_FILE = BASE_DIR / "examples" / "form_annotations.json"
TEMPLATE_PDF_FILE = BASE_DIR / "examples" / "demo_form.pdf"
OUTPUT_PDF_FILE = BASE_DIR / "output" / "annotated_demo.pdf"


def create_demo_template_if_missing(path: Path) -> None:
    """Create a clean 2-page generic demo form PDF if it does not already exist."""
    if path.exists():
        return

    doc = fitz.open()

    # Page 1: Primary Taxpayer Info
    # in pdfs, Top-Left Corner: PDF engines place (0,0) at the top-left corner of the page. x increases right, y increases downwards.
    # everything is measured in points (1 point = 1/72 inch). Standard US Letter size is 612 x 792 points (8.5 x 11 inches).

    page1 = doc.new_page(width=612, height=792)  # Standard US Letter (8.5 x 11 in)
    page1.insert_text((54, 70), "SAMPLE TAXPAYER INFORMATION FORM", fontsize=16, fontname="helv")
    page1.insert_text((54, 90), "Demonstration Form (Generic Tax Year)", fontsize=10, fontname="helv")
    page1.draw_line((54, 105), (558, 105), color=(0.2, 0.2, 0.2), width=1) # line from x = 54 to x = 558 

    labels_page1 = [
        (54, 152, "Taxpayer Name:"),
        (54, 187, "Filing Status:"),
        (54, 222, "Annual Wages:"),
        (54, 257, "Foreign Income Rate:"),
        (54, 292, "Spouse Name:"),
    ]
    boxes_page1 = [
        (220, 140, 470, 158),
        (220, 175, 470, 193),
        (220, 210, 470, 228),
        (220, 245, 470, 263),
        (220, 280, 470, 298),
    ] # Coordinates for the input boxes (x0, y0, x1, y1); text starts at x = 54 and y = 152; rectangles are drawn around the input areas
     # starting from x0 = 220 and y0 = 140 for the first box, to x1 = 470 and y1 = 158 for the first box, and so on for the other boxes.

    for x, y, label in labels_page1:
        page1.insert_text((x, y), label, fontsize=10, fontname="helv") # this actually draws the text labels on the PDF page at the specified coordinates with the specified font size and font name
    for rect in boxes_page1:
        page1.draw_rect(fitz.Rect(*rect), color=(0.7, 0.7, 0.7), width=0.75) # this draws the rectangles (input boxes) on the PDF page at the specified coordinates with the specified color and line width

    page1.insert_text((54, 740), "Page 1 of 2", fontsize=9, fontname="helv")

    # Page 2: Schedule & Dependents
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((54, 70), "SCHEDULE A - DEPENDENTS & SUPPLEMENTAL", fontsize=14, fontname="helv")
    page2.draw_line((54, 95), (558, 95), color=(0.2, 0.2, 0.2), width=1)

    page2.insert_text((54, 152), "Primary Dependent Name:", fontsize=10, fontname="helv")
    page2.draw_rect(fitz.Rect(220, 140, 470, 158), color=(0.7, 0.7, 0.7), width=0.75)
    page2.insert_text((54, 740), "Page 2 of 2", fontsize=9, fontname="helv")

    path.parent.mkdir(parents=True, exist_ok=True) # this creates the parent directories for the path if they do not already exist
    doc.save(str(path)) # this saves the PDF document to the specified path
    doc.close()
    print(f"Created demo template at: {path}")


def main() -> None:
    print("Running PDF Annotation Pipeline Demo...")

    create_demo_template_if_missing(TEMPLATE_PDF_FILE)

    with open(SAMPLE_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(ANNOTATIONS_FILE, "r", encoding="utf-8") as f:
        annotations_dict = json.load(f)

    doc_model = AnnotationDocument.model_validate(annotations_dict) # We're taking the entire JSON document and asking Pydantic: 
    # "Does this conform to our Python representation of the annotation contract?"

    rendered_fields = render_document(
        data=data,
        document=doc_model,
        template_path=TEMPLATE_PDF_FILE,
        output_path=OUTPUT_PDF_FILE,
    )

    print(f"\nSuccessfully rendered {len(rendered_fields)} fields into: {OUTPUT_PDF_FILE}")
    for rf in rendered_fields:
        align_str = rf.style.alignment.value if rf.style.alignment else "left"
        print(f"  - [{rf.annotation_id}] (Page {rf.page}, Align: {align_str}) -> '{rf.formatted_value}'")


if __name__ == "__main__":
    main()