#!/usr/bin/env python3
"""
Model Health Visualization Widget
Shows confidence levels, profit tracking, and model performance metrics
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QProgressBar, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from datetime import datetime, timedelta
import random
import math


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

        # Calculate dimensions
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
    """Simple profit/loss chart"""

    def __init__(self):
        super().__init__()
        self.data = []
        self.setMinimumHeight(200)
        self.is_simulation = True

    def set_data(self, data, is_simulation=True):
        self.data = data[-50:]  # Keep last 50 points
        self.is_simulation = is_simulation
        self.update()

    def add_point(self, value):
        self.data.append(value)
        if len(self.data) > 50:
            self.data.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        padding = 50

        # Draw background
        painter.fillRect(0, 0, width, height, QColor("#0f0f1a"))

        # Draw simulation notice if applicable
        if self.is_simulation:
            painter.setPen(QColor("#ffcc00"))
            font = QFont("Hack", 9)
            painter.setFont(font)
            painter.drawText(width - 150, 15, "SIMULATION DATA")

        if not self.data:
            painter.setPen(QColor("#666"))
            font = QFont("Hack", 12)
            painter.setFont(font)
            painter.drawText(0, 0, width, height, Qt.AlignCenter, "No data yet")
            return

        # Draw grid
        painter.setPen(QPen(QColor("#3a3a5e"), 1))
        for i in range(5):
            y = padding + (height - 2 * padding) * i // 4
            painter.drawLine(padding, y, width - padding, y)

        # Calculate scale
        min_val = min(self.data) if self.data else 0
        max_val = max(self.data) if self.data else 1
        if min_val == max_val:
            min_val -= 100
            max_val += 100

        range_val = max_val - min_val

        # Draw zero line if in range
        if min_val <= 0 <= max_val:
            zero_y = height - padding - ((0 - min_val) / range_val) * (height - 2 * padding)
            painter.setPen(QPen(QColor("#666"), 1, Qt.DashLine))
            painter.drawLine(padding, int(zero_y), width - padding, int(zero_y))
            painter.setPen(QColor("#888"))
            font = QFont("Hack", 8)
            painter.setFont(font)
            painter.drawText(5, int(zero_y) + 4, "$0")

        # Draw profit line
        if len(self.data) > 1:
            step = (width - 2 * padding) / (len(self.data) - 1)

            for i in range(len(self.data) - 1):
                x1 = padding + i * step
                x2 = padding + (i + 1) * step

                y1 = height - padding - ((self.data[i] - min_val) / range_val) * (height - 2 * padding)
                y2 = height - padding - ((self.data[i + 1] - min_val) / range_val) * (height - 2 * padding)

                # Color based on direction
                if self.data[i + 1] >= self.data[i]:
                    painter.setPen(QPen(QColor("#00ff41"), 2))
                else:
                    painter.setPen(QPen(QColor("#ff4444"), 2))

                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # Draw points
            for i, val in enumerate(self.data):
                x = padding + i * step
                y = height - padding - ((val - min_val) / range_val) * (height - 2 * padding)

                if val >= 0:
                    painter.setBrush(QBrush(QColor("#00ff41")))
                else:
                    painter.setBrush(QBrush(QColor("#ff4444")))

                painter.setPen(Qt.NoPen)
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)

        # Draw labels
        painter.setPen(QColor("#888"))
        font = QFont("Hack", 9)
        painter.setFont(font)
        painter.drawText(5, padding, f"${max_val:,.0f}")
        painter.drawText(5, height - padding + 15, f"${min_val:,.0f}")

        # Current value
        if self.data:
            current = self.data[-1]
            color = "#00ff41" if current >= 0 else "#ff4444"
            painter.setPen(QColor(color))
            font = QFont("Hack", 14, QFont.Bold)
            painter.setFont(font)
            painter.drawText(width - 120, 35, f"${current:,.2f}")


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

        # Status indicator
        self.status_label = QLabel("●")
        self.update_status(self.status)
        layout.addWidget(self.status_label)

        # Name
        name_label = QLabel(self.name)
        name_label.setStyleSheet("color: #888;")
        layout.addWidget(name_label)

        layout.addStretch()

        # Value
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


class ModelHealthWidget(QWidget):
    """Model health and confidence visualization"""

    def __init__(self):
        super().__init__()
        self.profit_history = [0]
        self.confidence = 50
        self.is_trading = False
        self.setup_ui()

        # Simulation timer for demo
        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self.simulate_update)
        self.sim_timer.start(2000)

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
        self.confidence_gauge.set_value(75)
        gauge_layout.addWidget(self.confidence_gauge, alignment=Qt.AlignCenter)

        # Explanation
        confidence_info = QLabel("Based on recent signal accuracy\nand market conditions")
        confidence_info.setStyleSheet("color: #666; font-size: 10px;")
        confidence_info.setAlignment(Qt.AlignCenter)
        gauge_layout.addWidget(confidence_info)

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

        comp_info = QLabel("Individual component performance metrics")
        comp_info.setStyleSheet("color: #666; font-size: 10px;")
        components_layout.addWidget(comp_info)

        self.trend_bar = self.create_confidence_bar("Trend Detection")
        components_layout.addLayout(self.trend_bar['layout'])

        self.signal_bar = self.create_confidence_bar("Signal Quality")
        components_layout.addLayout(self.signal_bar['layout'])

        self.risk_bar = self.create_confidence_bar("Risk Assessment")
        components_layout.addLayout(self.risk_bar['layout'])

        self.sentiment_bar = self.create_confidence_bar("Sentiment Analysis")
        components_layout.addLayout(self.sentiment_bar['layout'])

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

        perf_title = QLabel("PERFORMANCE SUMMARY")
        perf_title.setStyleSheet("color: #ffcc00; font-weight: bold;")
        perf_layout.addWidget(perf_title)

        # Mode indicator
        self.mode_label = QLabel("Mode: SIMULATION")
        self.mode_label.setStyleSheet("color: #ffcc00; font-size: 10px;")
        perf_layout.addWidget(self.mode_label)

        self.total_pnl_label = QLabel("$0.00")
        self.total_pnl_label.setStyleSheet("color: #00ff41; font-size: 28px; font-weight: bold;")
        self.total_pnl_label.setAlignment(Qt.AlignCenter)
        perf_layout.addWidget(self.total_pnl_label)

        pnl_subtitle = QLabel("Simulated P&L")
        pnl_subtitle.setStyleSheet("color: #666;")
        pnl_subtitle.setAlignment(Qt.AlignCenter)
        perf_layout.addWidget(pnl_subtitle)

        perf_grid = QGridLayout()

        self.win_rate_label = QLabel("--")
        self.win_rate_label.setStyleSheet("color: #00ff41; font-weight: bold;")
        perf_grid.addWidget(QLabel("Win Rate:"), 0, 0)
        perf_grid.addWidget(self.win_rate_label, 0, 1)

        self.profit_factor_label = QLabel("--")
        self.profit_factor_label.setStyleSheet("color: #00ccff; font-weight: bold;")
        perf_grid.addWidget(QLabel("Profit Factor:"), 1, 0)
        perf_grid.addWidget(self.profit_factor_label, 1, 1)

        self.sharpe_label = QLabel("--")
        self.sharpe_label.setStyleSheet("color: #ffcc00; font-weight: bold;")
        perf_grid.addWidget(QLabel("Sharpe Ratio:"), 2, 0)
        perf_grid.addWidget(self.sharpe_label, 2, 1)

        self.max_dd_label = QLabel("--")
        self.max_dd_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        perf_grid.addWidget(QLabel("Max Drawdown:"), 3, 0)
        perf_grid.addWidget(self.max_dd_label, 3, 1)

        perf_layout.addLayout(perf_grid)
        perf_layout.addStretch()
        gauges_layout.addWidget(perf_frame)

        layout.addLayout(gauges_layout)

        # Profit chart
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
        chart_title = QLabel("EQUITY CURVE")
        chart_title.setStyleSheet("color: #00ff41; font-weight: bold;")
        chart_header.addWidget(chart_title)

        chart_header.addStretch()

        # Chart info/explanation
        chart_info = QLabel("Simulated performance - not actual trading results")
        chart_info.setStyleSheet("color: #ffcc00; font-size: 10px;")
        chart_header.addWidget(chart_info)

        self.chart_status = QLabel("● Demo Mode")
        self.chart_status.setStyleSheet("color: #ffcc00;")
        chart_header.addWidget(self.chart_status)
        chart_layout.addLayout(chart_header)

        self.profit_chart = ProfitChart()
        chart_layout.addWidget(self.profit_chart)

        # Chart legend
        legend_layout = QHBoxLayout()
        legend_layout.addStretch()

        legend_info = QLabel("This chart shows simulated equity based on demo data. "
                            "Run actual trades or backtests for real performance data.")
        legend_info.setStyleSheet("color: #666; font-size: 10px;")
        legend_info.setWordWrap(True)
        legend_layout.addWidget(legend_info)

        legend_layout.addStretch()
        chart_layout.addLayout(legend_layout)

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

        health_info = QLabel("Real-time system component status")
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
            ("News Feed", "Active", "ok"),
            ("Model Status", "Ready", "ok"),
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
        label.setMinimumWidth(120)
        layout.addWidget(label)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(50)
        bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ff41;
                border-radius: 3px;
            }
        """)
        layout.addWidget(bar)

        value_label = QLabel("50%")
        value_label.setStyleSheet("color: #00ff41; font-weight: bold;")
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
        """Update health display - called by main window"""
        pass  # Real updates would happen here

    def simulate_update(self):
        """Simulate updates for demo"""
        # Update confidence values
        self.confidence = max(20, min(95, self.confidence + random.uniform(-5, 5)))
        self.confidence_gauge.set_value(self.confidence)

        self.update_confidence_bar(self.trend_bar, random.uniform(50, 90))
        self.update_confidence_bar(self.signal_bar, random.uniform(40, 85))
        self.update_confidence_bar(self.risk_bar, random.uniform(60, 95))
        self.update_confidence_bar(self.sentiment_bar, random.uniform(30, 80))

        # Update profit chart with simulation data
        last_profit = self.profit_history[-1] if self.profit_history else 0
        change = random.uniform(-50, 75)  # Slightly bullish bias for demo
        new_profit = last_profit + change
        self.profit_history.append(new_profit)
        self.profit_chart.set_data(self.profit_history, is_simulation=True)

        # Update P&L display
        color = "#00ff41" if new_profit >= 0 else "#ff4444"
        self.total_pnl_label.setText(f"${new_profit:,.2f}")
        self.total_pnl_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")

        # Update performance metrics (simulated)
        self.win_rate_label.setText(f"{random.uniform(45, 65):.1f}%")
        self.profit_factor_label.setText(f"{random.uniform(1.2, 2.5):.2f}")
        self.sharpe_label.setText(f"{random.uniform(0.8, 2.2):.2f}")
        self.max_dd_label.setText(f"${random.uniform(200, 800):.2f}")

    def set_pnl(self, pnl, is_simulation=False):
        """Set the P&L value"""
        self.profit_history.append(pnl)
        self.profit_chart.set_data(self.profit_history, is_simulation=is_simulation)

        color = "#00ff41" if pnl >= 0 else "#ff4444"
        self.total_pnl_label.setText(f"${pnl:,.2f}")
        self.total_pnl_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")

        if not is_simulation:
            self.mode_label.setText("Mode: LIVE DATA")
            self.mode_label.setStyleSheet("color: #00ff41; font-size: 10px;")
            self.chart_status.setText("● Live")
            self.chart_status.setStyleSheet("color: #00ff41;")

    def set_confidence(self, overall, trend=None, signal=None, risk=None, sentiment=None):
        """Set confidence values"""
        self.confidence_gauge.set_value(overall)

        if trend is not None:
            self.update_confidence_bar(self.trend_bar, trend)
        if signal is not None:
            self.update_confidence_bar(self.signal_bar, signal)
        if risk is not None:
            self.update_confidence_bar(self.risk_bar, risk)
        if sentiment is not None:
            self.update_confidence_bar(self.sentiment_bar, sentiment)

    def set_health_status(self, name, value, status):
        """Set health metric status"""
        if name in self.health_metrics:
            self.health_metrics[name].set_value(value, status)

    def set_live_mode(self, is_live):
        """Switch between live and simulation mode"""
        self.is_trading = is_live
        if is_live:
            self.mode_label.setText("Mode: LIVE")
            self.mode_label.setStyleSheet("color: #00ff41; font-size: 10px;")
            self.chart_status.setText("● Live")
            self.chart_status.setStyleSheet("color: #00ff41;")

            # Update health metrics for live mode
            self.health_metrics["API Connection"].set_value("Connected", "ok")
            self.health_metrics["Data Feed"].set_value("Live", "ok")
            self.health_metrics["Order Execution"].set_value("Ready", "ok")
        else:
            self.mode_label.setText("Mode: SIMULATION")
            self.mode_label.setStyleSheet("color: #ffcc00; font-size: 10px;")
            self.chart_status.setText("● Demo Mode")
            self.chart_status.setStyleSheet("color: #ffcc00;")

            # Update health metrics for demo mode
            self.health_metrics["API Connection"].set_value("Simulated", "warning")
            self.health_metrics["Data Feed"].set_value("Demo Mode", "warning")
            self.health_metrics["Order Execution"].set_value("Paper Only", "warning")
