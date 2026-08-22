"""Pydantic representation of the language-independent tax annotation contract."""

from enum import Enum
from typing import Annotated, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JSONPATH_REGEX = r"^\$(\.[a-zA-Z_][a-zA-Z0-9_]*|\[[0-9]+\])*$"


class CoordinateUnit(str, Enum):
    PT = "pt"


class CoordinateOrigin(str, Enum):
    TOP_LEFT = "top-left"


class FormatType(str, Enum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"


class TextAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"


class FormInfo(BaseModel): # actual data models
    model_config = ConfigDict(extra="forbid") # this corresponds to additionalProperties : False in JSON Schema, which means that any extra fields not defined in the model will raise a validation error.

    id: str
    tax_year: Annotated[int, Field(ge=1900)]
    revision: Optional[str] = None


class CoordinateSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: CoordinateUnit # it must be a coordinate unit, which is defined in the CoordinateUnit enum
    origin: CoordinateOrigin


class Format(BaseModel): # how the resolved value should be converted into display text.
    model_config = ConfigDict(extra="forbid") # Setting extra="forbid" causes Pydantic to raise a ValidationError instantly if any unrecognised fields are passed in the payload.

    type: FormatType
    currency: Optional[Annotated[str, Field(pattern=r"^[A-Z]{3}$")]] = None # the regex pattern means exactly 3 uppper case letters
    decimal_places: Optional[Annotated[int, Field(ge=0)]] = None 
    date_format: Optional[str] = None


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_size: Optional[Annotated[float, Field(gt=0)]] = None
    alignment: Optional[TextAlignment] = None


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Optional[Format] = None
    style: Optional[Style] = None


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, Field(pattern=JSONPATH_REGEX)]
    operator: ConditionOperator
    value: Union[str, int, float, bool]


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: Annotated[float, Field(gt=0)]
    height: Annotated[float, Field(gt=0)]


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: Annotated[int, Field(ge=1)]
    box: BoundingBox


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    source: Annotated[str, Field(pattern=JSONPATH_REGEX)]
    required: bool
    condition: Optional[Condition] = None
    target: Target
    format: Optional[Format] = None
    style: Optional[Style] = None


class AnnotationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid") # Don't allow random fields that aren't part of our defined structure.

    schema_version: str
    form: FormInfo # nested model, which means that the form field is itself a Pydantic model of type FormInfo
    coordinate_system: CoordinateSystem
    defaults: Defaults
    annotations: Annotated[List[Annotation], Field(min_length=1)]

    @model_validator(mode="after") # decorator used to run custom validation logic across the entire model as a whole, rather than checking just a single field in isolation.

    # The mode="after" argument indicates that this validator should be executed after the standard validation process has completed, allowing you to perform checks that depend on the fully validated state of the model.

    # "After you've finished constructing and validating the entire AnnotationDocument, run this custom check."

    def verify_unique_annotation_ids(self) -> "AnnotationDocument": # self = entire AnnotationDocument that pydantic just created
        seen_ids = set()
        duplicates = set()
        for ann in self.annotations: # self.annotations is a list of Annotation objects, and ann is each individual Annotation object in that list
            if ann.id in seen_ids:
                duplicates.add(ann.id)
            seen_ids.add(ann.id)
        if duplicates:
            raise ValueError(f"Annotation IDs must be unique. Duplicate IDs: {sorted(duplicates)}")
        return self