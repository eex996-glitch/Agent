#!/usr/bin/env python3
"""
Trading Dashboard Widget
Real-time trading display with profit highlighting
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from datetime import datetime
import random


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
        self.trades = []
        self.total_pnl = 0.0
        self.setup_ui()

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
        self.symbol_combo.addItems(["MESZ4", "MESH5", "ESZ4", "ESH5", "NQZ4", "NQH5"])
        self.symbol_combo.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        symbol_layout.addWidget(self.symbol_combo)
        controls_layout.addLayout(symbol_layout)

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
        self.start_btn = QPushButton("▶ START")
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

        self.emergency_btn = QPushButton("⚠ EMERGENCY STOP")
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

    def toggle_trading(self):
        """Toggle trading on/off"""
        self.trading_active = not self.trading_active
        if self.trading_active:
            self.start_btn.setText("⏹ STOP")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc00;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)
        else:
            self.start_btn.setText("▶ START")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00ff41;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)

    def set_trading_active(self, active):
        """Set trading state"""
        self.trading_active = active
        if active:
            self.start_btn.setText("⏹ STOP")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc00;
                    color: #000;
                    font-weight: bold;
                    padding: 12px;
                }
            """)
        else:
            self.start_btn.setText("▶ START")
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
        self.position_label.setText("EMERGENCY STOP")
        self.position_label.setStyleSheet("color: #ff4444; font-size: 18px; font-weight: bold;")
        self.start_btn.setText("▶ START")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #000;
                font-weight: bold;
                padding: 12px;
            }
        """)

    def update_data(self):
        """Update dashboard with latest data"""
        # This would normally pull from the trading engine
        # For demo, show some sample updates
        if self.trading_active:
            # Simulate price updates
            base_price = 5250.00
            price = base_price + random.uniform(-5, 5)
            self.price_label.setText(f"${price:,.2f}")

            # Update indicators
            trend = random.choice(["BULLISH", "BEARISH", "NEUTRAL"])
            trend_colors = {"BULLISH": "#00ff41", "BEARISH": "#ff4444", "NEUTRAL": "#ffcc00"}
            self.trend_label.setText(trend)
            self.trend_label.setStyleSheet(f"color: {trend_colors[trend]};")

            adx = random.uniform(15, 45)
            self.adx_label.setText(f"{adx:.1f}")
            self.adx_label.setStyleSheet(f"color: {'#00ff41' if adx > 25 else '#ffcc00'};")

            rsi = random.uniform(30, 70)
            self.rsi_label.setText(f"{rsi:.1f}")

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
