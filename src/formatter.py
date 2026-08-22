"""Value formatting engine for converting resolved Python values into display strings."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, Union

from src.models import Format, FormatType

CURRENCY_SYMBOLS: Dict[str, str] = { # if currency code is not here, then code falls back to its original currency code 
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "C$",
    "AUD": "A$",
}


class FormatError(Exception): # "The value I received cannot be formatted according to the requested format."
    """Raised when a value cannot be formatted according to the format specification."""


def _ensure_numeric(value: Any, format_name: str) -> Union[int, float, Decimal]: # Make sure a value is actually numeric before we perform numeric formatting.
    """Validate that value is numeric and explicitly not a boolean, preserving numeric type and precision."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise FormatError(
            f"Format type '{format_name}' requires numeric input, got {type(value).__name__} ({value!r})"
        )
    return value


def _to_decimal(value: Union[int, float, Decimal]) -> Decimal:
    """Convert an int, float, or Decimal into a Decimal object without floating-point artifacts."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Convert float via repr/str to avoid binary precision artifacts
        return Decimal(str(value))
    return Decimal(value)


def _format_with_separators(d: Decimal, places: int) -> str: # Take a number and produce a properly formatted number with commas and exactly the requested number of decimal places.
    """Format a Decimal with thousands separators and exact fixed decimal places using standard rounding."""
    quantizer = Decimal("1") if places == 0 else Decimal(f"1e-{places}") # This determines how many decimal places we want.
    try:
        quantized = d.quantize(quantizer, rounding=ROUND_HALF_UP) # "Round this Decimal to the number of decimal places specified by this quantizer."
    except InvalidOperation as e:
        raise FormatError(f"Failed to quantize decimal value {d} to {places} places: {e}") from e

    # Separate sign
    is_neg = quantized < 0
    abs_d = abs(quantized)

    sign, digits, exp = abs_d.as_tuple() # Decimal.as_tuple() exposes the internal representation of the Decimal.
    digits_str = "".join(str(digit) for digit in digits)

    if exp >= 0:
        int_part = digits_str + ("0" * exp)
        frac_part = ""
    else:
        # Number of fractional digits is -exp
        frac_len = -exp # if exp = -2 for 123.43 ; then, There should be 2 digits after the decimal point. ; frac_len = -(-2) = 2
        if len(digits_str) <= frac_len:
            int_part = "0"
            frac_part = ("0" * (frac_len - len(digits_str))) + digits_str
        else:
            int_part = digits_str[:-frac_len]
            frac_part = digits_str[-frac_len:]

    # Add thousands separators to integer part
    int_with_commas = f"{int(int_part):,}"

    if places > 0:
        formatted = f"{int_with_commas}.{frac_part}"
    else:
        formatted = int_with_commas

    return f"-{formatted}" if is_neg else formatted


def format_value(value: Any, format_spec: Format) -> str: # format_spec is the formatting instructions
    """Format a resolved Python value into its display string representation.

    Args:
        value: The resolved Python primitive value.
        format_spec: Validated Format model instance.

    Returns:
        str: Formatted display string.

    Raises:
        FormatError: If the input value is incompatible with the specified format.
    """
    fmt_type = format_spec.type

    # 1. TEXT
    if fmt_type == FormatType.TEXT:
        if isinstance(value, (dict, list)):
            raise FormatError(f"Cannot format complex container {type(value).__name__} as text")
        if value is None:
            return ""
        return str(value)

    # 2. INTEGER
    if fmt_type == FormatType.INTEGER:
        num = _ensure_numeric(value, "integer")
        if isinstance(num, (float, Decimal)):
            if num % 1 != 0:
                raise FormatError(f"Cannot format non-integral number {value} as integer")
        return f"{int(num):,}"

    # 3. DECIMAL
    if fmt_type == FormatType.DECIMAL:
        num = _ensure_numeric(value, "decimal")
        places = format_spec.decimal_places if format_spec.decimal_places is not None else 2
        d = _to_decimal(num)
        return _format_with_separators(d, places)

    # 4. CURRENCY
    if fmt_type == FormatType.CURRENCY:
        num = _ensure_numeric(value, "currency")
        places = format_spec.decimal_places if format_spec.decimal_places is not None else 2
        currency_code = (format_spec.currency or "USD").upper()

        d = _to_decimal(num)
        is_negative = d < 0
        abs_formatted = _format_with_separators(abs(d), places)

        if currency_code in CURRENCY_SYMBOLS:
            symbol = CURRENCY_SYMBOLS[currency_code]
            formatted = f"{symbol}{abs_formatted}"
        else:
            formatted = f"{currency_code} {abs_formatted}"

        return f"-{formatted}" if is_negative else formatted

    # 5. PERCENTAGE
    if fmt_type == FormatType.PERCENTAGE:
        num = _ensure_numeric(value, "percentage")
        places = format_spec.decimal_places if format_spec.decimal_places is not None else 2
        d = _to_decimal(num) * Decimal("100")
        formatted = _format_with_separators(d, places)
        return f"{formatted}%"

    # 6. DATE
    if fmt_type == FormatType.DATE:
        target_format = format_spec.date_format or "%m/%d/%Y"
        if isinstance(value, (datetime, date)):
            dt = value
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError as e:
                raise FormatError(f"Cannot parse date string '{value}': {e}") from e
        else:
            raise FormatError(f"Format type 'date' requires ISO date string or date object, got {type(value).__name__}")
        return dt.strftime(target_format)

    raise FormatError(f"Unsupported format type: {fmt_type}")