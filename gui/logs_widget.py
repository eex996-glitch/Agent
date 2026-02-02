#!/usr/bin/env python3
"""
Logs Widget for GUI
Display and manage trading performance logs with GitHub sync
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QGroupBox, QTextEdit, QComboBox, QMessageBox, QFileDialog,
    QProgressBar, QSplitter, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor
from datetime import datetime
import json


class GitHubSyncWorker(QThread):
    """Background worker for GitHub sync"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)

    def __init__(self, session_data, session_id, trades_csv=None):
        super().__init__()
        self.session_data = session_data
        self.session_id = session_id
        self.trades_csv = trades_csv

    def run(self):
        try:
            self.progress.emit("Syncing to GitHub...")

            from logs.github_sync import sync_to_github
            result = sync_to_github(
                self.session_data,
                self.session_id,
                self.trades_csv
            )

            if result.success:
                self.finished.emit(True, f"Synced! Commit: {result.commit_sha}")
            else:
                self.finished.emit(False, f"Failed: {result.message}")

        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")


class SessionCard(QFrame):
    """Card displaying session summary"""

    clicked = pyqtSignal(str)  # Emits session_id

    def __init__(self, session_data: dict):
        super().__init__()
        self.session_id = session_data.get('session_id', 'unknown')
        self.data = session_data
        self.setup_ui()

    def setup_ui(self):
        pnl = self.data.get('net_pnl', 0)

        if pnl > 0:
            border_color = "#00ff41"
        elif pnl < 0:
            border_color = "#ff4444"
        else:
            border_color = "#888888"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #16213e;
                border-left: 4px solid {border_color};
                border-radius: 4px;
                padding: 10px;
                margin: 3px;
            }}
            QFrame:hover {{
                background-color: #1a2a4e;
                cursor: pointer;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Header
        header = QHBoxLayout()
        id_label = QLabel(f"Session: {self.session_id}")
        id_label.setStyleSheet("color: #00ff41; font-weight: bold;")
        header.addWidget(id_label)

        date_str = self.data.get('start_time', '')[:10]
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #888;")
        header.addWidget(date_label)

        header.addStretch()

        mode = self.data.get('mode', 'paper').upper()
        mode_label = QLabel(mode)
        mode_colors = {'PAPER': '#ffcc00', 'DEMO': '#00ccff', 'LIVE': '#ff4444'}
        mode_label.setStyleSheet(f"color: {mode_colors.get(mode, '#888')};")
        header.addWidget(mode_label)

        layout.addLayout(header)

        # Stats
        stats = QHBoxLayout()

        trades = self.data.get('total_trades', 0)
        stats.addWidget(QLabel(f"Trades: {trades}"))

        win_rate = self.data.get('win_rate', 0)
        stats.addWidget(QLabel(f"Win: {win_rate:.1f}%"))

        pnl_label = QLabel(f"P&L: ${pnl:+,.2f}")
        pnl_label.setStyleSheet(f"color: {border_color}; font-weight: bold;")
        stats.addWidget(pnl_label)

        stats.addStretch()
        layout.addLayout(stats)

    def mousePressEvent(self, event):
        self.clicked.emit(self.session_id)


class LogsWidget(QWidget):
    """Main logs management widget"""

    def __init__(self, tracker=None):
        super().__init__()
        self.tracker = tracker
        self.sessions = []
        self.current_session = None
        self.sync_worker = None
        self.setup_ui()
        self.load_sessions()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # Left panel - session list
        left_panel = QVBoxLayout()

        # Header
        header = QHBoxLayout()
        title = QLabel("TRADING LOGS")
        title.setStyleSheet("color: #00ff41; font-size: 16px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_sessions)
        header.addWidget(refresh_btn)

        left_panel.addLayout(header)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Mode:"))
        self.mode_filter = QComboBox()
        self.mode_filter.addItems(["All", "Paper", "Demo", "Live"])
        self.mode_filter.currentTextChanged.connect(self.apply_filter)
        self.mode_filter.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        filter_layout.addWidget(self.mode_filter)
        left_panel.addLayout(filter_layout)

        # Sessions list
        self.sessions_container = QWidget()
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setAlignment(Qt.AlignTop)
        self.sessions_layout.setSpacing(5)

        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(self.sessions_container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        left_panel.addWidget(scroll)

        # Summary stats
        self.summary_label = QLabel("Total: 0 sessions | $0.00")
        self.summary_label.setStyleSheet("color: #888; padding: 5px;")
        left_panel.addWidget(self.summary_label)

        layout.addLayout(left_panel, 1)

        # Right panel - session details
        right_panel = QVBoxLayout()

        # Tabs for details
        self.details_tabs = QTabWidget()

        # Report tab
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("""
            background-color: #0f0f1a;
            color: #00ff41;
            font-family: 'Hack', monospace;
            border: 1px solid #3a3a5e;
        """)
        self.details_tabs.addTab(self.report_text, "Report")

        # Trades tab
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels([
            "Time", "Direction", "Entry", "Exit", "P&L", "Reason", "Duration"
        ])
        self.trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trades_table.setStyleSheet("""
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
        """)
        self.details_tabs.addTab(self.trades_table, "Trades")

        # JSON tab
        self.json_text = QTextEdit()
        self.json_text.setReadOnly(True)
        self.json_text.setStyleSheet("""
            background-color: #0f0f1a;
            color: #888;
            font-family: 'Hack', monospace;
            border: 1px solid #3a3a5e;
        """)
        self.details_tabs.addTab(self.json_text, "Raw JSON")

        right_panel.addWidget(self.details_tabs)

        # Action buttons
        actions = QHBoxLayout()

        self.save_btn = QPushButton("Save Session")
        self.save_btn.clicked.connect(self.save_current_session)
        actions.addWidget(self.save_btn)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        actions.addWidget(self.export_btn)

        self.sync_btn = QPushButton("Sync to GitHub")
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        self.sync_btn.clicked.connect(self.sync_to_github)
        actions.addWidget(self.sync_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #da3633;
                color: white;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_session)
        actions.addWidget(self.delete_btn)

        right_panel.addLayout(actions)

        # Sync status
        self.sync_status = QLabel("")
        self.sync_status.setStyleSheet("color: #888;")
        right_panel.addWidget(self.sync_status)

        layout.addLayout(right_panel, 2)

    def load_sessions(self):
        """Load all sessions from storage"""
        # Clear existing
        while self.sessions_layout.count():
            item = self.sessions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.sessions = []

        try:
            from logs.storage import LogStorage
            storage = LogStorage()

            for session_id in storage.list_sessions():
                data = storage.load_session(session_id)
                if data:
                    self.sessions.append(data)

                    card = SessionCard(data)
                    card.clicked.connect(self.show_session)
                    self.sessions_layout.addWidget(card)

            # Update summary
            total_pnl = sum(s.get('net_pnl', 0) for s in self.sessions)
            self.summary_label.setText(
                f"Total: {len(self.sessions)} sessions | ${total_pnl:+,.2f}"
            )

        except Exception as e:
            self.summary_label.setText(f"Error loading sessions: {e}")

    def apply_filter(self, mode_filter: str):
        """Apply mode filter to session list"""
        mode_filter = mode_filter.lower()

        for i in range(self.sessions_layout.count()):
            widget = self.sessions_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'data'):
                if mode_filter == "all":
                    widget.show()
                else:
                    session_mode = widget.data.get('mode', '').lower()
                    widget.setVisible(session_mode == mode_filter)

    def show_session(self, session_id: str):
        """Display session details"""
        # Find session data
        for session in self.sessions:
            if session.get('session_id') == session_id:
                self.current_session = session
                break
        else:
            return

        # Update report
        self.report_text.setText(self._generate_report(self.current_session))

        # Update trades table
        self.trades_table.setRowCount(0)
        trades = self.current_session.get('trades', [])

        for trade in trades:
            row = self.trades_table.rowCount()
            self.trades_table.insertRow(row)

            self.trades_table.setItem(row, 0, QTableWidgetItem(
                trade.get('entry_time', '')[:16]
            ))
            self.trades_table.setItem(row, 1, QTableWidgetItem(
                trade.get('direction', '').upper()
            ))
            self.trades_table.setItem(row, 2, QTableWidgetItem(
                f"${trade.get('entry_price', 0):,.2f}"
            ))
            self.trades_table.setItem(row, 3, QTableWidgetItem(
                f"${trade.get('exit_price', 0):,.2f}"
            ))

            pnl = trade.get('net_pnl', 0)
            pnl_item = QTableWidgetItem(f"${pnl:+,.2f}")
            pnl_item.setForeground(QColor("#00ff41" if pnl >= 0 else "#ff4444"))
            self.trades_table.setItem(row, 4, pnl_item)

            self.trades_table.setItem(row, 5, QTableWidgetItem(
                trade.get('exit_reason', '')
            ))

            # Calculate duration
            try:
                entry = datetime.fromisoformat(trade.get('entry_time', ''))
                exit_t = datetime.fromisoformat(trade.get('exit_time', ''))
                duration = (exit_t - entry).total_seconds() / 60
                duration_str = f"{duration:.0f}m"
            except:
                duration_str = "--"
            self.trades_table.setItem(row, 6, QTableWidgetItem(duration_str))

        # Update JSON
        self.json_text.setText(json.dumps(self.current_session, indent=2))

    def _generate_report(self, session: dict) -> str:
        """Generate text report for session"""
        s = session
        pnl = s.get('net_pnl', 0)

        return f"""
================================================================================
                        TRADING SESSION REPORT
================================================================================

Session ID: {s.get('session_id', 'unknown')}
Mode: {s.get('mode', 'paper').upper()}
Symbol: {s.get('symbol', 'MES')}

Period: {s.get('start_time', '')[:19]} to {s.get('end_time', '')[:19] if s.get('end_time') else 'Active'}

--------------------------------------------------------------------------------
                              ACCOUNT SUMMARY
--------------------------------------------------------------------------------

Starting Balance:     ${s.get('starting_balance', 50000):>12,.2f}
Ending Balance:       ${s.get('ending_balance', 50000):>12,.2f}
Net P&L:              ${pnl:>12,.2f} ({(pnl/s.get('starting_balance', 50000))*100:+.2f}%)

--------------------------------------------------------------------------------
                              TRADE STATISTICS
--------------------------------------------------------------------------------

Total Trades:         {s.get('total_trades', 0):>12}
Winning Trades:       {s.get('winning_trades', 0):>12}
Losing Trades:        {s.get('losing_trades', 0):>12}
Win Rate:             {s.get('win_rate', 0):>12.1f}%

Average Win:          ${s.get('average_win', 0):>12,.2f}
Average Loss:         ${s.get('average_loss', 0):>12,.2f}
Profit Factor:        {s.get('profit_factor', 0):>12.2f}

--------------------------------------------------------------------------------
                               RISK METRICS
--------------------------------------------------------------------------------

Max Drawdown:         ${s.get('max_drawdown', 0):>12,.2f}
Sharpe Ratio:         {s.get('sharpe_ratio', 0):>12.2f}

--------------------------------------------------------------------------------
                            PROP FIRM STATUS
--------------------------------------------------------------------------------

Profit Target:        ${s.get('profit_target', 3000):>12,.2f}
Progress:             {(pnl/s.get('profit_target', 3000))*100:>12.1f}%
Rules Violated:       {'YES' if s.get('rules_violated') else 'NO':>12}

================================================================================
"""

    def save_current_session(self):
        """Save current session to storage"""
        if not self.current_session:
            QMessageBox.warning(self, "Warning", "No session selected")
            return

        try:
            from logs.storage import LogStorage
            storage = LogStorage()
            storage.save_session(
                self.current_session.get('session_id'),
                self.current_session
            )
            self.sync_status.setText("Session saved locally")
            self.sync_status.setStyleSheet("color: #00ff41;")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def export_csv(self):
        """Export current session trades to CSV"""
        if not self.current_session:
            QMessageBox.warning(self, "Warning", "No session selected")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Trades", f"trades_{self.current_session.get('session_id')}.csv",
            "CSV Files (*.csv)"
        )

        if filepath:
            try:
                import csv
                trades = self.current_session.get('trades', [])

                if trades:
                    with open(filepath, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=trades[0].keys())
                        writer.writeheader()
                        writer.writerows(trades)

                    self.sync_status.setText(f"Exported to {filepath}")
                    self.sync_status.setStyleSheet("color: #00ff41;")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def sync_to_github(self):
        """Sync current session to GitHub"""
        if not self.current_session:
            QMessageBox.warning(self, "Warning", "No session selected")
            return

        self.sync_btn.setEnabled(False)
        self.sync_status.setText("Syncing to GitHub...")
        self.sync_status.setStyleSheet("color: #ffcc00;")

        self.sync_worker = GitHubSyncWorker(
            self.current_session,
            self.current_session.get('session_id')
        )
        self.sync_worker.finished.connect(self._on_sync_complete)
        self.sync_worker.start()

    def _on_sync_complete(self, success: bool, message: str):
        """Handle sync completion"""
        self.sync_btn.setEnabled(True)

        if success:
            self.sync_status.setText(message)
            self.sync_status.setStyleSheet("color: #00ff41;")
            QMessageBox.information(self, "Success", "Session synced to GitHub!")
        else:
            self.sync_status.setText(message)
            self.sync_status.setStyleSheet("color: #ff4444;")
            QMessageBox.warning(self, "Sync Failed", message)

    def delete_session(self):
        """Delete selected session"""
        if not self.current_session:
            QMessageBox.warning(self, "Warning", "No session selected")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete session {self.current_session.get('session_id')}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                from logs.storage import LogStorage
                storage = LogStorage()
                storage.delete_session(self.current_session.get('session_id'))
                self.current_session = None
                self.load_sessions()
                self.report_text.clear()
                self.trades_table.setRowCount(0)
                self.json_text.clear()
                self.sync_status.setText("Session deleted")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Delete failed: {e}")
