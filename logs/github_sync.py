#!/usr/bin/env python3
"""
GitHub Sync Module
Sync trading performance logs to GitHub repository
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a GitHub sync operation"""
    success: bool
    message: str
    commit_sha: str = ""
    files_synced: List[str] = None

    def __post_init__(self):
        if self.files_synced is None:
            self.files_synced = []


class GitHubSync:
    """
    Syncs performance logs to a GitHub repository

    Features:
    - Auto-commit trading session results
    - Push performance reports and metrics
    - Maintain history of all trading sessions
    - Generate summary markdown files
    """

    def __init__(
        self,
        repo_path: str = None,
        branch: str = None,
        results_dir: str = "results",
        auto_push: bool = True
    ):
        self.repo_path = Path(repo_path or os.getcwd())
        self.branch = branch
        self.results_dir = self.repo_path / results_dir
        self.auto_push = auto_push

        # Ensure results directory exists
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Git status
        self.is_git_repo = (self.repo_path / ".git").exists()

        if not self.is_git_repo:
            logger.warning(f"Not a git repository: {self.repo_path}")

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command"""
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {' '.join(cmd)}")
            logger.error(f"stderr: {e.stderr}")
            raise

    def _ensure_git_identity(self):
        """Ensure git user.name and user.email are set (required for commit)"""
        name_result = self._run_git("config", "user.name", check=False)
        if name_result.returncode != 0 or not name_result.stdout.strip():
            self._run_git("config", "user.name", "Trading Agent")
        email_result = self._run_git("config", "user.email", check=False)
        if email_result.returncode != 0 or not email_result.stdout.strip():
            self._run_git("config", "user.email", "agent@localhost")

    def _get_current_branch(self) -> str:
        """Get current git branch"""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD", check=False)
        return result.stdout.strip() if result.returncode == 0 else "main"

    def sync_session(
        self,
        session_data: Dict,
        session_id: str,
        trades_csv: str = None,
        include_report: bool = True
    ) -> SyncResult:
        """
        Sync a trading session to GitHub

        Args:
            session_data: Session dictionary from PerformanceTracker
            session_id: Unique session identifier
            trades_csv: Path to trades CSV file
            include_report: Generate and include markdown report

        Returns:
            SyncResult with sync status
        """
        if not self.is_git_repo:
            return SyncResult(
                success=False,
                message="Not a git repository"
            )

        files_to_add = []

        try:
            # Create session directory
            session_dir = self.results_dir / f"session_{session_id}"
            session_dir.mkdir(parents=True, exist_ok=True)

            # Save session JSON
            session_file = session_dir / "session.json"
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            files_to_add.append(str(session_file))

            # Copy trades CSV if provided
            if trades_csv and Path(trades_csv).exists():
                trades_dest = session_dir / "trades.csv"
                import shutil
                shutil.copy(trades_csv, trades_dest)
                files_to_add.append(str(trades_dest))

            # Generate report
            if include_report:
                report_file = session_dir / "report.md"
                report_content = self._generate_session_report(session_data)
                with open(report_file, 'w') as f:
                    f.write(report_content)
                files_to_add.append(str(report_file))

            # Update summary
            summary_file = self._update_summary()
            files_to_add.append(str(summary_file))

            # Git operations
            self._ensure_git_identity()

            for f in files_to_add:
                self._run_git("add", f)

            # Commit
            commit_msg = self._generate_commit_message(session_data)
            self._run_git("commit", "-m", commit_msg)

            # Get commit SHA
            result = self._run_git("rev-parse", "HEAD")
            commit_sha = result.stdout.strip()[:8]

            # Push if enabled
            if self.auto_push:
                branch = self.branch or self._get_current_branch()
                push_result = self._run_git("push", "-u", "origin", branch, check=False)

                if push_result.returncode != 0:
                    logger.warning(f"Push failed: {push_result.stderr}")
                    return SyncResult(
                        success=True,
                        message=f"Committed locally but push failed: {push_result.stderr}",
                        commit_sha=commit_sha,
                        files_synced=files_to_add
                    )

            logger.info(f"Session synced to GitHub: {commit_sha}")

            return SyncResult(
                success=True,
                message=f"Session {session_id} synced successfully",
                commit_sha=commit_sha,
                files_synced=files_to_add
            )

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return SyncResult(
                success=False,
                message=str(e)
            )

    def _generate_session_report(self, session: Dict) -> str:
        """Generate markdown report for a session"""
        s = session

        pnl = s.get('net_pnl', 0)
        if pnl > 0:
            status_text = "PROFITABLE"
        elif pnl < 0:
            status_text = "LOSS"
        else:
            status_text = "BREAK-EVEN"

        report = f"""# Trading Session Report

## Session: {s.get('session_id', 'Unknown')}

| Property | Value |
|----------|-------|
| **Status** | {status_text} |
| **Mode** | {s.get('mode', 'paper').upper()} |
| **Symbol** | {s.get('symbol', 'MES')} |
| **Start** | {s.get('start_time', '')[:19]} |
| **End** | {s.get('end_time', '')[:19] if s.get('end_time') else 'Active'} |

---

## Account Summary

| Metric | Value |
|--------|-------|
| Starting Balance | ${s.get('starting_balance', 50000):,.2f} |
| Ending Balance | ${s.get('ending_balance', 50000):,.2f} |
| **Net P&L** | **${pnl:,.2f}** |
| Gross P&L | ${s.get('gross_pnl', 0):,.2f} |
| Commission | ${s.get('total_commission', 0):,.2f} |

---

## Trade Statistics

| Metric | Value |
|--------|-------|
| Total Trades | {s.get('total_trades', 0)} |
| Winning Trades | {s.get('winning_trades', 0)} |
| Losing Trades | {s.get('losing_trades', 0)} |
| **Win Rate** | **{s.get('win_rate', 0):.1f}%** |

| Metric | Value |
|--------|-------|
| Average Win | ${s.get('average_win', 0):,.2f} |
| Average Loss | ${s.get('average_loss', 0):,.2f} |
| Largest Win | ${s.get('largest_win', 0):,.2f} |
| Largest Loss | ${s.get('largest_loss', 0):,.2f} |

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| **Profit Factor** | **{s.get('profit_factor', 0):.2f}** |
| Sharpe Ratio | {s.get('sharpe_ratio', 0):.2f} |
| Max Drawdown | ${s.get('max_drawdown', 0):,.2f} ({s.get('max_drawdown_percent', 0):.2f}%) |

---

## Prop Firm Status

| Rule | Status |
|------|--------|
| Profit Target | ${s.get('profit_target', 3000):,.2f} |
| Progress | {(pnl / s.get('profit_target', 3000) * 100):.1f}% |
| Max Loss Limit | ${s.get('max_loss_limit', 2000):,.2f} |
| Rules Violated | {'YES' if s.get('rules_violated') else 'NO'} |

{f"> **Violation:** {s.get('violation_reason')}" if s.get('rules_violated') else ""}

---

## Trade List

"""
        # Add trade list table
        trades = s.get('trades', [])
        if trades:
            report += "| # | Time | Direction | Entry | Exit | P&L | Reason |\n"
            report += "|---|------|-----------|-------|------|-----|--------|\n"

            for i, t in enumerate(trades[:20], 1):  # Limit to 20 trades
                entry_time = t.get('entry_time', '')[:16] if t.get('entry_time') else ''
                direction = t.get('direction', '').upper()
                entry_price = t.get('entry_price', 0)
                exit_price = t.get('exit_price', 0)
                trade_pnl = t.get('net_pnl', 0)
                reason = t.get('exit_reason', '')

                pnl_display = f"${trade_pnl:,.2f}"
                if trade_pnl > 0:
                    pnl_display = f"**+{pnl_display}**"
                elif trade_pnl < 0:
                    pnl_display = f"*{pnl_display}*"

                report += f"| {i} | {entry_time} | {direction} | ${entry_price:,.2f} | ${exit_price:,.2f} | {pnl_display} | {reason} |\n"

            if len(trades) > 20:
                report += f"\n*... and {len(trades) - 20} more trades*\n"
        else:
            report += "*No trades in this session*\n"

        report += f"""
---

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return report

    def _generate_commit_message(self, session: Dict) -> str:
        """Generate commit message for session sync"""
        session_id = session.get('session_id', 'unknown')
        pnl = session.get('net_pnl', 0)
        trades = session.get('total_trades', 0)
        win_rate = session.get('win_rate', 0)

        if pnl > 0:
            tag = "[PROFIT]"
        elif pnl < 0:
            tag = "[LOSS]"
        else:
            tag = "[FLAT]"

        subject = (
            f"{tag} Session {session_id}: "
            f"${pnl:+,.2f} ({trades} trades, {win_rate:.1f}% win rate)"
        )
        body = (
            f"Mode: {session.get('mode', 'paper')}\n"
            f"Symbol: {session.get('symbol', 'MES')}\n"
            f"Profit Factor: {session.get('profit_factor', 0):.2f}\n"
            f"Max Drawdown: ${session.get('max_drawdown', 0):.2f}"
        )
        return f"{subject}\n\n{body}"

    def _update_summary(self) -> Path:
        """Update the overall performance summary"""
        summary_file = self.results_dir / "PERFORMANCE_SUMMARY.md"

        # Load all sessions
        sessions = []
        for session_dir in self.results_dir.glob("session_*"):
            session_file = session_dir / "session.json"
            if session_file.exists():
                with open(session_file) as f:
                    sessions.append(json.load(f))

        # Sort by start time
        sessions.sort(key=lambda x: x.get('start_time', ''), reverse=True)

        # Calculate totals
        total_pnl = sum(s.get('net_pnl', 0) for s in sessions)
        total_trades = sum(s.get('total_trades', 0) for s in sessions)
        total_wins = sum(s.get('winning_trades', 0) for s in sessions)
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

        profitable_sessions = sum(1 for s in sessions if s.get('net_pnl', 0) > 0)
        losing_sessions = sum(1 for s in sessions if s.get('net_pnl', 0) < 0)

        summary = f"""# Performance Summary

*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Overall Statistics

| Metric | Value |
|--------|-------|
| **Total Sessions** | {len(sessions)} |
| **Profitable Sessions** | {profitable_sessions} |
| **Losing Sessions** | {losing_sessions} |
| **Total Trades** | {total_trades} |
| **Overall Win Rate** | {overall_win_rate:.1f}% |
| **Total Net P&L** | **${total_pnl:,.2f}** |

---

## Session History

| Session | Date | Mode | Symbol | Trades | Win Rate | P&L | Status |
|---------|------|------|--------|--------|----------|-----|--------|
"""

        for s in sessions[:50]:  # Last 50 sessions
            session_id = s.get('session_id', 'unknown')
            date = s.get('start_time', '')[:10]
            mode = s.get('mode', 'paper')
            symbol = s.get('symbol', 'MES')
            trades = s.get('total_trades', 0)
            win_rate = s.get('win_rate', 0)
            pnl = s.get('net_pnl', 0)

            if pnl > 0:
                status = "PROFIT"
            elif pnl < 0:
                status = "LOSS"
            else:
                status = "FLAT"

            summary += f"| {session_id} | {date} | {mode} | {symbol} | {trades} | {win_rate:.1f}% | ${pnl:,.2f} | {status} |\n"

        summary += """
---

## Performance Trends

*Charts and visualizations available in individual session reports.*

---

*This file is auto-generated. Do not edit manually.*
"""

        with open(summary_file, 'w') as f:
            f.write(summary)

        return summary_file

    def get_historical_performance(self) -> Dict:
        """Load and aggregate historical performance data"""
        sessions = []

        for session_dir in self.results_dir.glob("session_*"):
            session_file = session_dir / "session.json"
            if session_file.exists():
                with open(session_file) as f:
                    sessions.append(json.load(f))

        if not sessions:
            return {"sessions": 0, "total_pnl": 0, "total_trades": 0}

        return {
            "sessions": len(sessions),
            "total_pnl": sum(s.get('net_pnl', 0) for s in sessions),
            "total_trades": sum(s.get('total_trades', 0) for s in sessions),
            "total_wins": sum(s.get('winning_trades', 0) for s in sessions),
            "total_losses": sum(s.get('losing_trades', 0) for s in sessions),
            "best_session": max(sessions, key=lambda x: x.get('net_pnl', 0)),
            "worst_session": min(sessions, key=lambda x: x.get('net_pnl', 0)),
            "recent_sessions": sorted(sessions, key=lambda x: x.get('start_time', ''), reverse=True)[:5]
        }


def sync_to_github(
    session_data: Dict,
    session_id: str,
    trades_csv: str = None,
    repo_path: str = None,
    branch: str = None
) -> SyncResult:
    """
    Convenience function to sync session to GitHub

    Args:
        session_data: Session dictionary
        session_id: Session identifier
        trades_csv: Path to trades CSV
        repo_path: Repository path (default: current directory)
        branch: Git branch to push to

    Returns:
        SyncResult
    """
    syncer = GitHubSync(repo_path=repo_path, branch=branch)
    return syncer.sync_session(session_data, session_id, trades_csv)
