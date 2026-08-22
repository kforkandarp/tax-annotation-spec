"""Orchestration engine for resolving, evaluating, and formatting single annotations."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

from src.conditions import evaluate_condition
from src.formatter import format_value
from src.models import Annotation, BoundingBox, Defaults, Format, Style
from src.resolver import PathResolutionError, resolve


class ProcessorError(Exception):
    """Base exception for annotation processing errors."""


class MissingRequiredSourceError(ProcessorError): # The annotation says this data is required, but we couldn't find it.
    """Raised when a required annotation source path cannot be resolved from data."""


class MissingFormatSpecificationError(ProcessorError): # I found the value, but I don't know how you want me to display it.
    """Raised when neither the annotation nor defaults provide a format specification."""


class ProcessedField(BaseModel): # The final package of information that the renderer needs.
    """Render-ready data contract consumed by the downstream PDF renderer."""

    model_config = ConfigDict(extra="forbid")

    annotation_id: str
    label: str
    page: int
    box: BoundingBox
    formatted_value: str
    style: Style # alignment and font size


class ProcessResult(BaseModel): # outcome of processing an annotation
    """Outcome of processing an annotation, indicating rendered field or skip decision."""

    model_config = ConfigDict(extra="forbid")

    processed_field: Optional[ProcessedField] = None
    skipped: bool = False
    reason: Optional[str] = None


def _resolve_effective_format(
    annotation_format: Optional[Format], default_format: Optional[Format]
) -> Format:
    """Merge document default format and annotation format override into a new Format instance."""
    if annotation_format is None and default_format is None:
        raise MissingFormatSpecificationError(
            "Cannot format field: no format specified on annotation or document defaults"
        )
    if annotation_format is None:
        return default_format.model_copy()
    if default_format is None:
        return annotation_format.model_copy()

    # Annotation-level values override matching document defaults
    # Start with the document defaults, then replace anything the annotation explicitly specifies.
    merged_data = default_format.model_dump(exclude_unset=True) # model_dump converts to dictionary
    override_data = annotation_format.model_dump(exclude_unset=True)
    merged_data.update(override_data)

    return Format.model_validate(merged_data) # Take this normal dictionary and turn it back into a validated Format Pydantic object.


def _resolve_effective_style(
    annotation_style: Optional[Style], default_style: Optional[Style]
) -> Style:
    """Merge document default style and annotation style override into a new Style instance."""
    if annotation_style is None and default_style is None:
        return Style()
    if annotation_style is None:
        return default_style.model_copy()
    if default_style is None:
        return annotation_style.model_copy()

    # Annotation-level values override matching document defaults
    merged_data = default_style.model_dump(exclude_unset=True)
    override_data = annotation_style.model_dump(exclude_unset=True)
    merged_data.update(override_data)

    return Style.model_validate(merged_data)


def process_annotation(
    data: Any,
    annotation: Annotation,
    defaults: Defaults,
) -> ProcessResult:
    """Process a single annotation against input data and document defaults.

    Pipeline execution order:
    1. Condition check (if condition fails, skip immediately).
    2. Resolve source path (if missing: skip when optional, raise when required).
    3. Merge effective format and style.
    4. Format the resolved value into display text.
    5. Return a render-ready ProcessedField wrapped in ProcessResult.

    Args:
        data: Structured JSON-compatible input data.
        annotation: Validated Annotation model.
        defaults: Validated document-level Defaults model.

    Returns:
        ProcessResult: Either a populated processed_field or a skipped outcome.

    Raises:
        MissingRequiredSourceError: If a required source path is unresolvable.
        MissingFormatSpecificationError: If no format can be derived.
        InvalidPathSyntaxError: If JSONPath syntax is malformed.
        ConditionEvaluationError: If condition evaluation encounters incompatible types.
        FormatError: If formatting the resolved value fails.
    """
    # 1. Condition check
    if annotation.condition is not None:
        if not evaluate_condition(data, annotation.condition):
            return ProcessResult(skipped=True, reason="condition_not_met")

    # 2. Resolve source path
    try:
        raw_value = resolve(data, annotation.source)
    except PathResolutionError as e:
        if annotation.required:
            raise MissingRequiredSourceError(
                f"Required source '{annotation.source}' for annotation '{annotation.id}' "
                f"could not be resolved from input data: {e}"
            ) from e
        return ProcessResult(skipped=True, reason="optional_source_missing")

    # 3. Resolve effective format & style
    effective_format = _resolve_effective_format(annotation.format, defaults.format)
    effective_style = _resolve_effective_style(annotation.style, defaults.style)

    # 4. Format resolved value
    formatted_text = format_value(raw_value, effective_format)

    # 5. Build render-ready field
    field = ProcessedField(
        annotation_id=annotation.id,
        label=annotation.label,
        page=annotation.target.page,
        box=annotation.target.box.model_copy(),
        formatted_value=formatted_text,
        style=effective_style,
    )
    return ProcessResult(processed_field=field, skipped=False)