#!/usr/bin/env python3
"""
Sentiment Analysis Module
Analyzes news sentiment and adjusts trading parameters
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradingAdjustment:
    """Trading parameter adjustments based on sentiment"""
    position_size_multiplier: float = 1.0  # 0.5 to 1.5
    favor_direction: Optional[str] = None  # 'long', 'short', or None
    pause_new_entries: bool = False
    widen_stops_pct: float = 0.0  # Additional stop widening percentage
    confidence_modifier: float = 0.0  # -0.3 to 0.3
    reason: str = ""

    def to_dict(self) -> Dict:
        return {
            'position_size_multiplier': self.position_size_multiplier,
            'favor_direction': self.favor_direction,
            'pause_new_entries': self.pause_new_entries,
            'widen_stops_pct': self.widen_stops_pct,
            'confidence_modifier': self.confidence_modifier,
            'reason': self.reason
        }


class SentimentAnalyzer:
    """
    Analyzes text sentiment for financial news

    Uses a combination of:
    - Keyword matching with financial lexicon
    - Pattern recognition for market-moving phrases
    - Impact weighting based on source and timing
    """

    def __init__(self):
        # Bullish keywords and phrases
        self.bullish_terms = {
            # Strong bullish
            'surge': 0.8, 'soar': 0.8, 'rally': 0.7, 'boom': 0.8,
            'skyrocket': 0.9, 'breakout': 0.6, 'bullish': 0.7,

            # Moderate bullish
            'rise': 0.4, 'gain': 0.4, 'climb': 0.4, 'advance': 0.4,
            'up': 0.3, 'higher': 0.3, 'positive': 0.4, 'growth': 0.5,
            'strong': 0.4, 'beat': 0.5, 'exceed': 0.5, 'outperform': 0.5,

            # Economic bullish
            'rate cut': 0.6, 'dovish': 0.6, 'stimulus': 0.7,
            'recovery': 0.5, 'expansion': 0.5, 'hiring': 0.4,
        }

        # Bearish keywords and phrases
        self.bearish_terms = {
            # Strong bearish
            'crash': -0.9, 'plunge': -0.8, 'collapse': -0.9, 'tumble': -0.7,
            'plummet': -0.8, 'bearish': -0.7, 'crisis': -0.8,

            # Moderate bearish
            'fall': -0.4, 'drop': -0.4, 'decline': -0.4, 'slip': -0.3,
            'down': -0.3, 'lower': -0.3, 'negative': -0.4, 'weak': -0.4,
            'miss': -0.5, 'disappoint': -0.5, 'underperform': -0.5,

            # Economic bearish
            'rate hike': -0.5, 'hawkish': -0.5, 'inflation': -0.4,
            'recession': -0.7, 'contraction': -0.5, 'layoff': -0.5,
            'unemployment': -0.4, 'tariff': -0.4, 'war': -0.6,
        }

        # Neutral/uncertainty terms that reduce confidence
        self.uncertainty_terms = [
            'uncertain', 'volatile', 'mixed', 'flat', 'unchanged',
            'steady', 'sideways', 'consolidate', 'wait', 'unclear'
        ]

        # High-impact event patterns
        self.high_impact_patterns = [
            r'fed\s+(cut|raise|hold|pause)',
            r'fomc\s+(decision|meeting|statement)',
            r'(cpi|inflation)\s+(data|report|number)',
            r'jobs?\s+report',
            r'gdp\s+(growth|data|report)',
            r'earnings?\s+(beat|miss|surprise)',
            r'breaking:',
            r'alert:',
        ]

    def analyze(self, text: str) -> Tuple[float, str, float]:
        """
        Analyze sentiment of text

        Returns:
            Tuple of (score, sentiment_label, confidence)
            - score: -1.0 to 1.0
            - sentiment_label: 'bullish', 'bearish', or 'neutral'
            - confidence: 0.0 to 1.0
        """
        if not text:
            return 0.0, 'neutral', 0.0

        text_lower = text.lower()
        total_score = 0.0
        matches = 0
        confidence = 0.5  # Base confidence

        # Check bullish terms
        for term, weight in self.bullish_terms.items():
            if term in text_lower:
                total_score += weight
                matches += 1

        # Check bearish terms
        for term, weight in self.bearish_terms.items():
            if term in text_lower:
                total_score += weight  # weight is already negative
                matches += 1

        # Check uncertainty terms (reduce confidence)
        for term in self.uncertainty_terms:
            if term in text_lower:
                confidence -= 0.1

        # Check for high-impact patterns (increase confidence)
        for pattern in self.high_impact_patterns:
            if re.search(pattern, text_lower):
                confidence += 0.2
                break

        # Normalize score
        if matches > 0:
            score = max(-1.0, min(1.0, total_score / max(matches, 1)))
            confidence = max(0.1, min(1.0, confidence + (matches * 0.05)))
        else:
            score = 0.0
            confidence = 0.3

        # Determine sentiment label
        if score > 0.2:
            sentiment = 'bullish'
        elif score < -0.2:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        return score, sentiment, confidence

    def analyze_batch(self, texts: List[str]) -> Tuple[float, str, float]:
        """
        Analyze sentiment of multiple texts

        Returns weighted average sentiment
        """
        if not texts:
            return 0.0, 'neutral', 0.0

        scores = []
        confidences = []

        for text in texts:
            score, _, conf = self.analyze(text)
            scores.append(score)
            confidences.append(conf)

        # Weight by confidence
        total_weight = sum(confidences)
        if total_weight > 0:
            avg_score = sum(s * c for s, c in zip(scores, confidences)) / total_weight
            avg_confidence = sum(confidences) / len(confidences)
        else:
            avg_score = 0.0
            avg_confidence = 0.0

        # Determine sentiment
        if avg_score > 0.2:
            sentiment = 'bullish'
        elif avg_score < -0.2:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        return avg_score, sentiment, avg_confidence


class TradingAdjuster:
    """
    Adjusts trading parameters based on news sentiment

    This integrates with the trading strategy to modify:
    - Position sizing
    - Entry direction preference
    - Stop loss distances
    - Trade confidence levels
    """

    def __init__(self, analyzer: Optional[SentimentAnalyzer] = None):
        self.analyzer = analyzer or SentimentAnalyzer()
        self.current_sentiment = 0.0
        self.sentiment_history: List[Tuple[datetime, float]] = []
        self.high_impact_cooldown = timedelta(minutes=5)
        self.last_high_impact: Optional[datetime] = None

    def process_news(self, headlines: List[str], impacts: List[str] = None) -> TradingAdjustment:
        """
        Process news headlines and return trading adjustments

        Args:
            headlines: List of news headlines
            impacts: List of impact levels ('low', 'medium', 'high')

        Returns:
            TradingAdjustment with recommended parameter changes
        """
        if not headlines:
            return TradingAdjustment(reason="No news to process")

        # Analyze sentiment
        score, sentiment, confidence = self.analyzer.analyze_batch(headlines)

        # Update history
        self.current_sentiment = score
        self.sentiment_history.append((datetime.now(), score))

        # Keep last 100 entries
        if len(self.sentiment_history) > 100:
            self.sentiment_history = self.sentiment_history[-100:]

        # Create adjustment
        adjustment = TradingAdjustment()
        reasons = []

        # Check for high impact news
        if impacts:
            high_impact_count = sum(1 for i in impacts if i == 'high')
            if high_impact_count > 0:
                self.last_high_impact = datetime.now()
                adjustment.pause_new_entries = True
                adjustment.widen_stops_pct = 50.0
                reasons.append(f"{high_impact_count} high-impact news items detected")

        # Check if still in high-impact cooldown
        if self.last_high_impact:
            if datetime.now() - self.last_high_impact < self.high_impact_cooldown:
                adjustment.pause_new_entries = True
                reasons.append("High-impact news cooldown active")

        # Adjust based on sentiment strength
        if score > 0.5:
            adjustment.position_size_multiplier = 1.2
            adjustment.favor_direction = 'long'
            adjustment.confidence_modifier = 0.15
            reasons.append(f"Strong bullish sentiment ({score:.2f})")

        elif score > 0.2:
            adjustment.favor_direction = 'long'
            adjustment.confidence_modifier = 0.05
            reasons.append(f"Moderate bullish sentiment ({score:.2f})")

        elif score < -0.5:
            adjustment.position_size_multiplier = 0.8
            adjustment.favor_direction = 'short'
            adjustment.confidence_modifier = -0.1
            reasons.append(f"Strong bearish sentiment ({score:.2f})")

        elif score < -0.2:
            adjustment.favor_direction = 'short'
            adjustment.confidence_modifier = -0.05
            reasons.append(f"Moderate bearish sentiment ({score:.2f})")

        else:
            reasons.append(f"Neutral sentiment ({score:.2f})")

        # Check for sentiment shift (momentum)
        if len(self.sentiment_history) >= 5:
            recent = [s for _, s in self.sentiment_history[-5:]]
            older = [s for _, s in self.sentiment_history[-10:-5]] if len(self.sentiment_history) >= 10 else [0]

            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            shift = recent_avg - older_avg

            if abs(shift) > 0.3:
                if shift > 0:
                    reasons.append("Sentiment shifting bullish")
                    adjustment.confidence_modifier += 0.05
                else:
                    reasons.append("Sentiment shifting bearish")
                    adjustment.confidence_modifier -= 0.05

        adjustment.reason = "; ".join(reasons)
        return adjustment

    def should_take_trade(self, signal_direction: str, adjustment: TradingAdjustment) -> Tuple[bool, str]:
        """
        Determine if a trade should be taken based on sentiment

        Args:
            signal_direction: 'long' or 'short'
            adjustment: Current trading adjustment

        Returns:
            Tuple of (should_trade, reason)
        """
        # Don't trade during high-impact news
        if adjustment.pause_new_entries:
            return False, "Paused due to high-impact news"

        # Check if direction is favored
        if adjustment.favor_direction:
            if adjustment.favor_direction != signal_direction:
                # Allow but with reduced size (handled by multiplier)
                return True, f"Counter-sentiment trade ({signal_direction} vs {adjustment.favor_direction} sentiment)"

        return True, "Trade allowed by sentiment filter"

    def get_position_size_multiplier(self, base_size: float, adjustment: TradingAdjustment) -> float:
        """Get adjusted position size"""
        return base_size * adjustment.position_size_multiplier

    def get_stop_distance_multiplier(self, adjustment: TradingAdjustment) -> float:
        """Get stop distance multiplier"""
        return 1.0 + (adjustment.widen_stops_pct / 100.0)

    def get_sentiment_summary(self) -> Dict:
        """Get current sentiment summary"""
        return {
            'current_score': self.current_sentiment,
            'sentiment': 'bullish' if self.current_sentiment > 0.2 else 'bearish' if self.current_sentiment < -0.2 else 'neutral',
            'history_length': len(self.sentiment_history),
            'in_cooldown': self.last_high_impact is not None and datetime.now() - self.last_high_impact < self.high_impact_cooldown
        }
