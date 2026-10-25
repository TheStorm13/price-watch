"""Exact observation prices shared by all marketplace adapters."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


def normalize_price(value: Decimal | int | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ValueError("Цена должна быть Decimal или целым числом")
    value = Decimal(value)
    if not value.is_finite() or value < 0 or value >= 10**12:
        raise ValueError("Цена должна быть конечной, неотрицательной и меньше 10^12")
    try:
        with localcontext() as context:
            context.prec = max(28, len(value.as_tuple().digits) + 2)
            result = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Некорректная цена") from exc
    if result >= 10**12:
        raise ValueError("Цена после округления должна быть меньше 10^12")
    return result.copy_abs() if result.is_zero() else result
