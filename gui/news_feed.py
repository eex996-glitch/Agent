#!/usr/bin/env python3
"""
News Feed Widget with Sentiment Analysis
Pulls financial news and analyzes sentiment to influence trading decisions
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGroupBox, QPushButton, QComboBox,
    QProgressBar, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont
from datetime import datetime, timedelta
import random


class NewsItem(QFrame):
    """Individual news item display"""

    def __init__(self, headline, source, time, sentiment, impact):
        super().__init__()
        self.sentiment = sentiment
        self.impact = impact
        self.setup_ui(headline, source, time)

    def setup_ui(self, headline, source, time):
        # Color based on sentiment
        sentiment_colors = {
            'bullish': '#00ff41',
            'bearish': '#ff4444',
            'neutral': '#888888'
        }
        border_color = sentiment_colors.get(self.sentiment, '#3a3a5e')

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #16213e;
                border-left: 4px solid {border_color};
                border-radius: 4px;
                padding: 10px;
                margin: 5px;
            }}
            QFrame:hover {{
                background-color: #1a2a4e;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Header with sentiment badge
        header_layout = QHBoxLayout()

        # Sentiment badge
        sentiment_text = self.sentiment.upper()
        badge = QLabel(sentiment_text)
        badge.setStyleSheet(f"""
            background-color: {border_color};
            color: {'#000' if self.sentiment == 'bullish' else '#fff'};
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        header_layout.addWidget(badge)

        # Impact indicator
        impact_colors = {'high': '#ff4444', 'medium': '#ffcc00', 'low': '#888888'}
        impact_label = QLabel(f"⚡ {self.impact.upper()}")
        impact_label.setStyleSheet(f"color: {impact_colors.get(self.impact, '#888')};")
        header_layout.addWidget(impact_label)

        header_layout.addStretch()

        # Time
        time_label = QLabel(time)
        time_label.setStyleSheet("color: #666; font-size: 11px;")
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # Headline
        headline_label = QLabel(headline)
        headline_label.setWordWrap(True)
        headline_label.setStyleSheet("color: #eee; font-size: 13px;")
        layout.addWidget(headline_label)

        # Source
        source_label = QLabel(f"Source: {source}")
        source_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(source_label)


class SentimentGauge(QFrame):
    """Overall market sentiment gauge"""

    def __init__(self):
        super().__init__()
        self.sentiment_score = 0.0  # -1 to 1
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(self)

        title = QLabel("MARKET SENTIMENT")
        title.setStyleSheet("color: #888; font-size: 12px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.sentiment_label = QLabel("NEUTRAL")
        self.sentiment_label.setStyleSheet("color: #ffcc00; font-size: 24px; font-weight: bold;")
        self.sentiment_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sentiment_label)

        # Sentiment bar
        bar_layout = QHBoxLayout()
        bar_layout.addWidget(QLabel("🐻"))

        self.sentiment_bar = QProgressBar()
        self.sentiment_bar.setRange(0, 100)
        self.sentiment_bar.setValue(50)
        self.sentiment_bar.setTextVisible(False)
        self.sentiment_bar.setStyleSheet("""
            QProgressBar {
                background-color: #ff4444;
                border: none;
                border-radius: 4px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #00ff41;
                border-radius: 4px;
            }
        """)
        bar_layout.addWidget(self.sentiment_bar)

        bar_layout.addWidget(QLabel("🐂"))
        layout.addLayout(bar_layout)

        self.score_label = QLabel("Score: 0.00")
        self.score_label.setStyleSheet("color: #666; font-size: 11px;")
        self.score_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.score_label)

    def set_sentiment(self, score):
        """Set sentiment score (-1 to 1)"""
        self.sentiment_score = max(-1, min(1, score))

        # Update bar (convert -1:1 to 0:100)
        bar_value = int((self.sentiment_score + 1) * 50)
        self.sentiment_bar.setValue(bar_value)

        # Update label
        if self.sentiment_score > 0.3:
            self.sentiment_label.setText("BULLISH")
            self.sentiment_label.setStyleSheet("color: #00ff41; font-size: 24px; font-weight: bold;")
        elif self.sentiment_score < -0.3:
            self.sentiment_label.setText("BEARISH")
            self.sentiment_label.setStyleSheet("color: #ff4444; font-size: 24px; font-weight: bold;")
        else:
            self.sentiment_label.setText("NEUTRAL")
            self.sentiment_label.setStyleSheet("color: #ffcc00; font-size: 24px; font-weight: bold;")

        self.score_label.setText(f"Score: {self.sentiment_score:.2f}")


class TradingImpactWidget(QFrame):
    """Shows how news sentiment affects trading"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(self)

        title = QLabel("TRADING IMPACT")
        title.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(title)

        self.impact_text = QTextEdit()
        self.impact_text.setReadOnly(True)
        self.impact_text.setStyleSheet("""
            background-color: #0f0f1a;
            border: 1px solid #3a3a5e;
            color: #00ff41;
            font-family: 'Hack', monospace;
        """)
        self.impact_text.setMaximumHeight(150)
        layout.addWidget(self.impact_text)

        self.update_impact(0, [])

    def update_impact(self, sentiment_score, recent_news):
        """Update the trading impact based on sentiment"""
        text = []
        text.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sentiment Analysis Update")
        text.append("-" * 40)

        if sentiment_score > 0.5:
            text.append("⚡ STRONG BULLISH SIGNAL")
            text.append("• Increasing position size by 20%")
            text.append("• Tightening stops on shorts")
            text.append("• Favoring long entries")
        elif sentiment_score > 0.2:
            text.append("📈 MODERATE BULLISH BIAS")
            text.append("• Normal position sizing")
            text.append("• Slight preference for longs")
        elif sentiment_score < -0.5:
            text.append("⚡ STRONG BEARISH SIGNAL")
            text.append("• Reducing position size by 20%")
            text.append("• Tightening stops on longs")
            text.append("• Favoring short entries")
        elif sentiment_score < -0.2:
            text.append("📉 MODERATE BEARISH BIAS")
            text.append("• Cautious position sizing")
            text.append("• Slight preference for shorts")
        else:
            text.append("➖ NEUTRAL CONDITIONS")
            text.append("• Standard position sizing")
            text.append("• Following technical signals")

        # High impact news override
        high_impact = [n for n in recent_news if n.get('impact') == 'high']
        if high_impact:
            text.append("")
            text.append("⚠️ HIGH IMPACT NEWS DETECTED")
            text.append("• Pausing new entries for 5 min")
            text.append("• Widening stops by 50%")

        self.impact_text.setText("\n".join(text))


class NewsFeedWidget(QWidget):
    """News feed with sentiment analysis"""

    sentiment_updated = pyqtSignal(float)  # Emits sentiment score

    def __init__(self):
        super().__init__()
        self.news_items = []
        self.sentiment_score = 0.0
        self.setup_ui()

        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.fetch_news)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # Left side - news feed
        left_panel = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("📰 FINANCIAL NEWS FEED")
        header_label.setStyleSheet("color: #00ff41; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        # Filter combo
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All News", "High Impact", "Bullish Only", "Bearish Only"])
        self.filter_combo.setStyleSheet("background-color: #0f0f1a; padding: 5px;")
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        header_layout.addWidget(self.filter_combo)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.fetch_news)
        header_layout.addWidget(refresh_btn)

        left_panel.addLayout(header_layout)

        # Scrollable news area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1a1a2e;
            }
        """)

        self.news_container = QWidget()
        self.news_layout = QVBoxLayout(self.news_container)
        self.news_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.news_container)

        left_panel.addWidget(scroll_area)
        layout.addLayout(left_panel, 2)

        # Right side - sentiment analysis
        right_panel = QVBoxLayout()

        self.sentiment_gauge = SentimentGauge()
        right_panel.addWidget(self.sentiment_gauge)

        self.impact_widget = TradingImpactWidget()
        right_panel.addWidget(self.impact_widget)

        # News sources status
        sources_group = QGroupBox("News Sources")
        sources_group.setStyleSheet("""
            QGroupBox {
                background-color: #16213e;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #888;
                subcontrol-origin: margin;
                left: 10px;
            }
        """)
        sources_layout = QVBoxLayout(sources_group)

        sources = [
            ("Reuters", True),
            ("Bloomberg", True),
            ("CNBC", True),
            ("MarketWatch", True),
            ("Forex Factory", True),
        ]
        for source, active in sources:
            status = "●" if active else "○"
            color = "#00ff41" if active else "#ff4444"
            label = QLabel(f"{status} {source}")
            label.setStyleSheet(f"color: {color};")
            sources_layout.addWidget(label)

        right_panel.addWidget(sources_group)
        right_panel.addStretch()

        layout.addLayout(right_panel, 1)

        # Load initial news
        self.fetch_news()

    def fetch_news(self):
        """Fetch news from various sources"""
        # In production, this would call real news APIs
        # For demo, generate sample news
        sample_news = [
            {
                "headline": "Fed signals potential rate pause amid cooling inflation data",
                "source": "Reuters",
                "sentiment": "bullish",
                "impact": "high",
                "score": 0.7
            },
            {
                "headline": "S&P 500 futures rise as tech earnings exceed expectations",
                "source": "Bloomberg",
                "sentiment": "bullish",
                "impact": "medium",
                "score": 0.5
            },
            {
                "headline": "Oil prices surge on Middle East supply concerns",
                "source": "CNBC",
                "sentiment": "neutral",
                "impact": "medium",
                "score": 0.1
            },
            {
                "headline": "Treasury yields climb on strong jobs data",
                "source": "MarketWatch",
                "sentiment": "bearish",
                "impact": "medium",
                "score": -0.3
            },
            {
                "headline": "China economic data shows manufacturing contraction",
                "source": "Reuters",
                "sentiment": "bearish",
                "impact": "high",
                "score": -0.6
            },
            {
                "headline": "Nvidia announces new AI chip, stock jumps premarket",
                "source": "Bloomberg",
                "sentiment": "bullish",
                "impact": "low",
                "score": 0.4
            },
            {
                "headline": "European markets mixed ahead of ECB decision",
                "source": "CNBC",
                "sentiment": "neutral",
                "impact": "low",
                "score": 0.0
            },
        ]

        # Add some randomization for demo
        random.shuffle(sample_news)
        self.news_items = sample_news[:5]

        self.display_news()
        self.calculate_sentiment()

    def display_news(self):
        """Display news items in the feed"""
        # Clear existing items
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add news items
        for i, news in enumerate(self.news_items):
            time_str = (datetime.now() - timedelta(minutes=i * 5)).strftime("%H:%M")
            news_widget = NewsItem(
                headline=news["headline"],
                source=news["source"],
                time=time_str,
                sentiment=news["sentiment"],
                impact=news["impact"]
            )
            self.news_layout.addWidget(news_widget)

    def calculate_sentiment(self):
        """Calculate overall sentiment score"""
        if not self.news_items:
            self.sentiment_score = 0.0
        else:
            # Weight by impact
            impact_weights = {'high': 2.0, 'medium': 1.0, 'low': 0.5}
            total_weight = 0
            weighted_score = 0

            for news in self.news_items:
                weight = impact_weights.get(news['impact'], 1.0)
                weighted_score += news['score'] * weight
                total_weight += weight

            self.sentiment_score = weighted_score / total_weight if total_weight > 0 else 0.0

        self.sentiment_gauge.set_sentiment(self.sentiment_score)
        self.impact_widget.update_impact(self.sentiment_score, self.news_items)
        self.sentiment_updated.emit(self.sentiment_score)

    def apply_filter(self, filter_text):
        """Apply filter to news display"""
        # This would filter the displayed news
        pass

    def update_feed(self):
        """Called periodically to update the feed"""
        # In production, this would check for new news
        pass

    def get_sentiment_score(self):
        """Get current sentiment score for trading decisions"""
        return self.sentiment_score

    def get_trading_adjustment(self):
        """Get trading parameters adjustment based on sentiment"""
        adjustments = {
            'position_size_multiplier': 1.0,
            'favor_direction': None,
            'pause_trading': False,
            'widen_stops': False
        }

        if self.sentiment_score > 0.5:
            adjustments['position_size_multiplier'] = 1.2
            adjustments['favor_direction'] = 'long'
        elif self.sentiment_score > 0.2:
            adjustments['favor_direction'] = 'long'
        elif self.sentiment_score < -0.5:
            adjustments['position_size_multiplier'] = 0.8
            adjustments['favor_direction'] = 'short'
        elif self.sentiment_score < -0.2:
            adjustments['favor_direction'] = 'short'

        # Check for high impact news
        high_impact = [n for n in self.news_items if n.get('impact') == 'high']
        if high_impact:
            adjustments['pause_trading'] = True
            adjustments['widen_stops'] = True

        return adjustments
