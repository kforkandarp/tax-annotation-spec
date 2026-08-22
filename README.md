# Tax Form Annotation Specification & Reference Pipeline

A declarative, language-independent specification and Python reference implementation for resolving structured JSON input data, evaluating conditional visibility, formatting values, and rendering fields onto PDF form templates.

---

## 1. Project Overview
Filling tax forms programmatically requires decoupling data extraction and rendering rules from backend database schemas, application logic, and specific programming languages. 

This repository establishes a **JSON-based declarative annotation contract** that describes:
- **What** value to extract using a restricted JSONPath subset.
- **When** to render it using conditional evaluation rules.
- **How** to format it (text, currency, percentage, date, etc.).
- **Where** to place it using explicit PDF point bounding boxes.
- **How** to style it (font size, alignment).

The JSON Schema is the authoritative, platform-agnostic contract. The Python codebase serves as a reference implementation.

---

## 2. Problem Being Solved
Tax forms are strict visual grid layouts with distinct presentation requirements. Hardcoding coordinate mapping or data-formatting rules into application code creates tight coupling, prevents cross-language interoperability, and makes tax year or form revision updates difficult to maintain. 

This specification solves this problem by defining a portable declarative schema that separates form layout definitions from data ingestion and PDF rendering engines.

---

## 3. High-Level Architecture
The system is built as a pipeline of decoupled components with strict single-responsibility boundaries:

```
Structured Input Data + Annotation Document + PDF Template
↓
[ Models ]            (Pydantic validation)
↓
[ Resolver ]          (Restricted JSONPath traversal)
↓
[ Conditions ]         (Visibility evaluation)
↓
[ Formatter ]          (Precision display formatting)
↓
[ Processor ]          (Orchestration & default merging)
↓
[ Renderer ]          (PyMuPDF coordinate placement)
↓
Annotated Output PDF
```

### Component Responsibilities
- **`src.models`**: Pydantic v2 domain representations mirroring the JSON Schema with strict closed-model (`extra="forbid"`) boundaries and ID uniqueness enforcement.
- **`src.resolver`**: Traverses raw JSON dictionaries and lists using a restricted JSONPath subset without external dependencies.
- **`src.conditions`**: Evaluates single comparison rules (`equals`, `greater_than`, etc.) against resolved data to determine field visibility.
- **`src.formatter`**: Converts Python primitives into presentation strings using `Decimal` fixed-point arithmetic.
- **`src.processor`**: Coordinates condition checks, source resolution, single-level default merging, and formatting to produce a render-ready `ProcessedField`.
- **`src.renderer`**: Uses PyMuPDF to draw `ProcessedField` values inside bounded rectangles on the target PDF template.
- **`src.pipeline`**: Top-level entry point coordinating document-level processing and rendering.

---

## 4. Project Structure

```
tax-annotation-spec/
├── .gitignore
├── README.md
├── pyproject.toml
├── schema/
│   └── annotation.schema.json
├── examples/
│   ├── demo_form.pdf
│   ├── form_annotations.json
│   ├── render_demo.py
│   └── sample_data.json
├── src/
    ├── __init__.py
    ├── conditions.py
    ├── formatter.py
    ├── models.py
    ├── pipeline.py
    ├── processor.py
    ├── renderer.py
    └── resolver.py

```

---

## 5. Annotation Schema & Top-Level Structure
The JSON Schema Draft 2020-12 contract (`schema/annotation.schema.json`) enforces five mandatory top-level sections:

```json
{
  "schema_version": "1.0",
  "form": {
    "id": "GENERIC-TAX-01",
    "tax_year": 2025,
    "revision": "v1.0"
  },
  "coordinate_system": {
    "unit": "pt",
    "origin": "top-left"
  },
  "defaults": {
    "format": { "type": "text" },
    "style": { "font_size": 10.0, "alignment": "left" }
  },
  "annotations": [ ... ]
}
```

## 6. Supported JSONPath Subset
To guarantee cross-language predictability and prevent script-injection risks, the resolver enforces a strictly validated subset:
- Root: `$`
- Object properties: `$.taxpayer` or `$.taxpayer.income.wages`
- Zero-based array indexes: `$.dependents[0]` or `$.dependents[0].name`
- Property names must start with a letter/underscore followed by letters, digits, or underscores.
- **Not Supported by Design**: Wildcards (`*`), recursive descent (`..`), array slicing (`[:]`), filter expressions (`[?()]`), and embedded scripting.

## 7. Conditional Rendering
An annotation may define an optional `condition` block:
- **Supported Operators**: `equals`, `not_equals`, `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`.
- **Short-Circuit Semantics**: Conditions are evaluated before resolving or formatting the primary field. If a condition evaluates to `False`, the field is marked as skipped immediately.
- **Safe Fallback**: If a path referenced in a visibility condition does not exist in the data payload, the condition safely resolves to `False`.

## 8. Value Formatting
The formatter converts raw data into presentation strings using exact decimal handling:

| Format Type | Description | Key Defaults / Semantics | Example |
|---|---|---|---|
| text | Primitive string representation | Complex containers raise FormatError | "Jane" |
| integer | Thousands separators | Non-integral floats raise FormatError | 115000 → "115,000" |
| decimal | Fixed-point numeric | Defaults to decimal_places = 2 | 1234.5 → "1,234.50" |
| currency | Currency symbols + separators | Default: USD ($), decimal_places = 2 | 115000 → "$115,000.00" |
| percentage | Fractional input multiplied by 100 | Defaults to decimal_places = 2 | 0.15 → "15.00%" |
| date | ISO 8601 string parsing | Default: date_format = "%m/%d/%Y" | "2025-04-15" → "04/15/2025" |

Booleans are strictly validated to prevent Python from implicitly coercing `True`/`False` to `1`/`0` in numeric formats.

## 9. Positioning & Coordinate System
- **Unit**: PDF Points (`pt`, where $72\text{ pt} = 1\text{ inch}$).
- **Origin**: `top-left` $(0,0)$ located at the upper-left corner of the page ($+X$ rightward, $+Y$ downward).
- **Bounding Box**: Defined by `x`, `y`, `width` ($>0$), and `height` ($>0$).
- **Page Indexing**: Annotation pages are 1-based (`page: 1` corresponds to internal PDF index 0).

## 10. Defaults and Single-Level Overrides
Document-level defaults provide fallback values for `format` and `style`:
- **Precedence**: Annotation-level settings override matching document-level defaults.
- **Merging**: Property-level merge occurs non-mutatively without complex cascading or CSS inheritance rules.

## 11. PDF Rendering
- Utilizes PyMuPDF (`fitz`) as the single rendering engine.
- Overlays text onto the existing PDF template using `page.insert_textbox()`, preserving all vector lines, form titles, and background template contents.
- Supports text alignments: `left`, `center`, and `right`.
- Skipped annotations (due to false conditions or absent optional fields) are excluded from the rendering pass.

## 12. Local Setup & Execution Instructions (Windows)
Open PowerShell or Command Prompt in the repository root:

```cmd
:: 1. Create a virtual environment
python -m venv .venv

:: 2. Activate virtual environment
.venv\Scripts\activate

:: 3. Upgrade pip and install dependencies in editable mode
pip install --upgrade pip
pip install -e ".[dev]"
```


### Run the End-to-End Demo
```cmd
python -m examples.render_demo
```

The annotated PDF will be generated at:
`output/annotated_demo.pdf`

## 13. Design Decisions
- **Generic Over Form-Specific**: The schema and codebase make no assumptions about tax forms (e.g., IRS Form 1040) or jurisdictions.
- **Deterministic JSONPath**: A restricted path grammar ensures fast, secure, cross-language parsing without third-party JSONPath dependencies.
- **Exact Decimal Arithmetic**: Uses Python's `Decimal` module for currency, decimal, and percentage formatting to prevent IEEE-754 floating-point inaccuracies.
- **Decoupled Orchestration**: The renderer consumes pre-computed `ProcessedField` records and has zero knowledge of JSONPaths, conditions, or defaults.
- **Strict Typographical Bounds**: PyMuPDF standard-14 Helvetica (`helv`) is used to avoid external font file dependencies across platforms.

## 14. Limitations & Future Enhancements
- **Automatic Text Fitting**: Future iterations could dynamically adjust font sizes to fit constrained bounding boxes.
- **Custom Font Embedding**: Support for custom OTF/TTF fonts and explicit text colors/borders.
- **Complex Logic**: Future schema revisions could support composite boolean logic (AND/OR) for condition evaluation.
- **Visual Regression Testing**: Automated pixel-level diffing in CI for rendered PDFs.

---
