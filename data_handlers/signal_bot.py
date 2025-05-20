from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import requests
import json
import time
import threading
import logging
import random
import numpy as np
from .otc_data_handler import OTCDataHandler
from .telegram_service import TelegramService

class SignalBot:
    def __init__(self, otc_handler: OTCDataHandler, service_url: str, api_key: str, telegram_service: Optional[TelegramService] = None):
        self.otc_handler = otc_handler
        self.service_url = service_url
        self.api_key = api_key
        self.telegram_service = telegram_service
        self.running = False
        self.signal_thread = None
        self.logger = logging.getLogger(__name__)
        
        # Signal generation settings
        self.min_interval = 1  # Minimum minutes between signals
        self.max_interval = 15  # Maximum minutes between signals
        self.confidence_threshold = 0.7  # Minimum confidence to send signal
        
        # Technical analysis settings
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.volatility_threshold = 0.2  # 20% volatility threshold
        
        # Additional technical indicators settings
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
        self.stoch_k = 14
        self.stoch_d = 3
        self.stoch_smooth = 3
        
        # Risk management settings
        self.max_daily_signals = 50
        self.min_profit_target = 0.02  # 2% minimum profit target
        self.max_loss_limit = 0.01    # 1% maximum loss limit
        self.signal_history = []

    def start(self, symbols: List[str]):
        """Start the signal bot for the given symbols."""
        if self.running:
            self.logger.warning("Signal bot is already running")
            return
            
        self.running = True
        self.signal_thread = threading.Thread(target=self._signal_loop, args=(symbols,))
        self.signal_thread.daemon = True
        self.signal_thread.start()
        self.logger.info(f"Signal bot started for symbols: {symbols}")

    def stop(self):
        """Stop the signal bot."""
        self.running = False
        if self.signal_thread:
            self.signal_thread.join()
        self.logger.info("Signal bot stopped")

    def _signal_loop(self, symbols: List[str]):
        """Main loop for generating and sending signals."""
        while self.running:
            try:
                for symbol in symbols:
                    if not self.running:
                        break
                        
                    # Get market data
                    market_data = self.otc_handler.get_otc_data(symbol)
                    if not market_data:
                        continue
                        
                    # Generate signal based on technical analysis
                    signal = self._generate_signal(symbol, market_data)
                    if signal and signal['confidence'] >= self.confidence_threshold:
                        # Send signal to service and Telegram
                        self._send_signal(signal)
                        
                        # Send stats every 10 signals
                        if len(self.signal_history) % 10 == 0:
                            self._send_stats()
                        
                    # Random delay between signals
                    delay = random.randint(self.min_interval * 60, self.max_interval * 60)
                    time.sleep(delay)
                    
            except Exception as e:
                error_msg = f"Error in signal loop: {str(e)}"
                self.logger.error(error_msg)
                if self.telegram_service:
                    self.telegram_service.send_error(error_msg)
                time.sleep(60)  # Wait a minute before retrying

    def _calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """Calculate MACD indicator."""
        if len(prices) < self.macd_slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
            
        # Calculate EMAs
        ema_fast = np.mean(prices[-self.macd_fast:])
        ema_slow = np.mean(prices[-self.macd_slow:])
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line
        signal_line = np.mean(prices[-self.macd_signal:])
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        return {
            'macd': round(macd_line, 4),
            'signal': round(signal_line, 4),
            'histogram': round(histogram, 4)
        }

    def _calculate_bollinger_bands(self, prices: List[float]) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < self.bb_period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
            
        # Calculate middle band (SMA)
        middle = np.mean(prices[-self.bb_period:])
        
        # Calculate standard deviation
        std = np.std(prices[-self.bb_period:])
        
        # Calculate upper and lower bands
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)
        
        return {
            'upper': round(upper, 4),
            'middle': round(middle, 4),
            'lower': round(lower, 4)
        }

    def _calculate_stochastic(self, high: List[float], low: List[float], close: List[float]) -> Dict[str, float]:
        """Calculate Stochastic Oscillator."""
        if len(close) < self.stoch_k:
            return {'k': 50, 'd': 50}
            
        # Calculate %K
        lowest_low = min(low[-self.stoch_k:])
        highest_high = max(high[-self.stoch_k:])
        
        if highest_high == lowest_low:
            k = 50
        else:
            k = ((close[-1] - lowest_low) / (highest_high - lowest_low)) * 100
            
        # Calculate %D (SMA of %K)
        d = np.mean([k] * self.stoch_d)
        
        return {
            'k': round(k, 2),
            'd': round(d, 2)
        }

    def _check_risk_limits(self, symbol: str) -> bool:
        """Check if we've hit any risk management limits."""
        # Check daily signal limit
        today = datetime.now().date()
        today_signals = [s for s in self.signal_history 
                        if s['timestamp'].date() == today and s['symbol'] == symbol]
        
        if len(today_signals) >= self.max_daily_signals:
            self.logger.warning(f"Daily signal limit reached for {symbol}")
            return False
            
        return True

    def _generate_signal(self, symbol: str, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate trading signal based on technical analysis."""
        try:
            # Check risk limits
            if not self._check_risk_limits(symbol):
                return None
                
            indicators = market_data.get('indicators', {})
            if not indicators:
                return None
                
            # Get current price and basic indicators
            current_price = market_data.get('price')
            rsi = indicators.get('rsi')
            volatility = indicators.get('volatility', 0)
            
            if not all([current_price, rsi]):
                return None
                
            # Get historical data for advanced indicators
            historical_data = self.otc_handler.get_historical_data(symbol)
            if not historical_data:
                return None
                
            # Extract price data
            prices = [d['close'] for d in historical_data]
            highs = [d['high'] for d in historical_data]
            lows = [d['low'] for d in historical_data]
            
            # Calculate advanced indicators
            macd = self._calculate_macd(prices)
            bb = self._calculate_bollinger_bands(prices)
            stoch = self._calculate_stochastic(highs, lows, prices)
            
            # Initialize signal components
            direction = None
            confidence = 0.0
            reasons = []
            
            # RSI Analysis
            if rsi <= self.rsi_oversold:
                direction = "CALL"
                confidence += 0.3
                reasons.append(f"RSI oversold ({rsi})")
            elif rsi >= self.rsi_overbought:
                direction = "PUT"
                confidence += 0.3
                reasons.append(f"RSI overbought ({rsi})")
                
            # MACD Analysis
            if macd['histogram'] > 0 and macd['macd'] > macd['signal']:
                if direction == "CALL":
                    confidence += 0.2
                    reasons.append("MACD bullish crossover")
            elif macd['histogram'] < 0 and macd['macd'] < macd['signal']:
                if direction == "PUT":
                    confidence += 0.2
                    reasons.append("MACD bearish crossover")
                    
            # Bollinger Bands Analysis
            if current_price <= bb['lower']:
                if direction == "CALL":
                    confidence += 0.2
                    reasons.append("Price below lower Bollinger Band")
            elif current_price >= bb['upper']:
                if direction == "PUT":
                    confidence += 0.2
                    reasons.append("Price above upper Bollinger Band")
                    
            # Stochastic Analysis
            if stoch['k'] <= 20 and stoch['d'] <= 20:
                if direction == "CALL":
                    confidence += 0.1
                    reasons.append("Stochastic oversold")
            elif stoch['k'] >= 80 and stoch['d'] >= 80:
                if direction == "PUT":
                    confidence += 0.1
                    reasons.append("Stochastic overbought")
                    
            # Adjust confidence based on volatility
            if volatility > self.volatility_threshold:
                confidence *= 0.8
                reasons.append(f"High volatility ({volatility})")
                
            # Calculate profit target and stop loss
            if direction:
                if direction == "CALL":
                    profit_target = current_price * (1 + self.min_profit_target)
                    stop_loss = current_price * (1 - self.max_loss_limit)
                else:
                    profit_target = current_price * (1 - self.min_profit_target)
                    stop_loss = current_price * (1 + self.max_loss_limit)
                    
                # Create signal
                signal = {
                    'symbol': symbol,
                    'direction': direction,
                    'confidence': round(confidence, 2),
                    'price': current_price,
                    'timestamp': datetime.now().isoformat(),
                    'indicators': {
                        'rsi': rsi,
                        'volatility': volatility,
                        'macd': macd,
                        'bollinger_bands': bb,
                        'stochastic': stoch
                    },
                    'analysis': {
                        'reasons': reasons,
                        'profit_target': round(profit_target, 4),
                        'stop_loss': round(stop_loss, 4)
                    }
                }
                
                # Add to signal history
                self.signal_history.append(signal)
                
                return signal
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {str(e)}")
            return None

    def _send_signal(self, signal: Dict[str, Any]) -> bool:
        """Send signal to external service and Telegram."""
        success = True
        
        # Send to external service
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            response = requests.post(
                self.service_url,
                json=signal,
                headers=headers,
                timeout=10
            )
            
            response.raise_for_status()
            self.logger.info(f"Signal sent to service: {signal['symbol']} {signal['direction']}")
            
        except Exception as e:
            self.logger.error(f"Error sending signal to service: {str(e)}")
            success = False
            
        # Send to Telegram if configured
        if self.telegram_service:
            try:
                telegram_success = self.telegram_service.send_signal(signal)
                if not telegram_success:
                    self.logger.error("Failed to send signal to Telegram")
                    success = False
            except Exception as e:
                self.logger.error(f"Error sending signal to Telegram: {str(e)}")
                success = False
                
        return success

    def _send_stats(self):
        """Send statistics to Telegram."""
        if not self.telegram_service:
            return
            
        try:
            today = datetime.now().date()
            today_signals = [s for s in self.signal_history 
                           if s['timestamp'].date() == today]
            
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
            
            # Calculate average confidence
            avg_confidence = 0
            if today_signals:
                avg_confidence = sum(s['confidence'] for s in today_signals) / len(today_signals)
            
            stats = {
                'total_signals': len(today_signals),
                'symbol_stats': symbol_stats,
                'avg_confidence': avg_confidence * 100
            }
            
            self.telegram_service.send_stats(stats)
            
        except Exception as e:
            self.logger.error(f"Error sending stats: {str(e)}")

    def update_settings(self, 
                       min_interval: Optional[int] = None,
                       max_interval: Optional[int] = None,
                       confidence_threshold: Optional[float] = None,
                       rsi_oversold: Optional[int] = None,
                       rsi_overbought: Optional[int] = None,
                       volatility_threshold: Optional[float] = None,
                       max_daily_signals: Optional[int] = None,
                       min_profit_target: Optional[float] = None,
                       max_loss_limit: Optional[float] = None):
        """Update signal bot settings."""
        if min_interval is not None:
            self.min_interval = min_interval
        if max_interval is not None:
            self.max_interval = max_interval
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
        if rsi_oversold is not None:
            self.rsi_oversold = rsi_oversold
        if rsi_overbought is not None:
            self.rsi_overbought = rsi_overbought
        if volatility_threshold is not None:
            self.volatility_threshold = volatility_threshold
        if max_daily_signals is not None:
            self.max_daily_signals = max_daily_signals
        if min_profit_target is not None:
            self.min_profit_target = min_profit_target
        if max_loss_limit is not None:
            self.max_loss_limit = max_loss_limit
            
        self.logger.info("Signal bot settings updated") 