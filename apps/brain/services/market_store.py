from typing import Any


class MarketStore:
    """
    In-memory state store for the RIRI decision pipeline.

    The store keeps the latest result from each stage:

        Market
            ↓
        Scoring
            ↓
        Statistics
            ↓
        Fundamental
            ↓
        Pattern
            ↓
        AI Trader
            ↓
        AI Risk
            ↓
        Execution
            ↓
        Journal

    This store contains the latest state only.
    Persistent trade history belongs to TradeJournal.
    """

    def __init__(self) -> None:

        self.latest_market: Any = None

        self.latest_score: Any = None

        self.latest_statistics: Any = None

        self.latest_fundamental: Any = None

        self.latest_pattern: Any = None

        self.latest_decision: Any = None

        self.latest_risk: Any = None

        self.latest_execution: Any = None

        self.latest_journal: Any = None


    # ==================================================
    # MARKET
    # ==================================================

    def update(
        self,
        data: Any
    ) -> None:

        self.latest_market = data


    def get(self) -> Any:

        return self.latest_market


    # ==================================================
    # SCORING
    # ==================================================

    def update_score(
        self,
        score: Any
    ) -> None:

        self.latest_score = score


    def get_score(self) -> Any:

        return self.latest_score


    # ==================================================
    # STATISTICS
    # ==================================================

    def update_statistics(
        self,
        data: Any
    ) -> None:

        self.latest_statistics = data


    def get_statistics(self) -> Any:

        return self.latest_statistics


    # ==================================================
    # FUNDAMENTAL
    # ==================================================

    def update_fundamental(
        self,
        data: Any
    ) -> None:

        self.latest_fundamental = data


    def get_fundamental(self) -> Any:

        return self.latest_fundamental


    # ==================================================
    # PATTERN
    # ==================================================

    def update_pattern(
        self,
        data: Any
    ) -> None:

        self.latest_pattern = data


    def get_pattern(self) -> Any:

        return self.latest_pattern


    # ==================================================
    # AI TRADER
    # ==================================================

    def update_decision(
        self,
        data: Any
    ) -> None:

        self.latest_decision = data


    def get_decision(self) -> Any:

        return self.latest_decision


    # ==================================================
    # AI RISK
    # ==================================================

    def update_risk(
        self,
        data: Any
    ) -> None:

        self.latest_risk = data


    def get_risk(self) -> Any:

        return self.latest_risk


    # ==================================================
    # EXECUTION
    # ==================================================

    def update_execution(
        self,
        data: Any
    ) -> None:

        self.latest_execution = data


    def get_execution(self) -> Any:

        return self.latest_execution


    # ==================================================
    # JOURNAL
    # ==================================================

    def update_journal(
        self,
        data: Any
    ) -> None:

        self.latest_journal = data


    def get_journal(self) -> Any:

        return self.latest_journal


    # ==================================================
    # SNAPSHOT
    # ==================================================

    def snapshot(self) -> dict[str, Any]:
        """
        Return the complete latest RIRI state.

        Useful for:
        - dashboard
        - WebSocket
        - debugging
        - monitoring
        """

        return {
            "market": self.latest_market,
            "score": self.latest_score,
            "statistics": self.latest_statistics,
            "fundamental": self.latest_fundamental,
            "pattern": self.latest_pattern,
            "decision": self.latest_decision,
            "risk": self.latest_risk,
            "execution": self.latest_execution,
            "journal": self.latest_journal,
        }


    # ==================================================
    # RESET
    # ==================================================

    def reset_decision_state(self) -> None:
        """
        Clear transient decision-stage state.

        Market data remains available.

        This is useful before starting a new
        analysis cycle.
        """

        self.latest_score = None

        self.latest_statistics = None

        self.latest_fundamental = None

        self.latest_pattern = None

        self.latest_decision = None

        self.latest_risk = None

        self.latest_execution = None


# ==================================================
# SINGLETON
# ==================================================

market_store = MarketStore()