"""
Pytest Configuration and Fixtures
"""

import pytest
import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing"""
    return {
        'trade_id': 'test-001',
        'session_id': 'session-001',
        'symbol': 'MESZ4',
        'direction': 'long',
        'entry_time': datetime.now().isoformat(),
        'entry_price': 5250.00,
        'quantity': 2,
        'stop_loss': 5240.00,
        'take_profit': 5270.00,
        'status': 'open'
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing"""
    return {
        'session_id': 'session-001',
        'start_time': datetime.now().isoformat(),
        'mode': 'paper',
        'symbol': 'MESZ4',
        'starting_balance': 50000.0,
        'ending_balance': 50500.0,
        'net_pnl': 500.0,
        'total_trades': 5,
        'winning_trades': 3,
        'losing_trades': 2,
        'win_rate': 60.0,
        'profit_factor': 1.5,
        'max_drawdown': 200.0,
        'trades': []
    }


@pytest.fixture
def sample_ohlc_data():
    """Sample OHLC price data"""
    import pandas as pd
    import numpy as np

    dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
    base_price = 5250.0

    data = pd.DataFrame({
        'open': base_price + np.random.randn(100) * 5,
        'high': base_price + np.random.randn(100) * 5 + 3,
        'low': base_price + np.random.randn(100) * 5 - 3,
        'close': base_price + np.random.randn(100) * 5,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)

    # Ensure high is highest, low is lowest
    data['high'] = data[['open', 'high', 'close']].max(axis=1) + 1
    data['low'] = data[['open', 'low', 'close']].min(axis=1) - 1

    return data


@pytest.fixture
def mock_tradovate_client():
    """Mock Tradovate API client"""
    client = Mock()
    client.authenticate.return_value = True
    client.access_token = 'mock_token'
    client.user_id = 12345
    client.active_account_id = 67890
    client.accounts = [
        Mock(id=67890, name='Test Account', active=True)
    ]
    client.get_positions.return_value = []
    client.get_open_orders.return_value = []
    client.place_order.return_value = Mock(
        success=True,
        order_id=99999,
        message='Order placed'
    )
    return client


@pytest.fixture
def mffu_rules():
    """MFFU rules fixture"""
    from config.prop_firm_rules import get_mffu_rules
    return get_mffu_rules('Starter')


@pytest.fixture
def temp_log_dir(tmp_path):
    """Temporary directory for logs"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables after each test"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
