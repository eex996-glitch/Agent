#!/usr/bin/env python3
"""
Log Storage Module
Manages persistence and retrieval of trading logs
"""

import os
import json
import csv
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass
import shutil
from loguru import logger


@dataclass
class StorageStats:
    """Storage statistics"""
    total_sessions: int
    total_trades: int
    total_size_mb: float
    oldest_session: str
    newest_session: str


class LogStorage:
    """
    Manages log file storage

    Features:
    - JSON and CSV storage
    - Automatic compression of old logs
    - Session aggregation
    - Cleanup of old data
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or os.path.join(os.path.dirname(__file__), "data"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.sessions_dir = self.base_dir / "sessions"
        self.trades_dir = self.base_dir / "trades"
        self.balances_dir = self.base_dir / "balances"
        self.archive_dir = self.base_dir / "archive"

        for d in [self.sessions_dir, self.trades_dir, self.balances_dir, self.archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ==================== Session Storage ====================

    def save_session(self, session_id: str, data: Dict) -> Path:
        """Save session data"""
        filepath = self.sessions_dir / f"{session_id}.json"
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Session saved: {filepath}")
        return filepath

    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load session data"""
        filepath = self.sessions_dir / f"{session_id}.json"

        if not filepath.exists():
            # Check archive
            archived = self.archive_dir / f"{session_id}.json.gz"
            if archived.exists():
                return self._load_compressed(archived)
            return None

        with open(filepath) as f:
            return json.load(f)

    def list_sessions(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        mode: str = None
    ) -> List[str]:
        """List session IDs with optional filters"""
        sessions = []

        for f in self.sessions_dir.glob("*.json"):
            session_id = f.stem

            if start_date or end_date or mode:
                data = self.load_session(session_id)
                if data:
                    session_time = datetime.fromisoformat(data.get('start_time', '')[:19])

                    if start_date and session_time < start_date:
                        continue
                    if end_date and session_time > end_date:
                        continue
                    if mode and data.get('mode') != mode:
                        continue

            sessions.append(session_id)

        return sorted(sessions, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its related files"""
        deleted = False

        # Delete session file
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            deleted = True

        # Delete trades file
        trades_file = self.trades_dir / f"{session_id}.csv"
        if trades_file.exists():
            trades_file.unlink()
            deleted = True

        # Delete balance file
        balance_file = self.balances_dir / f"{session_id}.json"
        if balance_file.exists():
            balance_file.unlink()
            deleted = True

        return deleted

    # ==================== Trade Storage ====================

    def save_trades_csv(self, session_id: str, trades: List[Dict]) -> Path:
        """Save trades to CSV"""
        if not trades:
            return None

        filepath = self.trades_dir / f"{session_id}.csv"
        fieldnames = trades[0].keys()

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(trades)

        return filepath

    def load_trades_csv(self, session_id: str) -> List[Dict]:
        """Load trades from CSV"""
        filepath = self.trades_dir / f"{session_id}.csv"

        if not filepath.exists():
            return []

        trades = []
        with open(filepath, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                for key in ['entry_price', 'exit_price', 'pnl', 'net_pnl', 'quantity']:
                    if key in row and row[key]:
                        try:
                            row[key] = float(row[key])
                        except:
                            pass
                trades.append(row)

        return trades

    def append_trade(self, session_id: str, trade: Dict):
        """Append a single trade to CSV"""
        filepath = self.trades_dir / f"{session_id}.csv"
        file_exists = filepath.exists()

        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=trade.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade)

    # ==================== Balance History ====================

    def save_balance_history(self, session_id: str, history: List[Dict]) -> Path:
        """Save balance history"""
        filepath = self.balances_dir / f"{session_id}.json"
        with open(filepath, 'w') as f:
            json.dump(history, f)
        return filepath

    def load_balance_history(self, session_id: str) -> List[Dict]:
        """Load balance history"""
        filepath = self.balances_dir / f"{session_id}.json"

        if not filepath.exists():
            return []

        with open(filepath) as f:
            return json.load(f)

    # ==================== Aggregation ====================

    def get_aggregate_stats(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        mode: str = None
    ) -> Dict:
        """Get aggregated statistics across sessions"""
        sessions = self.list_sessions(start_date, end_date, mode)

        stats = {
            "session_count": len(sessions),
            "total_trades": 0,
            "total_pnl": 0.0,
            "total_wins": 0,
            "total_losses": 0,
            "best_session_pnl": 0.0,
            "worst_session_pnl": 0.0,
            "best_session_id": None,
            "worst_session_id": None,
            "modes": {},
            "symbols": {},
            "daily_pnl": {}
        }

        for session_id in sessions:
            data = self.load_session(session_id)
            if not data:
                continue

            pnl = data.get('net_pnl', 0)

            stats["total_trades"] += data.get('total_trades', 0)
            stats["total_pnl"] += pnl
            stats["total_wins"] += data.get('winning_trades', 0)
            stats["total_losses"] += data.get('losing_trades', 0)

            if pnl > stats["best_session_pnl"]:
                stats["best_session_pnl"] = pnl
                stats["best_session_id"] = session_id

            if pnl < stats["worst_session_pnl"]:
                stats["worst_session_pnl"] = pnl
                stats["worst_session_id"] = session_id

            # Group by mode
            mode = data.get('mode', 'unknown')
            if mode not in stats["modes"]:
                stats["modes"][mode] = {"count": 0, "pnl": 0}
            stats["modes"][mode]["count"] += 1
            stats["modes"][mode]["pnl"] += pnl

            # Group by symbol
            symbol = data.get('symbol', 'unknown')
            if symbol not in stats["symbols"]:
                stats["symbols"][symbol] = {"count": 0, "pnl": 0}
            stats["symbols"][symbol]["count"] += 1
            stats["symbols"][symbol]["pnl"] += pnl

            # Daily P&L
            day = data.get('start_time', '')[:10]
            if day:
                stats["daily_pnl"][day] = stats["daily_pnl"].get(day, 0) + pnl

        # Calculate win rate
        total = stats["total_wins"] + stats["total_losses"]
        stats["overall_win_rate"] = (stats["total_wins"] / total * 100) if total > 0 else 0

        return stats

    def get_all_trades(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Iterator[Dict]:
        """Iterate over all trades across sessions"""
        sessions = self.list_sessions(start_date, end_date)

        for session_id in sessions:
            trades = self.load_trades_csv(session_id)
            for trade in trades:
                trade['session_id'] = session_id
                yield trade

    # ==================== Maintenance ====================

    def archive_old_sessions(self, days_old: int = 30) -> int:
        """Compress sessions older than specified days"""
        cutoff = datetime.now() - timedelta(days=days_old)
        archived = 0

        for f in self.sessions_dir.glob("*.json"):
            data = self.load_session(f.stem)
            if not data:
                continue

            session_time = datetime.fromisoformat(data.get('start_time', '')[:19])

            if session_time < cutoff:
                # Compress and move
                self._compress_file(f, self.archive_dir / f"{f.stem}.json.gz")
                f.unlink()

                # Also compress trades if exists
                trades_file = self.trades_dir / f"{f.stem}.csv"
                if trades_file.exists():
                    self._compress_file(trades_file, self.archive_dir / f"{f.stem}_trades.csv.gz")
                    trades_file.unlink()

                archived += 1

        logger.info(f"Archived {archived} old sessions")
        return archived

    def cleanup(self, keep_days: int = 90) -> int:
        """Delete archived data older than specified days"""
        cutoff = datetime.now() - timedelta(days=keep_days)
        deleted = 0

        for f in self.archive_dir.glob("*.gz"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1

        logger.info(f"Deleted {deleted} old archive files")
        return deleted

    def get_storage_stats(self) -> StorageStats:
        """Get storage statistics"""
        sessions = self.list_sessions()

        total_size = 0
        for d in [self.sessions_dir, self.trades_dir, self.balances_dir, self.archive_dir]:
            for f in d.glob("*"):
                total_size += f.stat().st_size

        total_trades = 0
        for session_id in sessions:
            trades = self.load_trades_csv(session_id)
            total_trades += len(trades)

        return StorageStats(
            total_sessions=len(sessions),
            total_trades=total_trades,
            total_size_mb=total_size / (1024 * 1024),
            oldest_session=sessions[-1] if sessions else "",
            newest_session=sessions[0] if sessions else ""
        )

    def _compress_file(self, src: Path, dest: Path):
        """Compress a file with gzip"""
        with open(src, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _load_compressed(self, filepath: Path) -> Optional[Dict]:
        """Load a gzipped JSON file"""
        try:
            with gzip.open(filepath, 'rt') as f:
                return json.load(f)
        except:
            return None

    def export_all_to_csv(self, output_file: str = None) -> Path:
        """Export all sessions to a single CSV"""
        output_file = Path(output_file or self.base_dir / "all_sessions.csv")

        sessions = []
        for session_id in self.list_sessions():
            data = self.load_session(session_id)
            if data:
                # Flatten for CSV
                flat = {
                    'session_id': session_id,
                    'start_time': data.get('start_time', ''),
                    'end_time': data.get('end_time', ''),
                    'mode': data.get('mode', ''),
                    'symbol': data.get('symbol', ''),
                    'starting_balance': data.get('starting_balance', 0),
                    'ending_balance': data.get('ending_balance', 0),
                    'net_pnl': data.get('net_pnl', 0),
                    'total_trades': data.get('total_trades', 0),
                    'winning_trades': data.get('winning_trades', 0),
                    'losing_trades': data.get('losing_trades', 0),
                    'win_rate': data.get('win_rate', 0),
                    'profit_factor': data.get('profit_factor', 0),
                    'max_drawdown': data.get('max_drawdown', 0),
                    'rules_violated': data.get('rules_violated', False)
                }
                sessions.append(flat)

        if sessions:
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=sessions[0].keys())
                writer.writeheader()
                writer.writerows(sessions)

        return output_file
