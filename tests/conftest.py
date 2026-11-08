import textwrap
from pathlib import Path

import pytest

CONFIG = """
[warehouse]
path = "wh.db"

[date_dimension]
start = "2026-01-01"
end = "2026-01-31"

[[dimensions]]
name = "dim_customer"
source = "customers.csv"
natural_key = ["customer_id"]
tracked = ["segment"]

[dimensions.columns]
customer_id = "str"
nickname = "str"
segment = "str"

[[dimensions.rules]]
column = "customer_id"
rule = "unique"

[[facts]]
name = "fact_orders"
source = "orders.csv"
watermark = "ordered_on"
measures = ["amount"]

[facts.lookups]
customer_id = "dim_customer"

[facts.columns]
order_id = "str"
ordered_on = "date"
customer_id = "str"
amount = "float"

[[facts.rules]]
column = "amount"
rule = "min"
value = 0
"""


def write(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path):
    write(tmp_path / "config.toml", CONFIG)
    write(tmp_path / "customers.csv", """
        customer_id,nickname,segment
        C1,alpha,retail
        C2,beta,corporate
    """)
    write(tmp_path / "orders.csv", """
        order_id,ordered_on,customer_id,amount
        O1,2026-01-05,C1,10.5
        O2,2026-01-06,C2,20
        O3,2026-01-07,C9,5
    """)
    return tmp_path
