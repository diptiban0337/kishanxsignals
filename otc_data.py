try:
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.foreignexchange import ForeignExchange
except ImportError:
    print("Warning: alpha_vantage module not found. Some features may be limited.")
    TimeSeries = None
    ForeignExchange = None

import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import time
from typing import Dict, Optional, Tuple, Union
import os
import requests
import logging
import random
import numpy as np
from config import (
    ALPHA_VANTAGE_API_KEY,
    OPENEXCHANGERATES_API_KEY,
    CURRENCYLAYER_API_KEY,
    API_TIMEOUT,
    CACHE_DURATION,
    PREMIUM_API_ENABLED,
    PREMIUM_API_CALLS_PER_MINUTE
)
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OTCDataHandler:
    def __init__(self, api_key=ALPHA_VANTAGE_API_KEY):
        """
        Initialize OTC data handler with API key.
        
        Args:
            api_key (str): Alpha Vantage API key
        """
        if not api_key or api_key == "YOUR_PREMIUM_API_KEY":
            logger.error("Valid Alpha Vantage API key is required")
            raise ValueError("Valid Alpha Vantage API key is required")
            
        self.api_key = api_key
        self.ts = TimeSeries(key=api_key, output_format='pandas')
        self.fx = ForeignExchange(key=api_key, output_format='pandas')
        self.price_cache = {}
        self.last_api_call = 0
        self.api_call_count = 0
        
        # Define data sources in order of preference with improved rate limits
        self.data_sources = [
            {
                'name': 'ExchangeRate-API',
                'function': self._get_exchangerate_api_rate,
                'priority': 1,
                'rate_limit': 30,  # Increased rate limit
                'timeout': API_TIMEOUT,
                'retry_after': 60  # Retry after 60 seconds if rate limited
            },
            {
                'name': 'Alpha Vantage',
                'function': self._get_alpha_vantage_rate,
                'priority': 2,
                'rate_limit': 5,
                'timeout': API_TIMEOUT,
                'retry_after': 300  # Retry after 5 minutes if rate limited
            },
            {
                'name': 'Fixer.io',
                'function': self._get_fixer_rate,
                'priority': 3,
                'rate_limit': 10,
                'timeout': API_TIMEOUT,
                'retry_after': 60
            },
            {
                'name': 'Open Exchange Rates',
                'function': self._get_openexchangerates_rate,
                'priority': 4,
                'rate_limit': 10,
                'timeout': API_TIMEOUT,
                'retry_after': 60
            },
            {
                'name': 'Currency Layer',
                'function': self._get_currencylayer_rate,
                'priority': 5,
                'rate_limit': 10,
                'timeout': API_TIMEOUT,
                'retry_after': 60
            }
        ]
        
        # Initialize rate limiting for each source with improved tracking
        self.source_limits = {
            source['name']: {
                'last_call': 0,
                'call_count': 0,
                'last_error': None,
                'error_count': 0,
                'backoff_until': 0
            } for source in self.data_sources
        }
        
        self._validate_api_key()

    def _validate_api_key(self):
        """Validate the API key by making a test request."""
        try:
            logger.info("Validating Alpha Vantage API key")
            url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=EUR&to_currency=USD&apikey={self.api_key}"
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if "Error Message" in data:
                logger.error(f"Invalid API key: {data['Error Message']}")
                raise ValueError(f"Invalid API key: {data['Error Message']}")
                
            if "Note" in data:
                if "premium" in data["Note"].lower():
                    if not PREMIUM_API_ENABLED:
                        logger.warning("Premium API features required. Set PREMIUM_API_ENABLED=True in config.py")
                elif "API call frequency" in data["Note"]:
                    logger.warning(f"API rate limit reached: {data['Note']}")
                    
            logger.info("API key validation successful")
                    
        except requests.exceptions.Timeout:
            logger.warning("Timeout while validating API key. OTC features may be limited.")
            self.api_key_valid = False
            return
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while validating API key: {str(e)}")
            raise ValueError(f"Request error while validating API key: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to validate API key: {str(e)}")
            raise ValueError(f"Failed to validate API key: {str(e)}")

    def get_realtime_price(self, symbol: str, return_source: bool = False) -> Optional[Union[float, Tuple[float, str]]]:
        """
        Get real-time price for a symbol with improved error handling and fallback sources.
        Args:
            symbol (str): Symbol to get price for (e.g., 'AUDCAD_OTC')
            return_source (bool): If True, return (rate, source_name) tuple
        Returns:
            Optional[Union[float, Tuple[float, str]]]: Price and source if successful, None if failed
        """
        if not symbol.endswith('_OTC'):
            logger.error(f"Invalid symbol format: {symbol}")
            return None
        try:
            # Remove _OTC suffix and get base/quote currencies
            base_pair = symbol.replace('_OTC', '')
            base = base_pair[:3]
            quote = base_pair[3:]
            logger.info(f"Getting real-time price for {symbol} (base: {base}, quote: {quote})")
            invert_pairs = [
                ('USD', 'BRL'), ('USD', 'ARS'), ('USD', 'PKR'), ('USD', 'MXN'), ('USD', 'ZAR'),
                ('EUR', 'MXN'), ('EUR', 'ZAR'), ('GBP', 'MXN'), ('GBP', 'ZAR'), ('AUD', 'MXN'), ('AUD', 'ZAR'),
            ]
            data_sources = [
                (self._get_alpha_vantage_rate, 'Alpha Vantage'),
                (self._get_exchangerate_api_rate, 'ExchangeRate-API'),
                (self._get_fixer_rate, 'Fixer.io'),
                (self._get_openexchangerates_rate, 'Open Exchange Rates'),
                (self._get_currencylayer_rate, 'Currency Layer')
            ]
            for source_func, source_name in data_sources:
                try:
                    rate = source_func(base_pair)
                    if rate is not None:
                        needs_inversion = (base, quote) in invert_pairs
                        if needs_inversion:
                            rate = 1 / rate
                            logger.info(f"Inverted rate for {base}/{quote}: {rate}")
                        spread = 0.0002  # 2 pips spread
                        bid = rate * (1 - spread)
                        ask = rate * (1 + spread)
                        logger.info(f"Successfully got price for {symbol} from {source_name}: bid={bid}, ask={ask}")
                        if return_source:
                            return (rate, source_name)
                        else:
                            return rate
                except Exception as e:
                    logger.error(f"Error with {source_name} for {symbol}: {str(e)}")
                    continue
            logger.error(f"All data sources failed for {symbol}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting price for {symbol}: {str(e)}")
            return None

    def _check_rate_limit(self, source_name: str) -> bool:
        """Check if we're within rate limits for a data source with improved handling."""
        current_time = time.time()
        source_limit = self.source_limits[source_name]
        
        # Check if we're in backoff period
        if current_time < source_limit['backoff_until']:
            return False
            
        # Reset counter if a minute has passed
        if current_time - source_limit['last_call'] >= 60:
            source_limit['call_count'] = 0
            source_limit['last_call'] = current_time
            source_limit['error_count'] = 0
            
        # Get source config
        source_config = next((s for s in self.data_sources if s['name'] == source_name), None)
        if not source_config:
            return False
            
        # Check if we're within limits
        if source_limit['call_count'] < source_config['rate_limit']:
            source_limit['call_count'] += 1
            return True
            
        # If we hit the rate limit, set backoff period
        source_limit['backoff_until'] = current_time + source_config['retry_after']
        logger.warning(f"Rate limit reached for {source_name}, backing off for {source_config['retry_after']} seconds")
        return False

    def _validate_price(self, price: float) -> bool:
        """Validate if the price is reasonable."""
        if price is None or not isinstance(price, (int, float)):
            return False
        if price <= 0:
            return False
        if price > 1000000:  # Unrealistic exchange rate
            return False
        return True

    def _get_alpha_vantage_rate(self, pair: str) -> Optional[float]:
        """Get rate from Alpha Vantage with rate limit handling."""
        if not self.api_key:
            logger.warning("No Alpha Vantage API key provided")
            return None
            
        from_symbol = pair[:3]
        to_symbol = pair[3:]
        
        url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_symbol}&to_currency={to_symbol}&apikey={self.api_key}"
        
        try:
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API Error: {data['Error Message']}")
                return None
                
            if "Note" in data:
                if "premium" in data["Note"].lower():
                    logger.warning("Premium API features required")
                    return None
                elif "API call frequency" in data["Note"]:
                    logger.warning(f"API rate limit reached: {data['Note']}")
                    return None
                
            if "Realtime Currency Exchange Rate" in data:
                rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
                logger.info(f"Successfully fetched rate from Alpha Vantage: {rate}")
                return rate
                
        except Exception as e:
            logger.error(f"Error fetching from Alpha Vantage: {str(e)}")
            return None
        
        return None

    def _get_exchangerate_api_rate(self, pair: str) -> Optional[float]:
        """Get rate from ExchangeRate-API."""
        from_symbol = pair[:3]
        to_symbol = pair[3:]
        url = f"https://open.er-api.com/v6/latest/{from_symbol}"
        
        try:
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if data.get("result") == "error":
                logger.error(f"ExchangeRate-API Error: {data.get('error-type', 'Unknown error')}")
                return None
                
            if data.get("rates") and to_symbol in data["rates"]:
                rate = float(data["rates"][to_symbol])
                logger.info(f"Successfully fetched rate from ExchangeRate-API: {rate}")
                return rate
                
        except Exception as e:
            logger.error(f"Error fetching from ExchangeRate-API: {str(e)}")
            return None
        
        return None

    def _get_fixer_rate(self, from_currency, to_currency):
        """Get rate from Fixer.io API."""
        try:
            url = f"https://api.exchangerate.host/latest?base={from_currency}&symbols={to_currency}"
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if data.get("success", False) and to_currency in data.get("rates", {}):
                return float(data["rates"][to_currency])
                
        except Exception as e:
            logger.error(f"Fixer API error: {str(e)}")
            
        return None

    def _get_openexchangerates_rate(self, from_currency, to_currency):
        """Get rate from Open Exchange Rates API."""
        try:
            url = f"https://openexchangerates.org/api/latest.json?app_id={OPENEXCHANGERATES_API_KEY}&base={from_currency}&symbols={to_currency}"
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if data.get("rates") and to_currency in data["rates"]:
                return float(data["rates"][to_currency])
                
        except Exception as e:
            logger.error(f"Open Exchange Rates API error: {str(e)}")
            
        return None

    def _get_currencylayer_rate(self, from_currency, to_currency):
        """Get rate from Currency Layer API."""
        try:
            url = f"http://apilayer.net/api/live?access_key={CURRENCYLAYER_API_KEY}&currencies={to_currency}&source={from_currency}"
            response = requests.get(url, timeout=API_TIMEOUT)
            data = response.json()
            
            if data.get("success") and "quotes" in data:
                quote_key = f"{from_currency}{to_currency}"
                if quote_key in data["quotes"]:
                    return float(data["quotes"][quote_key])
                
        except Exception as e:
            logger.error(f"Currency Layer API error: {str(e)}")
            
        return None

    def _get_alpha_vantage_historical(self, from_currency: str, to_currency: str, interval: str = '1min') -> Optional[pd.DataFrame]:
        """Get historical data from Alpha Vantage."""
        try:
            if TimeSeries is None:
                logger.error("Alpha Vantage module not available")
                return None
                
            # Get intraday data
            data, _ = self.ts.get_intraday(
                symbol=f"{from_currency}{to_currency}",
                interval=interval,
                outputsize='compact'
            )
            
            if data is not None and not data.empty:
                # Rename columns to match our format
                data.columns = ['open', 'high', 'low', 'close', 'volume']
                return data
                
        except Exception as e:
            logger.error(f"Error fetching historical data from Alpha Vantage: {str(e)}")
            
        return None

    def get_historical_data(self, symbol: str, interval: str = '1min', 
                          output_size: str = 'compact') -> Optional[pd.DataFrame]:
        """Get historical data with improved error handling and fallback options."""
        try:
            if symbol.endswith('_OTC'):
                base_pair = symbol.replace('_OTC', '')
                from_currency = base_pair[:3]
                to_currency = base_pair[3:]
                
                # Try to get real data first
                data = self._get_alpha_vantage_historical(from_currency, to_currency, interval)
                
                # If Alpha Vantage fails, try alternative sources
                if data is None:
                    logger.info(f"Alpha Vantage failed for {symbol}, trying alternative sources...")
                    
                    # Try ExchangeRate-API for historical data
                    try:
                        url = f"https://open.er-api.com/v6/latest/{from_currency}"
                        response = requests.get(url, timeout=API_TIMEOUT)
                        data = response.json()
                        
                        if data.get("result") == "success" and to_currency in data.get("rates", {}):
                            # Create a simple DataFrame with current rate and some historical variation
                            current_rate = float(data["rates"][to_currency])
                            now = datetime.now()
                            
                            # Generate some historical data points with small variations
                            dates = pd.date_range(end=now, periods=30, freq='1min')
                            variations = np.random.normal(0, current_rate * 0.0001, len(dates))  # 0.01% variation
                            rates = current_rate + variations
                            
                            data = pd.DataFrame({
                                'open': rates,
                                'high': rates * (1 + np.random.uniform(0, 0.0002, len(dates))),
                                'low': rates * (1 - np.random.uniform(0, 0.0002, len(dates))),
                                'close': rates,
                                'volume': np.random.uniform(1000, 5000, len(dates))
                            }, index=dates)
                            
                            logger.info(f"Using ExchangeRate-API data for {symbol} with simulated historical data")
                            return data
                    except Exception as e:
                        logger.error(f"ExchangeRate-API error for historical data: {str(e)}")
                    
                    # If all sources fail, return None
                    logger.error(f"All data sources failed for historical data of {symbol}, no data available.")
                    return None
                    
                return data
        except Exception as e:
            logger.error(f"Error fetching historical data: {str(e)}")
            return None

    def calculate_technical_indicators(self, data: pd.DataFrame) -> Dict:
        """
        Calculate technical indicators for the given data using pandas_ta
        
        Args:
            data (pd.DataFrame): Price data
            
        Returns:
            Dict: Dictionary of technical indicators
        """
        try:
            # Ensure we have the required columns
            if '4. close' in data.columns:
                data = data.rename(columns={
                    '4. close': 'close',
                    '1. open': 'open',
                    '2. high': 'high',
                    '3. low': 'low',
                    '5. volume': 'volume'
                })

            # Calculate indicators manually since we have limited data points
            indicators = {}
            
            # Simple Moving Average (SMA)
            if len(data) >= 20:
                indicators['sma_20'] = data['close'].rolling(window=20).mean().iloc[-1]
            
            # Exponential Moving Average (EMA)
            if len(data) >= 20:
                indicators['ema_20'] = data['close'].ewm(span=20, adjust=False).mean().iloc[-1]
            
            # RSI
            if len(data) >= 14:
                delta = data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                indicators['rsi'] = (100 - (100 / (1 + rs))).iloc[-1]
            
            # MACD
            if len(data) >= 26:
                exp1 = data['close'].ewm(span=12, adjust=False).mean()
                exp2 = data['close'].ewm(span=26, adjust=False).mean()
                macd = exp1 - exp2
                signal = macd.ewm(span=9, adjust=False).mean()
                indicators['macd'] = macd.iloc[-1]
                indicators['macd_signal'] = signal.iloc[-1]
                indicators['macd_hist'] = (macd - signal).iloc[-1]
            
            # Bollinger Bands
            if len(data) >= 20:
                sma = data['close'].rolling(window=20).mean()
                std = data['close'].rolling(window=20).std()
                indicators['bb_upper'] = (sma + (std * 2)).iloc[-1]
                indicators['bb_middle'] = sma.iloc[-1]
                indicators['bb_lower'] = (sma - (std * 2)).iloc[-1]
            
            # Additional indicators
            if len(data) >= 14:
                # CCI - Fixed calculation without using mad()
                tp = (data['high'] + data['low'] + data['close']) / 3
                sma_tp = tp.rolling(window=20).mean()
                # Calculate mean deviation manually
                md = tp.rolling(window=20).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
                indicators['cci'] = ((tp - sma_tp) / (0.015 * md)).iloc[-1]
                
                # ADX
                tr = pd.DataFrame()
                tr['h-l'] = abs(data['high'] - data['low'])
                tr['h-pc'] = abs(data['high'] - data['close'].shift(1))
                tr['l-pc'] = abs(data['low'] - data['close'].shift(1))
                tr['tr'] = tr[['h-l', 'h-pc', 'l-pc']].max(axis=1)
                atr = tr['tr'].rolling(window=14).mean()
                indicators['atr'] = atr.iloc[-1]
            
            return indicators

        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return {}

    async def get_realtime_price_async(self, pair: str) -> Optional[Tuple[float, float]]:
        """Get real-time price data for a pair asynchronously"""
        try:
            # Remove _OTC suffix if present
            base_pair = pair.replace('_OTC', '')
            
            # Get the base currencies
            base_currency = base_pair[:3]  # First 3 characters
            quote_currency = base_pair[3:]  # Remaining characters
            
            # Get rates for both currencies
            base_rate = await self.get_currency_rate_async(base_currency)
            quote_rate = await self.get_currency_rate_async(quote_currency)
            
            if base_rate is None or quote_rate is None:
                print(f"Failed to get rates for {base_currency} or {quote_currency}")
                return None
                
            # Calculate the cross rate
            rate = base_rate / quote_rate
            
            # Add spread for OTC pairs
            spread = 0.0002  # 2 pips spread
            bid = rate * (1 - spread)
            ask = rate * (1 + spread)
            
            return (bid, ask)
            
        except Exception as e:
            print(f"Error in get_realtime_price_async: {str(e)}")
            return None 

    def _update_rate_limit(self, source_name: str):
        """Update rate limit tracking for a data source."""
        current_time = time.time()
        source_limit = self.source_limits[source_name]
        source_limit['last_call'] = current_time 