from abc import ABC, abstractmethod


class Memristor(ABC):
    @abstractmethod
    def apply_voltage(self, voltage: float, dt: float) -> float:
        pass

    @abstractmethod
    def resistance(self) -> float:
        """Return the current memristance (Ω)."""
        pass

    @abstractmethod
    def current(self, voltage: float) -> float:
        """Return current for the applied voltage."""
        pass

    @abstractmethod
    def state(self):
        """Return the internal state variable(s)."""
        pass

    @abstractmethod
    def reset(self):
        """Reset the memristor to its initial state."""
        pass

    