import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from data_handlers.otc_data_handler import OTCDataHandler
from data_handlers.signal_bot import SignalBot
from data_handlers.telegram_service import TelegramService
from dotenv import load_dotenv
import json
from datetime import datetime

def print_signal(signal):
    """Print signal details in a readable format."""
    print("\n=== New Trading Signal ===")
    print(f"Symbol: {signal['symbol']}")
    print(f"Direction: {signal['direction']}")
    print(f"Confidence: {signal['confidence'] * 100}%")
    print(f"Current Price: {signal['price']}")
    print("\nTechnical Indicators:")
    print(f"RSI: {signal['indicators']['rsi']}")
    print(f"Volatility: {signal['indicators']['volatility'] * 100}%")
    print(f"MACD: {signal['indicators']['macd']['macd']} (Signal: {signal['indicators']['macd']['signal']})")
    print(f"Bollinger Bands: {signal['indicators']['bollinger_bands']['lower']} - {signal['indicators']['bollinger_bands']['upper']}")
    print(f"Stochastic: K={signal['indicators']['stochastic']['k']}, D={signal['indicators']['stochastic']['d']}")
    print("\nAnalysis:")
    print("Reasons:", ", ".join(signal['analysis']['reasons']))
    print(f"Profit Target: {signal['analysis']['profit_target']}")
    print(f"Stop Loss: {signal['analysis']['stop_loss']}")
    print("=" * 30)

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize OTC handler
    otc_handler = OTCDataHandler(
        cache=None,  # You can use Redis or other cache here
        alpha_vantage_api_key=os.getenv('ALPHA_VANTAGE_API_KEY'),
        openexchangerates_api_key=os.getenv('OPENEXCHANGERATES_API_KEY'),
        currencylayer_api_key=os.getenv('CURRENCYLAYER_API_KEY'),
        api_timeout=10,
        cache_duration=60
    )
    
    # Initialize Telegram service if configured
    telegram_service = None
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if telegram_bot_token and telegram_chat_id:
        telegram_service = TelegramService(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id
        )
        print("Telegram service initialized")
    else:
        print("Telegram service not configured")
    
    # Initialize signal bot
    signal_bot = SignalBot(
        otc_handler=otc_handler,
        service_url=os.getenv('SIGNAL_SERVICE_URL'),  # Your signal service endpoint
        api_key=os.getenv('SIGNAL_SERVICE_API_KEY'),  # Your signal service API key
        telegram_service=telegram_service
    )
    
    # Configure signal bot settings
    signal_bot.update_settings(
        min_interval=5,        # Minimum 5 minutes between signals
        max_interval=30,       # Maximum 30 minutes between signals
        confidence_threshold=0.8,  # Only send signals with 80%+ confidence
        rsi_oversold=25,       # More conservative RSI oversold level
        rsi_overbought=75,     # More conservative RSI overbought level
        volatility_threshold=0.15,  # 15% volatility threshold
        max_daily_signals=50,  # Maximum 50 signals per day per symbol
        min_profit_target=0.02,  # 2% minimum profit target
        max_loss_limit=0.01    # 1% maximum loss limit
    )
    
    # List of symbols to monitor
    symbols = [
        'USDBRL_OTC',
        'EURUSD_OTC',
        'GBPUSD_OTC'
    ]
    
    try:
        # Start the signal bot
        print("Starting signal bot...")
        print("Monitoring symbols:", ", ".join(symbols))
        print("\nPress Ctrl+C to stop the bot")
        print("Available commands:")
        print("- 'settings': Update bot settings")
        print("- 'stats': Show signal statistics")
        print("- 'stop': Stop the bot")
        
        signal_bot.start(symbols)
        
        # Keep the main thread running
        while True:
            command = input("\nEnter command: ").lower()
            
            if command == 'stop':
                break
                
            elif command == 'settings':
                # Example of updating settings
                new_settings = {
                    'confidence_threshold': 0.85,  # Increase confidence threshold
                    'volatility_threshold': 0.12,  # Lower volatility threshold
                    'min_profit_target': 0.03,     # Increase profit target to 3%
                    'max_loss_limit': 0.015        # Increase loss limit to 1.5%
                }
                signal_bot.update_settings(**new_settings)
                print("\nSettings updated:")
                for key, value in new_settings.items():
                    print(f"- {key}: {value}")
                    
            elif command == 'stats':
                # Show signal statistics
                today = datetime.now().date()
                today_signals = [s for s in signal_bot.signal_history 
                               if s['timestamp'].date() == today]
                
                print("\n=== Signal Statistics ===")
                print(f"Total signals today: {len(today_signals)}")
                
                # Group by symbol
                symbol_stats = {}
                for signal in today_signals:
                    symbol = signal['symbol']
                    if symbol not in symbol_stats:
                        symbol_stats[symbol] = {'calls': 0, 'puts': 0}
                    if signal['direction'] == 'CALL':
                        symbol_stats[symbol]['calls'] += 1
                    else:
                        symbol_stats[symbol]['puts'] += 1
                
                print("\nSignals by symbol:")
                for symbol, stats in symbol_stats.items():
                    print(f"{symbol}: {stats['calls']} CALL, {stats['puts']} PUT")
                
                # Show average confidence
                if today_signals:
                    avg_confidence = sum(s['confidence'] for s in today_signals) / len(today_signals)
                    print(f"\nAverage confidence: {avg_confidence * 100:.1f}%")
                
    except KeyboardInterrupt:
        print("\nStopping signal bot...")
    finally:
        signal_bot.stop()
        print("Signal bot stopped")

if __name__ == "__main__":
    main() 