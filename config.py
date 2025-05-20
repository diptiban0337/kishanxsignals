"""
Configuration settings for the trading application.
"""

# API Configuration
ALPHA_VANTAGE_API_KEY = "35BDZ47V6D5T4B8G"
OPENEXCHANGERATES_API_KEY = "d16db1e03711417581ce5a2dda273830"  # Using same key as Alpha Vantage for now
CURRENCYLAYER_API_KEY = "9e46ca5a5edd08e5592cb1779e9dc05d"  # Using same key as Alpha Vantage for now

# API Settings
API_TIMEOUT = 10  # seconds
CACHE_DURATION = 300  # 5 minutes
PREMIUM_API_ENABLED = False
PREMIUM_API_CALLS_PER_MINUTE = 5

# Rate Limiting
ALPHA_VANTAGE_RATE_LIMIT = 5  # calls per minute
EXCHANGERATE_API_RATE_LIMIT = 10
FIXER_RATE_LIMIT = 10
OPENEXCHANGERATES_RATE_LIMIT = 10
CURRENCYLAYER_RATE_LIMIT = 10

# Data Source Priorities (1 is highest)
DATA_SOURCE_PRIORITIES = {
    'Alpha Vantage': 1,
    'ExchangeRate-API': 2,
    'Fixer.io': 3,
    'Open Exchange Rates': 4,
    'Currency Layer': 5
}

# Cache Settings
PRICE_CACHE_DURATION = 300  # 5 minutes
HISTORICAL_CACHE_DURATION = 3600  # 1 hour

# Validation Settings
MIN_PRICE = 0.000001
MAX_PRICE = 1000000
PRICE_VALIDATION_ENABLED = True

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "trading_app.log"

# Database
DATABASE_URL = "sqlite:///trading.db"

# WebSocket
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765

# Trading Settings
DEFAULT_TIMEFRAME = "1m"
DEFAULT_VOLUME_THRESHOLD = 100000
DEFAULT_SPREAD_THRESHOLD = 1.5

# Risk Management
MAX_POSITION_SIZE = 0.02  # 2% of account
MAX_DAILY_TRADES = 10
MAX_DAILY_LOSS = 0.05  # 5% of account
STOP_LOSS_PERCENTAGE = 0.02  # 2%
TAKE_PROFIT_PERCENTAGE = 0.04  # 4%

# Signal Generation
SIGNAL_CONFIDENCE_THRESHOLD = 0.75
MIN_VOLUME_THRESHOLD = 100000
MAX_SPREAD_THRESHOLD = 1.5
REQUIRED_CONFIRMATIONS = 2

# OTC Specific Settings
OTC_VOLUME_THRESHOLD = 150000
OTC_SPREAD_THRESHOLD = 1.0
OTC_MIN_ACCURACY = 0.75
OTC_REQUIRED_CONFIRMATIONS = 3 