class SignalStore:

    def __init__(self):

        self.pending_signal = None

    def set_signal(
        self,
        signal
    ):
        self.pending_signal = signal

    def get_signal(self):
        return self.pending_signal

    def clear(self):
        self.pending_signal = None


signal_store = SignalStore()