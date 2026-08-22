"""High-level document processing and PDF generation pipeline."""

from pathlib import Path
from typing import Any, List, Union

from src.models import AnnotationDocument
from src.processor import ProcessedField, process_annotation
from src.renderer import render_fields


def render_document(
    data: Any,
    document: AnnotationDocument,
    template_path: Union[str, Path],
    output_path: Union[str, Path],
) -> List[ProcessedField]:
    """Execute the end-to-end tax annotation pipeline.

    1. Iterates over all annotations defined in the AnnotationDocument.
    2. Executes process_annotation() for each (evaluating conditions, resolving paths,
       merging defaults, and formatting values).
    3. Filters out skipped fields.
    4. Passes render-ready fields to render_fields().
    5. Saves the final filled PDF.

    Args:
        data: Structured JSON-compatible input data.
        document: Validated AnnotationDocument model instance.
        template_path: Path to the input PDF template.
        output_path: Path where the filled PDF will be saved.

    Returns:
        List[ProcessedField]: List of successfully rendered fields.
    """
    rendered_fields: List[ProcessedField] = []

    for annotation in document.annotations:
        result = process_annotation(data, annotation, document.defaults)
        if not result.skipped and result.processed_field is not None:
            rendered_fields.append(result.processed_field)

    render_fields(template_path, rendered_fields, output_path)
    return rendered_fields