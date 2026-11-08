"""Construct a run's adapters with a single explicit Chrome owner."""
from ..application.product_service import ConnectorRegistry
from ..browser.session import ChromeSession
from .wildberries.client import AsyncWildberriesClient
from .wildberries.connector import WildberriesConnector
from .ozon import AsyncOzonClient, OzonConnector
from .aliexpress.client import AsyncAliExpressClient
from .aliexpress.connector import AliExpressConnector


def build_connectors(marketplaces, *, profile_dir, challenge_handler=None, chrome_binary=None,
                     chrome_platform='x11', browser_channel='chrome', headless=False, virtual_display=False):
    marketplaces = set(marketplaces)
    options = dict(profile_dir=profile_dir, chrome_binary=chrome_binary, chrome_platform=chrome_platform,
                   browser_channel=browser_channel, headless=headless, virtual_display=virtual_display)
    session = ChromeSession(**options)
    clients = {'ozon': (AsyncOzonClient, OzonConnector), 'aliexpress': (AsyncAliExpressClient, AliExpressConnector), 'wildberries': (AsyncWildberriesClient, WildberriesConnector)}
    return ConnectorRegistry([
        connector(client(**options, session=session, challenge_handler=challenge_handler))
        for marketplace, (client, connector) in clients.items() if marketplace in marketplaces
    ], run_session=session.collection_session)
