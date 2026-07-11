"""
VOx Memristor — Voltage Waveform Generators
============================================

Provides callable voltage waveform functions V(t) for use as the
driving input to the electro-thermal ODE system.

Each generator returns a function V(t) that accepts time in seconds
and returns voltage in volts. These are designed to be passed directly
to scipy.integrate.solve_ivp via the model's RHS function.

Supported waveforms:
    - Sinusoidal:  V(t) = V_amp * sin(2π f t)
    - Triangular:  V(t) = V_amp * (triangular wave at frequency f)
    - Pulse:       V(t) = V_amp during ON phase, 0 during OFF phase
    - DC sweep:    V(t) = linear ramp (−V_amp → +V_amp → −V_amp)

All waveforms satisfy V(0) = 0 to ensure the I-V curve passes
through the origin at t = 0 (required for pinched hysteresis).
"""

import numpy as np
from typing import Callable


def sinusoidal(amplitude: float, frequency: float,
               phase: float = 0.0) -> Callable[[float], float]:
    """
    Sinusoidal voltage waveform.

    V(t) = V_amp * sin(2π f t + φ₀)

    Parameters
    ----------
    amplitude : float
        Peak voltage amplitude [V].
    frequency : float
        Oscillation frequency [Hz].
    phase : float, optional
        Initial phase [rad]. Default: 0.0.

    Returns
    -------
    Callable[[float], float]
        Function V(t) returning voltage at time t.

    Physics
    -------
    The sinusoidal waveform is the standard excitation for
    characterizing memristive pinched hysteresis (Chua, 1971).
    The I-V Lissajous figure reveals the frequency-dependent
    hysteresis behavior.
    """
    omega = 2.0 * np.pi * frequency  # angular frequency [rad/s]

    def V(t):
        return amplitude * np.sin(omega * t + phase)

    return V


def triangular(amplitude: float, frequency: float) -> Callable[[float], float]:
    """
    Triangular voltage waveform.

    Linearly ramps between −V_amp and +V_amp at constant rate.
    Period T = 1/f. The waveform starts at V = 0 and goes positive first.

    Parameters
    ----------
    amplitude : float
        Peak voltage amplitude [V].
    frequency : float
        Oscillation frequency [Hz].

    Returns
    -------
    Callable[[float], float]
        Function V(t) returning voltage at time t.

    Physics
    -------
    Triangular waveforms provide a constant voltage sweep rate dV/dt,
    which is useful for I-V characterization because it separates
    capacitive and resistive contributions. The constant ramp rate
    means that any hysteresis observed is purely due to the device's
    internal dynamics, not the nonlinearity of the excitation.
    """
    period = 1.0 / frequency  # [s]

    def V(t):
        # Normalize time to [0, 1) within each period
        # Phase shift by T/4 so waveform starts at 0 going positive
        t_shifted = t + period / 4.0
        t_norm = (t_shifted % period) / period
        # Triangle: linear ramp up to 0.5, then ramp down
        return amplitude * (4.0 * np.abs(t_norm - 0.5) - 1.0)

    return V


def pulse(amplitude: float, frequency: float,
          duty_cycle: float = 0.5) -> Callable[[float], float]:
    """
    Rectangular pulse voltage waveform.

    V(t) = V_amp during the ON phase, 0 during the OFF phase.

    Parameters
    ----------
    amplitude : float
        Pulse voltage amplitude [V].
    frequency : float
        Repetition frequency [Hz].
    duty_cycle : float, optional
        Fraction of period that is ON [dimensionless, 0–1]. Default: 0.5.

    Returns
    -------
    Callable[[float], float]
        Function V(t) returning voltage at time t.

    Physics
    -------
    Pulse waveforms are used for:
    1. Measuring SET/RESET thresholds
    2. Characterizing switching speed (incubation time)
    3. Neuromorphic spiking applications
    The OFF phase allows the device to cool, probing the
    persistence of the metallic state (memory retention).
    """
    period = 1.0 / frequency  # [s]
    t_on = duty_cycle * period  # ON duration [s]

    def V(t):
        t_in_period = t % period
        # Use np.where for vectorized operation
        if isinstance(t, np.ndarray):
            return np.where(t_in_period < t_on, amplitude, 0.0)
        return amplitude if t_in_period < t_on else 0.0

    return V


def dc_sweep(amplitude: float, sweep_rate: float) -> Callable[[float], float]:
    """
    DC voltage sweep (linear ramp).

    Sweeps: 0 → +V_amp → 0 → −V_amp → 0

    This is a single full I-V sweep cycle commonly used for
    experimental memristor characterization.

    Parameters
    ----------
    amplitude : float
        Maximum sweep voltage [V].
    sweep_rate : float
        Voltage ramp rate [V/s].

    Returns
    -------
    Callable[[float], float]
        Function V(t) returning voltage at time t.

    Physics
    -------
    DC sweeps at slow rates approach quasi-static conditions where
    the device is in thermal equilibrium at each voltage. This reveals
    the intrinsic R(V) relationship. Faster sweeps introduce rate-
    dependent hysteresis due to thermal lag.
    """
    # Time for each quarter of the sweep cycle
    t_quarter = amplitude / sweep_rate  # [s]
    t_full = 4.0 * t_quarter  # total sweep time [s]

    def V(t):
        # Periodic with period t_full
        t_mod = t % t_full
        if isinstance(t_mod, np.ndarray):
            result = np.zeros_like(t_mod)
            # Quarter 1: 0 → +V_amp (ramp up)
            mask1 = t_mod < t_quarter
            result[mask1] = sweep_rate * t_mod[mask1]
            # Quarter 2: +V_amp → 0 (ramp down)
            mask2 = (t_mod >= t_quarter) & (t_mod < 2 * t_quarter)
            result[mask2] = amplitude - sweep_rate * (t_mod[mask2] - t_quarter)
            # Quarter 3: 0 → −V_amp (ramp negative)
            mask3 = (t_mod >= 2 * t_quarter) & (t_mod < 3 * t_quarter)
            result[mask3] = -sweep_rate * (t_mod[mask3] - 2 * t_quarter)
            # Quarter 4: −V_amp → 0 (ramp back to zero)
            mask4 = t_mod >= 3 * t_quarter
            result[mask4] = -amplitude + sweep_rate * (t_mod[mask4] - 3 * t_quarter)
            return result
        else:
            if t_mod < t_quarter:
                return sweep_rate * t_mod
            elif t_mod < 2.0 * t_quarter:
                return amplitude - sweep_rate * (t_mod - t_quarter)
            elif t_mod < 3.0 * t_quarter:
                return -sweep_rate * (t_mod - 2.0 * t_quarter)
            else:
                return -amplitude + sweep_rate * (t_mod - 3.0 * t_quarter)

    return V


def get_waveform(waveform_type: str, amplitude: float, frequency: float,
                 duty_cycle: float = 0.5,
                 sweep_rate: float = 1.0) -> Callable[[float], float]:
    """
    Factory function to create a voltage waveform by name.

    Parameters
    ----------
    waveform_type : str
        One of: "sinusoidal", "triangular", "pulse", "dc_sweep".
    amplitude : float
        Peak voltage [V].
    frequency : float
        Waveform frequency [Hz]. Ignored for dc_sweep.
    duty_cycle : float, optional
        Pulse duty cycle [0–1]. Only for "pulse".
    sweep_rate : float, optional
        Voltage ramp rate [V/s]. Only for "dc_sweep".

    Returns
    -------
    Callable[[float], float]
        Voltage waveform function V(t).

    Raises
    ------
    ValueError
        If waveform_type is not recognized.
    """
    waveform_type = waveform_type.lower().strip()

    if waveform_type == "sinusoidal":
        return sinusoidal(amplitude, frequency)
    elif waveform_type == "triangular":
        return triangular(amplitude, frequency)
    elif waveform_type == "pulse":
        return pulse(amplitude, frequency, duty_cycle)
    elif waveform_type == "dc_sweep":
        return dc_sweep(amplitude, sweep_rate)
    else:
        raise ValueError(
            f"Unknown waveform type: '{waveform_type}'. "
            f"Supported: sinusoidal, triangular, pulse, dc_sweep."
        )
