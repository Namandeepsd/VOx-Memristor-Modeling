"""
VOx Memristor — Core Electro-Thermal MIT Model
================================================

This module implements the physics of a VOx (VO₂) memristor whose
switching mechanism is the thermally-driven Metal-Insulator Transition.

Physical Mechanism
------------------
    Voltage → Current → Joule Heating → Temperature Rise
    → MIT (monoclinic ↔ rutile) → Metallic Phase Growth
    → Resistance Change

This is fundamentally different from the HP TiO₂ model where oxygen
vacancy drift drives resistance change.

Coupled ODE System
------------------
State vector: y = [T, φ]

    (1) Thermal:
        C_th * dT/dt = V²/R(T,φ) − G_th*(T − T_amb) − L*(φ_eq(T) − φ)/τ_φ

    (2) Phase kinetics:
        dφ/dt = (φ_eq(T) − φ) / τ_φ

    (3) Algebraic:
        R(T,φ) = R_m^φ * R_i^(1−φ)            [logarithmic mixing]
        I(t) = V(t) / R(T,φ)                   [Ohm's law]
        φ_eq(T) = 1 / (1 + exp(−(T−T_c)/ΔT))  [sigmoid equilibrium]

Derivation
----------
See implementation_plan.md, Layers 1–5 for the complete derivation
from first principles (energy conservation, KJMA nucleation, EMT).

References
----------
[1] Mott, N.F., "Metal-Insulator Transitions", Taylor & Francis (1990).
[2] Kumar, S., et al., Adv. Mater. 25, 6128 (2013).
[3] Pergament, A.L., et al., JSTQE 23(2), 2017.
[4] Berglund, C.N., Guggenheim, H.J., Phys. Rev. 185, 1022 (1969).
[5] Lichtenecker, K., Phys. Z. 27, 115 (1926).
"""

import numpy as np
from typing import Callable, Tuple

from .vox_parameters import VOxParameters


# =====================================================================
# Physical Constants
# =====================================================================

K_BOLTZMANN_EV = 8.617333262e-5  # Boltzmann constant [eV/K]


# =====================================================================
# LAYER 2: Phase Kinetics — Equilibrium Metallic Fraction
# =====================================================================

def phi_equilibrium(T: float, phi: float,
                    params: VOxParameters) -> float:
    """
    Equilibrium metallic fraction φ_eq(T) at temperature T.

    Derivation
    ----------
    For a two-level system (insulating vs metallic) in thermal equilibrium,
    the population of the high-energy (metallic) state follows the
    Fermi-Dirac distribution:

        φ_eq(T) = 1 / (1 + exp(−(T − T_c) / ΔT))

    This is a sigmoid function that:
        - → 0 as T → −∞  (fully insulating at low T)
        - = 0.5 at T = T_c (equal phase fractions at critical temp)
        - → 1 as T → +∞  (fully metallic at high T)

    Hysteresis Handling
    -------------------
    The critical temperature T_c differs for heating vs cooling:

    Mode "direction":
        T_c = T_IMT if dT/dt > 0 (heating)
        T_c = T_MIT if dT/dt ≤ 0 (cooling)
        Note: dT/dt is not available here; we infer direction from
        whether T > T_c_mid or compare with current phi.

    Mode "state_dependent":
        T_c(φ) = T_MIT + (T_IMT − T_MIT) * (1 − φ)
        When φ ≈ 0 (insulating), T_c ≈ T_IMT → hard to start transition
        When φ ≈ 1 (metallic), T_c ≈ T_MIT → hard to revert transition
        This naturally produces hysteresis without discontinuities.

    Parameters
    ----------
    T : float
        Current device temperature [K].
    phi : float
        Current metallic fraction [dimensionless, 0–1].
        Used only for "state_dependent" hysteresis mode.
    params : VOxParameters
        Model parameters.

    Returns
    -------
    float
        Equilibrium metallic fraction φ_eq ∈ [0, 1].

    Units
    -----
    Input: T [K], phi [dimensionless]
    Output: φ_eq [dimensionless]
    """
    if params.hysteresis_mode == "state_dependent":
        # T_c depends on current state: higher T_c when mostly insulating,
        # lower T_c when mostly metallic → creates hysteresis
        T_c = params.T_MIT + (params.T_IMT - params.T_MIT) * (1.0 - phi)
    elif params.hysteresis_mode == "direction":
        # Use midpoint temperature; direction is inferred from which
        # side of the transition the system is on
        T_mid = 0.5 * (params.T_IMT + params.T_MIT)
        if T > T_mid:
            T_c = params.T_IMT  # heating: need to reach T_IMT
        else:
            T_c = params.T_MIT  # cooling: need to drop below T_MIT
    else:
        raise ValueError(
            f"Unknown hysteresis mode: '{params.hysteresis_mode}'. "
            f"Supported: 'state_dependent', 'direction'."
        )

    # Sigmoid with numerically stable computation
    # Clip argument to prevent overflow in exp()
    arg = -(T - T_c) / params.delta_T
    arg = np.clip(arg, -500.0, 500.0)

    return 1.0 / (1.0 + np.exp(arg))


# =====================================================================
# LAYER 3: Resistance Model — R(T, φ)
# =====================================================================

def _resistance_metallic(T: float, params: VOxParameters) -> float:
    """
    Temperature-dependent metallic phase resistance.

    R_m(T) = R_m0 * (1 + α * (T − T_amb))

    Derivation
    ----------
    In the metallic (rutile) phase, conduction is via delocalized
    electrons. The resistance increases linearly with temperature
    due to increased electron-phonon scattering:

        ρ(T) = ρ₀ * (1 + α * (T − T_ref))

    This is the Bloch-Grüneisen relation in the linear regime
    (valid for T > Θ_D/5, where Θ_D is the Debye temperature).

    Parameters
    ----------
    T : float
        Temperature [K].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    float
        Metallic resistance R_m(T) [Ω].
    """
    return params.R_metallic * (1.0 + params.alpha_metallic * (T - params.T_amb))


def _resistance_insulating(T: float, params: VOxParameters) -> float:
    """
    Temperature-dependent insulating phase resistance.

    If use_arrhenius_Ri is True:
        R_i(T) = R_i0_eff * exp(E_g / (2 k_B T))

        where R_i0_eff is chosen so that R_i(T_amb) = R_insulating.

    If use_arrhenius_Ri is False:
        R_i(T) = R_insulating (constant).

    Derivation
    ----------
    In the insulating (monoclinic) phase, charge carriers must be
    thermally activated across the bandgap E_g ≈ 0.6 eV.
    The carrier concentration follows:

        n(T) ∝ exp(−E_g / (2 k_B T))

    so the resistivity:

        ρ(T) ∝ exp(+E_g / (2 k_B T))

    This is the standard semiconductor activation energy model.

    Parameters
    ----------
    T : float
        Temperature [K].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    float
        Insulating resistance R_i(T) [Ω].
    """
    if not params.use_arrhenius_Ri:
        return params.R_insulating

    # Arrhenius form: R_i(T) = R_i0_eff * exp(E_g / (2 k_B T))
    # Normalize so that R_i(T_amb) = R_insulating:
    #   R_i0_eff = R_insulating * exp(−E_g / (2 k_B T_amb))
    # Therefore:
    #   R_i(T) = R_insulating * exp(E_g/(2 k_B) * (1/T − 1/T_amb))
    exponent = (params.E_g / (2.0 * K_BOLTZMANN_EV)) * (1.0 / T - 1.0 / params.T_amb)
    # Clip to prevent overflow
    exponent = np.clip(exponent, -100.0, 100.0)
    return params.R_insulating * np.exp(exponent)


def resistance(T: float, phi: float, params: VOxParameters) -> float:
    """
    Device resistance as a function of temperature and metallic fraction.

    Derivation
    ----------
    The device is a two-phase composite of metallic (σ_m) and
    insulating (σ_i) domains with volume fractions φ and (1−φ).

    Logarithmic mixing (Lichtenecker rule):
        log R = φ * log R_m + (1−φ) * log R_i
        R = R_m^φ * R_i^(1−φ)

    This is the geometric mean of the two resistances, valid for
    a random mixture of phases (Lichtenecker, Phys. Z. 27, 1926).
    It naturally handles the orders-of-magnitude resistance change
    across the MIT.

    Parallel mixing:
        1/R = φ/R_m + (1−φ)/R_i

    Valid when metallic filaments form parallel current paths.

    Bruggeman EMT:
        φ * (σ_m − σ_eff)/(σ_m + 2σ_eff) + (1−φ) * (σ_i − σ_eff)/(σ_i + 2σ_eff) = 0

    Most rigorous; captures percolation threshold at φ_c = 1/3.

    Parameters
    ----------
    T : float
        Device temperature [K].
    phi : float
        Metallic volume fraction [dimensionless, 0–1].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    float
        Device resistance R [Ω].

    Units
    -----
    Input: T [K], phi [dimensionless]
    Output: R [Ω]
    """
    R_m = _resistance_metallic(T, params)
    R_i = _resistance_insulating(T, params)

    # Ensure phi is bounded
    phi_c = np.clip(phi, 0.0, 1.0)

    if params.resistance_model == "logarithmic":
        # R = R_m^φ * R_i^(1−φ)
        # Compute in log space for numerical stability:
        # log R = φ * log(R_m) + (1−φ) * log(R_i)
        log_R = phi_c * np.log(R_m) + (1.0 - phi_c) * np.log(R_i)
        return np.exp(log_R)

    elif params.resistance_model == "parallel":
        # 1/R = φ/R_m + (1−φ)/R_i
        conductance = phi_c / R_m + (1.0 - phi_c) / R_i
        return 1.0 / conductance

    elif params.resistance_model == "bruggeman":
        # Bruggeman EMT: solve for σ_eff numerically
        sigma_m = 1.0 / R_m
        sigma_i = 1.0 / R_i
        sigma_eff = _bruggeman_solve(sigma_m, sigma_i, phi_c)
        return 1.0 / sigma_eff

    else:
        raise ValueError(
            f"Unknown resistance model: '{params.resistance_model}'. "
            f"Supported: 'logarithmic', 'parallel', 'bruggeman'."
        )


def _bruggeman_solve(sigma_m: float, sigma_i: float,
                     phi: float) -> float:
    """
    Solve the Bruggeman effective medium equation for σ_eff.

    Bruggeman equation (3D, spherical inclusions):
        φ * (σ_m − σ_eff)/(σ_m + 2σ_eff) + (1−φ) * (σ_i − σ_eff)/(σ_i + 2σ_eff) = 0

    This is a quadratic in σ_eff. The physically meaningful root
    (positive, between σ_i and σ_m) is selected.

    Derivation
    ----------
    Rearranging the Bruggeman equation:
        φ*(σ_m − σ)(σ_i + 2σ) + (1−φ)*(σ_i − σ)(σ_m + 2σ) = 0

    Expanding:
        a*σ² + b*σ + c = 0

    where:
        a = −3
        b = (3φ − 1)*σ_m + (2 − 3φ)*σ_i
        c = σ_m * σ_i

    (Derivation verified by symbolic expansion.)

    Parameters
    ----------
    sigma_m : float
        Metallic conductivity [S].
    sigma_i : float
        Insulating conductivity [S].
    phi : float
        Metallic fraction [0–1].

    Returns
    -------
    float
        Effective conductivity σ_eff [S].
    """
    # Quadratic coefficients
    a = -3.0
    b = (3.0 * phi - 1.0) * sigma_m + (2.0 - 3.0 * phi) * sigma_i
    c = sigma_m * sigma_i

    # Discriminant
    discriminant = b * b - 4.0 * a * c

    if discriminant < 0:
        # Fallback: use logarithmic mixing
        return np.exp(phi * np.log(sigma_m) + (1.0 - phi) * np.log(sigma_i))

    sqrt_disc = np.sqrt(discriminant)

    # Two roots
    root1 = (-b + sqrt_disc) / (2.0 * a)
    root2 = (-b - sqrt_disc) / (2.0 * a)

    # Select the positive root that lies between σ_i and σ_m
    sigma_min = min(sigma_m, sigma_i)
    sigma_max = max(sigma_m, sigma_i)

    for root in [root1, root2]:
        if sigma_min <= root <= sigma_max:
            return root

    # If no root in range, return the positive one
    if root1 > 0:
        return root1
    if root2 > 0:
        return root2

    # Ultimate fallback
    return np.exp(phi * np.log(sigma_m) + (1.0 - phi) * np.log(sigma_i))


# =====================================================================
# LAYER 4: Electrical Equation — Ohm's Law
# =====================================================================

def current(V: float, T: float, phi: float,
            params: VOxParameters) -> float:
    """
    Device current from Ohm's law.

    I = V / R(T, φ)

    Derivation
    ----------
    For a purely resistive element (no parasitic capacitance or
    inductance), Ohm's law gives the instantaneous current.
    This is valid when:
        1. The device dimensions ≪ wavelength of the applied signal
        2. The operating frequency ≪ 1/RC_parasitic
    Both conditions are satisfied for typical VO₂ thin-film devices
    at frequencies below ~GHz.

    Parameters
    ----------
    V : float
        Applied voltage [V].
    T : float
        Device temperature [K].
    phi : float
        Metallic fraction [dimensionless, 0–1].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    float
        Device current I [A].

    Units
    -----
    Input: V [V], T [K], phi [dimensionless]
    Output: I [A]
    """
    R = resistance(T, phi, params)
    return V / R


# =====================================================================
# LAYER 5: Coupled ODE System — Right-Hand Side
# =====================================================================

def system_rhs(t: float, state: np.ndarray,
               V_func: Callable[[float], float],
               params: VOxParameters) -> np.ndarray:
    """
    Right-hand side of the coupled electro-thermal ODE system.

    State vector: y = [T, φ]

    Equations
    ---------
    (1) Thermal (energy conservation):
        C_th * dT/dt = V²/R(T,φ) − G_th*(T − T_amb) − L*(φ_eq − φ)/τ_φ

        Derivation: First Law of Thermodynamics applied to a lumped
        thermal mass. The three terms are:
        - V²/R: Joule heating power [W]
        - G_th*(T − T_amb): Newton's law cooling [W]
        - L*(φ_eq − φ)/τ_φ: Latent heat absorption/release [W]
          (substituted dφ/dt directly to keep the system explicit)

    (2) Phase kinetics (KJMA-motivated relaxation):
        dφ/dt = (φ_eq(T) − φ) / τ_φ

        Derivation: Nucleation-and-growth dynamics in the KJMA framework,
        simplified to a first-order relaxation toward the temperature-
        dependent equilibrium fraction.

    Parameters
    ----------
    t : float
        Current time [s].
    state : np.ndarray
        State vector [T, φ]:
            state[0] = T [K], device temperature
            state[1] = φ [dimensionless], metallic fraction
    V_func : Callable[[float], float]
        Voltage waveform function V(t) [V].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    np.ndarray
        Time derivatives [dT/dt, dφ/dt]:
            dydt[0] = dT/dt [K/s]
            dydt[1] = dφ/dt [1/s]

    Dimensional Analysis
    --------------------
    dT/dt:
        [W] / [J/K] = [K/s]  ✓
        Numerator: V²/R [W] − G_th*(T−T_amb) [W/K·K = W] − L*dφ/dt [J·s⁻¹ = W]
        Denominator: C_th [J/K]

    dφ/dt:
        [dimensionless] / [s] = [1/s]  ✓
    """
    T = state[0]
    phi = state[1]

    # Enforce physical bounds (soft clamping for solver stability)
    phi = np.clip(phi, 0.0, 1.0)

    # Applied voltage at time t
    V = V_func(t)

    # Device resistance [Ω]
    R = resistance(T, phi, params)

    # Joule heating power: P = V²/R [W]
    P_joule = V * V / R

    # Newton's law cooling: P_cool = G_th * (T − T_amb) [W]
    P_cool = params.G_th * (T - params.T_amb)

    # Equilibrium metallic fraction at current temperature
    phi_eq = phi_equilibrium(T, phi, params)

    # Phase kinetics: dφ/dt = (φ_eq − φ) / τ_φ [1/s]
    dphi_dt = (phi_eq - phi) / params.tau_phi

    # Latent heat power: P_latent = L * dφ/dt [W]
    # Positive dφ/dt (transition to metal) absorbs heat
    # Negative dφ/dt (transition to insulator) releases heat
    P_latent = params.L_latent * dphi_dt

    # Thermal equation: C_th * dT/dt = P_joule − P_cool − P_latent
    dT_dt = (P_joule - P_cool - P_latent) / params.C_th

    return np.array([dT_dt, dphi_dt])


def compute_outputs(t_array: np.ndarray, T_array: np.ndarray,
                    phi_array: np.ndarray,
                    V_func: Callable[[float], float],
                    params: VOxParameters) -> dict:
    """
    Compute all output quantities from the solved state trajectories.

    After solve_ivp returns T(t) and φ(t), this function computes
    the derived quantities: V, I, R, P, P_joule, P_cool.

    Parameters
    ----------
    t_array : np.ndarray
        Time points [s], shape (N,).
    T_array : np.ndarray
        Temperature trajectory [K], shape (N,).
    phi_array : np.ndarray
        Metallic fraction trajectory [dimensionless], shape (N,).
    V_func : Callable[[float], float]
        Voltage waveform function V(t).
    params : VOxParameters
        Model parameters.

    Returns
    -------
    dict
        Dictionary with keys:
            't'       : time [s]
            'T'       : temperature [K]
            'phi'     : metallic fraction [-]
            'V'       : voltage [V]
            'I'       : current [A]
            'R'       : resistance [Ω]
            'P'       : instantaneous power V*I [W]
            'P_joule' : Joule heating power V²/R [W]
            'P_cool'  : cooling power G_th*(T−T_amb) [W]
    """
    N = len(t_array)

    V_array = np.array([V_func(t) for t in t_array])
    R_array = np.array([
        resistance(T_array[i], phi_array[i], params) for i in range(N)
    ])
    I_array = V_array / R_array
    P_array = V_array * I_array
    P_joule_array = V_array ** 2 / R_array
    P_cool_array = params.G_th * (T_array - params.T_amb)

    return {
        't': t_array,
        'T': T_array,
        'phi': phi_array,
        'V': V_array,
        'I': I_array,
        'R': R_array,
        'P': P_array,
        'P_joule': P_joule_array,
        'P_cool': P_cool_array,
    }

# =====================================================================
# LAYER 5b: Coupled ODE System — Current-Bias Mode
# =====================================================================

def system_rhs_current_bias(t: float, state: np.ndarray,
                            I_func: Callable[[float], float],
                            params: VOxParameters) -> np.ndarray:
    """
    Right-hand side of the coupled electro-thermal ODE system in
    CURRENT-BIAS mode.

    In current-biased experiments, the current I(t) is the controlled
    input and the voltage V = I·R is the measured output.

    State vector: y = [T, φ]

    Equations
    ---------
    (1) Thermal (energy conservation):
        C_th * dT/dt = I²(t)·R(T,φ) − G_th*(T − T_amb) − L*(φ_eq − φ)/τ_φ

        Key difference from voltage bias: Joule heating is P = I²·R.
        When R drops (MIT), P_joule DECREASES (self-limiting).
        This is the opposite of voltage bias where P = V²/R INCREASES.

    (2) Phase kinetics (unchanged):
        dφ/dt = (φ_eq(T) − φ) / τ_φ

    Parameters
    ----------
    t : float
        Current time [s].
    state : np.ndarray
        State vector [T, φ].
    I_func : Callable[[float], float]
        Current waveform function I(t) [A].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    np.ndarray
        Time derivatives [dT/dt, dφ/dt].
    """
    T = state[0]
    phi = state[1]

    # Enforce physical bounds
    phi = np.clip(phi, 0.0, 1.0)

    # Applied current at time t
    I = I_func(t)

    # Device resistance [Ω]
    R = resistance(T, phi, params)

    # Joule heating power: P = I²·R [W] (current-bias)
    P_joule = I * I * R

    # Newton's law cooling: P_cool = G_th * (T − T_amb) [W]
    P_cool = params.G_th * (T - params.T_amb)

    # Equilibrium metallic fraction
    phi_eq = phi_equilibrium(T, phi, params)

    # Phase kinetics: dφ/dt = (φ_eq − φ) / τ_φ [1/s]
    dphi_dt = (phi_eq - phi) / params.tau_phi

    # Latent heat power: P_latent = L * dφ/dt [W]
    P_latent = params.L_latent * dphi_dt

    # Thermal equation: C_th * dT/dt = P_joule − P_cool − P_latent
    dT_dt = (P_joule - P_cool - P_latent) / params.C_th

    return np.array([dT_dt, dphi_dt])


def compute_outputs_current_bias(t_array: np.ndarray, T_array: np.ndarray,
                                 phi_array: np.ndarray,
                                 I_func: Callable[[float], float],
                                 params: VOxParameters) -> dict:
    """
    Compute all output quantities for CURRENT-BIASED simulations.

    After solve_ivp returns T(t) and φ(t), this function computes
    V = I·R and all derived power quantities.

    Parameters
    ----------
    t_array : np.ndarray
        Time points [s].
    T_array : np.ndarray
        Temperature trajectory [K].
    phi_array : np.ndarray
        Metallic fraction trajectory [dimensionless].
    I_func : Callable[[float], float]
        Current waveform function I(t) [A].
    params : VOxParameters
        Model parameters.

    Returns
    -------
    dict
        Dictionary with all output arrays.
    """
    N = len(t_array)

    I_array = np.array([I_func(t) for t in t_array])
    R_array = np.array([
        resistance(T_array[i], phi_array[i], params) for i in range(N)
    ])
    V_array = I_array * R_array  # V = I·R (Ohm's law, current bias)
    P_array = V_array * I_array
    P_joule_array = I_array ** 2 * R_array  # P = I²·R
    P_cool_array = params.G_th * (T_array - params.T_amb)

    return {
        't': t_array,
        'T': T_array,
        'phi': phi_array,
        'V': V_array,
        'I': I_array,
        'R': R_array,
        'P': P_array,
        'P_joule': P_joule_array,
        'P_cool': P_cool_array,
    }
