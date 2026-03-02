"""
Polymarket CLOB MCP Server
--------------------------
Exposes the py-clob-client as an MCP (Model Context Protocol) skill so that
AI agents can interact with the Polymarket Central Limit Order Book.

Environment variables
---------------------
CLOB_API_URL      Base URL of the CLOB API  (default: https://clob.polymarket.com)
CHAIN_ID          Polygon chain ID           (default: 137)
PK                Wallet private key         (required for L1/L2 operations)
CLOB_API_KEY      CLOB API key               (required for L2 operations)
CLOB_SECRET       CLOB API secret            (required for L2 operations)
CLOB_PASS_PHRASE  CLOB API passphrase        (required for L2 operations)

Usage
-----
Run as a standalone stdio MCP server:
    python mcp_server.py

Or mount it inside a larger FastMCP application:
    from mcp_server import mcp
"""

import os
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    OpenOrderParams,
    OrderArgs,
    TradeParams,
)
from py_clob_client.constants import POLYGON

load_dotenv()

# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

mcp = FastMCP("polymarket-clob")

# ---------------------------------------------------------------------------
# Lazy client factory
# ---------------------------------------------------------------------------

_client: Optional[ClobClient] = None


def _get_client() -> ClobClient:
    """Return a cached ClobClient, initialised from environment variables."""
    global _client
    if _client is not None:
        return _client

    host = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
    key = os.getenv("PK")
    chain_id = int(os.getenv("CHAIN_ID", str(POLYGON)))

    api_key = os.getenv("CLOB_API_KEY")
    api_secret = os.getenv("CLOB_SECRET")
    api_passphrase = os.getenv("CLOB_PASS_PHRASE")

    creds: Optional[ApiCreds] = None
    if api_key and api_secret and api_passphrase:
        creds = ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        )

    _client = ClobClient(host, key=key, chain_id=chain_id if key else None, creds=creds)
    return _client


# ---------------------------------------------------------------------------
# Public / L0 tools  (no authentication required)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_ok() -> dict:
    """Health-check the Polymarket CLOB API. Returns the server status."""
    return _get_client().get_ok()


@mcp.tool()
def get_server_time() -> dict:
    """Return the current timestamp reported by the Polymarket CLOB server."""
    return _get_client().get_server_time()


@mcp.tool()
def get_markets(next_cursor: str = "MA==") -> dict:
    """
    Return a page of active Polymarket markets.

    Args:
        next_cursor: Pagination cursor returned from the previous call.
                     Pass the default value "MA==" to start from the beginning.
    """
    return _get_client().get_markets(next_cursor=next_cursor)


@mcp.tool()
def get_simplified_markets(next_cursor: str = "MA==") -> dict:
    """
    Return a page of active Polymarket markets in simplified form.

    Args:
        next_cursor: Pagination cursor. Pass "MA==" to start from the beginning.
    """
    return _get_client().get_simplified_markets(next_cursor=next_cursor)


@mcp.tool()
def get_market(condition_id: str) -> dict:
    """
    Return full details for a single market.

    Args:
        condition_id: The condition ID of the market.
    """
    return _get_client().get_market(condition_id)


@mcp.tool()
def get_order_book(token_id: str) -> dict:
    """
    Return the current order book (bids and asks) for the given token.

    Args:
        token_id: The token ID of the conditional token asset.
    """
    book = _get_client().get_order_book(token_id)
    if book is None:
        return {}
    return {
        "market": book.market,
        "asset_id": book.asset_id,
        "hash": book.hash,
        "timestamp": book.timestamp,
        "tick_size": book.tick_size,
        "bids": [{"price": l.price, "size": l.size} for l in (book.bids or [])],
        "asks": [{"price": l.price, "size": l.size} for l in (book.asks or [])],
    }


@mcp.tool()
def get_midpoint(token_id: str) -> dict:
    """
    Return the mid-market price for the given token.

    Args:
        token_id: The token ID of the conditional token asset.
    """
    return _get_client().get_midpoint(token_id)


@mcp.tool()
def get_price(token_id: str, side: str) -> dict:
    """
    Return the best available price on the given side of the market.

    Args:
        token_id: The token ID of the conditional token asset.
        side:     "BUY" or "SELL".
    """
    return _get_client().get_price(token_id, side)


@mcp.tool()
def get_spread(token_id: str) -> dict:
    """
    Return the bid-ask spread for the given token.

    Args:
        token_id: The token ID of the conditional token asset.
    """
    return _get_client().get_spread(token_id)


@mcp.tool()
def get_tick_size(token_id: str) -> str:
    """
    Return the minimum tick size for the given token.

    Args:
        token_id: The token ID of the conditional token asset.
    """
    return _get_client().get_tick_size(token_id)


@mcp.tool()
def get_last_trade_price(token_id: str) -> dict:
    """
    Return the price of the most recent trade for the given token.

    Args:
        token_id: The token ID of the conditional token asset.
    """
    return _get_client().get_last_trade_price(token_id)


@mcp.tool()
def get_market_trades_events(condition_id: str) -> dict:
    """
    Return the live trade events for a market.

    Args:
        condition_id: The condition ID of the market.
    """
    return _get_client().get_market_trades_events(condition_id)


# ---------------------------------------------------------------------------
# Authenticated / L2 tools  (requires PK + API credentials)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_orders(
    market: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> list:
    """
    Return open orders for the authenticated user.
    Requires L2 authentication (PK + CLOB_API_KEY/CLOB_SECRET/CLOB_PASS_PHRASE).

    Args:
        market:   Optional condition ID to filter orders by market.
        asset_id: Optional token ID to filter orders by asset.
    """
    params = OpenOrderParams(market=market or None, asset_id=asset_id or None)
    return _get_client().get_orders(params=params)


@mcp.tool()
def get_order(order_id: str) -> dict:
    """
    Return details for a specific order.
    Requires L2 authentication.

    Args:
        order_id: The order ID.
    """
    return _get_client().get_order(order_id)


@mcp.tool()
def get_trades(
    market: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> list:
    """
    Return the trade history for the authenticated user.
    Requires L2 authentication.

    Args:
        market:   Optional condition ID to filter trades by market.
        asset_id: Optional token ID to filter trades by asset.
    """
    params = TradeParams(market=market or None, asset_id=asset_id or None)
    return _get_client().get_trades(params=params)


@mcp.tool()
def cancel_order(order_id: str) -> dict:
    """
    Cancel a specific open order.
    Requires L2 authentication.

    Args:
        order_id: The ID of the order to cancel.
    """
    return _get_client().cancel(order_id)


@mcp.tool()
def cancel_all_orders() -> dict:
    """
    Cancel all open orders for the authenticated user.
    Requires L2 authentication.
    """
    return _get_client().cancel_all()


@mcp.tool()
def create_and_post_order(
    token_id: str,
    price: float,
    size: float,
    side: str,
    order_type: str = "GTC",
) -> dict:
    """
    Create a signed limit order and submit it to the order book.
    Requires L2 authentication.

    Args:
        token_id:   Token ID of the conditional token asset being traded.
        price:      Limit price (e.g. 0.65 for 65 cents).
        size:       Order size in units of the conditional token.
        side:       "BUY" or "SELL".
        order_type: Order type – "GTC" (default), "GTD", "FOK", or "FAK".
    """
    from py_clob_client.clob_types import OrderType

    order_type_map = {
        "GTC": OrderType.GTC,
        "GTD": OrderType.GTD,
        "FOK": OrderType.FOK,
        "FAK": OrderType.FAK,
    }
    ot = order_type_map.get(order_type.upper(), OrderType.GTC)

    client = _get_client()
    order_args = OrderArgs(token_id=token_id, price=price, size=size, side=side)
    order = client.create_order(order_args)
    return client.post_order(order, orderType=ot)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
