from collections.abc import Callable

from cdp import Wallet, Asset
from pydantic import BaseModel, Field
from web3 import Web3
import requests

TEST_PROMPT = "I want to trade 1 eth to arb using mev resistant cow trade. I'm on Arbitrum Mainnent and I i want to trade 1 eth"

bot_address = "0x8180822B1B58D72369f6aa191F7EFf39d60d20d0"

COW_TRADE_PROMPT = """
This tool will facilitate MEV resistant trades on CoW protocol. It will trade a specified amount of a from asset to a to asset for the wallet. It takes the the amount of the from asset to trade, the from asset ID to trade, and the to asset ID to receive from the trade as inputs. Trades are only supported on Arbitrum Mainnet (e.g. `arbitrum-mainnet`). Never allow trades on any other network."""

RELAYER_ADDRESS = '0xC92E8bdf79f0507f65a392b0ab4667716BFE0110'
GET_QUOTE_URL = 'http://localhost:3000/api/createCoWOrder'

class CoWTradeInput(BaseModel):
    """Input argument schema for trade action."""

    amount: str = Field(
        ..., description="The amount of the from asset to trade, e.g. `15`, `0.000001`"
    )
    from_asset_id: str = Field(
        ...,
        description="The from asset ID to trade, e.g. `eth`, `0x036CbD53842c5426634e7929541eC2318f3dCF7e`",
    )
    to_asset_id: str = Field(
        ...,
        description="The to asset ID to receive from the trade, e.g. `eth`, `0x036CbD53842c5426634e7929541eC2318f3dCF7e`",
    )


def cow_trade(wallet: Wallet, amount: str, from_asset_id: str, to_asset_id: str) -> str:
    """Trade a specified amount of a from asset to a to asset for the wallet. Trades are only supported on Mainnets.

    Args:
        wallet (Wallet): The wallet to trade the asset from.
        amount (str): The amount of the from asset to trade, e.g. `15`, `0.000001`.
        from_asset_id (str): The from asset ID to trade (e.g., "eth", "usdc", or a valid contract address like "0x036CbD53842c5426634e7929541eC2318f3dCF7e").
        to_asset_id (str): The from asset ID to trade (e.g., "eth", "usdc", or a valid contract address like "0x036CbD53842c5426634e7929541eC2318f3dCF7e").

    Returns:
        str: A message containing the trade details.

    """
    try:
        # Get private key of the wallet
        pk_bytes = wallet._addresses[0]._key.key
        pk_key = Web3.to_hex(pk_bytes)

        from_asset = Asset.fetch("arbitrum-mainnet", from_asset_id)
        to_asset = Asset.fetch("arbitrum-mainnet", to_asset_id)

        sell_token = from_asset._contract_address
        buy_token = to_asset._contract_address

        if not sell_token or not buy_token:
            raise Exception("Asset is not supported or Invalid asset ID")

        sell_token_decimals = from_asset._decimals

        sell_amount = None

        if sell_token_decimals == 18:
            sell_amount = Web3.to_wei(float(amount), 'ether')
        else:
            sell_amount = Web3.to_wei(float(amount), 'lovelace')

        #####################
        # APPROVE SELL TOKENS
        #####################

        invocation = wallet.invoke_contract(
            contract_address=sell_token,
            method="approve",
            args={"spender": RELAYER_ADDRESS, "value": str(sell_amount)},
        )
        invocation.wait()

        #####################
        # GET ORDER FROM API
        #####################

        quoteRequest = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": str(sell_amount),
            "ownerAddress": pk_key,
        }
        
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(GET_QUOTE_URL, headers=headers, json=quoteRequest)
        # Check if the request was successful
        if response.status_code != 200:
            raise Exception(f"Error posting order on CoW Swap: {response.text}")
        
        order_id = response.json()['orderId']

    except Exception as e:
        return f"Error trading assets {e!s}"

    return f"Submitted the trade id {order_id} to solvers.\nYou can view the trade at https://explorer.cow.fi/arb1/orders/{order_id}?tab=overview Trade {amount} of {from_asset_id} for {to_asset_id}.\n"
