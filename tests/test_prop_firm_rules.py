"""
Tests for MFFU Prop Firm Rules
"""

import pytest
from config.prop_firm_rules import (
    get_mffu_rules,
    get_mffu_funded_rules,
    MFFURules,
    AccountTier
)


class TestMFFURules:
    """Tests for MFFU evaluation rules"""

    def test_starter_tier_defaults(self, mffu_rules):
        """Test Starter tier has correct default values"""
        assert mffu_rules.account_size == 50000.0
        assert mffu_rules.profit_target == 3000.0
        assert mffu_rules.max_loss_limit == 2000.0
        assert mffu_rules.max_contracts == 5
        assert mffu_rules.has_daily_loss_limit is False
        assert mffu_rules.has_consistency_rule is False

    def test_standard_tier(self):
        """Test Standard tier configuration"""
        rules = get_mffu_rules('Standard')
        assert rules.account_size == 100000.0
        assert rules.profit_target == 6000.0
        assert rules.max_loss_limit == 3500.0
        assert rules.max_contracts == 10

    def test_premium_tier(self):
        """Test Premium tier configuration"""
        rules = get_mffu_rules('Premium')
        assert rules.account_size == 150000.0
        assert rules.profit_target == 9000.0
        assert rules.max_loss_limit == 5000.0
        assert rules.max_contracts == 15

    def test_tier_aliases(self):
        """Test that 50K/100K/150K aliases work"""
        starter = get_mffu_rules('50K')
        standard = get_mffu_rules('100K')
        premium = get_mffu_rules('150K')

        assert starter.tier == AccountTier.STARTER
        assert standard.tier == AccountTier.STANDARD
        assert premium.tier == AccountTier.PREMIUM

    def test_case_insensitive_tier(self):
        """Test tier names are case insensitive"""
        lower = get_mffu_rules('starter')
        upper = get_mffu_rules('STARTER')
        mixed = get_mffu_rules('Starter')

        assert lower.tier == upper.tier == mixed.tier

    def test_scaling_plan_starter(self, mffu_rules):
        """Test scaling plan for Starter tier"""
        assert len(mffu_rules.scaling_plan) == 4

        # At $0 profit, max 2 contracts
        assert mffu_rules.get_max_contracts_for_profit(0) == 2

        # At $1000 profit, max 3 contracts
        assert mffu_rules.get_max_contracts_for_profit(1000) == 3

        # At $1500 profit, max 4 contracts
        assert mffu_rules.get_max_contracts_for_profit(1500) == 4

        # At $2000+ profit, max 5 contracts
        assert mffu_rules.get_max_contracts_for_profit(2000) == 5
        assert mffu_rules.get_max_contracts_for_profit(3000) == 5

    def test_drawdown_not_breached(self, mffu_rules):
        """Test drawdown check when not breached"""
        starting = 50000
        hwm = 51000
        current = 49500

        breached = mffu_rules.check_max_loss_breach(hwm, current, starting)
        assert breached is False

    def test_drawdown_breached(self, mffu_rules):
        """Test drawdown check when breached"""
        starting = 50000
        hwm = 51000
        current = 48000  # Below floor of $49000 (hwm - $2000)

        breached = mffu_rules.check_max_loss_breach(hwm, current, starting)
        assert breached is True

    def test_available_risk_calculation(self, mffu_rules):
        """Test available risk calculation"""
        starting = 50000
        hwm = 51000
        current = 50000

        available = mffu_rules.get_available_risk(hwm, current, starting)
        # Floor is $49000 (hwm - $2000), so available is $1000
        assert available == 1000.0

    def test_drawdown_floor(self, mffu_rules):
        """Test drawdown floor calculation"""
        starting = 50000
        hwm = 52000

        floor = mffu_rules.get_drawdown_floor(hwm, starting)
        # Floor is max(50000-2000, 52000-2000) = max(48000, 50000) = 50000
        assert floor == 50000.0

    def test_progress_to_target(self, mffu_rules):
        """Test progress percentage calculation"""
        assert mffu_rules.get_progress_to_target(0) == 0.0
        assert mffu_rules.get_progress_to_target(1500) == 50.0
        assert mffu_rules.get_progress_to_target(3000) == 100.0
        assert mffu_rules.get_progress_to_target(6000) == 200.0

    def test_payout_calculation(self, mffu_rules):
        """Test profit split calculation"""
        trader, firm = mffu_rules.calculate_payout(1000)
        assert trader == 800.0  # 80%
        assert firm == 200.0   # 20%

    def test_no_daily_loss_limit(self, mffu_rules):
        """Test MFFU has no daily loss limit"""
        assert mffu_rules.has_daily_loss_limit is False
        assert mffu_rules.daily_loss_limit == 0.0

    def test_no_consistency_rule(self, mffu_rules):
        """Test MFFU has no consistency rule"""
        assert mffu_rules.has_consistency_rule is False
        assert mffu_rules.consistency_threshold == 1.0  # 100% = no limit


class TestMFFUFundedRules:
    """Tests for MFFU funded account rules"""

    def test_funded_starter(self):
        """Test funded account for Starter tier"""
        rules = get_mffu_funded_rules('Starter')
        assert rules.starting_balance == 0.0
        assert rules.max_loss_limit == 2000.0
        assert rules.profit_split_trader == 0.80
        assert rules.can_upgrade_split is True
        assert rules.upgraded_split == 0.90

    def test_funded_standard(self):
        """Test funded account for Standard tier"""
        rules = get_mffu_funded_rules('Standard')
        assert rules.max_loss_limit == 3500.0
        assert rules.max_contracts == 10

    def test_funded_premium(self):
        """Test funded account for Premium tier"""
        rules = get_mffu_funded_rules('Premium')
        assert rules.max_loss_limit == 5000.0
        assert rules.max_contracts == 15
