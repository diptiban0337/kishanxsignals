import logging
from typing import Optional, Dict
import requests
from config import ALPHA_VANTAGE_API_KEY, API_TIMEOUT

logger = logging.getLogger(__name__)

def get_cached_realtime_forex(symbol: str) -> Optional[float]:
    """Get real-time Forex price data with caching."""
    try:
        # First try ExchangeRate-API
        from_symbol = symbol[:3]
        to_symbol = symbol[3:]
        url = f"https://open.er-api.com/v6/latest/{from_symbol}"
        
        response = requests.get(url, timeout=API_TIMEOUT)
        data = response.json()
        
        if data.get("result") == "success" and to_symbol in data.get("rates", {}):
            rate = float(data["rates"][to_symbol])
            logger.info(f"Successfully fetched rate for {symbol} from ExchangeRate-API: {rate}")
            return rate
            
        # If ExchangeRate-API fails, try Alpha Vantage
        url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={from_symbol}&to_currency={to_symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url, timeout=API_TIMEOUT)
        data = response.json()
        
        if "Realtime Currency Exchange Rate" in data:
            rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
            logger.info(f"Successfully fetched rate for {symbol} from Alpha Vantage: {rate}")
            return rate
            
        # If both APIs fail, try Fixer.io
        url = f"http://data.fixer.io/api/latest?access_key=YOUR_FIXER_API_KEY&base={from_symbol}&symbols={to_symbol}"
        response = requests.get(url, timeout=API_TIMEOUT)
        data = response.json()
        
        if data.get("success", False) and to_symbol in data.get("rates", {}):
            rate = float(data["rates"][to_symbol])
            logger.info(f"Successfully fetched rate for {symbol} from Fixer.io: {rate}")
            return rate
            
        logger.error(f"Failed to fetch rate for {symbol} from all sources")
        return None
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while fetching rate for {symbol}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while fetching rate for {symbol}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error fetching rate for {symbol}: {str(e)}")
        return None 