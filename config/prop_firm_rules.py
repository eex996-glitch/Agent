"""
Prop Firm Rules Configuration

This module defines the specific rules for MyFundedFutures (MFFU).
MFFU is a futures prop firm offering evaluation accounts with EOD trailing drawdown.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum


class AccountTier(Enum):
    """MyFundedFutures account tiers"""
    STARTER = "Starter"      # $50K
    STANDARD = "Standard"    # $100K
    PREMIUM = "Premium"      # $150K


@dataclass
class ScalingLevel:
    """Position scaling based on account profit"""
    min_profit: float
    max_contracts: int


@dataclass
class MFFURules:
    """
    MyFundedFutures (MFFU) Evaluation Rules

    Key Features:
    1. EOD Trailing Drawdown - Trails at end of day only
    2. NO Daily Loss Limit - Trade without daily caps
    3. NO Consistency Rule - No restrictions on profit distribution
    4. No Time Limit - Take as long as needed to pass
    5. Scaling Plan - Position sizes based on profit
    6. 80/20 Profit Split (upgradeable to 90/10)

    Website: https://myfundedfutures.com
    """

    # Account tier
    tier: AccountTier = AccountTier.STARTER

    # Account size (simulated balance)
    account_size: float = 50000.0

    # Profit target to pass evaluation
    profit_target: float = 3000.0

    # Maximum loss limit (EOD trailing drawdown)
    max_loss_limit: float = 2000.0

    # MFFU has NO daily loss limit
    daily_loss_limit: float = 0.0
    has_daily_loss_limit: bool = False

    # MFFU has NO consistency rule
    has_consistency_rule: bool = False
    consistency_threshold: float = 1.0  # 100% - no restriction

    # Maximum contracts allowed
    max_contracts: int = 5

    # Scaling plan levels
    scaling_plan: List[ScalingLevel] = field(default_factory=list)

    # Trading hours (CT timezone) - Sunday 5PM to Friday 4PM
    trading_start_hour: int = 17  # 5 PM CT Sunday
    trading_end_hour: int = 16    # 4 PM CT Friday

    # Position must be flat by this time (before daily close)
    flat_by_hour: int = 15
    flat_by_minute: int = 55  # 3:55 PM CT

    # Minimum trading days (MFFU has no minimum)
    min_trading_days: int = 1

    # Profit split
    profit_split_trader: float = 0.80  # 80% to trader
    profit_split_firm: float = 0.20    # 20% to firm

    # Payout rules
    min_payout_amount: float = 500.0
    payout_frequency: str = "weekly"  # Can request weekly

    # Evaluation fee (monthly)
    monthly_fee: float = 150.0

    def __post_init__(self):
        """Initialize tier-specific rules"""
        self._set_tier_rules()
        self._set_scaling_plan()

    def _set_tier_rules(self):
        """Set rules based on account tier"""
        tier_configs = {
            AccountTier.STARTER: {
                "account_size": 50000.0,
                "profit_target": 3000.0,
                "max_loss_limit": 2000.0,
                "max_contracts": 5,
                "monthly_fee": 150.0
            },
            AccountTier.STANDARD: {
                "account_size": 100000.0,
                "profit_target": 6000.0,
                "max_loss_limit": 3500.0,
                "max_contracts": 10,
                "monthly_fee": 250.0
            },
            AccountTier.PREMIUM: {
                "account_size": 150000.0,
                "profit_target": 9000.0,
                "max_loss_limit": 5000.0,
                "max_contracts": 15,
                "monthly_fee": 350.0
            }
        }

        config = tier_configs.get(self.tier, tier_configs[AccountTier.STARTER])
        self.account_size = config["account_size"]
        self.profit_target = config["profit_target"]
        self.max_loss_limit = config["max_loss_limit"]
        self.max_contracts = config["max_contracts"]
        self.monthly_fee = config["monthly_fee"]

    def _set_scaling_plan(self):
        """Set scaling plan based on tier - MFFU scaling"""
        scaling_configs = {
            AccountTier.STARTER: [
                ScalingLevel(0, 2),       # Start with 2 contracts
                ScalingLevel(1000, 3),    # +$1000 = 3 contracts
                ScalingLevel(1500, 4),    # +$1500 = 4 contracts
                ScalingLevel(2000, 5),    # +$2000 = 5 contracts (max)
            ],
            AccountTier.STANDARD: [
                ScalingLevel(0, 3),       # Start with 3 contracts
                ScalingLevel(1500, 5),    # +$1500 = 5 contracts
                ScalingLevel(3000, 7),    # +$3000 = 7 contracts
                ScalingLevel(4500, 10),   # +$4500 = 10 contracts (max)
            ],
            AccountTier.PREMIUM: [
                ScalingLevel(0, 5),       # Start with 5 contracts
                ScalingLevel(2000, 8),    # +$2000 = 8 contracts
                ScalingLevel(4000, 12),   # +$4000 = 12 contracts
                ScalingLevel(6000, 15),   # +$6000 = 15 contracts (max)
            ]
        }

        self.scaling_plan = scaling_configs.get(
            self.tier,
            scaling_configs[AccountTier.STARTER]
        )

    def get_max_contracts_for_profit(self, profit: float) -> int:
        """
        Get maximum allowed contracts based on current profit

        Args:
            profit: Current cumulative profit in account

        Returns:
            Maximum number of contracts allowed
        """
        max_contracts = self.scaling_plan[0].max_contracts

        for level in self.scaling_plan:
            if profit >= level.min_profit:
                max_contracts = level.max_contracts

        return min(max_contracts, self.max_contracts)

    def check_max_loss_breach(
        self,
        high_water_mark: float,
        current_balance: float,
        starting_balance: float
    ) -> bool:
        """
        Check if maximum loss limit has been breached

        MFFU uses END OF DAY trailing drawdown:
        - Drawdown only trails at the END of each trading day
        - Intraday profits don't move the drawdown level
        - This is more forgiving than real-time trailing

        Args:
            high_water_mark: Highest end-of-day balance achieved
            current_balance: Current account balance
            starting_balance: Initial account balance

        Returns:
            True if max loss limit has been breached
        """
        # Floor = highest EOD balance - max loss limit
        # Cannot go below starting balance - max loss limit initially

        absolute_floor = starting_balance - self.max_loss_limit
        trailing_floor = high_water_mark - self.max_loss_limit

        # The effective floor is the higher of the two
        effective_floor = max(absolute_floor, trailing_floor)

        return current_balance <= effective_floor

    def get_available_risk(
        self,
        high_water_mark: float,
        current_balance: float,
        starting_balance: float
    ) -> float:
        """
        Calculate available risk before hitting drawdown limit

        Args:
            high_water_mark: Highest end-of-day balance
            current_balance: Current balance
            starting_balance: Starting balance

        Returns:
            Dollar amount of risk available
        """
        absolute_floor = starting_balance - self.max_loss_limit
        trailing_floor = high_water_mark - self.max_loss_limit
        effective_floor = max(absolute_floor, trailing_floor)

        return max(0, current_balance - effective_floor)

    def get_drawdown_floor(
        self,
        high_water_mark: float,
        starting_balance: float
    ) -> float:
        """
        Get the current drawdown floor (minimum allowed balance)

        Args:
            high_water_mark: Highest EOD balance
            starting_balance: Starting balance

        Returns:
            The minimum allowed balance before breach
        """
        absolute_floor = starting_balance - self.max_loss_limit
        trailing_floor = high_water_mark - self.max_loss_limit
        return max(absolute_floor, trailing_floor)

    def calculate_payout(self, profit: float) -> Tuple[float, float]:
        """
        Calculate payout split

        Args:
            profit: Total profit to split

        Returns:
            Tuple of (trader_amount, firm_amount)
        """
        trader_amount = profit * self.profit_split_trader
        firm_amount = profit * self.profit_split_firm
        return (trader_amount, firm_amount)

    def get_progress_to_target(self, current_profit: float) -> float:
        """
        Get progress percentage toward profit target

        Args:
            current_profit: Current cumulative profit

        Returns:
            Percentage progress (0-100+)
        """
        return (current_profit / self.profit_target) * 100


@dataclass
class MFFUFundedRules:
    """
    MyFundedFutures Funded Account Rules

    After passing evaluation, these rules apply to the funded account.
    """

    tier: AccountTier = AccountTier.STARTER

    # Funded accounts start at $0 balance
    starting_balance: float = 0.0

    # Maximum loss limit (same as evaluation)
    max_loss_limit: float = 2000.0

    # No consistency requirements
    has_consistency_rule: bool = False

    # Profit split (can be upgraded)
    profit_split_trader: float = 0.80
    can_upgrade_split: bool = True
    upgraded_split: float = 0.90  # After meeting requirements

    # Payout requirements
    min_payout_amount: float = 500.0
    max_payout_percentage: float = 1.0  # 100% of profits available

    # Scaling (same as evaluation)
    max_contracts: int = 5

    def __post_init__(self):
        """Set tier-specific funded rules"""
        limits = {
            AccountTier.STARTER: {"max_loss": 2000.0, "max_contracts": 5},
            AccountTier.STANDARD: {"max_loss": 3500.0, "max_contracts": 10},
            AccountTier.PREMIUM: {"max_loss": 5000.0, "max_contracts": 15}
        }
        config = limits.get(self.tier, limits[AccountTier.STARTER])
        self.max_loss_limit = config["max_loss"]
        self.max_contracts = config["max_contracts"]


# Factory functions
def get_mffu_rules(tier: str = "Starter") -> MFFURules:
    """
    Get MyFundedFutures evaluation rules for a specific tier

    Args:
        tier: Account tier (Starter, Standard, Premium) or (50K, 100K, 150K)

    Returns:
        MFFURules instance
    """
    # Support both naming conventions
    tier_map = {
        "starter": AccountTier.STARTER,
        "standard": AccountTier.STANDARD,
        "premium": AccountTier.PREMIUM,
        "50k": AccountTier.STARTER,
        "100k": AccountTier.STANDARD,
        "150k": AccountTier.PREMIUM
    }

    account_tier = tier_map.get(tier.lower(), AccountTier.STARTER)
    return MFFURules(tier=account_tier)


def get_mffu_funded_rules(tier: str = "Starter") -> MFFUFundedRules:
    """
    Get MyFundedFutures funded account rules

    Args:
        tier: Account tier

    Returns:
        MFFUFundedRules instance
    """
    tier_map = {
        "starter": AccountTier.STARTER,
        "standard": AccountTier.STANDARD,
        "premium": AccountTier.PREMIUM,
        "50k": AccountTier.STARTER,
        "100k": AccountTier.STANDARD,
        "150k": AccountTier.PREMIUM
    }

    account_tier = tier_map.get(tier.lower(), AccountTier.STARTER)
    return MFFUFundedRules(tier=account_tier)


# Example usage and testing
if __name__ == "__main__":
    print("=" * 60)
    print("       MyFundedFutures (MFFU) Evaluation Rules")
    print("=" * 60)

    for tier_name in ["Starter", "Standard", "Premium"]:
        rules = get_mffu_rules(tier_name)

        print(f"\n{'='*60}")
        print(f"  {tier_name.upper()} ACCOUNT (${rules.account_size:,.0f})")
        print(f"{'='*60}")
        print(f"  Profit Target:     ${rules.profit_target:,.0f}")
        print(f"  Max Loss Limit:    ${rules.max_loss_limit:,.0f} (EOD trailing)")
        print(f"  Max Contracts:     {rules.max_contracts}")
        print(f"  Daily Loss Limit:  {'None' if not rules.has_daily_loss_limit else f'${rules.daily_loss_limit:,.0f}'}")
        print(f"  Consistency Rule:  {'None' if not rules.has_consistency_rule else 'Yes'}")
        print(f"  Monthly Fee:       ${rules.monthly_fee:,.0f}")
        print(f"  Profit Split:      {rules.profit_split_trader*100:.0f}% / {rules.profit_split_firm*100:.0f}%")

        print(f"\n  Scaling Plan:")
        for level in rules.scaling_plan:
            print(f"    Profit >= ${level.min_profit:,.0f}: Max {level.max_contracts} contracts")

    print("\n" + "=" * 60)
    print("  KEY MFFU ADVANTAGES")
    print("=" * 60)
    print("  ✓ NO Daily Loss Limit")
    print("  ✓ NO Consistency Rule")
    print("  ✓ EOD Trailing (not real-time)")
    print("  ✓ No time limit to pass")
    print("  ✓ Weekly payout requests")
    print("  ✓ Upgradeable to 90/10 split")

    print("\n" + "=" * 60)
    print("  DRAWDOWN EXAMPLE (Starter $50K)")
    print("=" * 60)
    rules = get_mffu_rules("Starter")
    starting = 50000

    # Simulate EOD balances
    eod_balances = [50000, 51000, 51500, 51200, 52000]
    hwm = starting

    print(f"\n  Starting Balance: ${starting:,}")
    print(f"  Max Loss Limit: ${rules.max_loss_limit:,}")

    for day, balance in enumerate(eod_balances, 1):
        hwm = max(hwm, balance)
        floor = rules.get_drawdown_floor(hwm, starting)
        available = rules.get_available_risk(hwm, balance, starting)

        print(f"\n  Day {day}:")
        print(f"    EOD Balance: ${balance:,}")
        print(f"    High Water Mark: ${hwm:,}")
        print(f"    Drawdown Floor: ${floor:,}")
        print(f"    Available Risk: ${available:,}")
