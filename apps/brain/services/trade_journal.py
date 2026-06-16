from pathlib import Path
from datetime import datetime
import json


class TradeJournal:

    def __init__(self):

        self.path = Path(
            "trade_journal.json"
        )

        if not self.path.exists():

            self.path.write_text("[]")

    def add(self, trade):

        trades = json.loads(
            self.path.read_text()
        )

        trade["timestamp"] = (
            datetime.utcnow().isoformat()
        )

        trades.append(trade)

        self.path.write_text(
            json.dumps(
                trades,
                indent=2
            )
        )

    def write(
        self,
        trade
    ):
        self.add(trade)

    def all(self):

        return json.loads(
            self.path.read_text()
        )


trade_journal = TradeJournal()