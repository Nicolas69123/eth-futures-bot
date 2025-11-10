#!/usr/bin/env python3
"""
Backtest de la Stratégie Hedge Fibonacci V4.1
Test sur données historiques Bitget (1 mois)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json

# Configuration de la stratégie
CAPITAL_INITIAL = 100  # 100€
MARGIN_INITIAL = 0.05  # 0.05€ par position
LEVERAGE = 50
TP_PERCENT = 0.5  # Take Profit à 0.5%
FIBO_LEVELS = [0.8, 1.6, 3.2, 6.4, 12.8]  # Progression x2
COMMISSION_RATE = 0.055 / 100  # 0.055% Bitget Futures

class BacktestEngine:
    def __init__(self, symbol='DOGE/USDT:USDT', timeframe='15m', lookback_days=30):
        """Initialize backtest engine"""
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_days = lookback_days

        # Load API credentials for data fetching
        load_dotenv()

        # Initialize exchange
        self.exchange = ccxt.bitget({
            'apiKey': os.getenv('BITGET_API_KEY'),
            'secret': os.getenv('BITGET_SECRET_KEY'),
            'password': os.getenv('BITGET_PASSPHRASE'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultMarginMode': 'cross'
            }
        })

        # Trading state
        self.reset_state()

        # Performance tracking
        self.trades = []
        self.equity_curve = []

    def reset_state(self):
        """Reset trading state"""
        self.capital = CAPITAL_INITIAL
        self.positions = {
            'long': None,
            'short': None
        }
        self.orders = {
            'tp_long': None,
            'tp_short': None,
            'fibo_long': [],
            'fibo_short': []
        }

    def fetch_historical_data(self):
        """Fetch historical OHLCV data from Bitget"""
        print(f"📊 Fetching {self.lookback_days} days of {self.timeframe} data for {self.symbol}...")

        since = self.exchange.milliseconds() - (self.lookback_days * 24 * 60 * 60 * 1000)
        ohlcv = []

        while since < self.exchange.milliseconds():
            try:
                batch = self.exchange.fetch_ohlcv(
                    self.symbol,
                    timeframe=self.timeframe,
                    since=since,
                    limit=1000
                )
                if not batch:
                    break
                ohlcv.extend(batch)
                since = batch[-1][0] + 1
                print(f"  • Fetched {len(ohlcv)} candles...")
            except Exception as e:
                print(f"⚠️ Error fetching data: {e}")
                break

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        print(f"✅ Downloaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        return df

    def open_hedge(self, price, timestamp):
        """Open initial hedge positions"""
        # Calculate position size
        notional = MARGIN_INITIAL * LEVERAGE
        size = notional / price

        # Open LONG
        self.positions['long'] = {
            'entry_price': price,
            'avg_price': price,
            'size': size,
            'margin': MARGIN_INITIAL,
            'total_margin': MARGIN_INITIAL,
            'pnl': 0,
            'open_time': timestamp
        }

        # Open SHORT
        self.positions['short'] = {
            'entry_price': price,
            'avg_price': price,
            'size': size,
            'margin': MARGIN_INITIAL,
            'total_margin': MARGIN_INITIAL,
            'pnl': 0,
            'open_time': timestamp
        }

        # Place TP orders
        self.orders['tp_long'] = price * (1 + TP_PERCENT/100)
        self.orders['tp_short'] = price * (1 - TP_PERCENT/100)

        # Place initial Fibo orders
        self.orders['fibo_long'] = [price * (1 - FIBO_LEVELS[0]/100)]
        self.orders['fibo_short'] = [price * (1 + FIBO_LEVELS[0]/100)]

        # Deduct commission
        commission = notional * 2 * COMMISSION_RATE
        self.capital -= commission

        # Track the trade
        self.trades.append({
            'timestamp': timestamp,
            'type': 'OPEN_HEDGE',
            'price': price,
            'size': size * 2,
            'commission': commission
        })

    def check_tp_hit(self, price):
        """Check if any TP is hit"""
        tp_hit = None

        # Check LONG TP
        if self.positions['long'] and self.orders['tp_long']:
            if price >= self.orders['tp_long']:
                tp_hit = 'long'

        # Check SHORT TP
        if self.positions['short'] and self.orders['tp_short']:
            if price <= self.orders['tp_short']:
                tp_hit = 'short'

        return tp_hit

    def check_fibo_hit(self, price):
        """Check if any Fibo level is hit"""
        fibo_hit = None

        # Check LONG Fibo (price going down)
        if self.orders['fibo_long']:
            for fibo_price in self.orders['fibo_long']:
                if price <= fibo_price:
                    fibo_hit = ('long', fibo_price)
                    break

        # Check SHORT Fibo (price going up)
        if self.orders['fibo_short']:
            for fibo_price in self.orders['fibo_short']:
                if price >= fibo_price:
                    fibo_hit = ('short', fibo_price)
                    break

        return fibo_hit

    def close_position_tp(self, side, price, timestamp):
        """Close position on TP hit"""
        pos = self.positions[side]
        if not pos:
            return

        # Calculate profit (always 0.5% of total margin)
        profit = pos['total_margin'] * LEVERAGE * (TP_PERCENT/100)

        # Add profit to capital
        self.capital += profit

        # Commission
        commission = pos['total_margin'] * LEVERAGE * COMMISSION_RATE
        self.capital -= commission

        # Track the trade
        self.trades.append({
            'timestamp': timestamp,
            'type': f'TP_{side.upper()}',
            'price': price,
            'size': pos['size'],
            'profit': profit,
            'commission': commission
        })

        # Reset position
        self.positions[side] = None
        self.positions['long' if side == 'short' else 'short'] = None

        # Clear all orders
        self.orders = {
            'tp_long': None,
            'tp_short': None,
            'fibo_long': [],
            'fibo_short': []
        }

        # Reopen hedge
        self.open_hedge(price, timestamp)

    def double_position(self, side, fibo_price, current_price, timestamp, fibo_index):
        """Double position when Fibo hit"""
        pos = self.positions[side]
        if not pos:
            return

        # Double the margin
        new_margin = pos['margin']  # Same margin as last addition
        new_size = (new_margin * LEVERAGE) / current_price

        # Update position
        old_total = pos['avg_price'] * pos['size']
        new_total = fibo_price * new_size

        pos['size'] += new_size
        pos['avg_price'] = (old_total + new_total) / pos['size']
        pos['total_margin'] += new_margin
        pos['margin'] = new_margin * 2  # For next doubling

        # Update TP based on new average price
        if side == 'long':
            self.orders['tp_long'] = pos['avg_price'] * (1 + TP_PERCENT/100)
        else:
            self.orders['tp_short'] = pos['avg_price'] * (1 - TP_PERCENT/100)

        # Place next Fibo level
        if fibo_index < len(FIBO_LEVELS) - 1:
            next_fibo_level = FIBO_LEVELS[fibo_index + 1]
            if side == 'long':
                next_price = pos['entry_price'] * (1 - next_fibo_level/100)
                self.orders['fibo_long'].append(next_price)
            else:
                next_price = pos['entry_price'] * (1 + next_fibo_level/100)
                self.orders['fibo_short'].append(next_price)

        # Commission
        commission = new_margin * LEVERAGE * COMMISSION_RATE
        self.capital -= commission

        # Track the trade
        self.trades.append({
            'timestamp': timestamp,
            'type': f'FIBO_{side.upper()}_{fibo_index+1}',
            'price': fibo_price,
            'size': new_size,
            'new_avg': pos['avg_price'],
            'commission': commission
        })

    def update_pnl(self, price):
        """Update PnL for all positions"""
        total_pnl = 0

        # LONG PnL
        if self.positions['long']:
            pos = self.positions['long']
            price_change = (price - pos['avg_price']) / pos['avg_price']
            pos['pnl'] = pos['total_margin'] * LEVERAGE * price_change
            total_pnl += pos['pnl']

        # SHORT PnL
        if self.positions['short']:
            pos = self.positions['short']
            price_change = (pos['avg_price'] - price) / pos['avg_price']
            pos['pnl'] = pos['total_margin'] * LEVERAGE * price_change
            total_pnl += pos['pnl']

        return total_pnl

    def run_backtest(self):
        """Run the backtest simulation"""
        # Fetch historical data
        df = self.fetch_historical_data()

        print("\n" + "="*80)
        print("🚀 STARTING BACKTEST")
        print("="*80)
        print(f"Capital: {CAPITAL_INITIAL}€")
        print(f"Margin per position: {MARGIN_INITIAL}€")
        print(f"Leverage: {LEVERAGE}x")
        print(f"TP: {TP_PERCENT}%")
        print(f"Fibo levels: {FIBO_LEVELS}")
        print("="*80 + "\n")

        # Initialize with first price
        initial_price = df.iloc[0]['close']
        self.open_hedge(initial_price, df.index[0])

        # Simulate each candle
        for idx, row in df.iterrows():
            current_price = row['close']

            # Update PnL
            total_pnl = self.update_pnl(current_price)

            # Track equity
            equity = self.capital + total_pnl
            self.equity_curve.append({
                'timestamp': idx,
                'price': current_price,
                'equity': equity,
                'pnl': total_pnl
            })

            # Check for liquidation
            if equity <= 0:
                print(f"💥 LIQUIDATION at {idx}! Price: ${current_price:.5f}")
                break

            # Check TP hits
            tp_hit = self.check_tp_hit(current_price)
            if tp_hit:
                self.close_position_tp(tp_hit, current_price, idx)

            # Check Fibo hits
            fibo_hit = self.check_fibo_hit(current_price)
            if fibo_hit:
                side, fibo_price = fibo_hit
                # Find which Fibo level was hit
                if side == 'long':
                    fibo_index = len(self.orders['fibo_long']) - 1
                else:
                    fibo_index = len(self.orders['fibo_short']) - 1
                self.double_position(side, fibo_price, current_price, idx, fibo_index)

        # Final statistics
        self.print_results()

    def print_results(self):
        """Print backtest results"""
        print("\n" + "="*80)
        print("📊 BACKTEST RESULTS")
        print("="*80)

        # Calculate metrics
        equity_df = pd.DataFrame(self.equity_curve)
        final_equity = equity_df['equity'].iloc[-1]
        total_return = ((final_equity - CAPITAL_INITIAL) / CAPITAL_INITIAL) * 100

        # Count trade types
        tp_trades = [t for t in self.trades if 'TP' in t['type']]
        fibo_trades = [t for t in self.trades if 'FIBO' in t['type']]

        # Calculate total profit from TPs
        tp_profit = sum([t.get('profit', 0) for t in tp_trades])
        total_commission = sum([t.get('commission', 0) for t in self.trades])

        # Max drawdown
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()

        print(f"Initial Capital: {CAPITAL_INITIAL:.2f}€")
        print(f"Final Equity: {final_equity:.2f}€")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Max Drawdown: {max_drawdown:.2f}%")
        print()
        print(f"Total Trades: {len(self.trades)}")
        print(f"TP Hits: {len(tp_trades)}")
        print(f"Fibo Hits: {len(fibo_trades)}")
        print(f"TP Profit: {tp_profit:.2f}€")
        print(f"Total Commissions: {total_commission:.2f}€")
        print()
        print(f"Daily Return: {total_return / self.lookback_days:.2f}%")
        print(f"Monthly Return (projected): {total_return:.2f}%")

        # Show trade distribution
        print("\n📈 Trade Distribution:")
        trade_types = {}
        for t in self.trades:
            trade_type = t['type'].split('_')[0]
            trade_types[trade_type] = trade_types.get(trade_type, 0) + 1

        for ttype, count in trade_types.items():
            print(f"  • {ttype}: {count} trades")

        # Save results to file
        results = {
            'config': {
                'capital': CAPITAL_INITIAL,
                'margin': MARGIN_INITIAL,
                'leverage': LEVERAGE,
                'tp_percent': TP_PERCENT,
                'fibo_levels': FIBO_LEVELS
            },
            'results': {
                'final_equity': final_equity,
                'total_return': total_return,
                'max_drawdown': max_drawdown,
                'total_trades': len(self.trades),
                'tp_hits': len(tp_trades),
                'fibo_hits': len(fibo_trades)
            },
            'trades': self.trades[-10:]  # Last 10 trades
        }

        with open('backtest_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print("\n✅ Results saved to backtest_results.json")
        print("="*80)

if __name__ == "__main__":
    # Run backtest
    backtest = BacktestEngine(
        symbol='DOGE/USDT:USDT',
        timeframe='15m',
        lookback_days=30
    )

    try:
        backtest.run_backtest()
    except Exception as e:
        print(f"❌ Backtest error: {e}")
        import traceback
        traceback.print_exc()