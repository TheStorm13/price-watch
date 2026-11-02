"""Small diagnostic examples; durable target results remain authoritative."""
import json

MAX_ERRORS = 20
MAX_DIAGNOSTIC_BYTES = 128 * 1024
MAX_ERROR_BYTES = 6000


def bounded_error(error: dict) -> tuple[dict, bool]:
    limits = {'marketplace': 64, 'externalId': 512, 'at': 64,
              'type': 128, 'message': 1024, 'traceback': 4096}
    result = {'cardId': error.get('cardId')}
    if not isinstance(result['cardId'], (int, type(None))):
        result['cardId'] = None
    if 'variantId' in error:
        result['variantId'] = error['variantId'] if isinstance(error['variantId'], int) else None
    shortened = False
    for key, limit in limits.items():
        value = error.get(key)
        if value is None:
            result[key] = None
            continue
        raw = str(value)
        # PostgreSQL jsonb cannot represent U+0000, even JSON-escaped.
        sanitized = raw.replace('\x00', '\ufffd')
        shortened |= sanitized != raw
        encoded = sanitized.encode('utf-8', errors='replace')
        shortened |= len(encoded) > limit
        result[key] = encoded[:limit].decode('utf-8', errors='ignore')
    # Escaped control characters may occupy more JSON bytes than UTF-8 text.
    for key in ('traceback', 'message', 'externalId', 'type', 'at', 'marketplace'):
        while len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_ERROR_BYTES and result[key]:
            result[key] = result[key][:len(result[key]) // 2]
            shortened = True
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_ERROR_BYTES:
        result['cardId'] = None
        shortened = True
    return result, shortened
