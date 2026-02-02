"""
Prop Firm Rules Configuration

This module defines the specific rules for various prop trading firms.
Focus is on Topstep Trading Combine rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum


class AccountTier(Enum):
    """Topstep account tiers"""
    TIER_50K = "50K"
    TIER_100K = "100K"
    TIER_150K = "150K"


@dataclass
class ScalingLevel:
    """Position scaling based on account balance"""
    min_balance: float
    max_contracts: int


@dataclass
class TopstepRules:
    """
    Topstep Trading Combine Rules
    
    Key Rules:
    1. Maximum Loss Limit (MLL) - End of day trailing drawdown
    2. Consistency Target - Best day < 50% of profit target
    3. Scaling Plan - Position size based on balance
    4. No time limit to pass
    5. Minimum 2 trading days
    """
    
    # Account tier
    tier: AccountTier = AccountTier.TIER_50K
    
    # Profit target to pass evaluation
    profit_target: float = 3000.0
    
    # Maximum loss limit (trailing drawdown from high water mark)
    max_loss_limit: float = 2000.0
    
    # Daily loss limit (if applicable - not on TopstepX after Aug 2024)
    daily_loss_limit: float = 1000.0
    has_daily_loss_limit: bool = False  # TopstepX removed this
    
    # Consistency target: best day must be < this % of profit target
    consistency_threshold: float = 0.50  # 50%
    
    # Maximum contracts allowed
    max_contracts: int = 5
    
    # Scaling plan levels
    scaling_plan: List[ScalingLevel] = field(default_factory=list)
    
    # Trading hours (CT timezone)
    trading_start_hour: int = 17  # 5 PM CT
    trading_end_hour: int = 16  # 4 PM CT next day
    
    # Position must be flat by this time
    flat_by_hour: int = 15  # 3 PM CT
    flat_by_minute: int = 10
    
    # Minimum trading days before passing
    min_trading_days: int = 2
    
    # Minimum winning day amount for payout eligibility
    winning_day_threshold: float = 150.0
    
    # Winning days needed for first payout
    winning_days_for_payout: int = 5
    
    def __post_init__(self):
        """Initialize tier-specific rules"""
        self._set_tier_rules()
        self._set_scaling_plan()
    
    def _set_tier_rules(self):
        """Set rules based on account tier"""
        tier_configs = {
            AccountTier.TIER_50K: {
                "profit_target": 3000.0,
                "max_loss_limit": 2000.0,
                "daily_loss_limit": 1000.0,
                "max_contracts": 5
            },
            AccountTier.TIER_100K: {
                "profit_target": 6000.0,
                "max_loss_limit": 3000.0,
                "daily_loss_limit": 2000.0,
                "max_contracts": 10
            },
            AccountTier.TIER_150K: {
                "profit_target": 9000.0,
                "max_loss_limit": 4500.0,
                "daily_loss_limit": 3000.0,
                "max_contracts": 15
            }
        }
        
        config = tier_configs.get(self.tier, tier_configs[AccountTier.TIER_50K])
        self.profit_target = config["profit_target"]
        self.max_loss_limit = config["max_loss_limit"]
        self.daily_loss_limit = config["daily_loss_limit"]
        self.max_contracts = config["max_contracts"]
    
    def _set_scaling_plan(self):
        """Set scaling plan based on tier"""
        # Scaling plans from Topstep
        scaling_configs = {
            AccountTier.TIER_50K: [
                ScalingLevel(0, 2),
                ScalingLevel(1500, 3),
                ScalingLevel(2000, 4),
                ScalingLevel(2500, 5),
            ],
            AccountTier.TIER_100K: [
                ScalingLevel(0, 3),
                ScalingLevel(2000, 5),
                ScalingLevel(3500, 7),
                ScalingLevel(5000, 10),
            ],
            AccountTier.TIER_150K: [
                ScalingLevel(0, 5),
                ScalingLevel(3000, 8),
                ScalingLevel(5000, 12),
                ScalingLevel(7500, 15),
            ]
        }
        
        self.scaling_plan = scaling_configs.get(
            self.tier, 
            scaling_configs[AccountTier.TIER_50K]
        )
    
    def get_max_contracts_for_balance(self, profit: float) -> int:
        """
        Get maximum allowed contracts based on current profit
        
        Args:
            profit: Current cumulative profit in account
            
        Returns:
            Maximum number of contracts allowed
        """
        max_contracts = self.scaling_plan[0].max_contracts
        
        for level in self.scaling_plan:
            if profit >= level.min_balance:
                max_contracts = level.max_contracts
        
        return min(max_contracts, self.max_contracts)
    
    def calculate_consistency_target(self, best_day_profit: float) -> float:
        """
        Calculate required total profit for consistency target
        
        If best day > 50% of profit target, need more total profit.
        
        Args:
            best_day_profit: Highest single day profit
            
        Returns:
            Minimum total profit required to pass
        """
        required_total = best_day_profit / self.consistency_threshold
        return max(required_total, self.profit_target)
    
    def is_consistency_met(self, best_day: float, total_profit: float) -> bool:
        """
        Check if consistency target is met
        
        Args:
            best_day: Best single day profit
            total_profit: Total cumulative profit
            
        Returns:
            True if consistency target is met
        """
        if total_profit <= 0:
            return False
        
        best_day_percentage = best_day / total_profit
        return best_day_percentage < self.consistency_threshold
    
    def get_recommended_daily_target(self) -> Tuple[float, float]:
        """
        Get recommended daily profit target range for consistency
        
        Returns:
            Tuple of (min_target, max_target) for daily profits
        """
        # To pass with good consistency, aim for profits spread over ~10 days
        # Min: Enough to hit $150 winning day threshold
        # Max: Stay under 50% of total needed
        
        min_target = self.winning_day_threshold
        max_target = self.profit_target * 0.15  # 15% of target per day max
        
        return (min_target, max_target)
    
    def check_max_loss_breach(
        self, 
        high_water_mark: float, 
        current_balance: float,
        starting_balance: float
    ) -> bool:
        """
        Check if maximum loss limit has been breached
        
        Topstep uses END OF DAY trailing drawdown:
        - MLL is set at end of each day based on highest EOD balance
        - Current balance must not drop below (high_water_mark - max_loss_limit)
        
        Args:
            high_water_mark: Highest end-of-day balance achieved
            current_balance: Current account balance
            starting_balance: Initial account balance
            
        Returns:
            True if MLL has been breached
        """
        # MLL floor = highest EOD balance - max loss limit
        # But floor cannot go below starting balance - max loss limit
        
        absolute_floor = starting_balance - self.max_loss_limit
        trailing_floor = high_water_mark - self.max_loss_limit
        
        # Use the higher of the two floors
        effective_floor = max(absolute_floor, trailing_floor)
        
        return current_balance <= effective_floor
    
    def get_available_risk(
        self, 
        high_water_mark: float,
        current_balance: float,
        starting_balance: float
    ) -> float:
        """
        Calculate available risk before hitting MLL
        
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


@dataclass
class ExpressFundedRules:
    """
    Topstep Express Funded Account Rules
    
    After passing Trading Combine, these rules apply.
    """
    
    tier: AccountTier = AccountTier.TIER_50K
    
    # Starting balance (always $0)
    starting_balance: float = 0.0
    
    # Maximum loss limit based on tier
    max_loss_limit: float = 2000.0
    
    # No consistency target in funded account
    has_consistency_target: bool = False
    
    # Payout requirements
    winning_days_for_payout: int = 5
    winning_day_threshold: float = 150.0
    max_payout_amount: float = 5000.0
    max_payout_percentage: float = 0.50  # 50% of balance
    
    def __post_init__(self):
        """Set tier-specific rules"""
        limits = {
            AccountTier.TIER_50K: 2000.0,
            AccountTier.TIER_100K: 3000.0,
            AccountTier.TIER_150K: 4500.0
        }
        self.max_loss_limit = limits.get(self.tier, 2000.0)


# Factory functions
def get_topstep_rules(tier: str = "50K") -> TopstepRules:
    """
    Get Topstep Trading Combine rules for a specific tier
    
    Args:
        tier: Account tier (50K, 100K, 150K)
        
    Returns:
        TopstepRules instance
    """
    tier_map = {
        "50K": AccountTier.TIER_50K,
        "100K": AccountTier.TIER_100K,
        "150K": AccountTier.TIER_150K
    }
    
    account_tier = tier_map.get(tier.upper(), AccountTier.TIER_50K)
    return TopstepRules(tier=account_tier)


def get_express_funded_rules(tier: str = "50K") -> ExpressFundedRules:
    """
    Get Express Funded Account rules
    
    Args:
        tier: Account tier
        
    Returns:
        ExpressFundedRules instance
    """
    tier_map = {
        "50K": AccountTier.TIER_50K,
        "100K": AccountTier.TIER_100K,
        "150K": AccountTier.TIER_150K
    }
    
    account_tier = tier_map.get(tier.upper(), AccountTier.TIER_50K)
    return ExpressFundedRules(tier=account_tier)


# Example usage and testing
if __name__ == "__main__":
    # Test Topstep rules
    rules = get_topstep_rules("50K")
    
    print("=== Topstep 50K Trading Combine Rules ===")
    print(f"Profit Target: ${rules.profit_target:,.0f}")
    print(f"Max Loss Limit: ${rules.max_loss_limit:,.0f}")
    print(f"Max Contracts: {rules.max_contracts}")
    print(f"Consistency Target: Best day < {rules.consistency_threshold*100}% of total")
    
    print("\n=== Scaling Plan ===")
    for level in rules.scaling_plan:
        print(f"  Profit >= ${level.min_balance:,.0f}: Max {level.max_contracts} contracts")
    
    print("\n=== Consistency Check ===")
    test_cases = [
        (1500, 3000),  # Best day is 50% - borderline
        (1000, 3000),  # Best day is 33% - good
        (2000, 3000),  # Best day is 67% - fails
    ]
    
    for best_day, total in test_cases:
        met = rules.is_consistency_met(best_day, total)
        pct = (best_day / total) * 100
        status = "✓ PASS" if met else "✗ FAIL"
        print(f"  Best: ${best_day}, Total: ${total} ({pct:.1f}%) -> {status}")
    
    print("\n=== MLL Check ===")
    hwm = 51000  # High water mark
    starting = 50000
    
    test_balances = [49500, 49000, 48500, 48000, 47500]
    for balance in test_balances:
        breached = rules.check_max_loss_breach(hwm, balance, starting)
        available = rules.get_available_risk(hwm, balance, starting)
        status = "BREACH!" if breached else f"OK (${available:.0f} available)"
        print(f"  Balance: ${balance:,} -> {status}")
