import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime

class TelegramService:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)

    def send_signal(self, signal: Dict[str, Any]) -> bool:
        """Send trading signal to Telegram channel."""
        try:
            # Format the message
            message = self._format_signal_message(signal)
            
            # Send message
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            response.raise_for_status()
            self.logger.info(f"Signal sent to Telegram: {signal['symbol']} {signal['direction']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending signal to Telegram: {str(e)}")
            return False

    def _format_signal_message(self, signal: Dict[str, Any]) -> str:
        """Format signal data into a readable Telegram message."""
        # Emoji mapping
        emojis = {
            "CALL": "🟢",
            "PUT": "🔴",
            "profit": "📈",
            "loss": "📉",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        
        # Format the message
        message = f"""
<b>{emojis[signal['direction']]} {signal['symbol']} {signal['direction']} Signal</b>

💰 Price: {signal['price']}
🎯 Confidence: {signal['confidence'] * 100}%

<b>Technical Indicators:</b>
• RSI: {signal['indicators']['rsi']}
• Volatility: {signal['indicators']['volatility'] * 100}%
• MACD: {signal['indicators']['macd']['macd']} (Signal: {signal['indicators']['macd']['signal']})
• Stochastic: K={signal['indicators']['stochastic']['k']}, D={signal['indicators']['stochastic']['d']}

<b>Analysis:</b>
{emojis['info']} Reasons:
{chr(10).join('• ' + reason for reason in signal['analysis']['reasons'])}

{emojis['profit']} Profit Target: {signal['analysis']['profit_target']}
{emojis['loss']} Stop Loss: {signal['analysis']['stop_loss']}

⏰ Time: {datetime.fromisoformat(signal['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message

    def send_error(self, error_message: str) -> bool:
        """Send error message to Telegram channel."""
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": f"⚠️ Error: {error_message}",
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending error message to Telegram: {str(e)}")
            return False

    def send_stats(self, stats: Dict[str, Any]) -> bool:
        """Send statistics to Telegram channel."""
        try:
            message = f"""
<b>📊 Signal Statistics</b>

Total Signals Today: {stats['total_signals']}

<b>Signals by Symbol:</b>
{chr(10).join(f'• {symbol}: {data["calls"]} CALL, {data["puts"]} PUT' for symbol, data in stats['symbol_stats'].items())}

Average Confidence: {stats['avg_confidence']:.1f}%
"""
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending stats to Telegram: {str(e)}")
            return False

    @staticmethod
    def get_chat_id(bot_token: str) -> str:
        """
        Get the chat ID for a Telegram bot.
        
        Args:
            bot_token (str): The bot token from BotFather
            
        Returns:
            str: The chat ID or None if not found
        """
        try:
            # Make request to Telegram API
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            response = requests.get(url)
            data = response.json()
            
            if data.get("ok"):
                updates = data.get("result", [])
                if updates:
                    # Get the chat ID from the first message
                    chat_id = updates[0]["message"]["chat"]["id"]
                    return str(chat_id)
                else:
                    print("No messages found. Please send a message to your bot first.")
                    return None
            else:
                print(f"Error getting updates: {data.get('description')}")
                return None
                
        except Exception as e:
            print(f"Error getting chat ID: {str(e)}")
            return None 