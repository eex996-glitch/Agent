#!/usr/bin/env python3
"""
Model Health Visualization Widget
Shows confidence levels, profit tracking, and model performance metrics.
Displays real data from strategy tournament results (not random simulation).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QProgressBar, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from datetime import datetime
import json
import os


class CircularGauge(QWidget):
    """Circular gauge for confidence display"""

    def __init__(self, title="", max_value=100):
        super().__init__()
        self.title = title
        self.max_value = max_value
        self.value = 0
        self.setMinimumSize(150, 150)

    def set_value(self, value):
        self.value = min(max(0, value), self.max_value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height) - 20
        x = (width - size) // 2
        y = (height - size) // 2

        # Background circle
        painter.setPen(QPen(QColor("#3a3a5e"), 8))
        painter.drawArc(x, y, size, size, 0, 360 * 16)

        # Value arc
        percentage = self.value / self.max_value
        if percentage > 0.7:
            color = QColor("#00ff41")
        elif percentage > 0.4:
            color = QColor("#ffcc00")
        else:
            color = QColor("#ff4444")

        painter.setPen(QPen(color, 8))
        span = int(-percentage * 360 * 16)
        painter.drawArc(x, y, size, size, 90 * 16, span)

        # Center text
        painter.setPen(QColor("#eee"))
        font = QFont("Hack", 20, QFont.Bold)
        painter.setFont(font)
        painter.drawText(x, y, size, size, Qt.AlignCenter, f"{self.value:.0f}%")

        # Title
        painter.setPen(QColor("#888"))
        font = QFont("Hack", 10)
        painter.setFont(font)
        painter.drawText(x, y + size - 25, size, 25, Qt.AlignCenter, self.title)


class ProfitChart(QWidget):
    """Equity curve chart showing backtest performance"""

    def __init__(self):
        super().__init__()
        self.data = []
        self.setMinimumHeight(200)
        self.label = ""

    def set_data(self, data, label=""):
        self.data = data[-50:] if len(data) > 50 else data
        self.label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        padding = 50

        # Draw background
        painter.fillRect(0, 0, width, height, QColor("#0f0f1a"))

        # Label
        if self.label:
            painter.setPen(QColor("#00ff41"))
            font = QFont("Hack", 9)
            painter.setFont(font)
            painter.drawText(width - 200, 15, self.label)

        if not self.data:
            painter.setPen(QColor("#666"))
            font = QFont("Hack", 12)
            painter.setFont(font)
            painter.drawText(0, 0, width, height, Qt.AlignCenter,
                             "Run tournament to see equity curve")
            return

        # Draw grid
        painter.setPen(QPen(QColor("#3a3a5e"), 1))
        for i in range(5):
            y = padding + (height - 2 * padding) * i // 4
            painter.drawLine(padding, y, width - padding, y)

        # Calculate scale
        min_val = min(self.data)
        max_val = max(self.data)
        if min_val == max_val:
            min_val -= 100
            max_val += 100

        range_val = max_val - min_val

        # Draw zero/starting line if in range
        start_val = self.data[0] if self.data else 0
        if min_val <= start_val <= max_val:
            start_y = height - padding - ((start_val - min_val) / range_val) * (height - 2 * padding)
            painter.setPen(QPen(QColor("#666"), 1, Qt.DashLine))
            painter.drawLine(padding, int(start_y), width - padding, int(start_y))
            painter.setPen(QColor("#888"))
            font = QFont("Hack", 8)
            painter.setFont(font)
            painter.drawText(5, int(start_y) + 4, f"${start_val:,.0f}")

        # Draw profit line
        if len(self.data) > 1:
            step = (width - 2 * padding) / (len(self.data) - 1)

            for i in range(len(self.data) - 1):
                x1 = padding + i * step
                x2 = padding + (i + 1) * step

                y1 = height - padding - ((self.data[i] - min_val) / range_val) * (height - 2 * padding)
                y2 = height - padding - ((self.data[i + 1] - min_val) / range_val) * (height - 2 * padding)

                if self.data[i + 1] >= self.data[i]:
                    painter.setPen(QPen(QColor("#00ff41"), 2))
                else:
                    painter.setPen(QPen(QColor("#ff4444"), 2))

                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw labels
        painter.setPen(QColor("#888"))
        font = QFont("Hack", 9)
        painter.setFont(font)
        painter.drawText(5, padding, f"${max_val:,.0f}")
        painter.drawText(5, height - padding + 15, f"${min_val:,.0f}")

        # Current value
        if self.data:
            current = self.data[-1]
            start = self.data[0]
            pnl = current - start
            color = "#00ff41" if pnl >= 0 else "#ff4444"
            painter.setPen(QColor(color))
            font = QFont("Hack", 14, QFont.Bold)
            painter.setFont(font)
            painter.drawText(width - 150, 35, f"${pnl:+,.2f}")


class HealthMetric(QFrame):
    """Individual health metric display"""

    def __init__(self, name, value=0, status="ok"):
        super().__init__()
        self.name = name
        self.value = value
        self.status = status
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.status_label = QLabel("●")
        self.update_status(self.status)
        layout.addWidget(self.status_label)

        name_label = QLabel(self.name)
        name_label.setStyleSheet("color: #888;")
        layout.addWidget(name_label)

        layout.addStretch()

        self.value_label = QLabel(str(self.value))
        self.value_label.setStyleSheet("color: #eee; font-weight: bold;")
        layout.addWidget(self.value_label)

    def update_status(self, status):
        self.status = status
        colors = {
            "ok": "#00ff41",
            "warning": "#ffcc00",
            "error": "#ff4444",
            "inactive": "#666"
        }
        color = colors.get(status, "#666")
        self.status_label.setStyleSheet(f"color: {color}; font-size: 14px;")

    def set_value(self, value, status=None):
        self.value = value
        self.value_label.setText(str(value))
        if status:
            self.update_status(status)


class TournamentWorker(QThread):
    """Background worker for running strategy tournament"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            from strategy.tournament import run_tournament
            result = run_tournament(progress_callback=self.progress.emit)
            self.finished.emit(result.to_dict())
        except Exception as e:
            self.error.emit(str(e))


class ModelHealthWidget(QWidget):
    """Model health and confidence visualization - data-driven, not random"""

    def __init__(self):
        super().__init__()
        self.tournament_data = None
        self.is_running = False
        self.setup_ui()

        # Load cached tournament results on startup
        QTimer.singleShot(500, self._load_cached_results)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Top row - confidence gauges
        gauges_layout = QHBoxLayout()

        # Overall confidence gauge
        gauge_frame = QFrame()
        gauge_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        gauge_layout = QVBoxLayout(gauge_frame)

        gauge_title = QLabel("OVERALL CONFIDENCE")
        gauge_title.setStyleSheet("color: #00ff41; font-weight: bold;")
        gauge_title.setAlignment(Qt.AlignCenter)
        gauge_layout.addWidget(gauge_title)

        self.confidence_gauge = CircularGauge("Strategy")
        self.confidence_gauge.set_value(0)
        gauge_layout.addWidget(self.confidence_gauge, alignment=Qt.AlignCenter)

        self.confidence_info = QLabel("Run tournament to assess\nstrategy confidence")
        self.confidence_info.setStyleSheet("color: #666; font-size: 10px;")
        self.confidence_info.setAlignment(Qt.AlignCenter)
        gauge_layout.addWidget(self.confidence_info)

        # Run tournament button
        from PyQt5.QtWidgets import QPushButton
        self.run_btn = QPushButton("Run Strategy Tournament")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #000;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00cc33;
            }
            QPushButton:disabled {
                background-color: #2a2a3e;
                color: #666;
            }
        """)
        self.run_btn.clicked.connect(self._run_tournament)
        gauge_layout.addWidget(self.run_btn)

        gauges_layout.addWidget(gauge_frame)

        # Component confidences
        components_frame = QFrame()
        components_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        components_layout = QVBoxLayout(components_frame)

        comp_title = QLabel("COMPONENT CONFIDENCE")
        comp_title.setStyleSheet("color: #00ccff; font-weight: bold;")
        components_layout.addWidget(comp_title)

        comp_info = QLabel("Based on backtest performance of best strategy")
        comp_info.setStyleSheet("color: #666; font-size: 10px;")
        components_layout.addWidget(comp_info)

        self.trend_bar = self.create_confidence_bar("Trend Detection")
        components_layout.addLayout(self.trend_bar['layout'])

        self.signal_bar = self.create_confidence_bar("Signal Quality")
        components_layout.addLayout(self.signal_bar['layout'])

        self.risk_bar = self.create_confidence_bar("Risk Assessment")
        components_layout.addLayout(self.risk_bar['layout'])

        self.consistency_bar = self.create_confidence_bar("Consistency (MFFU)")
        components_layout.addLayout(self.consistency_bar['layout'])

        components_layout.addStretch()
        gauges_layout.addWidget(components_frame)

        # Performance summary
        perf_frame = QFrame()
        perf_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        perf_layout = QVBoxLayout(perf_frame)

        perf_title = QLabel("BEST STRATEGY PERFORMANCE")
        perf_title.setStyleSheet("color: #ffcc00; font-weight: bold;")
        perf_layout.addWidget(perf_title)

        self.strategy_name_label = QLabel("Strategy: --")
        self.strategy_name_label.setStyleSheet("color: #00ff41; font-size: 11px;")
        perf_layout.addWidget(self.strategy_name_label)

        self.total_pnl_label = QLabel("--")
        self.total_pnl_label.setStyleSheet(
            "color: #888; font-size: 28px; font-weight: bold;")
        self.total_pnl_label.setAlignment(Qt.AlignCenter)
        perf_layout.addWidget(self.total_pnl_label)

        pnl_subtitle = QLabel("Backtest Net P&L")
        pnl_subtitle.setStyleSheet("color: #666;")
        pnl_subtitle.setAlignment(Qt.AlignCenter)
        perf_layout.addWidget(pnl_subtitle)

        perf_grid = QGridLayout()

        metrics_defs = [
            ("Win Rate:", "win_rate_label", "--"),
            ("Profit Factor:", "profit_factor_label", "--"),
            ("Sharpe Ratio:", "sharpe_label", "--"),
            ("Max Drawdown:", "max_dd_label", "--"),
            ("Total Trades:", "trades_label", "--"),
            ("Avg Trade:", "avg_trade_label", "--"),
        ]

        label_colors = ["#00ff41", "#00ccff", "#ffcc00", "#ff4444", "#eee", "#eee"]

        for i, (text, attr, default) in enumerate(metrics_defs):
            label = QLabel(text)
            label.setStyleSheet("color: #888;")
            perf_grid.addWidget(label, i, 0)

            val_label = QLabel(default)
            val_label.setStyleSheet(
                f"color: {label_colors[i]}; font-weight: bold;")
            setattr(self, attr, val_label)
            perf_grid.addWidget(val_label, i, 1)

        perf_layout.addLayout(perf_grid)
        perf_layout.addStretch()
        gauges_layout.addWidget(perf_frame)

        layout.addLayout(gauges_layout)

        # Strategy Rankings Table
        rankings_frame = QFrame()
        rankings_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        rankings_layout = QVBoxLayout(rankings_frame)

        rankings_header = QHBoxLayout()
        rankings_title = QLabel("STRATEGY RANKINGS")
        rankings_title.setStyleSheet("color: #00ff41; font-weight: bold;")
        rankings_header.addWidget(rankings_title)
        rankings_header.addStretch()

        self.tournament_status = QLabel("No tournament results")
        self.tournament_status.setStyleSheet("color: #666; font-size: 10px;")
        rankings_header.addWidget(self.tournament_status)
        rankings_layout.addLayout(rankings_header)

        self.rankings_table = QTableWidget()
        self.rankings_table.setColumnCount(8)
        self.rankings_table.setHorizontalHeaderLabels([
            "Rank", "Strategy", "Return", "Win Rate",
            "Profit Factor", "Sharpe", "Max DD", "Score"
        ])
        self.rankings_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.rankings_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f0f1a;
                color: #eee;
                border: 1px solid #3a3a5e;
                gridline-color: #3a3a5e;
            }
            QHeaderView::section {
                background-color: #16213e;
                color: #00ff41;
                padding: 5px;
                border: 1px solid #3a3a5e;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3a3a5e;
            }
        """)
        self.rankings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rankings_table.setSelectionBehavior(QTableWidget.SelectRows)
        rankings_layout.addWidget(self.rankings_table)

        layout.addWidget(rankings_frame)

        # Equity curve
        chart_frame = QFrame()
        chart_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        chart_layout = QVBoxLayout(chart_frame)

        chart_header = QHBoxLayout()
        chart_title = QLabel("EQUITY CURVE (Best Strategy Backtest)")
        chart_title.setStyleSheet("color: #00ff41; font-weight: bold;")
        chart_header.addWidget(chart_title)
        chart_header.addStretch()

        self.chart_status = QLabel("No data")
        self.chart_status.setStyleSheet("color: #666;")
        chart_header.addWidget(self.chart_status)
        chart_layout.addLayout(chart_header)

        self.profit_chart = ProfitChart()
        chart_layout.addWidget(self.profit_chart)

        layout.addWidget(chart_frame)

        # System health metrics
        health_frame = QFrame()
        health_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        health_layout = QVBoxLayout(health_frame)

        health_header = QHBoxLayout()
        health_title = QLabel("SYSTEM HEALTH")
        health_title.setStyleSheet("color: #00ff41; font-weight: bold;")
        health_header.addWidget(health_title)
        health_header.addStretch()

        health_info = QLabel("System component status")
        health_info.setStyleSheet("color: #666; font-size: 10px;")
        health_header.addWidget(health_info)
        health_layout.addLayout(health_header)

        metrics_grid = QGridLayout()

        self.health_metrics = {}
        metrics = [
            ("API Connection", "Simulated", "warning"),
            ("Data Feed", "Demo Mode", "warning"),
            ("Order Execution", "Paper Only", "warning"),
            ("Risk Monitor", "Active", "ok"),
            ("Strategy Engine", "Ready", "ok"),
            ("Tournament", "Not Run", "inactive"),
        ]

        for i, (name, value, status) in enumerate(metrics):
            metric = HealthMetric(name, value, status)
            self.health_metrics[name] = metric
            metrics_grid.addWidget(metric, i // 3, i % 3)

        health_layout.addLayout(metrics_grid)
        layout.addWidget(health_frame)

    def create_confidence_bar(self, name):
        """Create a labeled progress bar"""
        layout = QHBoxLayout()

        label = QLabel(name)
        label.setStyleSheet("color: #888;")
        label.setMinimumWidth(140)
        layout.addWidget(label)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3a3a5e;
                border-radius: 3px;
            }
        """)
        layout.addWidget(bar)

        value_label = QLabel("--")
        value_label.setStyleSheet("color: #666; font-weight: bold;")
        value_label.setMinimumWidth(45)
        layout.addWidget(value_label)

        return {'layout': layout, 'bar': bar, 'label': value_label}

    def update_confidence_bar(self, bar_dict, value):
        """Update a confidence bar"""
        bar_dict['bar'].setValue(int(value))
        bar_dict['label'].setText(f"{value:.0f}%")

        if value >= 70:
            color = "#00ff41"
        elif value >= 40:
            color = "#ffcc00"
        else:
            color = "#ff4444"

        bar_dict['label'].setStyleSheet(f"color: {color}; font-weight: bold;")
        bar_dict['bar'].setStyleSheet(f"""
            QProgressBar {{
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                height: 20px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

    def update_health(self):
        """Update health display - called by main window timer"""
        pass  # Data is static from tournament results, no random updates

    def _load_cached_results(self):
        """Load previously saved tournament results"""
        try:
            from strategy.tournament import get_latest_tournament_results
            result = get_latest_tournament_results()
            if result:
                self._apply_tournament_data(result.to_dict())
        except Exception:
            pass

    def _run_tournament(self):
        """Run strategy tournament in background"""
        if self.is_running:
            return

        self.is_running = True
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running Tournament...")
        self.tournament_status.setText("Tournament in progress...")
        self.tournament_status.setStyleSheet("color: #ffcc00; font-size: 10px;")
        self.health_metrics["Tournament"].set_value("Running...", "warning")

        self.worker = TournamentWorker()
        self.worker.progress.connect(self._on_tournament_progress)
        self.worker.finished.connect(self._on_tournament_finished)
        self.worker.error.connect(self._on_tournament_error)
        self.worker.start()

    def _on_tournament_progress(self, message):
        self.tournament_status.setText(message)

    def _on_tournament_finished(self, result_dict):
        self.is_running = False
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Strategy Tournament")
        self.health_metrics["Tournament"].set_value("Complete", "ok")
        self._apply_tournament_data(result_dict)

    def _on_tournament_error(self, error_msg):
        self.is_running = False
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run Strategy Tournament")
        self.tournament_status.setText(f"Error: {error_msg}")
        self.tournament_status.setStyleSheet("color: #ff4444; font-size: 10px;")
        self.health_metrics["Tournament"].set_value("Error", "error")

    def _apply_tournament_data(self, data):
        """Apply tournament results to all widgets"""
        self.tournament_data = data
        scores = data.get('scores', [])
        confidence = data.get('confidence_metrics', {})

        # Update confidence gauge
        overall = confidence.get('overall', 50)
        self.confidence_gauge.set_value(overall)

        best_name = data.get('best_strategy', 'Unknown')
        self.confidence_info.setText(
            f"Best: {best_name}\n"
            f"Tested {data.get('num_strategies', 0)} strategies"
        )

        # Update component bars
        self.update_confidence_bar(
            self.trend_bar, confidence.get('trend_detection', 50))
        self.update_confidence_bar(
            self.signal_bar, confidence.get('signal_quality', 50))
        self.update_confidence_bar(
            self.risk_bar, confidence.get('risk_assessment', 50))

        # Consistency from best strategy
        best_score = scores[0] if scores else {}
        consistency_val = best_score.get('consistency_score', 0)
        # For prop firms, consistency < 50% is good
        if consistency_val > 0:
            cons_confidence = max(0, 100 - consistency_val * 2)
        else:
            cons_confidence = 50
        self.update_confidence_bar(self.consistency_bar, cons_confidence)

        # Update performance summary
        if scores:
            best = scores[0]
            self.strategy_name_label.setText(f"Strategy: {best.get('name', '--')}")

            pnl = best.get('total_return', 0)
            color = "#00ff41" if pnl >= 0 else "#ff4444"
            self.total_pnl_label.setText(f"${pnl:+,.2f}")
            self.total_pnl_label.setStyleSheet(
                f"color: {color}; font-size: 28px; font-weight: bold;")

            self.win_rate_label.setText(f"{best.get('win_rate', 0):.1f}%")
            self.profit_factor_label.setText(
                f"{best.get('profit_factor', 0):.2f}")
            self.sharpe_label.setText(f"{best.get('sharpe_ratio', 0):.2f}")
            self.max_dd_label.setText(f"${best.get('max_drawdown', 0):,.2f}")
            self.trades_label.setText(f"{best.get('num_trades', 0)}")
            self.avg_trade_label.setText(
                f"${best.get('avg_trade', 0):,.2f}")

        # Update rankings table
        self.rankings_table.setRowCount(len(scores))
        for i, s in enumerate(scores):
            pnl = s.get('total_return', 0)
            pnl_color = "#00ff41" if pnl >= 0 else "#ff4444"

            items = [
                (f"#{i+1}", "#eee"),
                (s.get('name', ''), "#00ccff"),
                (f"${pnl:+,.2f}", pnl_color),
                (f"{s.get('win_rate', 0):.1f}%", "#eee"),
                (f"{s.get('profit_factor', 0):.2f}", "#eee"),
                (f"{s.get('sharpe_ratio', 0):.2f}", "#eee"),
                (f"${s.get('max_drawdown', 0):,.2f}", "#ff4444"),
                (f"{s.get('composite_score', 0):.1f}", "#ffcc00"),
            ]

            for j, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                if i == 0:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.rankings_table.setItem(i, j, item)

        # Update timestamp
        ts = data.get('timestamp', '')
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                self.tournament_status.setText(
                    f"Last run: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except (ValueError, TypeError):
                self.tournament_status.setText(f"Results loaded")
        self.tournament_status.setStyleSheet("color: #00ff41; font-size: 10px;")

        # Update chart status
        self.chart_status.setText(f"Best: {best_name}")
        self.chart_status.setStyleSheet("color: #00ff41;")

    def set_confidence(self, overall, trend=None, signal=None, risk=None,
                       consistency=None):
        """Set confidence values programmatically"""
        self.confidence_gauge.set_value(overall)

        if trend is not None:
            self.update_confidence_bar(self.trend_bar, trend)
        if signal is not None:
            self.update_confidence_bar(self.signal_bar, signal)
        if risk is not None:
            self.update_confidence_bar(self.risk_bar, risk)
        if consistency is not None:
            self.update_confidence_bar(self.consistency_bar, consistency)

    def set_health_status(self, name, value, status):
        """Set health metric status"""
        if name in self.health_metrics:
            self.health_metrics[name].set_value(value, status)

    def set_live_mode(self, is_live):
        """Switch between live and simulation mode"""
        if is_live:
            self.health_metrics["API Connection"].set_value("Connected", "ok")
            self.health_metrics["Data Feed"].set_value("Live", "ok")
            self.health_metrics["Order Execution"].set_value("Ready", "ok")
        else:
            self.health_metrics["API Connection"].set_value("Simulated", "warning")
            self.health_metrics["Data Feed"].set_value("Demo Mode", "warning")
            self.health_metrics["Order Execution"].set_value("Paper Only", "warning")
