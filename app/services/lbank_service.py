"""LBank Exchange Service - Optimized implementation with rate limiting"""
import asyncio
import hashlib
import hmac
import secrets
import time
from typing import Dict, List, Optional, Any
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
        
        # Rate limiters: Orders 500/10s, Others 200/10s
        self.general_rate_limiter = RateLimiter(max_requests=200, window_seconds=10)
        self.order_rate_limiter = RateLimiter(max_requests=500, window_seconds=10)
        
        # Cache for prices (valid for 5 seconds)
        self._price_cache: Dict[str, Dict[str, float]] = {}
        self._price_cache_timestamp: float = 0
        self._price_cache_ttl: float = 5.0  # 5 seconds cache

        # Try loading official LBank connector; fall back to manual HTTP if unavailable
        self._connector_available = False
        self._ConnectorClient = None
        try:
            from lbank.old_api import BlockHttpClient  # type: ignore
            self._ConnectorClient = BlockHttpClient
            self._connector_available = True
            logger.info("lbank-connector-python detected; will use official client")
        except Exception as e:
            logger.info(f"lbank-connector-python not available or failed to import: {e}; falling back to manual HTTP")
    
    def _is_result_true(self, val: Any) -> bool:
        """Check if result is True"""
        return val is True or val == 'true' or val == 'True' or str(val).lower() == 'true'
    
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

    async def _connector_request(
        self,
        method: str,
        api_path: str,
        api_key: str,
        api_secret: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use official connector client synchronously inside thread, wrapped for async."""
        if not self._connector_available or self._ConnectorClient is None:
            raise RuntimeError("Connector not available")

        # Respect rate limiting for private endpoints
        await self.general_rate_limiter.wait_if_needed()

        def _sync_call() -> Dict[str, Any]:
            client = self._ConnectorClient(
                sign_method="HmacSHA256",
                api_key=api_key,
                api_secret=api_secret,
                base_url="https://api.lbkex.com/",
                is_json=True,
                log_level=logging.WARNING,
            )
            return client.http_request(method.lower(), api_path, payload=payload or {})  # type: ignore[arg-type]

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
                    payload={},
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
                    payload={},
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
            
            # Process futures/trade account balances
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
                
                for sym in all_symbols:
                    symbol = str(sym).upper()
                    if not symbol:
                        continue
                    
                    free = float(free_obj.get(sym, 0))
                    frozen = float(freeze_obj.get(sym, 0))
                    qty = free + frozen
                    
                    if qty <= 0:
                        continue
                    
                    try:
                        price = self._get_price_from_map(symbol, price_map)
                        current_price = price if price and price > 0 else None
                        value_usd = qty * current_price if current_price else None
                        
                        # Check if asset already exists (SPOT)
                        existing_idx = next(
                            (i for i, a in enumerate(assets) if a['symbol'] == symbol),
                            None
                        )
                        
                        if existing_idx is not None:
                            # Merge with existing asset
                            existing = assets[existing_idx]
                            combined_qty = existing['quantity'] + qty
                            combined_val = (existing['valueUSD'] or 0) + (value_usd or 0)
                            assets[existing_idx] = {
                                **existing,
                                "quantity": combined_qty,
                                "valueUSD": combined_val,
                                "accountType": "COMBINED",
                                "lastUpdated": datetime.utcnow().isoformat()
                            }
                        else:
                            assets.append({
                                "id": f"lbank-trade-{symbol.lower()}-{int(time.time() * 1000)}",
                                "symbol": symbol,
                                "quantity": qty,
                                "free": free,
                                "frozen": frozen,
                                "priceUSD": current_price,
                                "valueUSD": value_usd,
                                "costBasis": 0,
                                "averageBuyPrice": 0,
                                "unrealizedPnl": 0,
                                "unrealizedPnlPercent": 0,
                                "tier": self._get_asset_tier(symbol),
                                "accountType": "FUTURES",
                                "lastUpdated": datetime.utcnow().isoformat()
                            })
                        
                        if value_usd:
                            total_value_usd += value_usd
                    except Exception as e:
                        logger.warning(f"Failed to process trade asset {symbol}: {e}")
            
            logger.info(f"Portfolio: ${total_value_usd:.2f} USD, {len(assets)} assets")
            
            return {
                "totalValueUSD": total_value_usd,
                "costBasis": 0,  # Not available from LBank API
                "assets": assets,
            }
        except Exception as e:
            logger.error(f"LBank portfolio error: {e}", exc_info=True)
            raise Exception(f"Failed to fetch portfolio from LBank: {e}")