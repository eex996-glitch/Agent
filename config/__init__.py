"""
Configuration Package

Exports main configuration objects for easy importing.
"""

from .settings import (
    Settings,
    settings,
    TradingMode,
    PropFirm,
    AccountConfig,
    RiskConfig,
    MarketConfig,
    StrategyConfig,
    DataConfig,
    LoggingConfig,
    MARKETS,
    load_settings_from_env
)

from .prop_firm_rules import (
    TopstepRules,
    ExpressFundedRules,
    AccountTier,
    ScalingLevel,
    get_topstep_rules,
    get_express_funded_rules
)

__all__ = [
    # Settings
    "Settings",
    "settings",
    "TradingMode",
    "PropFirm",
    "AccountConfig",
    "RiskConfig",
    "MarketConfig",
    "StrategyConfig",
    "DataConfig",
    "LoggingConfig",
    "MARKETS",
    "load_settings_from_env",
    
    # Prop Firm Rules
    "TopstepRules",
    "ExpressFundedRules",
    "AccountTier",
    "ScalingLevel",
    "get_topstep_rules",
    "get_express_funded_rules"
]
