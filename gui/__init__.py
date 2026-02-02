# GUI Module for Futures Trading Agent
# Kali Linux compatible PyQt5 interface

from .main_window import MainWindow
from .dashboard import DashboardWidget
from .news_feed import NewsFeedWidget
from .model_health import ModelHealthWidget
from .logs_widget import LogsWidget

__all__ = ['MainWindow', 'DashboardWidget', 'NewsFeedWidget', 'ModelHealthWidget', 'LogsWidget']
