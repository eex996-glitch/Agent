#!/usr/bin/env python3
"""
Main GUI Window for Futures Trading Agent
Kali Linux compatible PyQt5 interface
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QAction, QLabel,
    QMessageBox, QSplitter, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

from .dashboard import DashboardWidget
from .news_feed import NewsFeedWidget
from .model_health import ModelHealthWidget
from .logs_widget import LogsWidget


class MainWindow(QMainWindow):
    """Main application window with dark theme for Kali Linux"""

    def __init__(self, trader=None):
        super().__init__()
        self.trader = trader
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

        for mode in ["Backtest", "Paper", "Demo", "Live"]:
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
        self.tabs.addTab(self.dashboard, "📊 Dashboard")

        # News feed tab
        self.news_feed = NewsFeedWidget()
        self.tabs.addTab(self.news_feed, "📰 News Feed")

        # Model health tab
        self.model_health = ModelHealthWidget()
        self.tabs.addTab(self.model_health, "💚 Model Health")

        # Logs tab
        self.logs_widget = LogsWidget()
        self.tabs.addTab(self.logs_widget, "📋 Logs")

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.mode_label = QLabel("Mode: Paper")
        self.mode_label.setStyleSheet("color: #ffcc00;")
        self.status_bar.addPermanentWidget(self.mode_label)

        self.connection_label = QLabel("● Disconnected")
        self.connection_label.setStyleSheet("color: #ff4444;")
        self.status_bar.addPermanentWidget(self.connection_label)

    def update_all(self):
        """Update all widgets"""
        self.dashboard.update_data()
        self.news_feed.update_feed()
        self.model_health.update_health()

    def start_trading(self):
        """Start trading"""
        self.status_label.setText("Trading started...")
        self.connection_label.setText("● Connected")
        self.connection_label.setStyleSheet("color: #00ff41;")
        if self.dashboard:
            self.dashboard.set_trading_active(True)

    def stop_trading(self):
        """Stop trading"""
        self.status_label.setText("Trading stopped")
        self.connection_label.setText("● Disconnected")
        self.connection_label.setStyleSheet("color: #ff4444;")
        if self.dashboard:
            self.dashboard.set_trading_active(False)

    def set_mode(self, mode):
        """Set trading mode"""
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
            "<p>⚠️ Trading involves risk. Use responsibly.</p>"
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
