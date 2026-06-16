class MarketStore:

    def __init__(self):

        self.latest_market = None

        self.latest_score = None

        self.latest_statistics = None
        self.latest_fundamental = None
        self.latest_pattern = None

        self.latest_decision = None
        self.latest_risk = None

    # Market

    def update(self, data):
        self.latest_market = data

    def get(self):
        return self.latest_market

    # Score

    def update_score(self, score):
        self.latest_score = score

    def get_score(self):
        return self.latest_score

    # Statistics

    def update_statistics(self, data):
        self.latest_statistics = data

    def get_statistics(self):
        return self.latest_statistics

    # Fundamental

    def update_fundamental(self, data):
        self.latest_fundamental = data

    def get_fundamental(self):
        return self.latest_fundamental

    # Pattern

    def update_pattern(self, data):
        self.latest_pattern = data

    def get_pattern(self):
        return self.latest_pattern

    # Trader

    def update_decision(self, data):
        self.latest_decision = data

    def get_decision(self):
        return self.latest_decision

    # Risk

    def update_risk(self, data):
        self.latest_risk = data

    def get_risk(self):
        return self.latest_risk


market_store = MarketStore()