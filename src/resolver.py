"""JSONPath subset resolver for structured JSON-compatible Python data structures."""

import re
from typing import Any, List, Union
# any: Used because data can legitimately be many different Python types:
# List[Union[str, int]] means: a list containing strings and/or integers.

from src.models import JSONPATH_REGEX

_JSONPATH_PATTERN = re.compile(JSONPATH_REGEX)
_TOKEN_PATTERN = re.compile(r"\.([a-zA-Z_][a-zA-Z0-9_]*)|\[([0-9]+)\]")


class ResolverError(Exception):
    """Base exception for all path resolution failures."""


class InvalidPathSyntaxError(ResolverError): # the parh itself is invalid
    """Raised when the path syntax violates the supported JSONPath subset."""


class PathResolutionError(ResolverError): 
    """Raised when a valid path cannot be resolved against the given data."""


class MissingPropertyError(PathResolutionError): # The path is valid, but the requested dictionary key doesn't exist. 
    # $.taxpayer.income.salary but the data contains only: income: wages: 115000. There is no salary.
    """Raised when an object property is missing."""


class IndexOutOfBoundsError(PathResolutionError): # The path is valid and we're accessing an array, but the requested index doesn't exist.
    """Raised when an array index is out of bounds."""


class TypeMismatchError(PathResolutionError): # The path says to perform an operation that doesn't make sense for the current data type.
    """Raised when traversing an unexpected data type (e.g., indexing a scalar)."""


def _parse_tokens(path: str) -> List[Union[str, int]]:
    # input: "$.dependents[0].name"
    # output: ["dependents", 0, "name"] --> list containing strings and integers, representing the property names and array indices in the path.

    """Validate path syntax and parse into property names and integer array indices."""
    if not isinstance(path, str) or not _JSONPATH_PATTERN.fullmatch(path): #  fullmatch => Does the entire path conform to our grammar?
        # is path a string? Does it match the regex for our supported JSONPath subset?
        raise InvalidPathSyntaxError(f"Invalid JSONPath syntax: '{path}'")

    tokens: List[Union[str, int]] = []
    # Match every component following '$'
    for prop, idx in _TOKEN_PATTERN.findall(path[1:]): # path[1:] skips the leading '$' character, which is always present in valid paths.
        if prop:
            tokens.append(prop)
        elif idx:
            tokens.append(int(idx))
    return tokens


def resolve(data: Any, path: str) -> Any:
    """Resolve a restricted JSONPath expression against a structured data payload.

    Args:
        data: Root structured input data (dict, list, or scalar). This is the actual backend data
        path: Restricted JSONPath expression starting with '$'.

    Returns:
        The exact underlying Python value preserving original types.

    Raises:
        InvalidPathSyntaxError: If path does not match the supported syntax.
        MissingPropertyError: If a referenced object key does not exist.
        IndexOutOfBoundsError: If an array index is out of range.
        TypeMismatchError: If traversing an object key on non-dict or index on non-list.
    """
    tokens = _parse_tokens(path) # tokens is a list of string and integer values representing the property names and array indices in the path.
    current = data # "Where am I currently standing inside the data?"; initially, we start at the root of the data structure.

    for i, token in enumerate(tokens): # i tells us which step we are at, i = 0, i = 1 etc
        if isinstance(token, str):
            if not isinstance(current, dict):
                traversed = "$" + "".join(
                    f".{t}" if isinstance(t, str) else f"[{t}]" for t in tokens[:i]
                )
                raise TypeMismatchError(
                    f"Cannot access property '{token}' on non-object value at '{traversed}': "
                    f"type {type(current).__name__}"
                )
            if token not in current:
                raise MissingPropertyError(f"Property '{token}' not found in object")
            current = current[token]

        elif isinstance(token, int):
            if not isinstance(current, list):
                traversed = "$" + "".join(
                    f".{t}" if isinstance(t, str) else f"[{t}]" for t in tokens[:i]
                )
                raise TypeMismatchError(
                    f"Cannot index non-array value at '{traversed}' with index [{token}]: "
                    f"type {type(current).__name__}"
                )
            if token < 0 or token >= len(current):
                raise IndexOutOfBoundsError(
                    f"Array index [{token}] out of bounds (length: {len(current)})"
                )
            current = current[token]

    return current