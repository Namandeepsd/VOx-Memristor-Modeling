"""
VOx Memristor — ODE Solver Wrapper
====================================

Wraps scipy.integrate.solve_ivp to solve the coupled electro-thermal
ODE system for the VOx MIT memristor model.

The solver handles:
    1. Configuration of the stiff ODE solver (Radau by default)
    2. Adaptive time stepping with user-configurable tolerances
    3. Dense output for smooth interpolation
    4. Post-processing to compute all derived quantities
    5. Physical bounds enforcement

Design Decisions
----------------
- **Solver choice: Radau** — The system is stiff because the phase
  transition creates a sharp sigmoid that makes the Jacobian ill-
  conditioned. Radau (implicit Runge-Kutta) handles this robustly.
  Alternative: BDF for very stiff problems.

- **Dense output** — Enabled to allow fine-grained plotting without
  requiring excessively small fixed time steps.

- **Bounds** — Temperature is bounded below by 0 K (physical).
  Metallic fraction is bounded to [0, 1] (definition).
"""

import numpy as np
from scipy.integrate import solve_ivp
from typing import Callable, Optional

from .vox_parameters import VOxParameters
from .vox_model import system_rhs, compute_outputs, system_rhs_current_bias, compute_outputs_current_bias
from .vox_waveforms import get_waveform


class SimulationResult:
    """
    Container for all simulation results.

    Attributes
    ----------
    t : np.ndarray
        Time points [s], shape (N,).
    T : np.ndarray
        Device temperature [K], shape (N,).
    phi : np.ndarray
        Metallic fraction [dimensionless], shape (N,).
    V : np.ndarray
        Applied voltage [V], shape (N,).
    I : np.ndarray
        Device current [A], shape (N,).
    R : np.ndarray
        Device resistance [Ω], shape (N,).
    P : np.ndarray
        Instantaneous power V*I [W], shape (N,).
    P_joule : np.ndarray
        Joule heating power V²/R [W], shape (N,).
    P_cool : np.ndarray
        Cooling power G_th*(T−T_amb) [W], shape (N,).
    params : VOxParameters
        Parameters used for this simulation.
    success : bool
        Whether the solver converged.
    message : str
        Solver status message.
    """

    def __init__(self, outputs: dict, params: VOxParameters,
                 success: bool, message: str):
        self.t = outputs['t']
        self.T = outputs['T']
        self.phi = outputs['phi']
        self.V = outputs['V']
        self.I = outputs['I']
        self.R = outputs['R']
        self.P = outputs['P']
        self.P_joule = outputs['P_joule']
        self.P_cool = outputs['P_cool']
        self.params = params
        self.success = success
        self.message = message

    def summary(self) -> str:
        """Print a diagnostic summary of the simulation results."""
        lines = [
            "=" * 55,
            "Simulation Results Summary",
            "=" * 55,
            f"  Solver status  : {'SUCCESS' if self.success else 'FAILED'}",
            f"  Message        : {self.message}",
            f"  Time points    : {len(self.t)}",
            f"  Time range     : [{self.t[0]:.2e}, {self.t[-1]:.2e}] s",
            "",
            "  Temperature:",
            f"    min = {self.T.min():.2f} K",
            f"    max = {self.T.max():.2f} K",
            f"    ΔT  = {self.T.max() - self.T.min():.2f} K",
            "",
            "  Metallic fraction:",
            f"    min = {self.phi.min():.6f}",
            f"    max = {self.phi.max():.6f}",
            "",
            "  Resistance:",
            f"    min = {self.R.min():.2f} Ω",
            f"    max = {self.R.max():.2f} Ω",
            f"    ratio = {self.R.max()/self.R.min():.1f}",
            "",
            "  Current:",
            f"    |I|_max = {np.abs(self.I).max():.4e} A",
            "",
            "  Power:",
            f"    P_joule_max = {self.P_joule.max():.4e} W",
            "=" * 55,
        ]
        return "\n".join(lines)


def solve_vox(params: VOxParameters,
              V_func: Optional[Callable[[float], float]] = None,
              n_eval: int = 5000,
              method: str = 'Radau') -> SimulationResult:
    """
    Solve the coupled electro-thermal ODE system for the VOx memristor.

    Solves:
        C_th * dT/dt = V²/R(T,φ) − G_th*(T−T_amb) − L*dφ/dt
        dφ/dt = (φ_eq(T) − φ) / τ_φ

    using scipy.integrate.solve_ivp with an implicit solver suitable
    for stiff systems.

    Parameters
    ----------
    params : VOxParameters
        Complete parameter set for the model.
    V_func : Callable[[float], float], optional
        Voltage waveform V(t). If None, it is constructed from
        params.waveform_type, params.V_amplitude, params.frequency.
    n_eval : int, optional
        Number of evenly-spaced time points for output. Default: 5000.
    method : str, optional
        ODE solver method. Default: 'Radau' (implicit, L-stable,
        suitable for stiff problems).
        Alternatives: 'BDF' (also implicit), 'RK45' (explicit, non-stiff).

    Returns
    -------
    SimulationResult
        Object containing all time series and metadata.

    Notes
    -----
    Why Radau?
    ----------
    The MIT phase transition creates a sharp sigmoid in φ_eq(T).
    When T crosses T_c, the RHS changes rapidly, making the system
    stiff. Explicit solvers (RK45) would require extremely small
    time steps near the transition, while Radau adapts automatically.

    The solver uses dense output (`dense_output=True`) to evaluate
    the solution at arbitrary time points without reducing step size.
    """
    # ---- Build voltage waveform if not provided ----
    if V_func is None:
        V_func = get_waveform(
            waveform_type=params.waveform_type,
            amplitude=params.V_amplitude,
            frequency=params.frequency,
            duty_cycle=params.duty_cycle,
            sweep_rate=params.dc_sweep_rate,
        )

    # ---- Time span ----
    t_start = 0.0
    t_end = params.simulation_time
    t_eval = np.linspace(t_start, t_end, n_eval)

    # ---- Initial conditions ----
    y0 = np.array([params.T_initial, params.phi_initial])

    # ---- Solve the coupled ODEs ----
    if params.bias_mode == "current":
        rhs_func = lambda t, y: system_rhs_current_bias(t, y, V_func, params)
    else:
        rhs_func = lambda t, y: system_rhs(t, y, V_func, params)

    sol = solve_ivp(
        fun=rhs_func,
        t_span=(t_start, t_end),
        y0=y0,
        method=method,
        t_eval=t_eval,
        rtol=params.rtol,
        atol=params.atol,
        max_step=params.effective_max_step,
        dense_output=True,
    )

    # ---- Extract state trajectories ----
    T_array = sol.y[0]
    phi_array = np.clip(sol.y[1], 0.0, 1.0)  # enforce bounds

    # ---- Compute all derived quantities ----
    if params.bias_mode == "current":
        outputs = compute_outputs_current_bias(sol.t, T_array, phi_array, V_func, params)
    else:
        outputs = compute_outputs(sol.t, T_array, phi_array, V_func, params)

    return SimulationResult(
        outputs=outputs,
        params=params,
        success=sol.success,
        message=sol.message,
    )
