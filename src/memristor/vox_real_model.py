"""
VOx Memristor — REAL (Non-Ideal) Electro-Thermal MIT Model
============================================================

This module implements a physically realistic model of a VOx memristor
that goes beyond the ideal lumped-element approximation. It includes:

  1. Arrhenius temperature-dependent insulating resistance R_i(T)
  2. Metallic resistance with temperature coefficient (TCR)
  3. Series contact/electrode resistance R_contact
  4. Temperature-dependent phase relaxation time tau_phi(T)
  5. Non-linear thermal conductance G_th(T)
  6. State-dependent hysteresis with asymmetric transition widths

These corrections are needed to match experimental V(I) and I(V) curves
from real VOx thin-film devices, which show:
  - Curved (non-linear) pre-switching I-V due to Arrhenius conduction
  - Gradual NDR snap-back due to dynamic nucleation kinetics
  - High-current resistance floor due to contact resistance
  - Asymmetric heating/cooling transitions

The IDEAL model code in vox_model.py is fully preserved and untouched.

References
----------
[1] Mott, N.F., Metal-Insulator Transitions, Taylor & Francis (1990).
[2] Pergament, A.L., et al., JSTQE 23(2), 2017.
[3] Kumar, S., et al., Adv. Mater. 25, 6128 (2013).
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable, Optional
from scipy.integrate import solve_ivp


# =====================================================================
# Physical Constants
# =====================================================================

K_B_EV = 8.617333262e-5   # Boltzmann constant [eV/K]


# =====================================================================
# PARAMETERS
# =====================================================================

@dataclass
class RealVOxParameters:
    """
    Complete parameter set for the REAL (non-ideal) VOx model.

    Calibrated against experimental data from the paper:
      - Figure 2: R-T characteristics → R_i_ref, R_m, T_IMT, T_MIT
      - Figure 3: V(I) at 295K → G_th, E_g, switching threshold
      - Figure 5: Multi-amplitude sweeps → R_contact, alpha_m
      - Figure 6: 32 voltage sweeps → C_th, tau_phi
    """

    # --- Thermal ---
    C_th: float = 5.0e-9
    """Thermal capacitance [J/K]. Larger than ideal model to represent
    realistic thermal mass of the active VO2 region plus substrate."""

    G_th_0: float = 3.0e-4
    """Base thermal conductance [W/K]. Calibrated from switching power
    at the NDR threshold: G_th ≈ P_switch / ΔT_switch."""

    G_th_nonlinear: float = 5.0e-7
    """Non-linear thermal conductance coefficient [W/K²].
    G_th(T) = G_th_0 + G_th_nonlinear * (T - T_amb).
    Models enhanced heat loss at high temperatures (radiation + phonon)."""

    T_amb: float = 297.0
    """Ambient temperature [K]. Set to 297K per paper conditions."""

    L_latent: float = 5.0e-9
    """Latent heat of MIT [J]."""

    # --- MIT Transition ---
    T_IMT: float = 308.0
    """Insulator-to-Metal transition temperature (heating) [K].
    Extracted from Figure 2b."""

    T_MIT: float = 300.0
    """Metal-to-Insulator transition temperature (cooling) [K].
    Extracted from Figure 2a."""

    delta_T: float = 3.5
    """Transition width [K]. Controls sigmoid sharpness."""

    tau_phi_0: float = 5.0e-7
    """Base phase relaxation time [s]."""

    E_a_kinetics: float = 0.15
    """Activation energy for phase kinetics [eV].
    tau_phi(T) = tau_phi_0 * exp(E_a / (k_B * T)).
    Higher T → faster relaxation → faster switching."""

    hysteresis_mode: str = "state_dependent"

    # --- Electrical ---
    R_m_0: float = 80.0
    """Base metallic resistance at T_ref [Ω]. From Figure 2c: R_MET ≈ 90Ω."""

    alpha_m: float = 1.2e-3
    """Metallic TCR [1/K]. R_m(T) = R_m_0 * (1 + alpha_m*(T-T_ref))."""

    R_i_ref: float = 12000.0
    """Insulating resistance at T_ref [Ω].
    This is NOT the full R_INS from Figure 2 (which is at ~290K).
    At T_ref=297K (paper operating temperature), R_i is already
    reduced from Arrhenius conduction."""

    T_ref: float = 297.0
    """Reference temperature for R_i_ref [K]."""

    E_g: float = 0.45
    """Activation energy for insulating conduction [eV].
    R_i(T) = R_i_ref * exp(E_g/(2*k_B) * (1/T - 1/T_ref)).
    Half the VO2 optical bandgap (~0.6 eV)."""

    R_contact: float = 50.0
    """Series contact/electrode resistance [Ω].
    Models imperfect metal-VO2 interfaces. Creates a resistance
    floor in the fully metallic state."""

    resistance_model: str = "logarithmic"

    # --- Simulation ---
    bias_mode: str = "current"
    V_amplitude: float = 1.0e-3
    frequency: float = 1.0
    n_cycles: int = 1
    waveform_type: str = "triangular"

    # --- Solver ---
    rtol: float = 1e-8
    atol: float = 1e-10

    # --- Initial conditions ---
    T_initial: float = 297.0
    phi_initial: float = 0.0

    @property
    def simulation_time(self) -> float:
        return self.n_cycles / self.frequency

    @property
    def effective_max_step(self) -> float:
        return 1.0 / (200.0 * self.frequency)


# =====================================================================
# PHYSICS: Temperature-Dependent Resistance
# =====================================================================

def R_insulating(T: float, params: RealVOxParameters) -> float:
    """
    Arrhenius temperature-dependent insulating resistance.

    R_i(T) = R_i_ref * exp( E_g/(2*k_B) * (1/T - 1/T_ref) )

    As T increases, thermal excitation of carriers across the bandgap
    reduces R_i even BEFORE the structural phase transition.
    This creates the curved pre-switching I-V seen in experiments.
    """
    exponent = (params.E_g / (2.0 * K_B_EV)) * (1.0/T - 1.0/params.T_ref)
    return params.R_i_ref * np.exp(exponent)


def R_metallic(T: float, params: RealVOxParameters) -> float:
    """
    Metallic resistance with linear temperature coefficient (TCR).

    R_m(T) = R_m_0 * (1 + α_m * (T - T_ref))

    Metals have positive TCR: resistance increases with temperature.
    """
    return params.R_m_0 * (1.0 + params.alpha_m * (T - params.T_ref))


def resistance(T: float, phi: float, params: RealVOxParameters) -> float:
    """
    Total device resistance including contact resistance.

    R_total = R_device(T, φ) + R_contact

    where R_device uses the logarithmic (Lichtenecker) mixing rule:
        R_device = R_m(T)^φ * R_i(T)^(1-φ)
    """
    R_m = R_metallic(T, params)
    R_i = R_insulating(T, params)

    phi_c = np.clip(phi, 0.0, 1.0)

    # Logarithmic mixing (Lichtenecker)
    log_R = phi_c * np.log(R_m) + (1.0 - phi_c) * np.log(R_i)
    R_device = np.exp(log_R)

    return R_device + params.R_contact


# =====================================================================
# PHYSICS: Phase Kinetics
# =====================================================================

def G_thermal(T: float, params: RealVOxParameters) -> float:
    """
    Temperature-dependent thermal conductance.

    G_th(T) = G_th_0 + G_th_nonlinear * (T - T_amb)

    At high temperatures, radiation and enhanced phonon transport
    increase heat dissipation, preventing unrealistic temperature runaway.
    """
    return params.G_th_0 + params.G_th_nonlinear * max(0.0, T - params.T_amb)


def tau_phi(T: float, params: RealVOxParameters) -> float:
    """
    Temperature-dependent phase relaxation time.

    tau_phi(T) = tau_phi_0 * exp(E_a / (k_B * T))

    At higher temperatures, thermal energy helps overcome nucleation
    barriers, making the phase transition faster.
    """
    val = params.tau_phi_0 * np.exp(params.E_a_kinetics / (K_B_EV * T))
    return val


def phi_equilibrium(T: float, phi: float,
                    params: RealVOxParameters) -> float:
    """
    Equilibrium metallic fraction using state-dependent hysteresis.

    T_c(φ) = T_MIT + (T_IMT - T_MIT) * (1 - φ)

    This makes the effective transition temperature depend on the
    current phase state, creating smooth hysteresis without
    discontinuities in the ODE RHS.
    """
    if params.hysteresis_mode == "state_dependent":
        T_c = params.T_MIT + (params.T_IMT - params.T_MIT) * (1.0 - phi)
    else:
        T_c = params.T_IMT  # fallback

    arg = -(T - T_c) / params.delta_T
    arg = np.clip(arg, -500.0, 500.0)
    return 1.0 / (1.0 + np.exp(arg))


# =====================================================================
# ODE RIGHT-HAND SIDES
# =====================================================================

def system_rhs_voltage(t, state, V_func, params):
    """RHS for VOLTAGE-BIASED mode: P_joule = V²/R."""
    T, phi = state[0], np.clip(state[1], 0.0, 1.0)
    V = V_func(t)
    R = resistance(T, phi, params)
    G = G_thermal(T, params)
    tau = tau_phi(T, params)
    phi_eq = phi_equilibrium(T, phi, params)

    P_joule = V * V / R
    P_cool = G * (T - params.T_amb)
    dphi_dt = (phi_eq - phi) / tau
    P_latent = params.L_latent * dphi_dt
    dT_dt = (P_joule - P_cool - P_latent) / params.C_th

    return np.array([dT_dt, dphi_dt])


def system_rhs_current(t, state, I_func, params):
    """RHS for CURRENT-BIASED mode: P_joule = I²·R."""
    T, phi = state[0], np.clip(state[1], 0.0, 1.0)
    I = I_func(t)
    R = resistance(T, phi, params)
    G = G_thermal(T, params)
    tau = tau_phi(T, params)
    phi_eq = phi_equilibrium(T, phi, params)

    P_joule = I * I * R
    P_cool = G * (T - params.T_amb)
    dphi_dt = (phi_eq - phi) / tau
    P_latent = params.L_latent * dphi_dt
    dT_dt = (P_joule - P_cool - P_latent) / params.C_th

    return np.array([dT_dt, dphi_dt])


# =====================================================================
# SOLVER
# =====================================================================

def solve_real_vox(params: RealVOxParameters,
                   input_func: Optional[Callable] = None,
                   n_eval: int = 5000,
                   method: str = 'Radau') -> dict:
    """
    Solve the coupled ODEs for the real VOx model.

    Returns a dict with t, T, phi, V, I, R arrays.
    """
    # Build default waveform if not provided
    if input_func is None:
        amp = params.V_amplitude
        freq = params.frequency
        if params.waveform_type == "triangular":
            def input_func(t):
                phase = (t * freq) % 1.0
                if phase < 0.25:
                    return amp * (phase / 0.25)
                elif phase < 0.75:
                    return amp * (1.0 - (phase - 0.25) / 0.25)
                else:
                    return amp * (-1.0 + (phase - 0.75) / 0.25)
        else:
            def input_func(t):
                return amp * np.sin(2.0 * np.pi * freq * t)

    t_end = params.simulation_time
    t_eval = np.linspace(0, t_end, n_eval)
    y0 = np.array([params.T_initial, params.phi_initial])

    if params.bias_mode == "current":
        rhs = lambda t, y: system_rhs_current(t, y, input_func, params)
    else:
        rhs = lambda t, y: system_rhs_voltage(t, y, input_func, params)

    sol = solve_ivp(
        fun=rhs,
        t_span=(0, t_end),
        y0=y0,
        method=method,
        t_eval=t_eval,
        rtol=params.rtol,
        atol=params.atol,
        max_step=params.effective_max_step,
        dense_output=True,
    )

    T_arr = sol.y[0]
    phi_arr = np.clip(sol.y[1], 0.0, 1.0)
    R_arr = np.array([resistance(T_arr[i], phi_arr[i], params)
                      for i in range(len(sol.t))])

    if params.bias_mode == "current":
        I_arr = np.array([input_func(t) for t in sol.t])
        V_arr = I_arr * R_arr
    else:
        V_arr = np.array([input_func(t) for t in sol.t])
        I_arr = V_arr / R_arr

    return {
        't': sol.t, 'T': T_arr, 'phi': phi_arr,
        'V': V_arr, 'I': I_arr, 'R': R_arr,
        'success': sol.success, 'message': sol.message,
    }
