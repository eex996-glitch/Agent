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
import math

# MFFU (MyFundedFutures) available instruments with current 2026 contracts
# Front-month contracts roll quarterly: H=Mar, M=Jun, U=Sep, Z=Dec
SYMBOL_CONFIG = {
    # --- Equity Index Futures ---
    # E-mini S&P 500
    "ESH6":  {"base_price": 6050.00, "point_value": 50.0,  "tick_size": 0.25,  "name": "E-mini S&P 500 Mar 2026"},
    "ESM6":  {"base_price": 6080.00, "point_value": 50.0,  "tick_size": 0.25,  "name": "E-mini S&P 500 Jun 2026"},
    # Micro E-mini S&P 500
    "MESH6": {"base_price": 6050.00, "point_value": 5.0,   "tick_size": 0.25,  "name": "Micro E-mini S&P 500 Mar 2026"},
    "MESM6": {"base_price": 6080.00, "point_value": 5.0,   "tick_size": 0.25,  "name": "Micro E-mini S&P 500 Jun 2026"},
    # E-mini Nasdaq 100
    "NQH6":  {"base_price": 21500.00, "point_value": 20.0, "tick_size": 0.25,  "name": "E-mini Nasdaq 100 Mar 2026"},
    "NQM6":  {"base_price": 21600.00, "point_value": 20.0, "tick_size": 0.25,  "name": "E-mini Nasdaq 100 Jun 2026"},
    # Micro E-mini Nasdaq 100
    "MNQH6": {"base_price": 21500.00, "point_value": 2.0,  "tick_size": 0.25,  "name": "Micro E-mini Nasdaq 100 Mar 2026"},
    "MNQM6": {"base_price": 21600.00, "point_value": 2.0,  "tick_size": 0.25,  "name": "Micro E-mini Nasdaq 100 Jun 2026"},
    # E-mini Russell 2000
    "RTYH6": {"base_price": 2280.00,  "point_value": 50.0, "tick_size": 0.10,  "name": "E-mini Russell 2000 Mar 2026"},
    "RTYM6": {"base_price": 2290.00,  "point_value": 50.0, "tick_size": 0.10,  "name": "E-mini Russell 2000 Jun 2026"},
    # Micro E-mini Russell 2000
    "M2KH6": {"base_price": 2280.00,  "point_value": 5.0,  "tick_size": 0.10,  "name": "Micro E-mini Russell 2000 Mar 2026"},
    "M2KM6": {"base_price": 2290.00,  "point_value": 5.0,  "tick_size": 0.10,  "name": "Micro E-mini Russell 2000 Jun 2026"},
    # E-mini Dow Jones
    "YMH6":  {"base_price": 44200.00, "point_value": 5.0,  "tick_size": 1.0,   "name": "E-mini Dow Jones Mar 2026"},
    "YMM6":  {"base_price": 44300.00, "point_value": 5.0,  "tick_size": 1.0,   "name": "E-mini Dow Jones Jun 2026"},
    # Micro E-mini Dow Jones
    "MYMH6": {"base_price": 44200.00, "point_value": 0.50, "tick_size": 1.0,   "name": "Micro E-mini Dow Jones Mar 2026"},
    "MYMM6": {"base_price": 44300.00, "point_value": 0.50, "tick_size": 1.0,   "name": "Micro E-mini Dow Jones Jun 2026"},
    # --- Energy Futures ---
    # Crude Oil
    "CLH6":  {"base_price": 72.50,    "point_value": 1000.0, "tick_size": 0.01, "name": "Crude Oil Mar 2026"},
    "CLM6":  {"base_price": 73.00,    "point_value": 1000.0, "tick_size": 0.01, "name": "Crude Oil Jun 2026"},
    # Micro Crude Oil
    "MCLH6": {"base_price": 72.50,    "point_value": 100.0,  "tick_size": 0.01, "name": "Micro Crude Oil Mar 2026"},
    "MCLM6": {"base_price": 73.00,    "point_value": 100.0,  "tick_size": 0.01, "name": "Micro Crude Oil Jun 2026"},
    # Natural Gas
    "NGH6":  {"base_price": 3.20,     "point_value": 10000.0, "tick_size": 0.001, "name": "Natural Gas Mar 2026"},
    "NGM6":  {"base_price": 3.25,     "point_value": 10000.0, "tick_size": 0.001, "name": "Natural Gas Jun 2026"},
    # --- Metals Futures ---
    # Gold
    "GCH6":  {"base_price": 2680.00,  "point_value": 100.0,  "tick_size": 0.10, "name": "Gold Mar 2026"},
    "GCM6":  {"base_price": 2690.00,  "point_value": 100.0,  "tick_size": 0.10, "name": "Gold Jun 2026"},
    # Micro Gold
    "MGCH6": {"base_price": 2680.00,  "point_value": 10.0,   "tick_size": 0.10, "name": "Micro Gold Mar 2026"},
    "MGCM6": {"base_price": 2690.00,  "point_value": 10.0,   "tick_size": 0.10, "name": "Micro Gold Jun 2026"},
    # Silver
    "SIH6":  {"base_price": 31.50,    "point_value": 5000.0, "tick_size": 0.005, "name": "Silver Mar 2026"},
    # --- Treasury Futures ---
    # 10-Year T-Note
    "ZNH6":  {"base_price": 110.50,   "point_value": 1000.0, "tick_size": 0.015625, "name": "10-Year T-Note Mar 2026"},
    # 30-Year T-Bond
    "ZBH6":  {"base_price": 119.00,   "point_value": 1000.0, "tick_size": 0.03125,  "name": "30-Year T-Bond Mar 2026"},
    # 5-Year T-Note
    "ZFH6":  {"base_price": 108.00,   "point_value": 1000.0, "tick_size": 0.0078125, "name": "5-Year T-Note Mar 2026"},
    # 2-Year T-Note
    "ZTH6":  {"base_price": 103.50,   "point_value": 2000.0, "tick_size": 0.0078125, "name": "2-Year T-Note Mar 2026"},
    # --- Currency Futures ---
    # Euro FX
    "6EH6":  {"base_price": 1.0850,   "point_value": 125000.0, "tick_size": 0.00005, "name": "Euro FX Mar 2026"},
    # Micro EUR/USD
    "M6EH6": {"base_price": 1.0850,   "point_value": 12500.0,  "tick_size": 0.0001,  "name": "Micro EUR/USD Mar 2026"},
    # --- Agricultural Futures ---
    # Corn
    "ZCH6":  {"base_price": 4.85,     "point_value": 50.0,   "tick_size": 0.0025, "name": "Corn Mar 2026"},
    # Soybeans
    "ZSH6":  {"base_price": 13.20,    "point_value": 50.0,   "tick_size": 0.0025, "name": "Soybeans Mar 2026"},
    # Wheat
    "ZWH6":  {"base_price": 6.10,     "point_value": 50.0,   "tick_size": 0.0025, "name": "Wheat Mar 2026"},
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
        self.current_symbol = "MESH6"
        self.simulated_prices = {}  # Track simulated prices per symbol
        self.price_history = {}  # Price history per symbol for indicator calc
        self.signal_wait_reasons = []
        self.bars_analyzed = 0
        self.last_signal_check = None
        self.setup_ui()

        # Initialize prices for all symbols
        for symbol, config in SYMBOL_CONFIG.items():
            self.simulated_prices[symbol] = config["base_price"]
            self.price_history[symbol] = [config["base_price"]]

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Top metrics row
        metrics_layout = QHBoxLayout()

        self.balance_card = MetricCard("ACCOUNT BALANCE", "$50,000.00", "Starting balance", "#00ff41")
        metrics_layout.addWidget(self.balance_card)

        self.pnl_card = MetricCard("TODAY'S P&L", "$0.00", "0 trades", "#00ff41")
        metrics_layout.addWidget(self.pnl_card)

        self.drawdown_card = MetricCard("EOD DRAWDOWN", "0.0%", "Floor: $48,000", "#ffcc00")
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
        self.symbol_info_label = QLabel(SYMBOL_CONFIG["MESH6"]["name"])
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

        # MFFU Account Progress
        mffu_separator = QLabel("--- MFFU PROGRESS ---")
        mffu_separator.setStyleSheet("color: #ffcc00; font-size: 10px;")
        mffu_separator.setAlignment(Qt.AlignCenter)
        position_layout.addWidget(mffu_separator)

        mffu_grid = QGridLayout()
        mffu_grid.addWidget(QLabel("Profit Target:"), 0, 0)
        self.target_label = QLabel("$3,000")
        self.target_label.setStyleSheet("color: #00ff41;")
        mffu_grid.addWidget(self.target_label, 0, 1)

        mffu_grid.addWidget(QLabel("Progress:"), 1, 0)
        self.progress_label = QLabel("0.0%")
        self.progress_label.setStyleSheet("color: #ffcc00;")
        mffu_grid.addWidget(self.progress_label, 1, 1)

        mffu_grid.addWidget(QLabel("Scale Level:"), 2, 0)
        self.scale_label = QLabel("2 contracts")
        self.scale_label.setStyleSheet("color: #00ccff;")
        mffu_grid.addWidget(self.scale_label, 2, 1)

        position_layout.addLayout(mffu_grid)
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

    def _compute_ema(self, prices, period):
        """Compute EMA from price list"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _compute_rsi(self, prices, period=14):
        """Compute RSI from price list"""
        if len(prices) < period + 1:
            return 50.0  # Neutral when not enough data
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        recent = changes[-period:]
        gains = [c for c in recent if c > 0]
        losses = [-c for c in recent if c < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_adx_approx(self, prices, period=14):
        """Approximate ADX from price movement volatility"""
        if len(prices) < period + 1:
            return 20.0
        changes = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        recent = changes[-period:]
        avg_move = sum(recent) / len(recent) if recent else 0
        price_range = max(prices[-period:]) - min(prices[-period:])
        if avg_move == 0:
            return 15.0
        # Directional movement ratio: how much of movement is directional
        net_move = abs(prices[-1] - prices[-period])
        directionality = net_move / (sum(recent) + 0.001)
        # Scale to ADX-like range (10-60)
        adx = 10 + directionality * 50
        return min(60, max(10, adx))

    def _detect_trend(self, prices):
        """Detect trend from EMA alignment"""
        if len(prices) < 21:
            return "NEUTRAL"
        ema_fast = self._compute_ema(prices, 9)
        ema_slow = self._compute_ema(prices, 21)
        if ema_fast > ema_slow * 1.001:
            return "BULLISH"
        elif ema_fast < ema_slow * 0.999:
            return "BEARISH"
        return "NEUTRAL"

    def _simulate_price_step(self, symbol):
        """Generate next simulated price using random walk with mean reversion"""
        config = SYMBOL_CONFIG.get(symbol, {})
        base_price = config.get("base_price", 5000)
        tick_size = config.get("tick_size", 0.25)
        old_price = self.simulated_prices.get(symbol, base_price)
        history = self.price_history.get(symbol, [base_price])

        # Mean-reverting random walk scaled to tick size
        # Use deterministic-looking variation based on price history length
        n = len(history)
        # Simple pseudo-random using price digits and bar count
        seed_val = (old_price * 1000 + n * 7) % 1000 / 1000.0
        direction = math.sin(n * 0.3) + math.cos(n * 0.17) * 0.5
        volatility = tick_size * 4
        change = direction * volatility

        # Mean reversion toward base price
        reversion = (base_price - old_price) * 0.02
        new_price = old_price + change + reversion

        # Snap to tick size
        new_price = round(new_price / tick_size) * tick_size

        self.simulated_prices[symbol] = new_price
        history.append(new_price)
        # Keep last 200 prices for indicator calculation
        if len(history) > 200:
            history.pop(0)
        self.price_history[symbol] = history
        return new_price

    def update_data(self):
        """Update dashboard with latest data - all indicators computed from price history"""
        symbol = self.current_symbol
        config = SYMBOL_CONFIG.get(symbol, {})
        base_price = config.get("base_price", 5000)

        # Simulate price movement
        new_price = self._simulate_price_step(symbol)
        prices = self.price_history.get(symbol, [new_price])

        # Update price display
        self.price_label.setText(f"${new_price:,.2f}")

        price_change = new_price - base_price
        change_pct = (price_change / base_price) * 100
        change_color = "#00ff41" if price_change >= 0 else "#ff4444"
        self.price_change_label.setText(f"{price_change:+.2f} ({change_pct:+.2f}%) | Point: ${config.get('point_value', 5):.2f}")
        self.price_change_label.setStyleSheet(f"color: {change_color}; font-size: 12px;")

        # Compute indicators from price history
        trend = self._detect_trend(prices)
        trend_colors = {"BULLISH": "#00ff41", "BEARISH": "#ff4444", "NEUTRAL": "#ffcc00"}
        self.trend_label.setText(trend)
        self.trend_label.setStyleSheet(f"color: {trend_colors[trend]};")

        adx = self._compute_adx_approx(prices)
        self.adx_label.setText(f"{adx:.1f}")
        adx_color = "#00ff41" if adx > 25 else "#ffcc00" if adx > 20 else "#ff4444"
        self.adx_label.setStyleSheet(f"color: {adx_color};")

        rsi = self._compute_rsi(prices)
        self.rsi_label.setText(f"{rsi:.1f}")
        rsi_color = "#ff4444" if rsi > 70 else "#ff4444" if rsi < 30 else "#00ff41"
        self.rsi_label.setStyleSheet(f"color: {rsi_color};")

        # Sentiment comes from news feed if available, otherwise show as N/A
        self.sentiment_label.setText("N/A")
        self.sentiment_label.setStyleSheet("color: #666;")

        # If actively trading, analyze signals
        if self.trading_active and not self.emergency_stopped:
            self.bars_analyzed += 1
            self.analyze_trading_conditions(trend, adx, rsi, new_price)

    def analyze_trading_conditions(self, trend, adx, rsi, price):
        """
        Analyze market conditions, identify patterns, assess signals,
        and log the assessment to both the status panel and log files.
        """
        config = SYMBOL_CONFIG.get(self.current_symbol, {})
        assessment = {
            'timestamp': datetime.now().isoformat(),
            'symbol': self.current_symbol,
            'price': price,
            'bar': self.bars_analyzed,
            'indicators': {'trend': trend, 'adx': round(adx, 1), 'rsi': round(rsi, 1)},
            'patterns': [],
            'signal_checks': [],
            'decision': 'NO_TRADE',
            'reasons': []
        }

        # --- Pattern Detection ---
        # EMA alignment check
        if trend == "BULLISH":
            assessment['patterns'].append("EMA_BULLISH_ALIGNMENT: Fast EMA > Slow EMA > 200 EMA")
        elif trend == "BEARISH":
            assessment['patterns'].append("EMA_BEARISH_ALIGNMENT: Fast EMA < Slow EMA < 200 EMA")
        else:
            assessment['patterns'].append("EMA_MIXED: No clear EMA alignment detected")

        # ADX trend strength pattern
        if adx > 40:
            assessment['patterns'].append(f"STRONG_TREND: ADX={adx:.1f} indicates very strong trend")
        elif adx > 25:
            assessment['patterns'].append(f"MODERATE_TREND: ADX={adx:.1f} confirms trending market")
        elif adx > 20:
            assessment['patterns'].append(f"WEAK_TREND: ADX={adx:.1f} trend developing")
        else:
            assessment['patterns'].append(f"RANGING: ADX={adx:.1f} market is choppy/sideways")

        # RSI pattern detection
        if rsi > 70:
            assessment['patterns'].append(f"RSI_OVERBOUGHT: RSI={rsi:.1f} potential reversal zone")
        elif rsi > 60:
            assessment['patterns'].append(f"RSI_BULLISH_MOMENTUM: RSI={rsi:.1f} strong upward momentum")
        elif rsi < 30:
            assessment['patterns'].append(f"RSI_OVERSOLD: RSI={rsi:.1f} potential reversal zone")
        elif rsi < 40:
            assessment['patterns'].append(f"RSI_BEARISH_MOMENTUM: RSI={rsi:.1f} strong downward momentum")
        else:
            assessment['patterns'].append(f"RSI_NEUTRAL: RSI={rsi:.1f} no extreme readings")

        # Momentum divergence simulation
        if trend == "BULLISH" and rsi < 45:
            assessment['patterns'].append("BEARISH_DIVERGENCE: Price trending up but RSI weakening")
        elif trend == "BEARISH" and rsi > 55:
            assessment['patterns'].append("BULLISH_DIVERGENCE: Price trending down but RSI strengthening")

        # --- Signal Quality Checks ---
        signal_score = 0
        max_score = 5

        # Check 1: Trend direction
        if trend in ["BULLISH", "BEARISH"]:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] Trend Direction: {trend}")
        else:
            assessment['signal_checks'].append("[FAIL] Trend Direction: No clear trend")
            assessment['reasons'].append("No clear trend direction identified")

        # Check 2: Trend strength (ADX)
        if adx >= 25:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] Trend Strength: ADX={adx:.1f} >= 25")
        else:
            assessment['signal_checks'].append(f"[FAIL] Trend Strength: ADX={adx:.1f} < 25 threshold")
            assessment['reasons'].append(f"ADX too low ({adx:.1f}) - need >= 25 for confirmed trend")

        # Check 3: RSI not extreme
        if 30 <= rsi <= 70:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] RSI Range: {rsi:.1f} within tradeable zone")
        else:
            assessment['signal_checks'].append(f"[FAIL] RSI Extreme: {rsi:.1f} outside 30-70 range")
            assessment['reasons'].append(f"RSI at extreme ({rsi:.1f}) - waiting for normalization")

        # Check 4: Pullback to EMA zone (computed from price history)
        prices = self.price_history.get(self.current_symbol, [])
        pullback_detected = False
        if len(prices) >= 21 and trend != "NEUTRAL":
            ema_fast = self._compute_ema(prices, 9)
            ema_slow = self._compute_ema(prices, 21)
            # Pullback: price is near the fast EMA (within 0.3% of EMA)
            ema_dist = abs(price - ema_fast) / ema_fast if ema_fast > 0 else 1
            pullback_detected = ema_dist < 0.003
        if pullback_detected:
            signal_score += 1
            assessment['signal_checks'].append("[PASS] Pullback: Price near EMA entry zone")
        else:
            assessment['signal_checks'].append("[FAIL] Pullback: Price not at optimal entry level")
            assessment['reasons'].append("Waiting for pullback to EMA zone for entry")

        # Check 5: Risk/Reward ratio (based on ATR-like volatility)
        rr_ok = False
        if len(prices) >= 15:
            recent_changes = [abs(prices[i] - prices[i - 1]) for i in range(max(1, len(prices) - 14), len(prices))]
            avg_range = sum(recent_changes) / len(recent_changes) if recent_changes else 0
            # R/R is favorable if trend strength (ADX) supports a 1.5:1 move
            # With stop at 1.5x ATR and target at 2.5x ATR = 1.67:1 R/R
            rr_ok = adx >= 22 and avg_range > 0
        if rr_ok:
            signal_score += 1
            assessment['signal_checks'].append("[PASS] Risk/Reward: >= 1.5:1 ratio achievable")
        else:
            assessment['signal_checks'].append("[FAIL] Risk/Reward: < 1.5:1 - poor reward setup")
            assessment['reasons'].append("Risk/reward ratio below 1.5:1 minimum")

        # --- Decision ---
        if signal_score >= 4:
            signal_type = "LONG" if trend == "BULLISH" else "SHORT"
            assessment['decision'] = f"SIGNAL_{signal_type}"

            self.add_status_message(f"=== SIGNAL: {signal_type} at ${price:,.2f} ===")
            self.add_status_message(f"  Quality: {signal_score}/{max_score} checks passed")
            for p in assessment['patterns'][:2]:
                self.add_status_message(f"  Pattern: {p}")
            self.add_status_message(f"  (Paper mode - simulated execution)")
        elif self.bars_analyzed % 5 == 0:
            # Log periodic assessment
            self.add_status_message(f"--- Signal Assessment (Bar #{self.bars_analyzed}) ---")
            self.add_status_message(f"  Score: {signal_score}/{max_score} | Need 4+ to trade")
            for check in assessment['signal_checks']:
                self.add_status_message(f"  {check}")
            if assessment['reasons']:
                self.add_status_message(f"  Waiting: {assessment['reasons'][0]}")

        # --- Write to log file ---
        self._log_signal_assessment(assessment)

    def _log_signal_assessment(self, assessment):
        """Write signal assessment to log file for learning"""
        import json, os

        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f"signal_log_{datetime.now().strftime('%Y%m%d')}.jsonl")
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(assessment) + '\n')
        except Exception:
            pass  # Don't crash the GUI on log write failure

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
        """Update P&L display and MFFU progress"""
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

        # Update MFFU progress
        profit_target = 3000  # Starter tier default
        progress = (self.total_pnl / profit_target) * 100 if profit_target > 0 else 0
        progress = max(0, progress)
        prog_color = "#00ff41" if progress >= 100 else "#ffcc00"
        self.progress_label.setText(f"{progress:.1f}%")
        self.progress_label.setStyleSheet(f"color: {prog_color};")

        # Update scaling level based on profit
        if self.total_pnl >= 2000:
            self.scale_label.setText("5 contracts (max)")
        elif self.total_pnl >= 1500:
            self.scale_label.setText("4 contracts")
        elif self.total_pnl >= 1000:
            self.scale_label.setText("3 contracts")
        else:
            self.scale_label.setText("2 contracts")

        # Update drawdown info
        starting_balance = 50000
        current_balance = starting_balance + self.total_pnl
        dd_floor = starting_balance - 2000  # Starter tier MLL
        dd_pct = ((current_balance - dd_floor) / starting_balance) * 100 if starting_balance > 0 else 0
        dd_color = "#00ff41" if dd_pct > 2 else "#ffcc00" if dd_pct > 1 else "#ff4444"
        self.drawdown_card.set_value(f"${current_balance - dd_floor:,.0f}", dd_color)
        self.drawdown_card.set_subtitle(f"Floor: ${dd_floor:,.0f}")
