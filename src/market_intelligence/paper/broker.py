from ..storage import Storage
class PaperBroker:
    def __init__(self, storage=None): self.storage=storage or Storage()
    def buy(self,symbol,market,qty,price,fee_bps=15.0): return self.storage.execute_paper_order(symbol,market,"BUY",qty,price,fee_bps)
    def sell(self,symbol,market,qty,price,fee_bps=15.0): return self.storage.execute_paper_order(symbol,market,"SELL",qty,price,fee_bps)
    def snapshot(self): return self.storage.paper_snapshot()
