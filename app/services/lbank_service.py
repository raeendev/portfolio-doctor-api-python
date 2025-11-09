"""LBank Exchange Service - Optimized implementation with rate limiting"""
import asyncio
import hashlib
import hmac
import secrets
import time
from typing import Dict, List, Optional, Any
import os
from datetime import datetime
from collections import deque
import httpx
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for LBank API requests"""
    
    def __init__(self, max_requests: int, window_seconds: int = 10):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()
    
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove requests outside the window
        while self.requests and self.requests[0] < now - self.window_seconds:
            self.requests.popleft()
        
        # If at limit, wait until oldest request expires
        if len(self.requests) >= self.max_requests:
            sleep_time = self.window_seconds - (now - self.requests[0]) + 0.1
            if sleep_time > 0:
                logger.warning(f"Rate limit reached ({self.max_requests}/{self.window_seconds}s), waiting {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                # Re-check after sleep
                now = time.time()
                while self.requests and self.requests[0] < now - self.window_seconds:
                    self.requests.popleft()
        
        # Record this request
        self.requests.append(time.time())


class LBankService:
    """LBank Exchange API Service with rate limiting and optimized requests"""
    
    def __init__(self):
        self.rest_hosts = [
            'https://www.lbkex.net',
            'https://api.lbkex.com',
            'https://api.lbank.info',
        ]
        contract_env = os.getenv("LBANK_CONTRACT_BASE_URL")
        if contract_env:
            self.contract_hosts = [contract_env.rstrip("/")]
        else:
            # Official contract REST endpoint (per docs: https://lbkperp.lbank.com/)
            self.contract_hosts = [
                "https://lbkperp.lbank.com",
            ]

        self.contract_asset = os.getenv("LBANK_CONTRACT_ASSET", "USDT")
        # SwapU = USDT-margined perpetual per docs
        self.contract_product_group = os.getenv("LBANK_CONTRACT_PRODUCT_GROUP", "SwapU")
        
        # Rate limiters: Orders 500/10s, Others 200/10s
        self.general_rate_limiter = RateLimiter(max_requests=200, window_seconds=10)
        self.order_rate_limiter = RateLimiter(max_requests=500, window_seconds=10)
        
        # Cache for prices (valid for 5 seconds)
        self._price_cache: Dict[str, Dict[str, float]] = {}
        self._price_cache_timestamp: float = 0
        self._price_cache_ttl: float = 5.0  # 5 seconds cache

        # Feature flag: allow opting into official connector via env (default: OFF for reliability)
        self._use_connector = os.getenv("LBANK_USE_CONNECTOR", "false").lower() == "true"
        # Try loading official LBank connector; fall back to manual HTTP if unavailable
        self._connector_available = False
        self._ConnectorClient = None
        try:
            if self._use_connector:
                from lbank.old_api import BlockHttpClient  # type: ignore
                self._ConnectorClient = BlockHttpClient
                self._connector_available = True
                logger.info("lbank-connector-python detected; using official client per LBANK_USE_CONNECTOR=true")
            else:
                logger.info("LBANK_USE_CONNECTOR is false; using manual HTTP signing path")
        except Exception as e:
            logger.info(f"lbank-connector-python not available or failed to import: {e}; falling back to manual HTTP")
    
    def _is_result_true(self, val: Any) -> bool:
        """Check if result is True"""
        return val is True or val == 'true' or val == 'True' or str(val).lower() == 'true'

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Safely convert to float, returning None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    async def _fetch_server_timestamp(self, base_url: str) -> int:
        """Fetch server timestamp from LBank (public endpoint, no auth needed)"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"{base_url}/v2/timestamp.do",
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )
                data = res.json()
                ts = data.get('timestamp') or data.get('data')
                if ts:
                    return int(ts)
        except Exception as e:
            logger.debug(f"Failed to fetch server timestamp from {base_url}: {e}")
        
        # Fallback to local timestamp
        return int(time.time() * 1000)
    
    def _generate_echo_str(self) -> str:
        """Generate random echo string (30-40 characters as per docs)"""
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(secrets.choice(chars) for _ in range(32))  # 32 chars is safe
    
    def _sign_params_hmac(self, params: Dict[str, Any], secret_key: str) -> str:
        """
        Sign parameters with HMAC-SHA256 according to LBank documentation:
        1. Sort parameters alphabetically (excluding 'sign')
        2. Create MD5 hash of parameter string (uppercase hex)
        3. Create HMAC-SHA256 of MD5 hash
        """
        # Filter out 'sign' parameter and sort alphabetically
        sorted_params = sorted([(k, v) for k, v in params.items() if k != 'sign'])
        
        # Create parameter string
        param_str = '&'.join(f"{k}={v}" for k, v in sorted_params)
        
        # Create MD5 hash (uppercase hex)
        md5_hash = hashlib.md5(param_str.encode('utf-8')).hexdigest().upper()
        
        # Create HMAC-SHA256 signature
        sign = hmac.new(
            secret_key.encode('utf-8'),
            md5_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return sign
    
    async def _post_signed(
        self, 
        base_url: str, 
        path: str, 
        api_key: str, 
        api_secret: str, 
        extra_params: Optional[Dict[str, Any]] = None,
        is_order_request: bool = False
    ) -> Dict[str, Any]:
        """
        Post signed request to LBank API with rate limiting
        """
        # Apply appropriate rate limiter
        if is_order_request:
            await self.order_rate_limiter.wait_if_needed()
        else:
            await self.general_rate_limiter.wait_if_needed()
        
        # Get server timestamp (strongly recommended per docs)
        timestamp = await self._fetch_server_timestamp(base_url)
        
        # Build parameters
        params = {
            "api_key": api_key,
            "signature_method": "HmacSHA256",
            "timestamp": timestamp,
            "echostr": self._generate_echo_str(),
            **(extra_params or {})
        }
        
        # Generate signature
        sign = self._sign_params_hmac(params, api_secret)
        params["sign"] = sign
        
        # Convert to form data
        form_data = {k: str(v) for k, v in params.items()}
        
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'User-Agent': 'PortfolioDoctor/1.0',
            'Accept': 'application/json'
        }
        
        # Retry logic for rate limit errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{base_url}{path}",
                        data=form_data,
                        headers=headers
                    )
                    data = response.json()
                    
                    # Check for rate limit error (10004)
                    error_code = data.get('error_code')
                    if error_code == '10004' and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        logger.warning(f"Rate limit error, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    return data
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning(f"Timeout, retrying {attempt + 1}/{max_retries}")
                    await asyncio.sleep(1)
                    continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Request failed: {e}, retrying {attempt + 1}/{max_retries}")
                    await asyncio.sleep(1)
                    continue
                raise
        
        raise Exception("Max retries exceeded")

    async def _post_contract_signed(
        self,
        path: str,
        api_key: str,
        api_secret: str,
        extra_params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """Signed request against the LBank Contract API (futures)."""
        await self.general_rate_limiter.wait_if_needed()

        last_error: Optional[Exception] = None
        method = method.upper()

        for base_url in self.contract_hosts:
            timestamp = await self._fetch_server_timestamp(self.rest_hosts[0])

            params: Dict[str, Any] = {
                "api_key": api_key,
                "signature_method": "HmacSHA256",
                "timestamp": timestamp,
                "echostr": self._generate_echo_str(),
            }
            if extra_params:
                params.update(extra_params)

            sign = self._sign_params_hmac(params, api_secret)
            params_with_sign = {**params, "sign": sign}

            headers = {
                "User-Agent": "PortfolioDoctor/1.0",
                "Accept": "application/json",
                "timestamp": str(timestamp),
                "signature_method": "HmacSHA256",
                "echostr": params_with_sign["echostr"],
            }

            request_kwargs: Dict[str, Any]
            if method == "GET":
                request_kwargs = {
                    "params": {k: str(v) for k, v in params_with_sign.items()},
                    "headers": headers,
                }
            else:
                headers["Content-Type"] = "application/json"
                request_kwargs = {
                    "json": params_with_sign,
                    "headers": headers,
                }

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.request(
                            method,
                            f"{base_url}{path}",
                            **request_kwargs,
                        )
                        response.raise_for_status()
                        logger.debug(f"Contract API success via {base_url}{path}")
                        return response.json()
                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        logger.warning(
                            f"Contract API timeout ({base_url}{path}), retrying in {wait_time}s "
                            f"({attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    last_error = None
                    continue
                except Exception as exc:
                    last_error = exc
                    status_code = getattr(getattr(exc, "response", None), "status_code", None)
                    logger.warning(
                        f"Contract API request failed ({base_url}{path} - {exc}, status={status_code}), "
                        f"attempt {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.warning(f"Contract API request failed ({base_url}{path}), trying next host")
                        break

        if last_error:
            raise last_error
        raise Exception("Contract API: all hosts unreachable")

    def _parse_contract_balances(
        self,
        payload: Any,
        price_map: Dict[str, float],
    ) -> Dict[str, Any]:
        """Normalize contract account balance payload into assets list."""
        assets: List[Dict[str, Any]] = []
        total_value = 0.0

        if isinstance(payload, dict):
            data = payload.get("data", payload)
        else:
            data = payload

        entries: List[Dict[str, Any]] = []

        if isinstance(data, dict):
            # Some responses keyed by currency, others nested under balances/accountBalance
            candidate_lists = [
                data.get("balances"),
                data.get("accountBalance"),
                data.get("assets"),
                data.get("accounts"),
            ]
            entries_detected = False
            for candidate in candidate_lists:
                if isinstance(candidate, list):
                    entries.extend([entry for entry in candidate if isinstance(entry, dict)])
                    entries_detected = True
            if not entries_detected:
                # treat dict itself as a single entry
                entries.append(data)
        elif isinstance(data, list):
            entries.extend([entry for entry in data if isinstance(entry, dict)])

        stablecoins = {"USDT", "USDC", "TUSD", "USDD", "BUSD"}

        for entry in entries:
            currency = str(entry.get("asset") or entry.get("currency") or entry.get("symbol") or "USDT").upper()

            margin_balance = self._safe_float(
                entry.get("marginBalance")
                or entry.get("equity")
                or entry.get("balance")
                or entry.get("cashBalance")
                or entry.get("asset")
            )
            available_balance = self._safe_float(
                entry.get("availableBalance")
                or entry.get("available")
                or entry.get("withdrawAvailable")
                or entry.get("cashBalance")
            )
            frozen_balance = None
            if margin_balance is not None and available_balance is not None:
                frozen_balance = max(margin_balance - available_balance, 0.0)

            unrealized = self._safe_float(entry.get("unrealizedPnl") or entry.get("unrealized") or entry.get("profit"))

            # Determine USD valuation
            value_usd: Optional[float] = None
            price_usd: Optional[float] = None
            amount_reference = margin_balance if margin_balance is not None else available_balance

            if amount_reference is None:
                continue

            if currency in stablecoins:
                price_usd = 1.0
                value_usd = amount_reference
            else:
                price_usd = self._get_price_from_map(currency, price_map)
                if price_usd:
                    value_usd = amount_reference * price_usd

            assets.append(
                {
                    "symbol": currency,
                    "free": available_balance if available_balance is not None else amount_reference,
                    "frozen": frozen_balance if frozen_balance is not None else 0.0,
                    "quantity": margin_balance if margin_balance is not None else amount_reference,
                    "priceUSD": price_usd,
                    "valueUSD": value_usd,
                    "unrealizedPnl": unrealized,
                    "accountType": "FUTURES",
                }
            )

            if value_usd is not None:
                total_value += value_usd

        return {"totalValueUSD": total_value, "assets": assets}

    def _parse_contract_positions(
        self,
        payload: Any,
        price_map: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Normalize contract positions list (best effort)."""
        if isinstance(payload, dict):
            data = payload.get("data", payload)
        else:
            data = payload

        if isinstance(data, dict) and isinstance(data.get("positions"), list):
            positions_raw = data.get("positions")
        elif isinstance(data, list):
            positions_raw = data
        else:
            positions_raw = []

        positions: List[Dict[str, Any]] = []
        for entry in positions_raw:
            if not isinstance(entry, dict):
                continue

            symbol = str(entry.get("symbol") or entry.get("contract") or entry.get("pair") or "").upper()
            if not symbol:
                continue

            side = str(entry.get("side") or entry.get("direction") or entry.get("positionSide") or "").upper()
            size = self._safe_float(entry.get("size") or entry.get("volume") or entry.get("positionAmt") or entry.get("qty"))
            entry_price = self._safe_float(entry.get("entryPrice") or entry.get("avgPrice") or entry.get("openPrice"))
            mark_price = self._safe_float(entry.get("markPrice") or entry.get("lastPrice"))
            leverage = entry.get("leverage") or entry.get("leverRate")
            unrealized = self._safe_float(entry.get("unrealizedPnl") or entry.get("profit"))

            notional_value = None
            price_for_value = mark_price or entry_price
            if size is not None and price_for_value:
                notional_value = size * price_for_value
            elif size is not None and symbol.endswith("USDT"):
                notional_value = size
                price_for_value = 1.0
            elif size is not None:
                mapped_price = self._get_price_from_map(symbol.replace("USDT", ""), price_map)
                if mapped_price:
                    notional_value = size * mapped_price
                    price_for_value = mapped_price

            positions.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "quantity": size,
                    "entryPrice": entry_price,
                    "markPrice": mark_price,
                    "leverage": leverage,
                    "unrealizedPnl": unrealized,
                    "notionalValueUSD": notional_value,
                }
            )

        return positions

    async def _legacy_futures_balances(self, api_key: str, api_secret: str, price_map: Dict[str, float]) -> Dict[str, Any]:
        """Fallback to legacy supplement endpoint (spot-style account) if contract API unavailable."""
        data = await self._get_trade_balances(api_key, api_secret)
        if not self._is_result_true(data.get("result")):
            error_code = data.get("error_code", "Unknown")
            error_msg = data.get("msg") or data.get("error_msg", "Unknown error")
            raise Exception(f"LBank API error: {error_code} - {error_msg}")

        info = data.get("info") or data.get("data") or data
        balances = info.get("balances", []) if isinstance(info, dict) else []
        free_obj: Dict[str, float] = {}
        freeze_obj: Dict[str, float] = {}
        if isinstance(balances, list) and balances:
            for bal in balances:
                sym = str(bal.get("asset", "")).upper()
                if not sym:
                    continue
                free_obj[sym] = float(bal.get("free", 0) or 0)
                freeze_obj[sym] = float(bal.get("locked", 0) or 0)
        else:
            if isinstance(info, dict):
                if isinstance(info.get("free"), dict):
                    for k, v in info["free"].items():
                        free_obj[str(k).upper()] = float(v or 0)
                if isinstance(info.get("freeze"), dict):
                    for k, v in info["freeze"].items():
                        freeze_obj[str(k).upper()] = float(v or 0)

        items: List[Dict[str, Any]] = []
        total_value = 0.0
        for sym in sorted(set(list(free_obj.keys()) + list(freeze_obj.keys()))):
            qty = float(free_obj.get(sym, 0)) + float(freeze_obj.get(sym, 0))
            if qty <= 0:
                continue
            price = self._get_price_from_map(sym, price_map)
            value = qty * price if price and price > 0 else None
            if value:
                total_value += value
            items.append(
                {
                    "symbol": sym,
                    "free": float(free_obj.get(sym, 0)),
                    "frozen": float(freeze_obj.get(sym, 0)),
                    "quantity": qty,
                    "priceUSD": price if price and price > 0 else None,
                    "valueUSD": value,
                    "accountType": "FUTURES",
                }
            )

        return {"totalValueUSD": total_value, "assets": items, "positions": []}

    async def _connector_request(
        self,
        method: str,
        api_path: str,
        api_key: str,
        api_secret: str,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use official connector client synchronously inside thread, wrapped for async."""
        if not self._connector_available or self._ConnectorClient is None:
            raise RuntimeError("Connector not available")

        # Respect rate limiting for private endpoints
        await self.general_rate_limiter.wait_if_needed()

        # Build required params (the connector does not inject api_key/signature params by itself)
        timestamp = await self._fetch_server_timestamp("https://api.lbkex.com")
        base_params: Dict[str, Any] = {
            "api_key": api_key,
            "signature_method": "HmacSHA256",
            "timestamp": timestamp,
            "echostr": self._generate_echo_str(),
        }
        if extra_params:
            base_params.update(extra_params)

        def _sync_call() -> Dict[str, Any]:
            client = self._ConnectorClient(
                sign_method="HmacSHA256",
                api_key=api_key,
                api_secret=api_secret,
                base_url="https://api.lbkex.com/",
                is_json=False,
                log_level=logging.WARNING,
            )
            return client.http_request(method.lower(), api_path, payload=base_params)  # type: ignore[arg-type]

        # Run blocking client in a thread
        return await asyncio.to_thread(_sync_call)
    
    async def _get_user_assets_supplement(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """
        Get user spot assets from supplement API
        According to LBank docs, /v2/supplement/user_info.do returns a direct array
        or an object with result field
        """
        errors = []
        # Prefer official connector if present
        if self._connector_available:
            try:
                data = await self._connector_request(
                    method="post",
                    api_path="v2/supplement/user_info.do",
                    api_key=api_key,
                    api_secret=api_secret,
                    extra_params={},
                )
                
                # Handle direct array response (per LBank docs example)
                if isinstance(data, list) and len(data) > 0:
                    logger.info(f"Received direct array response via connector with {len(data)} assets")
                    return {"result": True, "data": data}
                
                # Handle object response with result field
                if isinstance(data, dict):
                    if self._is_result_true(data.get('result')):
                        return data
                    
                    # Check for API errors
                    error_code = data.get('error_code')
                    error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
                    if error_code:
                        logger.error(f"LBank API error: {error_code} - {error_msg}")
                        errors.append(f"connector: {error_code} - {error_msg}")
                
                # If we get here, response format is unexpected but might be valid
                logger.warning(f"Unexpected response format via connector, attempting to extract data")
                return {"result": True, "data": data}
            except Exception as e:
                logger.error(f"Connector exception fetching user_info: {e}", exc_info=True)
                errors.append(f"connector: {str(e)}")
        
        # Fallback to manual HTTP across hosts
        for host in self.rest_hosts:
            try:
                data = await self._post_signed(
                    host,
                    '/v2/supplement/user_info.do',
                    api_key,
                    api_secret
                )
                
                # Handle direct array response
                if isinstance(data, list) and len(data) > 0:
                    logger.info(f"Received direct array response from {host} with {len(data)} assets")
                    return {"result": True, "data": data}
                
                # Handle object response with result field
                if isinstance(data, dict):
                    if self._is_result_true(data.get('result')):
                        return data
                    
                    error_code = data.get('error_code')
                    error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
                    if error_code:
                        logger.error(f"LBank API error from {host}: {error_code} - {error_msg}")
                        errors.append(f"{host}: {error_code} - {error_msg}")
                        continue
                
                # Unexpected but possibly valid format
                logger.warning(f"Unexpected response format from {host}, attempting to extract data")
                return {"result": True, "data": data}
            except Exception as e:
                logger.error(f"Exception fetching from {host}: {e}", exc_info=True)
                errors.append(f"{host}: {str(e)}")
                continue
        
        logger.error(f"All methods failed for supplement/user_info: {errors}")
        raise Exception(f"Failed to fetch user assets: {', '.join(errors)}")
    
    async def _get_trade_balances(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """Get trade account balances (futures/margin)"""
        errors = []
        # Prefer official connector if present
        if self._connector_available:
            try:
                data = await self._connector_request(
                    method="post",
                    api_path="v2/supplement/user_info_account.do",
                    api_key=api_key,
                    api_secret=api_secret,
                    extra_params={},
                )
                if self._is_result_true(data.get('result')):
                    return data
                error_code = data.get('error_code')
                error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
                logger.error(f"LBank API error: {error_code} - {error_msg}")
                errors.append(f"connector: {error_code} - {error_msg}")
            except Exception as e:
                errors.append(f"connector: {str(e)}")
        
        # Fallback to manual HTTP across hosts
        for host in self.rest_hosts:
            try:
                data = await self._post_signed(
                    host,
                    '/v2/supplement/user_info_account.do',
                    api_key,
                    api_secret
                )
                
                if self._is_result_true(data.get('result')):
                    return data
                
                error_code = data.get('error_code')
                error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
                logger.error(f"LBank API error from {host}: {error_code} - {error_msg}")
                errors.append(f"{host}: {error_code} - {error_msg}")
            except Exception as e:
                errors.append(f"{host}: {str(e)}")
                continue
        
        logger.error(f"All hosts failed for user_info_account: {errors}")
        raise Exception(f"Failed to fetch trade balances: {', '.join(errors)}")
    
    async def _get_all_prices_optimized(self) -> Dict[str, float]:
        """
        Get all prices in one request using /v2/supplement/ticker/price.do
        This is a public endpoint, no authentication needed, and returns all prices
        Uses caching to avoid unnecessary requests
        """
        # Check cache
        now = time.time()
        if (now - self._price_cache_timestamp) < self._price_cache_ttl and self._price_cache:
            return self._price_cache
        
        # Apply rate limiter (even for public endpoints, be respectful)
        await self.general_rate_limiter.wait_if_needed()
        
        for base_url in self.rest_hosts:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Request all prices by not providing symbol parameter
                    res = await client.get(
                        f"{base_url}/v2/supplement/ticker/price.do",
                        headers={'Accept': 'application/json'}
                    )
                    
                    if res.status_code != 200:
                        continue
                    
                    payload = res.json()
                    
                    # Handle different response formats
                    price_data = []
                    if isinstance(payload, list):
                        price_data = payload
                    elif isinstance(payload, dict):
                        if 'data' in payload:
                            price_data = payload['data'] if isinstance(payload['data'], list) else [payload['data']]
                        else:
                            price_data = [payload]
                    
                    price_map = {}
                    for row in price_data:
                        symbol = str(row.get('symbol', '')).lower()
                        price = row.get('price')
                        
                        if symbol and price:
                            try:
                                price_float = float(price)
                                if price_float > 0:
                                    price_map[symbol] = price_float
                            except (ValueError, TypeError):
                                continue
                    
                    if price_map:
                        # Update cache
                        self._price_cache = price_map
                        self._price_cache_timestamp = now
                        logger.info(f"Fetched {len(price_map)} prices from LBank")
                        return price_map
            except Exception as e:
                logger.warning(f"Failed to fetch all prices from {base_url}: {e}")
                continue
        
        # Return cached data if available, even if expired
        if self._price_cache:
            logger.warning("Using expired price cache")
            return self._price_cache
        
        return {}
    
    def _get_price_from_map(self, symbol: str, price_map: Dict[str, float]) -> Optional[float]:
        """Get price from price map with fallback logic"""
        symbol_upper = symbol.upper()
        
        # Stablecoins
        if symbol_upper in ['USDT', 'USDC', 'TUSD', 'USDD']:
            return 1.0
        
        symbol_lower = symbol.lower()
        
        # Try USDT pair first
        usdt_pair = f"{symbol_lower}_usdt"
        if usdt_pair in price_map and price_map[usdt_pair] > 0:
            return price_map[usdt_pair]
        
        # Try USD pair
        usd_pair = f"{symbol_lower}_usd"
        if usd_pair in price_map and price_map[usd_pair] > 0:
            return price_map[usd_pair]
        
        # Try BTC pair and convert via BTC/USDT
        btc_pair = f"{symbol_lower}_btc"
        btc_usdt = price_map.get('btc_usdt', 0)
        if btc_pair in price_map and price_map[btc_pair] > 0 and btc_usdt > 0:
            return price_map[btc_pair] * btc_usdt
        
        return None
    
    def _get_asset_tier(self, symbol: str) -> str:
        """Get asset tier classification"""
        core_assets = ['BTC', 'ETH', 'USDT', 'USDC']
        satellite_assets = ['ADA', 'DOT', 'LINK', 'XRP', 'MATIC', 'BNB', 'SOL']
        
        symbol_upper = symbol.upper()
        if symbol_upper in core_assets:
            return 'CORE'
        if symbol_upper in satellite_assets:
            return 'SATELLITE'
        return 'SPECULATIVE'
    
    def _get_display_name(self, symbol: str) -> str:
        """Get display name for symbol"""
        name_map = {
            'USDT': 'Tether',
            'USDC': 'USD Coin',
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'BNB': 'BNB',
            'ADA': 'Cardano',
            'DOT': 'Polkadot',
            'LINK': 'Chainlink',
            'XRP': 'XRP',
            'MATIC': 'Polygon',
            'SOL': 'Solana',
        }
        return name_map.get(symbol.upper(), symbol)
    
    def _extract_assets_from_response(self, response_data: Any) -> List[Dict[str, Any]]:
        """
        Extract asset list from LBank response formats.
        According to docs: /v2/supplement/user_info.do returns direct array:
        [{"coin": "btc", "usableAmt": "110.00869", "freezeAmt": "0.02", "assetAmt": "110.02869", ...}]
        """
        list_data = []
        
        # Direct array response (most common per LBank docs)
        if isinstance(response_data, list):
            list_data = response_data
            logger.debug(f"Extracted {len(list_data)} assets from direct array response")
            return list_data
        
        # Object response with nested data
        if isinstance(response_data, dict):
            # Check data field first
            if isinstance(response_data.get('data'), list):
                list_data = response_data['data']
                logger.debug(f"Extracted {len(list_data)} assets from response.data")
                return list_data
            
            # Check nested data.data
            if isinstance(response_data.get('data', {}).get('data'), list):
                list_data = response_data['data']['data']
                logger.debug(f"Extracted {len(list_data)} assets from response.data.data")
                return list_data
            
            # Check info field
            if isinstance(response_data.get('info'), list):
                list_data = response_data['info']
                logger.debug(f"Extracted {len(list_data)} assets from response.info")
                return list_data
            
            # Search for first array with coin/asset fields (fallback)
            for key, v in response_data.items():
                if isinstance(v, list) and v:
                    first_item = v[0] if v else {}
                    if isinstance(first_item, dict):
                        # Check for LBank-specific fields
                        if any(key in first_item for key in ['coin', 'usableAmt', 'assetAmt', 'freezeAmt']):
                            list_data = v
                            logger.debug(f"Extracted {len(list_data)} assets from response.{key}")
                            return list_data
        
        if not list_data:
            logger.warning(f"No assets extracted from response. Response type: {type(response_data)}, Keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'N/A'}")
        
        return list_data
    
    async def get_user_info(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """Get user info (spot account)"""
        masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        logger.info(f"Fetching user info for API Key: {masked_key}")
        
        data = await self._get_user_assets_supplement(api_key, api_secret)
        if not self._is_result_true(data.get('result')):
            error_code = data.get('error_code', 'Unknown')
            error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
            raise Exception(f"LBank API error: {error_code} - {error_msg}")
        
        return data
    
    async def get_account_balance(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """Get account balance (trade account)"""
        masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        logger.info(f"Fetching account balance for API Key: {masked_key}")
        
        data = await self._get_trade_balances(api_key, api_secret)
        if not self._is_result_true(data.get('result')):
            error_code = data.get('error_code', 'Unknown')
            error_msg = data.get('msg') or data.get('error_msg', 'Unknown error')
            raise Exception(f"LBank API error: {error_code} - {error_msg}")
        
        return data
    
    async def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get ticker price for a symbol (uses cached price map)"""
        try:
            price_map = await self._get_all_prices_optimized()
            return self._get_price_from_map(symbol, price_map)
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def get_portfolio_data(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """
        Get complete portfolio data from LBank with optimized requests:
        - Single request for all prices (cached)
        - Parallel requests for spot and trade accounts
        """
        try:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
            logger.info(f"Fetching portfolio data from LBank for API Key: {masked_key}")
            
            # Fetch prices first (public, no auth, cached)
            price_map = await self._get_all_prices_optimized()
            
            # Fetch spot and trade balances
            wallet_task = self._get_user_assets_supplement(api_key, api_secret)
            trade_task = None
            
            try:
                trade_task = self._get_trade_balances(api_key, api_secret)
            except Exception:
                # Trade account might not exist or be accessible
                pass
            
            # Wait for spot account
            wallet = await wallet_task
            
            # Check result - but handle direct array responses too
            if isinstance(wallet, dict) and not self._is_result_true(wallet.get('result')):
                error_code = wallet.get('error_code', 'Unknown')
                error_msg = wallet.get('msg') or wallet.get('error_msg', '')
                raise Exception(f"LBank supplement user_info error: {error_code} - {error_msg}")
            
            # Log wallet structure for debugging
            logger.debug(f"Wallet response type: {type(wallet)}, is_list: {isinstance(wallet, list)}, keys: {list(wallet.keys()) if isinstance(wallet, dict) else 'N/A'}")
            
            # Wait for trade account if requested
            trade_info = None
            if trade_task:
                try:
                    trade_info = await trade_task
                    if not self._is_result_true(trade_info.get('result')):
                        logger.warning("Trade account data unavailable or invalid")
                        trade_info = None
                except Exception as e:
                    logger.warning(f"Failed to fetch trade balances: {e}")
                    trade_info = None
            
            assets = []
            total_value_usd = 0.0
            
            # Process spot assets - LBank returns: coin, usableAmt, freezeAmt, assetAmt
            list_data = self._extract_assets_from_response(wallet)
            
            logger.info(f"Processing {len(list_data)} spot assets from LBank")
            
            # Filter assets with balance > 0
            for row in list_data:
                # LBank uses 'coin' field per documentation
                symbol = str(row.get('coin', '') or row.get('asset', '')).upper()
                if not symbol:
                    logger.warning(f"Skipping row with no coin/asset field: {row.keys()}")
                    continue
                
                # LBank API fields per documentation:
                # - usableAmt: available balance (string)
                # - freezeAmt: frozen balance (string)
                # - assetAmt: total balance (string) - should equal usableAmt + freezeAmt
                usable_str = str(row.get('usableAmt', '0') or '0').strip()
                frozen_str = str(row.get('freezeAmt', '0') or '0').strip()
                asset_amt_str = str(row.get('assetAmt', '0') or '0').strip()
                
                try:
                    usable = float(usable_str) if usable_str else 0.0
                    frozen = float(frozen_str) if frozen_str else 0.0
                    asset_amt = float(asset_amt_str) if asset_amt_str else 0.0
                    
                    # Calculate quantity: prefer assetAmt if available, otherwise sum
                    if asset_amt > 0:
                        quantity = asset_amt
                        # Validate: assetAmt should approximately equal usable + frozen
                        calculated_total = usable + frozen
                        if abs(asset_amt - calculated_total) > 0.0001:
                            logger.warning(f"Asset {symbol}: assetAmt ({asset_amt}) != usable+frozen ({calculated_total}), using assetAmt")
                    else:
                        quantity = usable + frozen
                    
                    if quantity <= 0:
                        continue
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid numeric values for {symbol}: usable={usable_str}, frozen={frozen_str}, assetAmt={asset_amt_str}, error: {e}")
                    continue
                
                logger.debug(f"Asset {symbol}: usable={usable}, frozen={frozen}, assetAmt={asset_amt}, quantity={quantity}")
                
                try:
                    price = self._get_price_from_map(symbol, price_map)
                    current_price = price if price and price > 0 else None
                    value_usd = quantity * current_price if current_price else None
                    
                    asset_data = {
                        "id": f"lbank-{symbol.lower()}-{int(time.time() * 1000)}",
                        "symbol": symbol,
                        "quantity": quantity,
                        "free": usable,
                        "frozen": frozen,
                        "priceUSD": current_price,
                        "valueUSD": value_usd,
                        "costBasis": 0,
                        "averageBuyPrice": 0,
                        "unrealizedPnl": 0,
                        "unrealizedPnlPercent": 0,
                        "tier": self._get_asset_tier(symbol),
                        "accountType": "SPOT",
                        "lastUpdated": datetime.utcnow().isoformat()
                    }
                    assets.append(asset_data)
                    
                    if value_usd:
                        total_value_usd += value_usd
                except Exception as e:
                    logger.warning(f"Failed to process spot asset {symbol}: {e}")
                    assets.append({
                        "id": f"lbank-{symbol.lower()}-{int(time.time() * 1000)}",
                        "symbol": symbol,
                        "quantity": quantity,
                        "free": usable,
                        "frozen": frozen,
                        "priceUSD": None,
                        "valueUSD": None,
                        "costBasis": 0,
                        "averageBuyPrice": 0,
                        "unrealizedPnl": 0,
                        "unrealizedPnlPercent": 0,
                        "tier": self._get_asset_tier(symbol),
                        "accountType": "SPOT",
                        "lastUpdated": datetime.utcnow().isoformat()
                    })
            
            # Process futures/trade account balances (do NOT merge into spot assets list)
            # Per LBank docs: /v2/supplement/user_info_account.do returns:
            # {"canTrade": true, "balances": [{"asset": "BTC", "free": "...", "locked": "..."}]}
            if trade_info:
                info = trade_info.get('info') or trade_info.get('data') or trade_info
                balances = info.get('balances', [])
                
                logger.info(f"Processing trade account with {len(balances) if isinstance(balances, list) else 'unknown'} balances")
                
                # Handle different response formats
                if isinstance(balances, list) and len(balances) > 0:
                    free_obj = {}
                    freeze_obj = {}
                    for bal in balances:
                        # LBank uses 'asset' field (uppercase like "BTC")
                        asset_symbol = str(bal.get('asset', '')).upper()
                        if asset_symbol:
                            free_val = float(bal.get('free', 0) or 0)
                            locked_val = float(bal.get('locked', 0) or 0)
                            free_obj[asset_symbol] = free_val
                            freeze_obj[asset_symbol] = locked_val
                            logger.debug(f"Trade asset {asset_symbol}: free={free_val}, locked={locked_val}")
                else:
                    # Fallback: check for free/freeze objects directly
                    free_obj = info.get('free', {}) if isinstance(info.get('free'), dict) else {}
                    freeze_obj = info.get('freeze', {}) if isinstance(info.get('freeze'), dict) else {}
                
                all_symbols = set(list(free_obj.keys()) + list(freeze_obj.keys()))
                
                # Skip adding futures into assets here. The portfolio service will fetch
                # futures balances separately through get_futures_balances and compose
                # the final totals accurately without double counting.
            
            # Recalculate total strictly from final asset list to avoid any double counting
            total_value_usd_final = 0.0
            for a in assets:
                try:
                    val = float(a.get("valueUSD") or 0)
                except Exception:
                    val = 0.0
                total_value_usd_final += val
            logger.info(f"Portfolio: ${total_value_usd_final:.2f} USD, {len(assets)} assets")

            return {
                "totalValueUSD": total_value_usd_final,
                "costBasis": 0,  # Not available from LBank API
                "assets": assets,
            }
        except Exception as e:
            logger.error(f"LBank portfolio error: {e}", exc_info=True)
            raise Exception(f"Failed to fetch portfolio from LBank: {e}")

    async def get_futures_balances(self, api_key: str, api_secret: str) -> Dict[str, Any]:
        """Return parsed futures/contract account balances as a flat list with USD value estimates."""
        price_map = await self._get_all_prices_optimized()

        # Attempt contract API first (accurate futures data)
        try:
            contract_balance = await self._post_contract_signed(
                "/cfd/openApi/v1/prv/account",
                api_key,
                api_secret,
                {
                    "asset": self.contract_asset,
                    "productGroup": self.contract_product_group,
                },
            )
            if self._is_result_true(contract_balance.get("result")):
                normalized = self._parse_contract_balances(contract_balance, price_map)

                # Try to enrich with positions (best effort, optional)
                positions: List[Dict[str, Any]] = []
                try:
                    contract_positions = await self._post_contract_signed(
                        "/cfd/openApi/v1/prv/position",
                        api_key,
                        api_secret,
                        {
                            "asset": self.contract_asset,
                            "productGroup": self.contract_product_group,
                        },
                    )
                    if self._is_result_true(contract_positions.get("result")):
                        positions = self._parse_contract_positions(contract_positions, price_map)
                except Exception as pos_exc:
                    logger.debug(f"Failed to fetch contract positions: {pos_exc}")

                normalized["positions"] = positions
                return normalized
            else:
                logger.warning(f"Contract balance API returned result={contract_balance.get('result')}, falling back")
        except Exception as contract_exc:
            logger.warning(f"Contract API fetch failed, falling back to supplement endpoint: {contract_exc}")

        # Fallback: legacy supplement endpoint (may mirror spot values)
        return await self._legacy_futures_balances(api_key, api_secret, price_map)
        