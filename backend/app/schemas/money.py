"""Upper bounds for money inputs, matching the NUMERIC columns they land in.

Without them an oversized amount passes validation and Postgres rejects the
write with `numeric field overflow` — a 500 instead of a 422 the client can
explain.
"""

from decimal import Decimal

MAX_NUMERIC_12_2 = Decimal("9999999999.99")
MAX_NUMERIC_14_2 = Decimal("999999999999.99")
MAX_INTEREST_RATE = Decimal("999.999")  # NUMERIC(6, 3)
