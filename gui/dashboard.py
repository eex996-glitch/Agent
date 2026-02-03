#!/usr/bin/env python3
"""
Trading Dashboard Widget
Real-time trading display with profit highlighting
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QSpinBox, QGroupBox, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
from datetime import datetime
import random

# Symbol configuration with realistic price ranges
SYMBOL_CONFIG = {
    "MESZ4": {"base_price": 5250.00, "point_value": 5.0, "tick_size": 0.25, "name": "Micro E-mini S&P 500 Dec 2024"},
    "MESH5": {"base_price": 5280.00, "point_value": 5.0, "tick_size": 0.25, "name": "Micro E-mini S&P 500 Mar 2025"},
    "ESZ4": {"base_price": 5250.00, "point_value": 50.0, "tick_size": 0.25, "name": "E-mini S&P 500 Dec 2024"},
    "ESH5": {"base_price": 5280.00, "point_value": 50.0, "tick_size": 0.25, "name": "E-mini S&P 500 Mar 2025"},
    "NQZ4": {"base_price": 18500.00, "point_value": 20.0, "tick_size": 0.25, "name": "E-mini Nasdaq 100 Dec 2024"},
    "NQH5": {"base_price": 18600.00, "point_value": 20.0, "tick_size": 0.25, "name": "E-mini Nasdaq 100 Mar 2025"},
}


class MetricCard(QFrame):
    """A card displaying a single metric"""

    def __init__(self, title, value="--", subtitle="", color="#00ff41"):
        super().__init__()
        self.color = color
        self.setup_ui(title, value, subtitle)

    def setup_ui(self, title, value, subtitle):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame:hover {{
                border-color: {self.color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {self.color}; font-size: 28px; font-weight: bold;")
        layout.addWidget(self.value_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.subtitle_label)

    def set_value(self, value, color=None):
        self.value_label.setText(str(value))
        if color:
            self.color = color
            self.value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")

    def set_subtitle(self, subtitle):
        self.subtitle_label.setText(subtitle)


class DashboardWidget(QWidget):
    """Main trading dashboard"""

    trade_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.trading_active = False
        self.emergency_stopped = False
        self.trades = []
        self.total_pnl = 0.0
        self.current_symbol = "MESZ4"
        self.simulated_prices = {}  # Track simulated prices per symbol
        self.signal_wait_reasons = []
        self.bars_analyzed = 0
        self.last_signal_check = None
        self.setup_ui()

        # Initialize prices for all symbols
        for symbol, config in SYMBOL_CONFIG.items():
            self.simulated_prices[symbol] = config["base_price"]

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Top metrics row
        metrics_layout = QHBoxLayout()

        self.balance_card = MetricCard("ACCOUNT BALANCE", "$50,000.00", "Starting balance", "#00ff41")
        metrics_layout.addWidget(self.balance_card)

        self.pnl_card = MetricCard("TODAY'S P&L", "$0.00", "0 trades", "#00ff41")
        metrics_layout.addWidget(self.pnl_card)

        self.drawdown_card = MetricCard("DRAWDOWN", "0.0%", "Max: $2,000", "#ffcc00")
        metrics_layout.addWidget(self.drawdown_card)

        self.win_rate_card = MetricCard("WIN RATE", "--", "No trades yet", "#00ccff")
        metrics_layout.addWidget(self.win_rate_card)

        layout.addLayout(metrics_layout)

        # Middle section - chart placeholder and controls
        middle_layout = QHBoxLayout()

        # Trading controls
        controls_group = QGroupBox("Trading Controls")
        controls_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #00ff41;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        controls_layout = QVBoxLayout(controls_group)

        # Symbol selector
        symbol_layout = QHBoxLayout()
        symbol_layout.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(list(SYMBOL_CONFIG.keys()))
        self.symbol_combo.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_changed)
        symbol_layout.addWidget(self.symbol_combo)
        controls_layout.addLayout(symbol_layout)

        # Symbol info label
        self.symbol_info_label = QLabel(SYMBOL_CONFIG["MESZ4"]["name"])
        self.symbol_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.symbol_info_label.setWordWrap(True)
        controls_layout.addWidget(self.symbol_info_label)

        # Risk per trade
        risk_layout = QHBoxLayout()
        risk_layout.addWidget(QLabel("Risk %:"))
        self.risk_spin = QSpinBox()
        self.risk_spin.setRange(1, 5)
        self.risk_spin.setValue(1)
        self.risk_spin.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        risk_layout.addWidget(self.risk_spin)
        controls_layout.addLayout(risk_layout)

        # Control buttons
        self.start_btn = QPushButton("START TRADING")
        self.start_btn.clicked.connect(self.toggle_trading)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #000;
                font-weight: bold;
                padding: 12px;
            }
        """)
        controls_layout.addWidget(self.start_btn)

        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: #fff;
                font-weight: bold;
                padding: 12px;
            }
        """)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        controls_layout.addWidget(self.emergency_btn)

        # Reset button (shown after emergency stop)
        self.reset_btn = QPushButton("RESET SYSTEM")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffcc00;
                color: #000;
                font-weight: bold;
                padding: 12px;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_system)
        self.reset_btn.hide()
        controls_layout.addWidget(self.reset_btn)

        controls_layout.addStretch()
        middle_layout.addWidget(controls_group, 1)

        # Position info
        position_group = QGroupBox("Current Position")
        position_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #00ccff;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        position_layout = QVBoxLayout(position_group)

        self.position_label = QLabel("NO POSITION")
        self.position_label.setStyleSheet("color: #888; font-size: 18px; font-weight: bold;")
        self.position_label.setAlignment(Qt.AlignCenter)
        position_layout.addWidget(self.position_label)

        position_details = QGridLayout()
        position_details.addWidget(QLabel("Entry:"), 0, 0)
        self.entry_label = QLabel("--")
        self.entry_label.setStyleSheet("color: #00ff41;")
        position_details.addWidget(self.entry_label, 0, 1)

        position_details.addWidget(QLabel("Stop Loss:"), 1, 0)
        self.stop_label = QLabel("--")
        self.stop_label.setStyleSheet("color: #ff4444;")
        position_details.addWidget(self.stop_label, 1, 1)

        position_details.addWidget(QLabel("Take Profit:"), 2, 0)
        self.tp_label = QLabel("--")
        self.tp_label.setStyleSheet("color: #00ff41;")
        position_details.addWidget(self.tp_label, 2, 1)

        position_details.addWidget(QLabel("Unrealized P&L:"), 3, 0)
        self.unrealized_label = QLabel("$0.00")
        self.unrealized_label.setStyleSheet("color: #888;")
        position_details.addWidget(self.unrealized_label, 3, 1)

        position_layout.addLayout(position_details)
        position_layout.addStretch()
        middle_layout.addWidget(position_group, 1)

        # Market info
        market_group = QGroupBox("Market Data")
        market_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #ffcc00;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        market_layout = QVBoxLayout(market_group)

        self.price_label = QLabel("--")
        self.price_label.setStyleSheet("color: #00ff41; font-size: 32px; font-weight: bold;")
        self.price_label.setAlignment(Qt.AlignCenter)
        market_layout.addWidget(self.price_label)

        self.price_change_label = QLabel("")
        self.price_change_label.setStyleSheet("color: #888; font-size: 12px;")
        self.price_change_label.setAlignment(Qt.AlignCenter)
        market_layout.addWidget(self.price_change_label)

        market_details = QGridLayout()
        market_details.addWidget(QLabel("Trend:"), 0, 0)
        self.trend_label = QLabel("--")
        market_details.addWidget(self.trend_label, 0, 1)

        market_details.addWidget(QLabel("ADX:"), 1, 0)
        self.adx_label = QLabel("--")
        market_details.addWidget(self.adx_label, 1, 1)

        market_details.addWidget(QLabel("RSI:"), 2, 0)
        self.rsi_label = QLabel("--")
        market_details.addWidget(self.rsi_label, 2, 1)

        market_details.addWidget(QLabel("News Sentiment:"), 3, 0)
        self.sentiment_label = QLabel("--")
        market_details.addWidget(self.sentiment_label, 3, 1)

        market_layout.addLayout(market_details)
        market_layout.addStretch()
        middle_layout.addWidget(market_group, 1)

        layout.addLayout(middle_layout)

        # Trading Status Panel (NEW)
        status_group = QGroupBox("Trading Status")
        status_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #00ccff;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        status_layout = QVBoxLayout(status_group)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(120)
        self.status_text.setStyleSheet("""
            QTextEdit {
                background-color: #0f0f1a;
                color: #00ff41;
                border: 1px solid #3a3a5e;
                font-family: 'Hack', monospace;
                font-size: 11px;
            }
        """)
        self.status_text.setText("System ready. Select a symbol and click START TRADING to begin.")
        status_layout.addWidget(self.status_text)

        layout.addWidget(status_group)

        # Trade history table
        history_group = QGroupBox("Trade History")
        history_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #00ff41;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        history_layout = QVBoxLayout(history_group)

        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(7)
        self.trade_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Side", "Entry", "Exit", "P&L", "Status"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trade_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f0f1a;
                gridline-color: #3a3a5e;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #00ff41;
                padding: 8px;
                border: 1px solid #3a3a5e;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        history_layout.addWidget(self.trade_table)

        layout.addWidget(history_group)

    def on_symbol_changed(self, symbol):
        """Handle symbol selection change"""
        self.current_symbol = symbol
        config = SYMBOL_CONFIG.get(symbol, {})
        self.symbol_info_label.setText(config.get("name", ""))

        # Update market data display immediately
        price = self.simulated_prices.get(symbol, config.get("base_price", 0))
        self.price_label.setText(f"${price:,.2f}")
        self.price_change_label.setText(f"Point Value: ${config.get('point_value', 5):.2f}")

        self.add_status_message(f"Symbol changed to {symbol} ({config.get('name', '')})")

    def toggle_trading(self):
        """Toggle trading on/off"""
        if self.emergency_stopped:
            self.add_status_message("System is in EMERGENCY STOP mode. Click RESET SYSTEM first.")
            return

        self.trading_active = not self.trading_active
        if self.trading_active:
            self.start_btn.setText("STOP TRADING")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc00;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)
            self.bars_analyzed = 0
            self.add_status_message(f"Trading STARTED on {self.current_symbol}")
            self.add_status_message("Analyzing market conditions...")
            self.add_status_message("Waiting for valid entry signals...")
        else:
            self.start_btn.setText("START TRADING")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00ff41;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)
            self.add_status_message("Trading STOPPED by user")

    def set_trading_active(self, active):
        """Set trading state"""
        if self.emergency_stopped and active:
            return  # Don't allow starting if emergency stopped

        self.trading_active = active
        if active:
            self.start_btn.setText("STOP TRADING")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc00;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)
        else:
            self.start_btn.setText("START TRADING")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00ff41;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)

    def emergency_stop(self):
        """Emergency stop - close all positions"""
        self.trading_active = False
        self.emergency_stopped = True
        self.position_label.setText("EMERGENCY STOP")
        self.position_label.setStyleSheet("color: #ff4444; font-size: 18px; font-weight: bold;")
        self.start_btn.setText("START TRADING")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: #aaa;
                font-weight: bold;
                padding: 12px;
            }
        """)
        self.start_btn.setEnabled(False)
        self.reset_btn.show()

        self.add_status_message("!!! EMERGENCY STOP ACTIVATED !!!")
        self.add_status_message("All positions closed. Trading halted.")
        self.add_status_message("Click RESET SYSTEM to resume normal operation.")

    def reset_system(self):
        """Reset system after emergency stop"""
        self.emergency_stopped = False
        self.position_label.setText("NO POSITION")
        self.position_label.setStyleSheet("color: #888; font-size: 18px; font-weight: bold;")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("START TRADING")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #000;
                font-weight: bold;
                padding: 12px;
            }
        """)
        self.reset_btn.hide()

        # Clear position details
        self.entry_label.setText("--")
        self.stop_label.setText("--")
        self.tp_label.setText("--")
        self.unrealized_label.setText("$0.00")

        self.add_status_message("System RESET complete")
        self.add_status_message("Ready to trade. Click START TRADING to begin.")

    def add_status_message(self, message):
        """Add a timestamped message to the status panel"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        current_text = self.status_text.toPlainText()
        lines = current_text.split('\n')

        # Keep only last 20 lines
        if len(lines) > 20:
            lines = lines[-20:]

        lines.append(f"[{timestamp}] {message}")
        self.status_text.setText('\n'.join(lines))

        # Scroll to bottom
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_data(self):
        """Update dashboard with latest data"""
        # Always update market data, even when not trading
        symbol = self.current_symbol
        config = SYMBOL_CONFIG.get(symbol, {})
        base_price = config.get("base_price", 5000)

        # Simulate price movement (different for each symbol)
        old_price = self.simulated_prices.get(symbol, base_price)
        change = random.uniform(-2, 2)
        new_price = old_price + change
        self.simulated_prices[symbol] = new_price

        # Update price display
        self.price_label.setText(f"${new_price:,.2f}")

        price_change = new_price - base_price
        change_pct = (price_change / base_price) * 100
        change_color = "#00ff41" if price_change >= 0 else "#ff4444"
        self.price_change_label.setText(f"{price_change:+.2f} ({change_pct:+.2f}%) | Point: ${config.get('point_value', 5):.2f}")
        self.price_change_label.setStyleSheet(f"color: {change_color}; font-size: 12px;")

        # Update market indicators
        trend = random.choice(["BULLISH", "BEARISH", "NEUTRAL"])
        trend_colors = {"BULLISH": "#00ff41", "BEARISH": "#ff4444", "NEUTRAL": "#ffcc00"}
        self.trend_label.setText(trend)
        self.trend_label.setStyleSheet(f"color: {trend_colors[trend]};")

        adx = random.uniform(15, 45)
        self.adx_label.setText(f"{adx:.1f}")
        adx_color = "#00ff41" if adx > 25 else "#ffcc00" if adx > 20 else "#ff4444"
        self.adx_label.setStyleSheet(f"color: {adx_color};")

        rsi = random.uniform(30, 70)
        self.rsi_label.setText(f"{rsi:.1f}")
        rsi_color = "#ff4444" if rsi > 70 else "#ff4444" if rsi < 30 else "#00ff41"
        self.rsi_label.setStyleSheet(f"color: {rsi_color};")

        sentiment = random.choice(["Bullish", "Bearish", "Neutral"])
        sent_colors = {"Bullish": "#00ff41", "Bearish": "#ff4444", "Neutral": "#ffcc00"}
        self.sentiment_label.setText(sentiment)
        self.sentiment_label.setStyleSheet(f"color: {sent_colors[sentiment]};")

        # If actively trading, analyze signals
        if self.trading_active and not self.emergency_stopped:
            self.bars_analyzed += 1
            self.analyze_trading_conditions(trend, adx, rsi, new_price)

    def analyze_trading_conditions(self, trend, adx, rsi, price):
        """Analyze conditions and provide feedback on why no trade"""
        reasons = []
        can_trade = True

        # Check ADX (trend strength)
        if adx < 20:
            reasons.append(f"ADX too low ({adx:.1f} < 20) - weak trend")
            can_trade = False
        elif adx < 25:
            reasons.append(f"ADX borderline ({adx:.1f}) - waiting for stronger trend")

        # Check RSI (overbought/oversold)
        if rsi > 70:
            reasons.append(f"RSI overbought ({rsi:.1f}) - risky for longs")
        elif rsi < 30:
            reasons.append(f"RSI oversold ({rsi:.1f}) - risky for shorts")

        # Check trend alignment
        if trend == "NEUTRAL":
            reasons.append("No clear trend direction")
            can_trade = False

        # Simulate occasional signal generation
        if can_trade and random.random() < 0.05:  # 5% chance per update
            signal_type = "LONG" if trend == "BULLISH" else "SHORT"
            self.add_status_message(f"Signal generated: {signal_type} at ${price:,.2f}")
            self.add_status_message(f"Conditions: Trend={trend}, ADX={adx:.1f}, RSI={rsi:.1f}")
            # In a real system, this would place an order
            self.add_status_message("(Paper mode - no real order placed)")

        # Update status periodically (every 10 bars)
        if self.bars_analyzed % 10 == 0:
            self.add_status_message(f"Bars analyzed: {self.bars_analyzed}")
            if reasons:
                self.add_status_message(f"Waiting: {reasons[0]}")

    def add_trade(self, trade):
        """Add a trade to the history"""
        row = self.trade_table.rowCount()
        self.trade_table.insertRow(row)

        self.trade_table.setItem(row, 0, QTableWidgetItem(trade.get('time', '--')))
        self.trade_table.setItem(row, 1, QTableWidgetItem(trade.get('symbol', '--')))
        self.trade_table.setItem(row, 2, QTableWidgetItem(trade.get('side', '--')))
        self.trade_table.setItem(row, 3, QTableWidgetItem(f"${trade.get('entry', 0):,.2f}"))
        self.trade_table.setItem(row, 4, QTableWidgetItem(f"${trade.get('exit', 0):,.2f}"))

        pnl = trade.get('pnl', 0)
        pnl_item = QTableWidgetItem(f"${pnl:,.2f}")
        pnl_item.setForeground(QColor("#00ff41" if pnl >= 0 else "#ff4444"))
        self.trade_table.setItem(row, 5, pnl_item)

        self.trade_table.setItem(row, 6, QTableWidgetItem(trade.get('status', 'Closed')))

        self.trades.append(trade)
        self.update_pnl()

    def update_pnl(self):
        """Update P&L display"""
        self.total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        color = "#00ff41" if self.total_pnl >= 0 else "#ff4444"
        self.pnl_card.set_value(f"${self.total_pnl:,.2f}", color)
        self.pnl_card.set_subtitle(f"{len(self.trades)} trades")

        # Update win rate
        if self.trades:
            wins = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
            win_rate = (wins / len(self.trades)) * 100
            self.win_rate_card.set_value(f"{win_rate:.1f}%")
            self.win_rate_card.set_subtitle(f"{wins}W / {len(self.trades) - wins}L")
