import numpy as np
from .base import Memristor


class HPMemristor(Memristor):
    """
    HP TiO2 memristor model (Strukov et al., 2008) with a Joglekar
    window function to keep the ion-drift boundary behavior physical.
    """

    def __init__(
        self,
        Ron=100,
        Roff=16000,
        D=10e-9,
        mu_v=1e-14,
        x0=0.2,
        p=1,
    ):
        self.Ron = Ron
        self.Roff = Roff
        self.D = D
        self.mu_v = mu_v
        self.x0 = x0
        self.x = x0
        self.p = p  # Joglekar window sharpness

    def memristance(self):
        """Linear interpolation between Ron and Roff based on state x."""
        return self.Ron * self.x + self.Roff * (1 - self.x)

    def current(self, voltage):
        """Ohm's law using the current memristance."""
        return voltage / self.memristance()

    def window(self, x=None, p=None):
        """Joglekar window function f(x) = 1 - (2x - 1)^(2p)."""
        if x is None:
            x = self.x
        if p is None:
            p = self.p
        return 1 - (2 * x - 1) ** (2 * p)

    def dxdt_from_current(self, i):
        """State derivative given an already-computed current."""
        k = (self.mu_v * self.Ron) / (self.D ** 2)
        return k * i * self.window()

    def dxdt(self, voltage):
        """State derivative computed directly from voltage (convenience)."""
        i = self.current(voltage)
        return self.dxdt_from_current(i)

    def update_state(self, voltage, dt):
        """
        Integrate the state x forward by dt given an applied voltage.
        Note: uses the current computed from the state BEFORE this
        update, i.e. call current(voltage) first if you need the
        current that corresponds to this step.
        """
        i = self.current(voltage)
        self.x += self.dxdt_from_current(i) * dt
        self.x = np.clip(self.x, 0.0, 1.0)

    def apply_voltage(self, voltage: float, dt: float) -> float:
        """
        Apply a voltage for time dt, update internal state, and return
        the current that actually flowed during this step (i.e. computed
        from the state BEFORE integration, not after).
        """
        i = self.current(voltage)       # current at x(t), before update
        self.update_state(voltage, dt)  # integrates x forward
        return i

    def resistance(self) -> float:
        """Return the current memristance (Ω)."""
        return self.memristance()

    def state(self):
        """Return the internal state variable x."""
        return self.x

    def reset(self):
        """Reset the memristor to its initial state."""
        self.x = self.x0