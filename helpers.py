# --------------------------------------------------
# external
# --------------------------------------------------
import re
import time
import logging
from types import TracebackType
from typing import Type, Optional


def parse_money(value: str) -> float:
    """Parse a money string and return a float. Removes any non-numeric characters except for '.' and '-'.

    Args:
        value (str): The money string to parse.

    Returns:
        float: The parsed money value as a float. Returns 0.0 if the input is empty or None.
    """
    if not value:
        return 0.0
    return float(re.sub(r"[^\d\.-]", "", value))


class LogTimer:
    """Context manager for logging the execution time of a block of code.

    Usage:
        with log_timer("My operation"):
            # some code to time
    """

    log = logging.getLogger(__name__)

    def __init__(self, msg: str = "Execution"):
        self.msg = msg

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        elapsed = time.perf_counter() - self.start
        logging.info(f"{self.msg} took {elapsed:.4f} seconds")
