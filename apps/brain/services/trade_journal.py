import json
from pathlib import Path
from datetime import datetime


class TradeJournal:

    def __init__(self):

        self.file_path = Path(
            "trade_journal.jsonl"
        )

    def write(
        self,
        payload: dict
    ):

        record = {
            "timestamp":
            datetime.utcnow().isoformat(),

            **payload
        }

        with open(
            self.file_path,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                json.dumps(
                    record,
                    default=str
                )
            )

            f.write("\n")

    def latest(
        self,
        limit: int = 50
    ):

        if not self.file_path.exists():
            return []

        with open(
            self.file_path,
            "r",
            encoding="utf-8"
        ) as f:

            lines = f.readlines()

        rows = []

        for line in lines[-limit:]:

            try:
                rows.append(
                    json.loads(line)
                )

            except Exception:
                pass

        return rows


trade_journal = TradeJournal()