#!/usr/bin/env python3
"""
Main GUI Window for Futures Trading Agent
Kali Linux compatible PyQt5 interface
"""

import sys
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QAction, QLabel,
    QMessageBox, QSplitter, QFrame, QDialog, QGroupBox, QSpinBox,
    QDoubleSpinBox, QComboBox, QPushButton, QProgressBar, QTextEdit,
    QGridLayout, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

from .dashboard import DashboardWidget
from .news_feed import NewsFeedWidget
from .model_health import ModelHealthWidget
from .logs_widget import LogsWidget


class BacktestWorker(QThread):
    """Background worker for running backtests using strategy tournament"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            import pandas as pd
            import numpy as np
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategy.tournament import run_tournament, generate_realistic_data

            self.progress.emit("Initializing strategy tournament...")

            n_bars = self.config.get('num_bars', 2000)

            # Run tournament (tests all strategies, picks the best)
            tournament_result = run_tournament(
                starting_balance=self.config.get('starting_balance', 50000),
                max_loss_limit=self.config.get('max_loss_limit', 2000),
                point_value=self.config.get('point_value', 5.0),
                symbol=self.config.get('symbol', 'MES'),
                n_bars=n_bars,
                progress_callback=self.progress.emit,
            )

            self.progress.emit("Selecting best strategy and compiling results...")

            # Get the best strategy's detailed results
            best_score = tournament_result.scores[0] if tournament_result.scores else None

            if best_score is None:
                self.error.emit("No strategies produced results")
                return

            # Now re-run only the best strategy for detailed trade data
            from strategy.trend_following import TrendFollowingStrategy
            from strategy.mean_reversion import MeanReversionStrategy
            from strategy.breakout import BreakoutStrategy
            from strategy.adaptive import AdaptiveStrategy

            strategy_map = {
                'TrendFollowing': lambda: TrendFollowingStrategy(
                    name="TrendFollowing",
                    params={'adx_threshold': 22.0, 'stop_loss_atr_mult': 1.8}),
                'MeanReversion': lambda: MeanReversionStrategy(
                    name="MeanReversion",
                    params={'require_reversal_candle': False,
                            'stop_loss_atr_mult': 1.5}),
                'Breakout': lambda: BreakoutStrategy(
                    name="Breakout",
                    params={'donchian_period': 18, 'volume_threshold': 1.2}),
                'Adaptive': lambda: AdaptiveStrategy(
                    name="Adaptive",
                    params={'entry_threshold': 60}),
                'TrendFollowing_Aggressive': lambda: TrendFollowingStrategy(
                    name="TrendFollowing_Aggressive",
                    params={'adx_threshold': 18.0, 'stop_loss_atr_mult': 1.5,
                            'take_profit_atr_mult': 4.0}),
                'MeanReversion_Relaxed': lambda: MeanReversionStrategy(
                    name="MeanReversion_Relaxed",
                    params={'require_reversal_candle': False,
                            'bb_entry_threshold': 0.15,
                            'rsi_oversold': 35, 'rsi_overbought': 65}),
            }

            best_name = best_score.name
            strategy_factory = strategy_map.get(best_name)
            if strategy_factory is None:
                # Default fallback
                strategy_factory = lambda: AdaptiveStrategy(name="Adaptive")

            self.progress.emit(f"Re-running best strategy ({best_name}) for detailed results...")

            strategy = strategy_factory()
            data = generate_realistic_data(n_bars)
            prepared = strategy.prepare_data(data.copy())

            bt_config = BacktestConfig(
                starting_balance=self.config.get('starting_balance', 50000),
                symbol=self.config.get('symbol', 'MES'),
                point_value=self.config.get('point_value', 5.0),
                max_loss_limit=self.config.get('max_loss_limit', 2000),
                daily_loss_limit=0,  # MFFU has no daily loss limit
                max_risk_per_trade=self.config.get('risk_per_trade', 0.01),
                max_contracts=self.config.get('max_contracts', 5)
            )

            engine = BacktestEngine(bt_config)
            result = engine.run(strategy, prepared, start_idx=250)

            self.progress.emit("Calculating results...")

            # Build result dict with tournament context
            result_dict = {
                'strategy_name': f"{result.strategy_name} (Tournament Winner)",
                'start_date': str(result.start_date),
                'end_date': str(result.end_date),
                'starting_balance': bt_config.starting_balance,
                'ending_balance': bt_config.starting_balance + result.total_return,
                'total_return': result.total_return,
                'total_return_pct': result.total_return_pct,
                'num_trades': result.num_trades,
                'num_winners': result.num_winners,
                'num_losers': result.num_losers,
                'win_rate': result.win_rate * 100,
                'avg_winner': result.avg_winner,
                'avg_loser': result.avg_loser,
                'profit_factor': result.profit_factor,
                'max_drawdown': result.max_drawdown,
                'max_drawdown_pct': result.max_drawdown_pct,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio,
                'avg_trade': result.avg_trade,
                'avg_bars_held': result.avg_bars_held,
                'best_day': result.best_day,
                'worst_day': result.worst_day,
                'consistency_score': result.consistency_score,
                'tournament_rankings': tournament_result.rankings,
                'tournament_scores': [s.to_dict() for s in tournament_result.scores],
                'trades': [
                    {
                        'entry_time': str(t.entry_time),
                        'exit_time': str(t.exit_time),
                        'direction': t.direction,
                        'entry_price': t.entry_price,
                        'exit_price': t.exit_price,
                        'quantity': t.quantity,
                        'net_pnl': t.net_pnl,
                        'exit_reason': t.exit_reason,
                        'bars_held': t.bars_held
                    } for t in result.trades
                ]
            }

            self.progress.emit("Tournament backtest complete!")
            self.finished.emit(result_dict)

        except Exception as e:
            self.error.emit(str(e))


class BacktestDialog(QDialog):
    """Dialog for running backtests"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run Backtest")
        self.setMinimumSize(800, 600)
        self.result = None
        self.worker = None
        self.setup_ui()
        self.apply_dark_theme()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                color: #eee;
            }
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                color: #00ff41;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #eee;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #0f0f1a;
                color: #00ff41;
                border: 1px solid #3a3a5e;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #3a3a5e;
                color: #eee;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00ff41;
                color: #000;
            }
            QPushButton:disabled {
                background-color: #2a2a3e;
                color: #666;
            }
            QProgressBar {
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ff41;
            }
            QTextEdit {
                background-color: #0f0f1a;
                color: #00ff41;
                border: 1px solid #3a3a5e;
                font-family: 'Hack', monospace;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Configuration section
        config_group = QGroupBox("Backtest Configuration")
        config_layout = QGridLayout(config_group)

        # Starting balance
        config_layout.addWidget(QLabel("Starting Balance:"), 0, 0)
        self.balance_spin = QDoubleSpinBox()
        self.balance_spin.setRange(1000, 1000000)
        self.balance_spin.setValue(50000)
        self.balance_spin.setPrefix("$")
        config_layout.addWidget(self.balance_spin, 0, 1)

        # Symbol
        config_layout.addWidget(QLabel("Symbol:"), 0, 2)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["MES", "ES", "NQ", "MNQ"])
        config_layout.addWidget(self.symbol_combo, 0, 3)

        # MFFU Account Tier
        config_layout.addWidget(QLabel("MFFU Tier:"), 1, 0)
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["Starter ($50K)", "Standard ($100K)", "Premium ($150K)"])
        self.tier_combo.currentIndexChanged.connect(self._on_tier_changed)
        config_layout.addWidget(self.tier_combo, 1, 1)

        # Max loss limit (set by tier, read-only display)
        config_layout.addWidget(QLabel("Max Loss (EOD):"), 1, 2)
        self.max_loss_label = QLabel("$2,000")
        self.max_loss_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        config_layout.addWidget(self.max_loss_label, 1, 3)

        # Risk per trade
        config_layout.addWidget(QLabel("Risk Per Trade:"), 2, 0)
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.5, 5.0)
        self.risk_spin.setValue(1.0)
        self.risk_spin.setSuffix("%")
        config_layout.addWidget(self.risk_spin, 2, 1)

        # Number of bars
        config_layout.addWidget(QLabel("Bars to Simulate:"), 2, 2)
        self.bars_spin = QSpinBox()
        self.bars_spin.setRange(500, 10000)
        self.bars_spin.setValue(2000)
        config_layout.addWidget(self.bars_spin, 2, 3)

        layout.addWidget(config_group)

        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to run backtest")
        self.status_label.setStyleSheet("color: #888;")
        progress_layout.addWidget(self.status_label)

        layout.addWidget(progress_group)

        # Results section
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("Backtest results will appear here...")
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.run_btn = QPushButton("Run Backtest")
        self.run_btn.clicked.connect(self.run_backtest)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #000;
                font-weight: bold;
            }
        """)
        button_layout.addWidget(self.run_btn)

        self.save_btn = QPushButton("Save to Logs")
        self.save_btn.clicked.connect(self.save_results)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _on_tier_changed(self, index):
        """Update settings when MFFU tier changes"""
        tier_settings = [
            (50000, 2000, 5, "$2,000"),
            (100000, 3500, 10, "$3,500"),
            (150000, 5000, 15, "$5,000"),
        ]
        if 0 <= index < len(tier_settings):
            balance, max_loss, max_contracts, loss_text = tier_settings[index]
            self.balance_spin.setValue(balance)
            self.max_loss_label.setText(loss_text)

    def _get_tier_max_loss(self):
        """Get max loss limit for selected tier"""
        tier_losses = [2000, 3500, 5000]
        index = self.tier_combo.currentIndex()
        return tier_losses[index] if 0 <= index < len(tier_losses) else 2000

    def _get_tier_max_contracts(self):
        """Get max contracts for selected tier"""
        tier_contracts = [5, 10, 15]
        index = self.tier_combo.currentIndex()
        return tier_contracts[index] if 0 <= index < len(tier_contracts) else 5

    def run_backtest(self):
        """Start the backtest"""
        self.run_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.show()
        self.results_text.clear()

        config = {
            'starting_balance': self.balance_spin.value(),
            'symbol': self.symbol_combo.currentText(),
            'max_loss_limit': self._get_tier_max_loss(),
            'risk_per_trade': self.risk_spin.value() / 100,
            'num_bars': self.bars_spin.value(),
            'max_contracts': self._get_tier_max_contracts(),
            'point_value': 5.0 if 'M' in self.symbol_combo.currentText() else 50.0
        }

        self.worker = BacktestWorker(config)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, message):
        """Handle progress updates"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #ffcc00;")

    def on_finished(self, result):
        """Handle backtest completion"""
        self.result = result
        self.progress_bar.hide()
        self.run_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText("Backtest complete!")
        self.status_label.setStyleSheet("color: #00ff41;")

        # Format results
        r = result
        pnl_color = "#00ff41" if r['total_return'] >= 0 else "#ff4444"

        report = f"""
================================================================================
                         BACKTEST RESULTS
================================================================================

Strategy: {r['strategy_name']}
Period: {r['start_date'][:10]} to {r['end_date'][:10]}

--------------------------------------------------------------------------------
                           ACCOUNT SUMMARY
--------------------------------------------------------------------------------

Starting Balance:     ${r['starting_balance']:>12,.2f}
Ending Balance:       ${r['ending_balance']:>12,.2f}
Net P&L:              ${r['total_return']:>12,.2f} ({r['total_return_pct']:+.2f}%)

--------------------------------------------------------------------------------
                           TRADE STATISTICS
--------------------------------------------------------------------------------

Total Trades:         {r['num_trades']:>12}
Winning Trades:       {r['num_winners']:>12}
Losing Trades:        {r['num_losers']:>12}
Win Rate:             {r['win_rate']:>12.1f}%

Average Winner:       ${r['avg_winner']:>12,.2f}
Average Loser:        ${r['avg_loser']:>12,.2f}
Average Trade:        ${r['avg_trade']:>12,.2f}
Profit Factor:        {r['profit_factor']:>12.2f}

--------------------------------------------------------------------------------
                            RISK METRICS
--------------------------------------------------------------------------------

Max Drawdown:         ${r['max_drawdown']:>12,.2f} ({r['max_drawdown_pct']:.2f}%)
Sharpe Ratio:         {r['sharpe_ratio']:>12.2f}
Sortino Ratio:        {r['sortino_ratio']:>12.2f}

--------------------------------------------------------------------------------
                         CONSISTENCY (PROP FIRM)
--------------------------------------------------------------------------------

Best Day:             ${r['best_day']:>12,.2f}
Worst Day:            ${r['worst_day']:>12,.2f}
Consistency Score:    {r['consistency_score']:>12.1f}%

================================================================================
                           SAMPLE TRADES
================================================================================
"""
        # Add sample trades
        for i, trade in enumerate(r['trades'][:10]):
            pnl_str = f"${trade['net_pnl']:+,.2f}"
            report += f"\n{i+1}. {trade['direction']:5} | Entry: ${trade['entry_price']:.2f} | "
            report += f"Exit: ${trade['exit_price']:.2f} | P/L: {pnl_str:>10} | {trade['exit_reason']}"

        if len(r['trades']) > 10:
            report += f"\n\n... and {len(r['trades']) - 10} more trades"

        # Add tournament rankings if available
        if 'tournament_rankings' in r:
            report += f"""

================================================================================
                        STRATEGY TOURNAMENT RANKINGS
================================================================================
"""
            for i, name in enumerate(r['tournament_rankings']):
                medal = ">>>" if i == 0 else "   "
                score_data = r.get('tournament_scores', [{}] * len(r['tournament_rankings']))
                if i < len(score_data):
                    s = score_data[i]
                    pnl = s.get('total_return', 0)
                    wr = s.get('win_rate', 0)
                    pf = s.get('profit_factor', 0)
                    cs = s.get('composite_score', 0)
                    report += f"\n{medal} #{i+1} {name:<30} P/L: ${pnl:>+10,.2f}  WR: {wr:>5.1f}%  PF: {pf:>5.2f}  Score: {cs:>5.1f}"
                else:
                    report += f"\n{medal} #{i+1} {name}"

        self.results_text.setText(report)

    def on_error(self, error_msg):
        """Handle backtest error"""
        self.progress_bar.hide()
        self.run_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")
        self.status_label.setStyleSheet("color: #ff4444;")
        self.results_text.setText(f"Backtest failed:\n\n{error_msg}")

    def save_results(self):
        """Save results to logs"""
        if not self.result:
            return

        try:
            from logs.storage import LogStorage
            storage = LogStorage()

            # Create session data
            session_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session_data = {
                'session_id': session_id,
                'mode': 'backtest',
                'symbol': self.symbol_combo.currentText(),
                'start_time': self.result['start_date'],
                'end_time': self.result['end_date'],
                'starting_balance': self.result['starting_balance'],
                'ending_balance': self.result['ending_balance'],
                'net_pnl': self.result['total_return'],
                'total_trades': self.result['num_trades'],
                'winning_trades': self.result['num_winners'],
                'losing_trades': self.result['num_losers'],
                'win_rate': self.result['win_rate'],
                'average_win': self.result['avg_winner'],
                'average_loss': self.result['avg_loser'],
                'profit_factor': self.result['profit_factor'],
                'max_drawdown': self.result['max_drawdown'],
                'sharpe_ratio': self.result['sharpe_ratio'],
                'trades': self.result['trades']
            }

            storage.save_session(session_id, session_data)
            QMessageBox.information(self, "Saved", f"Results saved to logs as {session_id}")

        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not save results: {e}")


class MainWindow(QMainWindow):
    """Main application window with dark theme for Kali Linux"""

    def __init__(self, trader=None):
        super().__init__()
        self.trader = trader
        self.current_mode = 'paper'
        self.setWindowTitle("Futures Trading Agent - Kali Linux")
        self.setMinimumSize(1400, 900)

        # Apply dark theme (matches Kali aesthetic)
        self.apply_dark_theme()

        # Setup UI
        self.setup_menu_bar()
        self.setup_central_widget()
        self.setup_status_bar()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all)
        self.update_timer.start(1000)  # Update every second

    def apply_dark_theme(self):
        """Apply Kali-style dark theme"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QWidget {
                background-color: #1a1a2e;
                color: #eee;
                font-family: 'Hack', 'DejaVu Sans Mono', monospace;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a5e;
                background-color: #16213e;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: #aaa;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #16213e;
                color: #00ff41;
                border-bottom: 2px solid #00ff41;
            }
            QTabBar::tab:hover {
                background-color: #252545;
            }
            QMenuBar {
                background-color: #0f0f1a;
                color: #eee;
                border-bottom: 1px solid #3a3a5e;
            }
            QMenuBar::item:selected {
                background-color: #3a3a5e;
            }
            QMenu {
                background-color: #1a1a2e;
                border: 1px solid #3a3a5e;
            }
            QMenu::item:selected {
                background-color: #00ff41;
                color: #000;
            }
            QStatusBar {
                background-color: #0f0f1a;
                color: #00ff41;
                border-top: 1px solid #3a3a5e;
            }
            QLabel {
                color: #eee;
            }
            QPushButton {
                background-color: #3a3a5e;
                color: #eee;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00ff41;
                color: #000;
            }
            QPushButton:pressed {
                background-color: #00cc33;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #0f0f1a;
                color: #00ff41;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 5px;
            }
            QScrollBar:vertical {
                background-color: #1a1a2e;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a5e;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00ff41;
            }
            QProgressBar {
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ff41;
                border-radius: 3px;
            }
        """)

    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        start_action = QAction("&Start Trading", self)
        start_action.setShortcut("Ctrl+S")
        start_action.triggered.connect(self.start_trading)
        file_menu.addAction(start_action)

        stop_action = QAction("S&top Trading", self)
        stop_action.setShortcut("Ctrl+T")
        stop_action.triggered.connect(self.stop_trading)
        file_menu.addAction(stop_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Mode menu
        mode_menu = menubar.addMenu("&Mode")

        backtest_action = QAction("Run &Backtest...", self)
        backtest_action.setShortcut("Ctrl+B")
        backtest_action.triggered.connect(self.show_backtest_dialog)
        mode_menu.addAction(backtest_action)

        mode_menu.addSeparator()

        for mode in ["Paper", "Demo", "Live"]:
            action = QAction(mode, self)
            action.triggered.connect(lambda checked, m=mode: self.set_mode(m.lower()))
            mode_menu.addAction(action)

        # View menu
        view_menu = menubar.addMenu("&View")

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.update_all)
        view_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_central_widget(self):
        """Setup the central widget with tabs"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("FUTURES TRADING AGENT")
        header.setFont(QFont("Hack", 18, QFont.Bold))
        header.setStyleSheet("color: #00ff41; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Dashboard tab
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.dashboard, "Dashboard")

        # News feed tab
        self.news_feed = NewsFeedWidget()
        self.tabs.addTab(self.news_feed, "News Feed")

        # Model health tab
        self.model_health = ModelHealthWidget()
        self.tabs.addTab(self.model_health, "Model Health")

        # Connect news sentiment to dashboard
        self.news_feed.sentiment_updated.connect(self._on_sentiment_updated)

        # Logs tab
        self.logs_widget = LogsWidget()
        self.tabs.addTab(self.logs_widget, "Logs")

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.mode_label = QLabel("Mode: Paper")
        self.mode_label.setStyleSheet("color: #ffcc00;")
        self.status_bar.addPermanentWidget(self.mode_label)

        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet("color: #ff4444;")
        self.status_bar.addPermanentWidget(self.connection_label)

    def update_all(self):
        """Update all widgets"""
        self.dashboard.update_data()
        self.news_feed.update_feed()
        self.model_health.update_health()

    def _on_sentiment_updated(self, score):
        """Update dashboard with news sentiment score"""
        if score > 0.3:
            label = "Bullish"
            color = "#00ff41"
        elif score < -0.3:
            label = "Bearish"
            color = "#ff4444"
        else:
            label = "Neutral"
            color = "#ffcc00"
        self.dashboard.sentiment_label.setText(f"{label} ({score:+.2f})")
        self.dashboard.sentiment_label.setStyleSheet(f"color: {color};")

    def start_trading(self):
        """Start trading"""
        self.status_label.setText("Trading started...")
        self.connection_label.setText("Connected")
        self.connection_label.setStyleSheet("color: #00ff41;")
        if self.dashboard:
            self.dashboard.set_trading_active(True)

    def stop_trading(self):
        """Stop trading"""
        self.status_label.setText("Trading stopped")
        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet("color: #ff4444;")
        if self.dashboard:
            self.dashboard.set_trading_active(False)

    def set_mode(self, mode):
        """Set trading mode"""
        self.current_mode = mode
        mode_colors = {
            'backtest': '#888888',
            'paper': '#ffcc00',
            'demo': '#00ccff',
            'live': '#ff4444'
        }
        color = mode_colors.get(mode, '#ffffff')
        self.mode_label.setText(f"Mode: {mode.capitalize()}")
        self.mode_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(f"Switched to {mode} mode")

    def show_backtest_dialog(self):
        """Show the backtest configuration dialog"""
        dialog = BacktestDialog(self)
        dialog.exec_()

        # Refresh logs after backtest (might have saved new results)
        self.logs_widget.load_sessions()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Futures Trading Agent",
            "<h2>Futures Trading Agent</h2>"
            "<p>Kali Linux Edition</p>"
            "<p>Automated futures trading system for prop firm evaluations.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Backtest, Paper, Demo, Live trading</li>"
            "<li>Real-time news sentiment analysis</li>"
            "<li>Model health monitoring</li>"
            "<li>Tradovate/MFFU integration</li>"
            "</ul>"
            "<p>Trading involves risk. Use responsibly.</p>"
        )

    def closeEvent(self, event):
        """Handle window close"""
        reply = QMessageBox.question(
            self, 'Exit',
            'Are you sure you want to exit?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.stop_trading()
            event.accept()
        else:
            event.ignore()


def run_gui(trader=None):
    """Launch the GUI application"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow(trader)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    run_gui()
