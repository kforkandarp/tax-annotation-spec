"""Condition evaluation engine for declarative tax form annotations."""

# conditions.py calls resolver.py so that resolving is left to resolver.py and conditions file doesn't implement them

from typing import Any

from src.models import Condition, ConditionOperator
from src.resolver import PathResolutionError, resolve


class ConditionEvaluationError(Exception): # "The condition itself is valid, but we can't perform the requested comparison because the values have incompatible types."
    """Raised when condition evaluation fails due to incompatible operand types."""


def evaluate_condition(data: Any, condition: Condition) -> bool: # does this condition pass --- this is the main function
    """Evaluate a single Condition against structured input data.

    Args:
        data: Structured JSON-compatible data (dict, list, or scalar).
        condition: Condition model instance defining source, operator, and target value. Validated condition object

    Returns:
        bool: True if the resolved value satisfies the condition, False otherwise.
              If the condition.source cannot be resolved against the data, returns False.

    Raises:
        InvalidPathSyntaxError: If condition.source has an invalid JSONPath syntax.
        ConditionEvaluationError: If types are incompatible for relational comparison.
    """
    try:
        resolved_value = resolve(data, condition.source)
    except PathResolutionError: # catches all 3 of the errors defined under it -- defined in resolver.py
        # Safe fallback: Missing/unresolvable source in a visibility condition yields False
        return False

    op = condition.operator
    target_value = condition.value

    # Strict type guarding: Prevent Python from treating bools as numeric ints (e.g. True == 1) THIS IS BECAUSE PYTHON'S BOOL IS A SUBCLASS OF INT

    if isinstance(resolved_value, bool) or isinstance(target_value, bool): # "Is either of the two values a boolean?"
        if not (isinstance(resolved_value, bool) and isinstance(target_value, bool)): # "Are both values actually booleans?" if yes then we dont need to compare it and we go to line 52 ( equality operators)
            if op == ConditionOperator.EQUALS: # overriding the behaviour -> true == 1 is true in python 
                return False
            if op == ConditionOperator.NOT_EQUALS:
                return True
            raise ConditionEvaluationError( # "You asked me to perform a numeric/relational comparison between a boolean and a non-boolean value. That's not allowed."
                f"Cannot perform relational comparison '{op.value}' between boolean and non-boolean: "
                f"{type(resolved_value).__name__} and {type(target_value).__name__}"
            )

    # 1. Equality operators
    if op == ConditionOperator.EQUALS:
        return resolved_value == target_value
    if op == ConditionOperator.NOT_EQUALS:
        return resolved_value != target_value

    # 2. Relational operators (numeric comparisons only)
    is_resolved_num = isinstance(resolved_value, (int, float)) and not isinstance(resolved_value, bool)
    is_target_num = isinstance(target_value, (int, float)) and not isinstance(target_value, bool)

    if not (is_resolved_num and is_target_num):
        raise ConditionEvaluationError(
            f"Relational operator '{op.value}' requires numeric operands, got "
            f"'{type(resolved_value).__name__}' and '{type(target_value).__name__}'"
        )

    if op == ConditionOperator.GREATER_THAN:
        return resolved_value > target_value
    if op == ConditionOperator.GREATER_THAN_OR_EQUAL:
        return resolved_value >= target_value
    if op == ConditionOperator.LESS_THAN:
        return resolved_value < target_value
    if op == ConditionOperator.LESS_THAN_OR_EQUAL:
        return resolved_value <= target_value

    raise ConditionEvaluationError(f"Unsupported condition operator: '{op}'")

