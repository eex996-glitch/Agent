#!/usr/bin/env python3
"""
News Feed Widget with Sentiment Analysis
Pulls financial news and analyzes sentiment to influence trading decisions
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGroupBox, QPushButton, QComboBox,
    QProgressBar, QTextEdit, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont
from datetime import datetime, timedelta


class NewsItem(QFrame):
    """Individual news item display"""

    def __init__(self, headline, source, time, sentiment, impact, score):
        super().__init__()
        self.sentiment = sentiment
        self.impact = impact
        self.score = score
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
                padding: 12px;
                margin: 5px;
            }}
            QFrame:hover {{
                background-color: #1a2a4e;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header with sentiment badge and impact
        header_layout = QHBoxLayout()

        # Sentiment badge
        sentiment_text = self.sentiment.upper()
        badge = QLabel(sentiment_text)
        badge.setStyleSheet(f"""
            background-color: {border_color};
            color: {'#000' if self.sentiment == 'bullish' else '#fff'};
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_layout.addWidget(badge)

        # Score indicator
        score_label = QLabel(f"Score: {self.score:+.2f}")
        score_color = "#00ff41" if self.score > 0 else "#ff4444" if self.score < 0 else "#888"
        score_label.setStyleSheet(f"color: {score_color}; font-size: 11px; font-weight: bold;")
        header_layout.addWidget(score_label)

        # Impact indicator
        impact_colors = {'high': '#ff4444', 'medium': '#ffcc00', 'low': '#888888'}
        impact_label = QLabel(f"Impact: {self.impact.upper()}")
        impact_label.setStyleSheet(f"color: {impact_colors.get(self.impact, '#888')}; font-size: 11px;")
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
        headline_label.setStyleSheet("color: #eee; font-size: 13px; line-height: 1.4;")
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
        title.setStyleSheet("color: #888; font-size: 12px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.sentiment_label = QLabel("NEUTRAL")
        self.sentiment_label.setStyleSheet("color: #ffcc00; font-size: 24px; font-weight: bold;")
        self.sentiment_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sentiment_label)

        # Sentiment bar
        bar_layout = QHBoxLayout()
        bear_label = QLabel("BEARISH")
        bear_label.setStyleSheet("color: #ff4444; font-size: 10px;")
        bar_layout.addWidget(bear_label)

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

        bull_label = QLabel("BULLISH")
        bull_label.setStyleSheet("color: #00ff41; font-size: 10px;")
        bar_layout.addWidget(bull_label)
        layout.addLayout(bar_layout)

        self.score_label = QLabel("Score: 0.00")
        self.score_label.setStyleSheet("color: #888; font-size: 12px;")
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

        self.score_label.setText(f"Score: {self.sentiment_score:+.2f}")


class TradingRecommendationWidget(QFrame):
    """Shows trading recommendations based on sentiment and model abilities"""

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

        title = QLabel("TRADING RECOMMENDATION")
        title.setStyleSheet("color: #00ccff; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        # Recommendation display
        self.recommendation_label = QLabel("HOLD")
        self.recommendation_label.setStyleSheet("color: #ffcc00; font-size: 28px; font-weight: bold;")
        self.recommendation_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.recommendation_label)

        self.confidence_label = QLabel("Confidence: --")
        self.confidence_label.setStyleSheet("color: #888; font-size: 12px;")
        self.confidence_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.confidence_label)

        # Reasoning section
        reason_label = QLabel("Reasoning:")
        reason_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 10px;")
        layout.addWidget(reason_label)

        self.reason_text = QTextEdit()
        self.reason_text.setReadOnly(True)
        self.reason_text.setMaximumHeight(80)
        self.reason_text.setStyleSheet("""
            QTextEdit {
                background-color: #0f0f1a;
                border: 1px solid #3a3a5e;
                color: #aaa;
                font-family: 'Hack', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.reason_text)

    def update_recommendation(self, sentiment_score, high_impact_news):
        """Update recommendation based on analysis"""
        reasons = []
        confidence = 50

        # Determine recommendation
        if high_impact_news:
            recommendation = "WAIT"
            color = "#ffcc00"
            reasons.append("High impact news detected - volatility expected")
            reasons.append("Recommend waiting for market to settle")
            confidence = 80
        elif sentiment_score > 0.5:
            recommendation = "FAVOR LONGS"
            color = "#00ff41"
            reasons.append(f"Strong bullish sentiment ({sentiment_score:+.2f})")
            reasons.append("Strategy: Look for long entry setups")
            reasons.append("Consider increasing position size by 20%")
            confidence = 75
        elif sentiment_score > 0.2:
            recommendation = "SLIGHT BULLISH"
            color = "#00ff41"
            reasons.append(f"Moderate bullish sentiment ({sentiment_score:+.2f})")
            reasons.append("Strategy: Normal trading with long bias")
            confidence = 60
        elif sentiment_score < -0.5:
            recommendation = "FAVOR SHORTS"
            color = "#ff4444"
            reasons.append(f"Strong bearish sentiment ({sentiment_score:+.2f})")
            reasons.append("Strategy: Look for short entry setups")
            reasons.append("Consider tightening stops on longs")
            confidence = 75
        elif sentiment_score < -0.2:
            recommendation = "SLIGHT BEARISH"
            color = "#ff4444"
            reasons.append(f"Moderate bearish sentiment ({sentiment_score:+.2f})")
            reasons.append("Strategy: Normal trading with short bias")
            confidence = 60
        else:
            recommendation = "NEUTRAL"
            color = "#ffcc00"
            reasons.append("Mixed/neutral sentiment detected")
            reasons.append("Strategy: Follow technical signals only")
            reasons.append("No directional bias recommended")
            confidence = 50

        self.recommendation_label.setText(recommendation)
        self.recommendation_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        self.confidence_label.setText(f"Confidence: {confidence}%")
        self.reason_text.setText("\n".join(f"• {r}" for r in reasons))


class SentimentFactorsWidget(QFrame):
    """Shows what factors are affecting sentiment"""

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

        title = QLabel("SENTIMENT FACTORS")
        title.setStyleSheet("color: #ffcc00; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        # Factor grid
        self.factors_layout = QGridLayout()
        layout.addLayout(self.factors_layout)

        # Initialize factor labels
        self.factor_labels = {}
        factors = [
            ("Fed Policy", 0, 0),
            ("Earnings", 0, 1),
            ("Economic Data", 1, 0),
            ("Geopolitical", 1, 1),
            ("Technical", 2, 0),
            ("Volume/Flow", 2, 1),
        ]

        for name, row, col in factors:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background-color: #0f0f1a;
                    border: 1px solid #3a3a5e;
                    border-radius: 4px;
                    padding: 5px;
                }
            """)
            f_layout = QVBoxLayout(frame)
            f_layout.setSpacing(2)
            f_layout.setContentsMargins(5, 5, 5, 5)

            name_label = QLabel(name)
            name_label.setStyleSheet("color: #888; font-size: 10px;")
            f_layout.addWidget(name_label)

            value_label = QLabel("--")
            value_label.setStyleSheet("color: #ffcc00; font-size: 12px; font-weight: bold;")
            f_layout.addWidget(value_label)

            self.factor_labels[name] = value_label
            self.factors_layout.addWidget(frame, row, col)

    def update_factors(self, news_items):
        """Update factors based on actual news content analysis"""
        # Keyword-based factor extraction from news headlines
        factor_keywords = {
            "Fed Policy": {
                "bullish": ["rate pause", "rate cut", "dovish", "easing"],
                "bearish": ["rate hike", "hawkish", "tightening", "inflation"],
            },
            "Earnings": {
                "bullish": ["earnings exceed", "beat expectations", "revenue growth", "stock jumps"],
                "bearish": ["earnings miss", "revenue decline", "profit warning", "stock falls"],
            },
            "Economic Data": {
                "bullish": ["jobs growth", "gdp growth", "consumer confidence"],
                "bearish": ["contraction", "unemployment", "recession", "slowdown"],
            },
            "Geopolitical": {
                "risk_on": ["trade deal", "peace", "stability"],
                "risk_off": ["supply concerns", "tensions", "conflict", "sanctions"],
            },
            "Technical": {
                "bullish": ["rise", "gains", "rally", "surge", "climb"],
                "bearish": ["fall", "decline", "drop", "plunge", "sell-off"],
            },
            "Volume/Flow": {
                "buying": ["buying", "inflow", "demand", "accumulation"],
                "selling": ["selling", "outflow", "liquidation"],
            },
        }

        # Scan all headlines for keyword matches
        all_text = " ".join(n.get("headline", "").lower() for n in news_items)

        factors = {}
        for factor_name, keywords in factor_keywords.items():
            score = 0
            for category, words in keywords.items():
                for word in words:
                    if word in all_text:
                        if category in ("bullish", "risk_on", "buying"):
                            score += 1
                        else:
                            score -= 1

            if factor_name == "Geopolitical":
                if score > 0:
                    factors[factor_name] = "Risk-On"
                elif score < 0:
                    factors[factor_name] = "Risk-Off"
                else:
                    factors[factor_name] = "Neutral"
            elif factor_name == "Volume/Flow":
                if score > 0:
                    factors[factor_name] = "Buying"
                elif score < 0:
                    factors[factor_name] = "Selling"
                else:
                    factors[factor_name] = "Mixed"
            else:
                if score > 0:
                    factors[factor_name] = "Bullish"
                elif score < 0:
                    factors[factor_name] = "Bearish"
                else:
                    factors[factor_name] = "Neutral"

        colors = {
            "Bullish": "#00ff41",
            "Bearish": "#ff4444",
            "Neutral": "#ffcc00",
            "Risk-On": "#00ff41",
            "Risk-Off": "#ff4444",
            "Buying": "#00ff41",
            "Selling": "#ff4444",
            "Mixed": "#ffcc00",
        }

        for name, value in factors.items():
            if name in self.factor_labels:
                self.factor_labels[name].setText(value)
                color = colors.get(value, "#888")
                self.factor_labels[name].setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")


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
        header_label = QLabel("FINANCIAL NEWS FEED")
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
        refresh_btn = QPushButton("Refresh")
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

        self.recommendation_widget = TradingRecommendationWidget()
        right_panel.addWidget(self.recommendation_widget)

        self.factors_widget = SentimentFactorsWidget()
        right_panel.addWidget(self.factors_widget)

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
                "headline": "Fed signals potential rate pause amid cooling inflation data, markets respond positively",
                "source": "Reuters",
                "sentiment": "bullish",
                "impact": "high",
                "score": 0.7
            },
            {
                "headline": "S&P 500 futures rise as tech earnings exceed Wall Street expectations",
                "source": "Bloomberg",
                "sentiment": "bullish",
                "impact": "medium",
                "score": 0.5
            },
            {
                "headline": "Oil prices surge on Middle East supply concerns, energy sector leads gains",
                "source": "CNBC",
                "sentiment": "neutral",
                "impact": "medium",
                "score": 0.1
            },
            {
                "headline": "Treasury yields climb on stronger than expected jobs data, rate cut odds decline",
                "source": "MarketWatch",
                "sentiment": "bearish",
                "impact": "medium",
                "score": -0.3
            },
            {
                "headline": "China economic data shows manufacturing contraction, global growth concerns rise",
                "source": "Reuters",
                "sentiment": "bearish",
                "impact": "high",
                "score": -0.6
            },
            {
                "headline": "Nvidia announces breakthrough AI chip architecture, stock jumps in premarket trading",
                "source": "Bloomberg",
                "sentiment": "bullish",
                "impact": "low",
                "score": 0.4
            },
            {
                "headline": "European markets trade mixed ahead of key ECB policy decision tomorrow",
                "source": "CNBC",
                "sentiment": "neutral",
                "impact": "low",
                "score": 0.0
            },
        ]

        # Display all sample news items (in production, API would provide fresh data)
        self.news_items = sample_news

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
                impact=news["impact"],
                score=news["score"]
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

        # Check for high impact news
        high_impact = [n for n in self.news_items if n.get('impact') == 'high']
        self.recommendation_widget.update_recommendation(self.sentiment_score, len(high_impact) > 0)
        self.factors_widget.update_factors(self.news_items)

        self.sentiment_updated.emit(self.sentiment_score)

    def apply_filter(self, filter_text):
        """Apply filter to news display"""
        filter_lower = filter_text.lower()

        for i in range(self.news_layout.count()):
            widget = self.news_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'sentiment'):
                if filter_lower == "all news":
                    widget.show()
                elif filter_lower == "high impact":
                    widget.setVisible(widget.impact == "high")
                elif filter_lower == "bullish only":
                    widget.setVisible(widget.sentiment == "bullish")
                elif filter_lower == "bearish only":
                    widget.setVisible(widget.sentiment == "bearish")

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
