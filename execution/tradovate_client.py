"""
Tradovate API Client for Paper and Live Trading

Supports:
- Demo/Paper trading (demo.tradovateapi.com)
- Live trading via MyFundedFutures/MFFU (live.tradovateapi.com)

API Documentation: https://api.tradovate.com
MFFU Website: https://myfundedfutures.com
"""

import os
import json
import time
import asyncio
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
import requests
import websocket
from loguru import logger


class TradovateEnvironment(Enum):
    """Trading environment selection"""
    DEMO = "demo"  # Paper trading
    LIVE = "live"  # Live trading (MFFU, etc.)


@dataclass
class TradovateCredentials:
    """Credentials for Tradovate API authentication"""
    username: str
    password: str
    app_id: str = "FuturesTradingAgent"
    app_version: str = "1.0.0"
    cid: str = ""  # Client ID from API settings
    sec: str = ""  # Secret key from API settings
    device_id: str = ""  # Optional device ID
    
    @classmethod
    def from_env(cls) -> 'TradovateCredentials':
        """Load credentials from environment variables"""
        return cls(
            username=os.getenv("TRADOVATE_USERNAME", ""),
            password=os.getenv("TRADOVATE_PASSWORD", ""),
            app_id=os.getenv("TRADOVATE_APP_ID", "FuturesTradingAgent"),
            app_version=os.getenv("TRADOVATE_APP_VERSION", "1.0.0"),
            cid=os.getenv("TRADOVATE_CID", ""),
            sec=os.getenv("TRADOVATE_SEC", ""),
            device_id=os.getenv("TRADOVATE_DEVICE_ID", ""),
        )
    
    @classmethod
    def from_file(cls, filepath: str) -> 'TradovateCredentials':
        """Load credentials from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def validate(self) -> bool:
        """Check if required credentials are present"""
        return all([self.username, self.password, self.cid, self.sec])


@dataclass
class OrderResult:
    """Result of an order placement"""
    success: bool
    order_id: Optional[int] = None
    message: str = ""
    raw_response: Dict = field(default_factory=dict)


@dataclass 
class Position:
    """Current position information"""
    account_id: int
    contract_id: int
    symbol: str
    net_pos: int  # Positive = long, negative = short
    net_price: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AccountInfo:
    """Account information"""
    id: int
    name: str
    user_id: int
    account_type: str
    active: bool
    clearing_house_id: int
    risk_category_id: int
    auto_liq_profile_id: int
    margin_account_type: str
    legal_status: str
    timestamp: datetime = field(default_factory=datetime.now)


class TradovateClient:
    """
    Tradovate REST API Client

    Supports both demo (paper) and live trading environments.
    For MyFundedFutures (MFFU) accounts, use the LIVE environment.
    """
    
    # API Base URLs
    DEMO_URL = "https://demo.tradovateapi.com/v1"
    LIVE_URL = "https://live.tradovateapi.com/v1"
    
    # WebSocket URLs
    DEMO_WS_URL = "wss://demo.tradovateapi.com/v1/websocket"
    LIVE_WS_URL = "wss://live.tradovateapi.com/v1/websocket"
    
    # Market Data URLs  
    DEMO_MD_URL = "wss://md-demo.tradovateapi.com/v1/websocket"
    LIVE_MD_URL = "wss://md.tradovateapi.com/v1/websocket"
    
    def __init__(
        self,
        credentials: TradovateCredentials,
        environment: TradovateEnvironment = TradovateEnvironment.DEMO,
        auto_renew_token: bool = True
    ):
        self.credentials = credentials
        self.environment = environment
        self.auto_renew_token = auto_renew_token
        
        # Set base URL based on environment
        self.base_url = self.LIVE_URL if environment == TradovateEnvironment.LIVE else self.DEMO_URL
        self.ws_url = self.LIVE_WS_URL if environment == TradovateEnvironment.LIVE else self.DEMO_WS_URL
        self.md_url = self.LIVE_MD_URL if environment == TradovateEnvironment.LIVE else self.DEMO_MD_URL
        
        # Authentication state
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.user_id: Optional[int] = None
        
        # Account state
        self.accounts: List[AccountInfo] = []
        self.active_account_id: Optional[int] = None
        
        # Session
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        # WebSocket connections
        self.ws: Optional[websocket.WebSocketApp] = None
        self.md_ws: Optional[websocket.WebSocketApp] = None
        
        # Callbacks
        self.on_order_update: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        self.on_fill: Optional[Callable] = None
        self.on_market_data: Optional[Callable] = None
        
        logger.info(f"TradovateClient initialized for {environment.value} environment")
    
    # ==================== Authentication ====================
    
    def authenticate(self) -> bool:
        """
        Authenticate with Tradovate API and get access token.
        
        Returns:
            bool: True if authentication successful
        """
        if not self.credentials.validate():
            logger.error("Invalid credentials - missing required fields")
            return False
        
        endpoint = f"{self.base_url}/auth/accesstokenrequest"
        
        payload = {
            "name": self.credentials.username,
            "password": self.credentials.password,
            "appId": self.credentials.app_id,
            "appVersion": self.credentials.app_version,
            "cid": self.credentials.cid,
            "sec": self.credentials.sec,
        }
        
        if self.credentials.device_id:
            payload["deviceId"] = self.credentials.device_id
        
        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "accessToken" in data:
                self.access_token = data["accessToken"]
                self.user_id = data.get("userId")
                
                # Calculate token expiry (typically 90 minutes)
                expires_in = data.get("expirationTime", 5400)  # Default 90 min
                if isinstance(expires_in, str):
                    # Parse ISO datetime string
                    self.token_expiry = datetime.fromisoformat(expires_in.replace("Z", "+00:00"))
                else:
                    self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                
                # Update session headers
                self.session.headers.update({
                    "Authorization": f"Bearer {self.access_token}"
                })
                
                logger.info(f"Authentication successful. User ID: {self.user_id}")
                
                # Load accounts
                self._load_accounts()
                
                return True
            else:
                error = data.get("errorText", "Unknown authentication error")
                logger.error(f"Authentication failed: {error}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication request failed: {e}")
            return False
    
    def renew_token(self) -> bool:
        """Renew access token before expiry"""
        endpoint = f"{self.base_url}/auth/renewaccesstoken"
        
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()
            
            if "accessToken" in data:
                self.access_token = data["accessToken"]
                expires_in = data.get("expirationTime", 5400)
                if isinstance(expires_in, str):
                    self.token_expiry = datetime.fromisoformat(expires_in.replace("Z", "+00:00"))
                else:
                    self.token_expiry = datetime.now() + timedelta(seconds=expires_in)
                
                self.session.headers.update({
                    "Authorization": f"Bearer {self.access_token}"
                })
                
                logger.info("Token renewed successfully")
                return True
            
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token renewal failed: {e}")
            return False
    
    def _check_token(self) -> bool:
        """Check if token is valid and renew if needed"""
        if not self.access_token:
            return False
        
        if self.token_expiry and datetime.now() > self.token_expiry - timedelta(minutes=5):
            if self.auto_renew_token:
                return self.renew_token()
            return False
        
        return True
    
    def _load_accounts(self):
        """Load user accounts"""
        accounts_data = self._get("/account/list")
        if accounts_data:
            self.accounts = []
            for acc in accounts_data:
                self.accounts.append(AccountInfo(
                    id=acc["id"],
                    name=acc["name"],
                    user_id=acc["userId"],
                    account_type=acc.get("accountType", ""),
                    active=acc.get("active", True),
                    clearing_house_id=acc.get("clearingHouseId", 0),
                    risk_category_id=acc.get("riskCategoryId", 0),
                    auto_liq_profile_id=acc.get("autoLiqProfileId", 0),
                    margin_account_type=acc.get("marginAccountType", ""),
                    legal_status=acc.get("legalStatus", "")
                ))
            
            if self.accounts:
                self.active_account_id = self.accounts[0].id
                logger.info(f"Loaded {len(self.accounts)} accounts. Active: {self.active_account_id}")
    
    # ==================== HTTP Helpers ====================
    
    def _get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make GET request"""
        if not self._check_token():
            logger.error("No valid token")
            return None
        
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GET {endpoint} failed: {e}")
            return None
    
    def _post(self, endpoint: str, data: Dict = None) -> Optional[Any]:
        """Make POST request"""
        if not self._check_token():
            logger.error("No valid token")
            return None
        
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"POST {endpoint} failed: {e}")
            return None
    
    # ==================== Account Operations ====================
    
    def get_accounts(self) -> List[AccountInfo]:
        """Get all available accounts"""
        return self.accounts
    
    def set_active_account(self, account_id: int) -> bool:
        """Set the active trading account"""
        if any(acc.id == account_id for acc in self.accounts):
            self.active_account_id = account_id
            logger.info(f"Active account set to: {account_id}")
            return True
        logger.error(f"Account {account_id} not found")
        return False
    
    def get_cash_balance(self, account_id: int = None) -> Optional[Dict]:
        """Get account cash balance"""
        acc_id = account_id or self.active_account_id
        return self._get(f"/cashBalance/getCashBalanceSnapshot", {"accountId": acc_id})
    
    def get_account_risk_status(self, account_id: int = None) -> Optional[Dict]:
        """Get account risk status"""
        acc_id = account_id or self.active_account_id
        return self._post("/accountRiskStatus/list", {"accountIds": [acc_id]})
    
    # ==================== Contract/Symbol Operations ====================
    
    def find_contract(self, symbol: str) -> Optional[Dict]:
        """Find contract by symbol name"""
        return self._get("/contract/find", {"name": symbol})
    
    def get_contract(self, contract_id: int) -> Optional[Dict]:
        """Get contract by ID"""
        return self._get(f"/contract/item", {"id": contract_id})
    
    def search_contracts(self, text: str) -> Optional[List[Dict]]:
        """Search for contracts"""
        return self._get("/contract/suggest", {"text": text, "nEntities": 10})
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        """Get product details"""
        return self._get("/product/item", {"id": product_id})
    
    # ==================== Position Operations ====================
    
    def get_positions(self, account_id: int = None) -> List[Position]:
        """Get all open positions"""
        acc_id = account_id or self.active_account_id
        data = self._get("/position/list", {"accountId": acc_id})
        
        positions = []
        if data:
            for pos in data:
                if pos.get("netPos", 0) != 0:
                    positions.append(Position(
                        account_id=pos["accountId"],
                        contract_id=pos["contractId"],
                        symbol=pos.get("symbol", ""),
                        net_pos=pos["netPos"],
                        net_price=pos.get("netPrice", 0)
                    ))
        return positions
    
    def get_position(self, contract_id: int, account_id: int = None) -> Optional[Position]:
        """Get position for specific contract"""
        positions = self.get_positions(account_id)
        for pos in positions:
            if pos.contract_id == contract_id:
                return pos
        return None
    
    # ==================== Order Operations ====================
    
    def place_order(
        self,
        symbol: str,
        action: str,  # "Buy" or "Sell"
        quantity: int,
        order_type: str = "Market",  # "Market", "Limit", "Stop", "StopLimit"
        price: float = None,
        stop_price: float = None,
        time_in_force: str = "Day",  # "Day", "GTC", "IOC", "FOK"
        account_id: int = None,
        is_automated: bool = True
    ) -> OrderResult:
        """
        Place an order
        
        Args:
            symbol: Contract symbol (e.g., "MESZ4", "ESH5")
            action: "Buy" or "Sell"
            quantity: Number of contracts
            order_type: Order type
            price: Limit price (required for Limit/StopLimit)
            stop_price: Stop price (required for Stop/StopLimit)
            time_in_force: Order duration
            account_id: Account to trade on
            is_automated: Mark as automated order (required for API trading)
        
        Returns:
            OrderResult with success status and order details
        """
        acc_id = account_id or self.active_account_id
        
        if not acc_id:
            return OrderResult(success=False, message="No active account")
        
        # Find contract
        contract = self.find_contract(symbol)
        if not contract:
            return OrderResult(success=False, message=f"Contract {symbol} not found")
        
        # Build order payload
        payload = {
            "accountSpec": self.credentials.username,
            "accountId": acc_id,
            "action": action,
            "symbol": symbol,
            "orderQty": quantity,
            "orderType": order_type,
            "timeInForce": time_in_force,
            "isAutomated": is_automated
        }
        
        if order_type in ["Limit", "StopLimit"] and price:
            payload["price"] = price
        
        if order_type in ["Stop", "StopLimit"] and stop_price:
            payload["stopPrice"] = stop_price
        
        # Place order
        result = self._post("/order/placeorder", payload)
        
        if result:
            if result.get("orderId"):
                return OrderResult(
                    success=True,
                    order_id=result["orderId"],
                    message="Order placed successfully",
                    raw_response=result
                )
            else:
                return OrderResult(
                    success=False,
                    message=result.get("failureText", result.get("failureReason", "Unknown error")),
                    raw_response=result
                )
        
        return OrderResult(success=False, message="Failed to place order")
    
    def place_bracket_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        entry_price: float = None,  # None for market
        stop_loss: float = None,
        take_profit: float = None,
        account_id: int = None,
        is_automated: bool = True
    ) -> OrderResult:
        """
        Place a bracket order (entry + stop loss + take profit)
        
        Uses OSO (Order Sends Order) for bracket functionality.
        """
        acc_id = account_id or self.active_account_id
        
        if not acc_id:
            return OrderResult(success=False, message="No active account")
        
        # Build OSO payload
        other_orders = []
        
        # Determine exit action
        exit_action = "Sell" if action == "Buy" else "Buy"
        
        # Stop loss order
        if stop_loss:
            other_orders.append({
                "action": exit_action,
                "orderType": "Stop",
                "stopPrice": stop_loss
            })
        
        # Take profit order
        if take_profit:
            other_orders.append({
                "action": exit_action,
                "orderType": "Limit",
                "price": take_profit
            })
        
        payload = {
            "accountSpec": self.credentials.username,
            "accountId": acc_id,
            "action": action,
            "symbol": symbol,
            "orderQty": quantity,
            "orderType": "Market" if entry_price is None else "Limit",
            "isAutomated": is_automated
        }
        
        if entry_price:
            payload["price"] = entry_price
        
        if other_orders:
            payload["bracket1"] = other_orders[0] if len(other_orders) > 0 else None
            payload["bracket2"] = other_orders[1] if len(other_orders) > 1 else None
        
        # Place OSO order
        result = self._post("/order/placeoso", payload)
        
        if result:
            if result.get("orderId"):
                return OrderResult(
                    success=True,
                    order_id=result["orderId"],
                    message="Bracket order placed successfully",
                    raw_response=result
                )
            else:
                return OrderResult(
                    success=False,
                    message=result.get("failureText", result.get("failureReason", "Unknown error")),
                    raw_response=result
                )
        
        return OrderResult(success=False, message="Failed to place bracket order")
    
    def modify_order(
        self,
        order_id: int,
        quantity: int = None,
        price: float = None,
        stop_price: float = None
    ) -> OrderResult:
        """Modify an existing order"""
        payload = {"orderId": order_id}
        
        if quantity:
            payload["orderQty"] = quantity
        if price:
            payload["price"] = price
        if stop_price:
            payload["stopPrice"] = stop_price
        
        result = self._post("/order/modifyorder", payload)
        
        if result:
            return OrderResult(
                success=True,
                order_id=order_id,
                message="Order modified",
                raw_response=result
            )
        
        return OrderResult(success=False, message="Failed to modify order")
    
    def cancel_order(self, order_id: int) -> OrderResult:
        """Cancel an order"""
        result = self._post("/order/cancelorder", {"orderId": order_id})
        
        if result:
            return OrderResult(
                success=True,
                order_id=order_id,
                message="Order cancelled",
                raw_response=result
            )
        
        return OrderResult(success=False, message="Failed to cancel order")
    
    def cancel_all_orders(self, account_id: int = None) -> bool:
        """Cancel all open orders"""
        acc_id = account_id or self.active_account_id
        orders = self.get_open_orders(acc_id)
        
        success = True
        for order in orders:
            result = self.cancel_order(order["id"])
            if not result.success:
                success = False
        
        return success
    
    def get_open_orders(self, account_id: int = None) -> List[Dict]:
        """Get all open orders"""
        acc_id = account_id or self.active_account_id
        result = self._get("/order/list", {"accountId": acc_id})
        
        if result:
            return [o for o in result if o.get("ordStatus") in ["Working", "Accepted"]]
        return []
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get order details by ID"""
        return self._get("/order/item", {"id": order_id})
    
    def get_fills(self, account_id: int = None) -> List[Dict]:
        """Get recent fills"""
        acc_id = account_id or self.active_account_id
        return self._get("/fill/list", {"accountId": acc_id}) or []
    
    # ==================== Liquidation ====================
    
    def liquidate_position(self, contract_id: int, account_id: int = None) -> OrderResult:
        """Liquidate a position (close at market)"""
        acc_id = account_id or self.active_account_id
        
        result = self._post("/order/liquidateposition", {
            "accountId": acc_id,
            "contractId": contract_id
        })
        
        if result:
            return OrderResult(
                success=True,
                message="Position liquidated",
                raw_response=result
            )
        
        return OrderResult(success=False, message="Failed to liquidate position")
    
    def flatten_all(self, account_id: int = None) -> bool:
        """Flatten all positions and cancel all orders"""
        acc_id = account_id or self.active_account_id
        
        # Cancel all orders first
        self.cancel_all_orders(acc_id)
        
        # Liquidate all positions
        positions = self.get_positions(acc_id)
        for pos in positions:
            self.liquidate_position(pos.contract_id, acc_id)
        
        logger.info("All positions flattened")
        return True
    
    # ==================== Context Manager ====================
    
    def __enter__(self):
        if not self.authenticate():
            raise ConnectionError("Failed to authenticate with Tradovate")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()


# ==================== Convenience Functions ====================

def create_demo_client(credentials: TradovateCredentials = None) -> TradovateClient:
    """Create a client for paper trading"""
    creds = credentials or TradovateCredentials.from_env()
    return TradovateClient(creds, TradovateEnvironment.DEMO)


def create_live_client(credentials: TradovateCredentials = None) -> TradovateClient:
    """Create a client for live trading (MFFU, etc.)"""
    creds = credentials or TradovateCredentials.from_env()
    return TradovateClient(creds, TradovateEnvironment.LIVE)


# ==================== Example Usage ====================

if __name__ == "__main__":
    # Example: Paper trading
    print("Tradovate Client Example")
    print("=" * 50)
    
    # Check for credentials
    creds = TradovateCredentials.from_env()
    if not creds.validate():
        print("\nTo use this client, set environment variables:")
        print("  export TRADOVATE_USERNAME='your_username'")
        print("  export TRADOVATE_PASSWORD='your_password'")
        print("  export TRADOVATE_CID='your_client_id'")
        print("  export TRADOVATE_SEC='your_secret_key'")
        print("\nOr create a credentials file:")
        print("""
{
    "username": "your_username",
    "password": "your_password",
    "cid": "your_client_id",
    "sec": "your_secret_key"
}
        """)
    else:
        # Connect and test
        with create_demo_client(creds) as client:
            print(f"\nConnected to {client.environment.value}")
            print(f"User ID: {client.user_id}")
            print(f"Accounts: {len(client.accounts)}")
            
            for acc in client.accounts:
                print(f"  - {acc.name} (ID: {acc.id})")
            
            # Get positions
            positions = client.get_positions()
            print(f"\nOpen positions: {len(positions)}")
            
            # Search for MES contract
            contracts = client.search_contracts("MES")
            if contracts:
                print(f"\nMES contracts found: {len(contracts)}")
                for c in contracts[:3]:
                    print(f"  - {c.get('name')}")
