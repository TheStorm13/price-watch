"""Backward-compatible facade for the Ozon transport."""

import sys
from pathlib import Path
from typing import Callable, Optional, Union

from marketplace_connector.connectors.ozon.client import OzonClient
from marketplace_connector.ports.challenge import CallableChallengeHandler


Confirmation = Callable[[str], str]


def wait_for_user(message: str) -> str:
    """Show interactive instructions without contaminating JSON stdout."""
    print(message, file=sys.stderr, end="", flush=True)
    return input()


class OzonRawCardParser(OzonClient):
    """Compatibility wrapper; new code should use ``OzonClient``."""

    def __init__(
        self,
        profile_dir: Union[str, Path],
        confirmation: Confirmation = wait_for_user,
        chrome_binary: Optional[Union[str, Path]] = None,
        json_wait_seconds: int = 15,
        chrome_platform: str = "x11",
    ):
        super().__init__(
            profile_dir=profile_dir,
            challenge_handler=CallableChallengeHandler(confirmation),
            chrome_binary=chrome_binary,
            json_wait_seconds=json_wait_seconds,
            chrome_platform=chrome_platform,
        )

    def fetch(self, article: Union[str, int]) -> str:
        return self.fetch_raw_text(article)

    normalize_article = staticmethod(OzonClient.normalize_product_id)
