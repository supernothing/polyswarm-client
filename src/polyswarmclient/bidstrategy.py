class BidStrategyBase:
    def __init__(self, min_bid_multiplier, max_bid_multiplier):
        self.min_bid_multiplier = min_bid_multiplier
        self.max_bid_multiplier = max_bid_multiplier
