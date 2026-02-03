#!/usr/bin/env python3
"""
Trading Dashboard Widget
Real-time trading display with profit highlighting
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QSpinBox, QGroupBox, QTextEdit,
    QScrollArea, QSplitter, QSizePolicy
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

# Shared GroupBox style
_GROUP_STYLE = """
    QGroupBox {
        background-color: #16213e;
        border: 1px solid #3a3a5e;
        border-radius: 8px;
        margin-top: 14px;
        padding: 14px 10px 10px 10px;
        font-size: 13px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }
"""


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
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {self.color}; font-size: 22px; font-weight: bold;")
        layout.addWidget(self.value_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.subtitle_label)

    def set_value(self, value, color=None):
        self.value_label.setText(str(value))
        if color:
            self.color = color
            self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")

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
        self.simulated_prices = {}
        self.price_history = {}
        self.signal_wait_reasons = []
        self.bars_analyzed = 0
        self.last_signal_check = None
        self.setup_ui()

        # Initialize prices for all symbols
        for symbol, config in SYMBOL_CONFIG.items():
            self.simulated_prices[symbol] = config["base_price"]
            self.price_history[symbol] = [config["base_price"]]

    def _make_group(self, title, title_color="#00ff41"):
        g = QGroupBox(title)
        g.setStyleSheet(_GROUP_STYLE + f"""
            QGroupBox::title {{ color: {title_color}; }}
        """)
        return g

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        # Use a scroll area so nothing gets clipped on smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── ROW 1: Market Data Banner (full width, prominent ticker) ─────
        market_frame = QFrame()
        market_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        mkt_layout = QHBoxLayout(market_frame)
        mkt_layout.setSpacing(20)

        # Left: symbol selector + name
        sym_col = QVBoxLayout()
        sym_col.setSpacing(4)

        sym_pick = QHBoxLayout()
        sym_lbl = QLabel("SYMBOL")
        sym_lbl.setStyleSheet("color: #888; font-size: 10px;")
        sym_pick.addWidget(sym_lbl)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(list(SYMBOL_CONFIG.keys()))
        self.symbol_combo.setStyleSheet(
            "background-color: #0f0f1a; padding: 5px; min-width: 100px; color: #00ff41; font-weight: bold;")
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_changed)
        sym_pick.addWidget(self.symbol_combo)
        sym_col.addLayout(sym_pick)

        self.ticker_name_label = QLabel(SYMBOL_CONFIG["MESH6"]["name"])
        self.ticker_name_label.setStyleSheet("color: #00ccff; font-size: 12px;")
        self.ticker_name_label.setWordWrap(True)
        sym_col.addWidget(self.ticker_name_label)

        self.ticker_details_label = QLabel("Point: $5.00  |  Tick: 0.25")
        self.ticker_details_label.setStyleSheet("color: #666; font-size: 10px;")
        sym_col.addWidget(self.ticker_details_label)

        mkt_layout.addLayout(sym_col)

        # Center: price display
        price_col = QVBoxLayout()
        price_col.setSpacing(2)
        price_col.setAlignment(Qt.AlignCenter)

        self.price_label = QLabel("$6,050.00")
        self.price_label.setStyleSheet("color: #00ff41; font-size: 36px; font-weight: bold;")
        self.price_label.setAlignment(Qt.AlignCenter)
        price_col.addWidget(self.price_label)

        self.price_change_label = QLabel("+0.00 (0.00%)")
        self.price_change_label.setStyleSheet("color: #888; font-size: 12px;")
        self.price_change_label.setAlignment(Qt.AlignCenter)
        price_col.addWidget(self.price_change_label)

        mkt_layout.addLayout(price_col, 1)

        # Right: indicators
        ind_col = QGridLayout()
        ind_col.setSpacing(6)

        for row, (lbl_text, attr, default) in enumerate([
            ("Trend", "trend_label", "--"),
            ("ADX",   "adx_label",   "--"),
            ("RSI",   "rsi_label",   "--"),
            ("Sentiment", "sentiment_label", "N/A"),
        ]):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            ind_col.addWidget(lbl, row, 0)
            val = QLabel(default)
            val.setStyleSheet("color: #eee; font-size: 12px; font-weight: bold;")
            val.setMinimumWidth(80)
            setattr(self, attr, val)
            ind_col.addWidget(val, row, 1)

        mkt_layout.addLayout(ind_col)
        layout.addWidget(market_frame)

        # ── ROW 2: Metric cards ──────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self.balance_card = MetricCard("ACCOUNT BALANCE", "$50,000.00", "Starting balance", "#00ff41")
        cards_row.addWidget(self.balance_card)

        self.pnl_card = MetricCard("SESSION P&L", "$0.00", "0 trades", "#00ff41")
        cards_row.addWidget(self.pnl_card)

        self.drawdown_card = MetricCard("EOD DRAWDOWN", "$2,000", "Floor: $48,000", "#ffcc00")
        cards_row.addWidget(self.drawdown_card)

        self.win_rate_card = MetricCard("WIN RATE", "--", "No trades yet", "#00ccff")
        cards_row.addWidget(self.win_rate_card)

        layout.addLayout(cards_row)

        # ── ROW 3: Two-column – Controls+Position | MFFU Progress ───────
        mid_row = QHBoxLayout()
        mid_row.setSpacing(10)

        # -- Left column: Trading Controls --
        controls_group = self._make_group("Trading Controls", "#00ff41")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(8)

        # Risk per trade
        risk_row = QHBoxLayout()
        risk_row.addWidget(QLabel("Risk %:"))
        self.risk_spin = QSpinBox()
        self.risk_spin.setRange(1, 5)
        self.risk_spin.setValue(1)
        self.risk_spin.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        risk_row.addWidget(self.risk_spin)
        controls_layout.addLayout(risk_row)

        # Buttons
        self.start_btn = QPushButton("START TRADING")
        self.start_btn.clicked.connect(self.toggle_trading)
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #00ff41; color: #000; font-weight: bold; padding: 10px; }
        """)
        controls_layout.addWidget(self.start_btn)

        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setStyleSheet("""
            QPushButton { background-color: #ff4444; color: #fff; font-weight: bold; padding: 10px; }
        """)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        controls_layout.addWidget(self.emergency_btn)

        self.reset_btn = QPushButton("RESET SYSTEM")
        self.reset_btn.setStyleSheet("""
            QPushButton { background-color: #ffcc00; color: #000; font-weight: bold; padding: 10px; }
        """)
        self.reset_btn.clicked.connect(self.reset_system)
        self.reset_btn.hide()
        controls_layout.addWidget(self.reset_btn)

        mid_row.addWidget(controls_group, 1)

        # -- Center column: Current Position --
        position_group = self._make_group("Current Position", "#00ccff")
        position_layout = QVBoxLayout(position_group)
        position_layout.setSpacing(6)

        self.position_label = QLabel("NO POSITION")
        self.position_label.setStyleSheet("color: #888; font-size: 16px; font-weight: bold;")
        self.position_label.setAlignment(Qt.AlignCenter)
        position_layout.addWidget(self.position_label)

        pos_grid = QGridLayout()
        pos_grid.setSpacing(4)
        for row, (lbl, attr, color) in enumerate([
            ("Entry:",          "entry_label",      "#00ff41"),
            ("Stop Loss:",      "stop_label",       "#ff4444"),
            ("Take Profit:",    "tp_label",         "#00ff41"),
            ("Unrealized P&L:", "unrealized_label", "#888"),
        ]):
            l = QLabel(lbl)
            l.setStyleSheet("color: #888;")
            pos_grid.addWidget(l, row, 0)
            v = QLabel("--" if "Unrealized" not in lbl else "$0.00")
            v.setStyleSheet(f"color: {color}; font-weight: bold;")
            setattr(self, attr, v)
            pos_grid.addWidget(v, row, 1)
        position_layout.addLayout(pos_grid)

        mid_row.addWidget(position_group, 1)

        # -- Right column: MFFU Evaluation Progress --
        mffu_group = self._make_group("MFFU Evaluation", "#ffcc00")
        mffu_layout = QVBoxLayout(mffu_group)
        mffu_layout.setSpacing(6)

        mffu_grid = QGridLayout()
        mffu_grid.setSpacing(6)

        mffu_items = [
            ("Profit Target:", "target_label",   "$3,000",      "#00ff41"),
            ("Progress:",      "progress_label", "0.0%",        "#ffcc00"),
            ("Scale Level:",   "scale_label",    "2 contracts", "#00ccff"),
            ("DD Remaining:",  "dd_remain_label","$2,000",      "#ffcc00"),
            ("DD Floor:",      "dd_floor_label", "$48,000",     "#ff4444"),
        ]
        for row, (lbl, attr, default, color) in enumerate(mffu_items):
            l = QLabel(lbl)
            l.setStyleSheet("color: #888; font-size: 11px;")
            mffu_grid.addWidget(l, row, 0)
            v = QLabel(default)
            v.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
            setattr(self, attr, v)
            mffu_grid.addWidget(v, row, 1)

        mffu_layout.addLayout(mffu_grid)

        # MFFU rules reminder
        rules_lbl = QLabel("No daily loss limit | EOD trailing DD\nNo consistency rule | No time limit")
        rules_lbl.setStyleSheet("color: #555; font-size: 9px;")
        rules_lbl.setAlignment(Qt.AlignCenter)
        mffu_layout.addWidget(rules_lbl)

        mid_row.addWidget(mffu_group, 1)

        layout.addLayout(mid_row)

        # ── ROW 4: Trading Status log ────────────────────────────────────
        status_group = self._make_group("Trading Status", "#00ccff")
        status_lay = QVBoxLayout(status_group)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(110)
        self.status_text.setStyleSheet("""
            QTextEdit {
                background-color: #0f0f1a;
                color: #00ff41;
                border: 1px solid #3a3a5e;
                font-family: 'Hack', monospace;
                font-size: 11px;
                padding: 4px;
            }
        """)
        self.status_text.setText("System ready. Select a symbol and click START TRADING to begin.")
        status_lay.addWidget(self.status_text)
        layout.addWidget(status_group)

        # ── ROW 5: Trade History ─────────────────────────────────────────
        history_group = self._make_group("Trade History", "#00ff41")
        history_lay = QVBoxLayout(history_group)

        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(7)
        self.trade_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Side", "Entry", "Exit", "P&L", "Status"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trade_table.setMaximumHeight(160)
        self.trade_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f0f1a;
                gridline-color: #3a3a5e;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #00ff41;
                padding: 6px;
                border: 1px solid #3a3a5e;
            }
            QTableWidget::item { padding: 4px; }
        """)
        history_lay.addWidget(self.trade_table)
        layout.addWidget(history_group)

        layout.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ---------------------------------------------------------- callbacks
    def on_symbol_changed(self, symbol):
        """Handle symbol selection change"""
        self.current_symbol = symbol
        config = SYMBOL_CONFIG.get(symbol, {})
        self.ticker_name_label.setText(config.get("name", symbol))
        self.ticker_details_label.setText(
            f"Point: ${config.get('point_value', 5):.2f}  |  Tick: {config.get('tick_size', 0.25)}")

        price = self.simulated_prices.get(symbol, config.get("base_price", 0))
        self.price_label.setText(f"${price:,.2f}")
        self.price_change_label.setText(f"+0.00 (0.00%)")
        self.price_change_label.setStyleSheet("color: #888; font-size: 12px;")

        self.add_status_message(f"Symbol changed to {symbol} ({config.get('name', '')})")

    def toggle_trading(self):
        if self.emergency_stopped:
            self.add_status_message("System is in EMERGENCY STOP mode. Click RESET SYSTEM first.")
            return
        self.trading_active = not self.trading_active
        if self.trading_active:
            self.start_btn.setText("STOP TRADING")
            self.start_btn.setStyleSheet(
                "QPushButton { background-color: #ffcc00; color: #000; font-weight: bold; padding: 10px; }")
            self.bars_analyzed = 0
            self.add_status_message(f"Trading STARTED on {self.current_symbol}")
            self.add_status_message("Analyzing market conditions...")
        else:
            self.start_btn.setText("START TRADING")
            self.start_btn.setStyleSheet(
                "QPushButton { background-color: #00ff41; color: #000; font-weight: bold; padding: 10px; }")
            self.add_status_message("Trading STOPPED by user")

    def set_trading_active(self, active):
        if self.emergency_stopped and active:
            return
        self.trading_active = active
        if active:
            self.start_btn.setText("STOP TRADING")
            self.start_btn.setStyleSheet(
                "QPushButton { background-color: #ffcc00; color: #000; font-weight: bold; padding: 10px; }")
        else:
            self.start_btn.setText("START TRADING")
            self.start_btn.setStyleSheet(
                "QPushButton { background-color: #00ff41; color: #000; font-weight: bold; padding: 10px; }")

    def emergency_stop(self):
        self.trading_active = False
        self.emergency_stopped = True
        self.position_label.setText("EMERGENCY STOP")
        self.position_label.setStyleSheet("color: #ff4444; font-size: 16px; font-weight: bold;")
        self.start_btn.setText("START TRADING")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #666; color: #aaa; font-weight: bold; padding: 10px; }")
        self.start_btn.setEnabled(False)
        self.reset_btn.show()
        self.add_status_message("!!! EMERGENCY STOP ACTIVATED !!!")
        self.add_status_message("All positions closed. Trading halted.")

    def reset_system(self):
        self.emergency_stopped = False
        self.position_label.setText("NO POSITION")
        self.position_label.setStyleSheet("color: #888; font-size: 16px; font-weight: bold;")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("START TRADING")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #00ff41; color: #000; font-weight: bold; padding: 10px; }")
        self.reset_btn.hide()
        self.entry_label.setText("--")
        self.stop_label.setText("--")
        self.tp_label.setText("--")
        self.unrealized_label.setText("$0.00")
        self.add_status_message("System RESET complete. Ready to trade.")

    def add_status_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        current_text = self.status_text.toPlainText()
        lines = current_text.split('\n')
        if len(lines) > 20:
            lines = lines[-20:]
        lines.append(f"[{timestamp}] {message}")
        self.status_text.setText('\n'.join(lines))
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # --------------------------------------------------------- indicators
    def _compute_ema(self, prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _compute_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        recent = changes[-period:]
        gains = [c for c in recent if c > 0]
        losses = [-c for c in recent if c < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_adx_approx(self, prices, period=14):
        if len(prices) < period + 1:
            return 20.0
        changes = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        recent = changes[-period:]
        if not recent or sum(recent) == 0:
            return 15.0
        net_move = abs(prices[-1] - prices[-period])
        directionality = net_move / (sum(recent) + 0.001)
        adx = 10 + directionality * 50
        return min(60, max(10, adx))

    def _detect_trend(self, prices):
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
        config = SYMBOL_CONFIG.get(symbol, {})
        base_price = config.get("base_price", 5000)
        tick_size = config.get("tick_size", 0.25)
        old_price = self.simulated_prices.get(symbol, base_price)
        history = self.price_history.get(symbol, [base_price])

        n = len(history)
        direction = math.sin(n * 0.3) + math.cos(n * 0.17) * 0.5
        volatility = tick_size * 4
        change = direction * volatility
        reversion = (base_price - old_price) * 0.02
        new_price = old_price + change + reversion
        new_price = round(new_price / tick_size) * tick_size

        self.simulated_prices[symbol] = new_price
        history.append(new_price)
        if len(history) > 200:
            history.pop(0)
        self.price_history[symbol] = history
        return new_price

    # ------------------------------------------------------- update cycle
    def update_data(self):
        symbol = self.current_symbol
        config = SYMBOL_CONFIG.get(symbol, {})
        base_price = config.get("base_price", 5000)

        new_price = self._simulate_price_step(symbol)
        prices = self.price_history.get(symbol, [new_price])

        # Price display
        self.price_label.setText(f"${new_price:,.2f}")
        price_change = new_price - base_price
        change_pct = (price_change / base_price) * 100
        change_color = "#00ff41" if price_change >= 0 else "#ff4444"
        self.price_change_label.setText(f"{price_change:+.2f} ({change_pct:+.2f}%)")
        self.price_change_label.setStyleSheet(f"color: {change_color}; font-size: 12px;")

        # Indicators
        trend = self._detect_trend(prices)
        trend_colors = {"BULLISH": "#00ff41", "BEARISH": "#ff4444", "NEUTRAL": "#ffcc00"}
        self.trend_label.setText(trend)
        self.trend_label.setStyleSheet(f"color: {trend_colors[trend]}; font-size: 12px; font-weight: bold;")

        adx = self._compute_adx_approx(prices)
        self.adx_label.setText(f"{adx:.1f}")
        adx_color = "#00ff41" if adx > 25 else "#ffcc00" if adx > 20 else "#ff4444"
        self.adx_label.setStyleSheet(f"color: {adx_color}; font-size: 12px; font-weight: bold;")

        rsi = self._compute_rsi(prices)
        self.rsi_label.setText(f"{rsi:.1f}")
        rsi_color = "#ff4444" if rsi > 70 or rsi < 30 else "#00ff41"
        self.rsi_label.setStyleSheet(f"color: {rsi_color}; font-size: 12px; font-weight: bold;")

        if self.trading_active and not self.emergency_stopped:
            self.bars_analyzed += 1
            self.analyze_trading_conditions(trend, adx, rsi, new_price)

    # ------------------------------------------------- signal assessment
    def analyze_trading_conditions(self, trend, adx, rsi, price):
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

        # Pattern detection
        if trend == "BULLISH":
            assessment['patterns'].append("EMA_BULLISH_ALIGNMENT")
        elif trend == "BEARISH":
            assessment['patterns'].append("EMA_BEARISH_ALIGNMENT")
        else:
            assessment['patterns'].append("EMA_MIXED")

        if adx > 40:
            assessment['patterns'].append(f"STRONG_TREND: ADX={adx:.1f}")
        elif adx > 25:
            assessment['patterns'].append(f"MODERATE_TREND: ADX={adx:.1f}")
        elif adx > 20:
            assessment['patterns'].append(f"WEAK_TREND: ADX={adx:.1f}")
        else:
            assessment['patterns'].append(f"RANGING: ADX={adx:.1f}")

        if rsi > 70:
            assessment['patterns'].append(f"RSI_OVERBOUGHT: {rsi:.1f}")
        elif rsi < 30:
            assessment['patterns'].append(f"RSI_OVERSOLD: {rsi:.1f}")

        if trend == "BULLISH" and rsi < 45:
            assessment['patterns'].append("BEARISH_DIVERGENCE")
        elif trend == "BEARISH" and rsi > 55:
            assessment['patterns'].append("BULLISH_DIVERGENCE")

        # Signal quality checks
        signal_score = 0
        max_score = 5

        if trend in ["BULLISH", "BEARISH"]:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] Trend: {trend}")
        else:
            assessment['signal_checks'].append("[FAIL] Trend: No clear trend")
            assessment['reasons'].append("No clear trend direction")

        if adx >= 25:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] ADX: {adx:.1f} >= 25")
        else:
            assessment['signal_checks'].append(f"[FAIL] ADX: {adx:.1f} < 25")
            assessment['reasons'].append(f"ADX too low ({adx:.1f})")

        if 30 <= rsi <= 70:
            signal_score += 1
            assessment['signal_checks'].append(f"[PASS] RSI: {rsi:.1f} in range")
        else:
            assessment['signal_checks'].append(f"[FAIL] RSI: {rsi:.1f} extreme")
            assessment['reasons'].append(f"RSI extreme ({rsi:.1f})")

        # Pullback check
        prices = self.price_history.get(self.current_symbol, [])
        pullback_detected = False
        if len(prices) >= 21 and trend != "NEUTRAL":
            ema_fast = self._compute_ema(prices, 9)
            ema_dist = abs(price - ema_fast) / ema_fast if ema_fast > 0 else 1
            pullback_detected = ema_dist < 0.003
        if pullback_detected:
            signal_score += 1
            assessment['signal_checks'].append("[PASS] Pullback to EMA zone")
        else:
            assessment['signal_checks'].append("[FAIL] No pullback to EMA")
            assessment['reasons'].append("Waiting for pullback")

        # R/R check
        rr_ok = False
        if len(prices) >= 15:
            recent_changes = [abs(prices[i] - prices[i - 1])
                              for i in range(max(1, len(prices) - 14), len(prices))]
            rr_ok = adx >= 22 and sum(recent_changes) > 0
        if rr_ok:
            signal_score += 1
            assessment['signal_checks'].append("[PASS] R/R >= 1.5:1")
        else:
            assessment['signal_checks'].append("[FAIL] R/R < 1.5:1")
            assessment['reasons'].append("Poor risk/reward")

        # Decision
        if signal_score >= 4:
            signal_type = "LONG" if trend == "BULLISH" else "SHORT"
            assessment['decision'] = f"SIGNAL_{signal_type}"
            self.add_status_message(f"=== SIGNAL: {signal_type} at ${price:,.2f} ({signal_score}/{max_score}) ===")
            self.add_status_message(f"  (Paper mode - simulated execution)")
        elif self.bars_analyzed % 5 == 0:
            self.add_status_message(f"--- Bar #{self.bars_analyzed}: {signal_score}/{max_score} checks ---")
            for check in assessment['signal_checks']:
                self.add_status_message(f"  {check}")

        self._log_signal_assessment(assessment)

    def _log_signal_assessment(self, assessment):
        import json, os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"signal_log_{datetime.now().strftime('%Y%m%d')}.jsonl")
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(assessment) + '\n')
        except Exception:
            pass

    # ------------------------------------------------------------ trades
    def add_trade(self, trade):
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
        self.total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        color = "#00ff41" if self.total_pnl >= 0 else "#ff4444"
        self.pnl_card.set_value(f"${self.total_pnl:,.2f}", color)
        self.pnl_card.set_subtitle(f"{len(self.trades)} trades")

        if self.trades:
            wins = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
            win_rate = (wins / len(self.trades)) * 100
            self.win_rate_card.set_value(f"{win_rate:.1f}%")
            self.win_rate_card.set_subtitle(f"{wins}W / {len(self.trades) - wins}L")

        # MFFU progress
        profit_target = 3000
        progress = max(0, (self.total_pnl / profit_target) * 100) if profit_target > 0 else 0
        prog_color = "#00ff41" if progress >= 100 else "#ffcc00"
        self.progress_label.setText(f"{progress:.1f}%")
        self.progress_label.setStyleSheet(f"color: {prog_color}; font-size: 12px; font-weight: bold;")

        if self.total_pnl >= 2000:
            self.scale_label.setText("5 contracts (max)")
        elif self.total_pnl >= 1500:
            self.scale_label.setText("4 contracts")
        elif self.total_pnl >= 1000:
            self.scale_label.setText("3 contracts")
        else:
            self.scale_label.setText("2 contracts")

        starting_balance = 50000
        current_balance = starting_balance + self.total_pnl
        dd_floor = starting_balance - 2000
        dd_remaining = current_balance - dd_floor
        dd_color = "#00ff41" if dd_remaining > 1000 else "#ffcc00" if dd_remaining > 500 else "#ff4444"
        self.drawdown_card.set_value(f"${dd_remaining:,.0f}", dd_color)
        self.drawdown_card.set_subtitle(f"Floor: ${dd_floor:,.0f}")
        self.dd_remain_label.setText(f"${dd_remaining:,.0f}")
        self.dd_remain_label.setStyleSheet(f"color: {dd_color}; font-size: 12px; font-weight: bold;")
        self.dd_floor_label.setText(f"${dd_floor:,.0f}")
