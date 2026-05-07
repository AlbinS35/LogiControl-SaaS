from abc import ABC, abstractmethod

class PaymentStrategy(ABC):
    @abstractmethod
    def process_payment(self, amount: float, currency: str = 'USD') -> bool:
        pass

class StripePaymentStrategy(PaymentStrategy):
    def process_payment(self, amount: float, currency: str = 'USD') -> bool:
        # Mock implementation for Stripe
        print(f"Processing ${amount} {currency} via Stripe")
        return True

class FastagPaymentStrategy(PaymentStrategy):
    def process_payment(self, amount: float, currency: str = 'USD') -> bool:
        # Mock implementation for Fastag
        print(f"Processing ${amount} {currency} via Fastag toll account")
        return True

class PaymentProcessor:
    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def pay(self, amount: float, currency: str = 'USD') -> bool:
        return self._strategy.process_payment(amount, currency)
