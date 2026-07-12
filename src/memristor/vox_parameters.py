"""
VOx Memristor Electro-Thermal Model — Parameter Definitions
=============================================================

This module defines all physical and simulation parameters for the
electro-thermal compact model of a VOx (VO₂) memristor undergoing a
Metal-Insulator Transition (MIT).

Every parameter includes:
    - Physical meaning
    - SI units
    - Typical value range
    - Reference to the equation where it appears

The parameters are organized into four categories:
    1. Thermal parameters — govern heat dynamics
    2. MIT transition parameters — govern phase kinetics
    3. Electrical parameters — govern resistance and conduction
    4. Simulation parameters — control numerics and input waveforms

References
----------
[1] Mott, N.F., "Metal-Insulator Transitions", Taylor & Francis (1990).
[2] Pergament, A.L., et al., "Oxide Electronics and Vanadium Dioxide
    Perspective", JSTQE 23(2), 2017.
[3] Kumar, S., et al., "Local Temperature Redistribution and Structural
    Transition During Joule-Heating-Driven Conductance Switching in VO₂",
    Adv. Mater. 25(42), 2013.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class VOxParameters:
    """
    Complete parameter set for the VOx electro-thermal MIT memristor model.

    The model solves two coupled ODEs:

        C_th * dT/dt = V²/R(T,φ) − G_th*(T − T_amb) − L * dφ/dt
        dφ/dt = (φ_eq(T) − φ) / τ_φ

    with:
        R(T,φ) = R_m^φ * R_i^(1−φ)       (logarithmic mixing)
        φ_eq(T) = 1 / (1 + exp(−(T − T_c)/ΔT))  (sigmoid)
        I(t) = V(t) / R(T,φ)              (Ohm's law)
    """

    # =================================================================
    # THERMAL PARAMETERS
    # =================================================================
    # Govern the heat balance equation (Layer 1 of the derivation).

    C_th: float = 3.0e-10
    """Thermal capacitance [J/K].

    Lumped thermal mass of the VO₂ device plus immediate substrate region.
    C_th = ρ * c_p * Volume, where ρ is density, c_p is specific heat,
    and Volume is the effective heated volume.

    Typical range: 10⁻¹² – 10⁻⁹ J/K for thin-film devices.

    Appears in: C_th * dT/dt = V²/R − G_th*(T − T_amb) − L*dφ/dt
    """

    G_th: float = 1.5e-5
    """Thermal conductance to the heat sink [W/K].

    Governs the rate of heat dissipation from the device to the substrate
    and ambient environment via Newton's law of cooling.
    G_th = k_sub * A / L_sub, where k_sub is substrate thermal conductivity,
    A is device cross-sectional area, and L_sub is thermal path length.

    Typical range: 10⁻⁶ – 10⁻⁴ W/K.

    The thermal time constant is τ_th = C_th / G_th.

    Appears in: C_th * dT/dt = V²/R − G_th*(T − T_amb) − L*dφ/dt
    """

    T_amb: float = 300.0
    """Ambient (heat sink) temperature [K].

    Reference temperature of the thermal reservoir. Typically room
    temperature (~300 K = 27°C).

    Appears in: G_th * (T − T_amb)
    """

    L_latent: float = 5.0e-10
    """Latent heat of the MIT phase transition [J].

    Energy absorbed (heating) or released (cooling) during the structural
    phase transition from monoclinic (insulating) to rutile (metallic).

    L = l_v * Volume, where l_v ≈ 2.5 × 10⁸ J/m³ is the volumetric
    latent heat of VO₂ [Ref: Berglund & Guggenheim, Phys. Rev. 185, 1969].

    Setting L = 0 disables latent heat effects.

    Appears in: C_th * dT/dt = V²/R − G_th*(T − T_amb) − L*dφ/dt
    """

    # =================================================================
    # MIT TRANSITION PARAMETERS
    # =================================================================
    # Govern the phase kinetics equation (Layer 2 of the derivation).

    T_IMT: float = 315.0
    """Insulator-to-Metal transition temperature (heating) [K].

    Critical temperature above which the metallic phase becomes
    thermodynamically stable during HEATING.

    For our calibrated thin-film model: T_IMT = 315 K.
    Can be tuned by doping (e.g., W lowers it ~26 K per at.% W)
    or substrate strain.

    Appears in: φ_eq(T) via T_c (when dT/dt > 0)
    """

    T_MIT: float = 298.0
    """Metal-to-Insulator transition temperature (cooling) [K].

    Critical temperature below which the insulating phase becomes
    thermodynamically stable during COOLING.

    T_MIT < T_IMT always (this difference produces hysteresis).
    The hysteresis width is ΔT_hyst = T_IMT − T_MIT ≈ 5–20 K.

    Appears in: φ_eq(T) via T_c (when dT/dt ≤ 0)
    """

    delta_T: float = 3.0
    """Transition width (sharpness) [K].

    Controls how abruptly the phase transition occurs in temperature
    space. Smaller values → sharper transition → more switch-like.

    Physically related to the distribution of local transition
    temperatures across different grains and domains.

    Typical range: 1–10 K.

    Appears in: φ_eq(T) = 1 / (1 + exp(−(T − T_c) / ΔT))
    """

    tau_phi: float = 1.0e-7
    """Phase relaxation time [s].

    Time constant for the metallic fraction to approach its equilibrium
    value. Governs how quickly domains nucleate and grow (or shrink).

    Physically: τ_φ ∝ τ₀ * exp(E_a / k_B T) for Arrhenius kinetics.
    Here we use a constant τ_φ as a first approximation.

    Typical range: 10⁻⁹ – 10⁻⁶ s for VO₂ thin films.

    Appears in: dφ/dt = (φ_eq(T) − φ) / τ_φ
    """

    hysteresis_mode: str = "state_dependent"
    """Hysteresis implementation mode.

    Options:
        "direction"       — Use T_IMT when dT/dt > 0, T_MIT when dT/dt ≤ 0.
                            Simple but introduces a discontinuity in the ODE
                            right-hand side at dT/dt = 0.
        "state_dependent" — T_c(φ) = T_MIT + (T_IMT − T_MIT) * (1 − φ).
                            Smooth, continuous, no discontinuities.
                            The effective transition temperature depends on
                            the current metallic fraction.

    Default: "state_dependent" (recommended for numerical stability).
    """

    # =================================================================
    # ELECTRICAL PARAMETERS
    # =================================================================
    # Govern the resistance model (Layer 3 of the derivation).

    R_metallic: float = 500.0
    """Resistance in the fully metallic state (φ = 1) [Ω].

    Low-resistance state after complete insulator-to-metal transition.
    Determined by the resistivity of the rutile metallic phase and
    device geometry: R_m = ρ_m * L / A.

    Typical range: 10² – 10³ Ω.

    Appears in: R(T,φ) = R_m^φ * R_i^(1−φ)
    """

    R_insulating: float = 50000.0
    """Resistance in the fully insulating state (φ = 0) [Ω].

    High-resistance state of the monoclinic insulating phase.
    R_i = ρ_i * L / A, where ρ_i ≫ ρ_m.

    The resistance ratio R_i/R_m is typically 10²–10⁴ for VO₂.

    Typical range: 10⁴ – 10⁶ Ω.

    Appears in: R(T,φ) = R_m^φ * R_i^(1−φ)
    """

    use_arrhenius_Ri: bool = False
    """Whether to include Arrhenius temperature dependence in R_i.

    If True: R_i(T) = R_i0 * exp(E_g / (2 * k_B * T))
    If False: R_i(T) = R_insulating (constant).

    The Arrhenius form captures the activated hopping conduction
    in the insulating phase. Disabled by default for simplicity.
    """

    E_g: float = 0.3
    """Activation energy for insulating-phase conduction [eV].

    Half the optical bandgap of insulating VO₂ (≈ 0.6 eV),
    used in the Arrhenius expression for R_i(T).

    Only used when use_arrhenius_Ri = True.

    Appears in: R_i(T) = R_i0 * exp(E_g / (2 * k_B * T))
    """

    alpha_metallic: float = 1.0e-3
    """Temperature coefficient of metallic resistance [1/K].

    Weak linear temperature dependence of the metallic phase:
    R_m(T) = R_m0 * (1 + α * (T − T_ref)).

    Typical for metals: α ≈ 10⁻³ K⁻¹.

    Set to 0 to disable this correction.

    Appears in: R_m(T) = R_m0 * (1 + α * (T − T_ref))
    """

    resistance_model: str = "logarithmic"
    """Resistance mixing rule for the two-phase composite.

    Options:
        "logarithmic" — log R = φ*log(R_m) + (1−φ)*log(R_i)
                         Lichtenecker rule for disordered composites.
                         Handles multi-decade R changes naturally.
        "parallel"    — 1/R = φ/R_m + (1−φ)/R_i
                         Valid for parallel filamentary conduction.
        "bruggeman"   — Bruggeman EMT (solved numerically).
                         Most rigorous, captures percolation threshold.

    Default: "logarithmic" (recommended for Stage 1).
    """

    # =================================================================
    # SIMULATION PARAMETERS
    # =================================================================
    # Control the voltage waveform and numerical solver.

    bias_mode: str = "voltage"
    """Bias mode for the simulation.

    Options:
        "voltage" — Voltage is the controlled input V(t).
        "current" — Current is the controlled input I(t).
    """

    V_amplitude: float = 3.0
    """Voltage amplitude [V].

    Peak amplitude of the applied voltage waveform.
    Must be large enough to drive sufficient Joule heating
    to reach T_IMT.

    Typical range: 0.5 – 10 V depending on device geometry.
    """

    frequency: float = 1.0e4
    """Voltage frequency [Hz].

    Frequency of the periodic voltage waveform.
    Should be chosen relative to the thermal time constant:
        f ≪ 1/τ_th → quasi-static (full switching each cycle)
        f ≫ 1/τ_th → too fast for thermal response

    Typical range: 10² – 10⁶ Hz.
    """

    waveform_type: str = "sinusoidal"
    """Type of voltage waveform.

    Options: "sinusoidal", "triangular", "pulse", "dc_sweep".
    """

    n_cycles: int = 3
    """Number of voltage cycles to simulate.

    More cycles show sweep-to-sweep evolution.
    """

    duty_cycle: float = 0.5
    """Duty cycle for pulse waveform [dimensionless, 0–1].

    Fraction of the period during which the pulse is HIGH.
    Only used when waveform_type = "pulse".
    """

    dc_sweep_rate: float = 1.0
    """DC sweep rate [V/s].

    Rate of voltage change for linear DC sweep.
    Only used when waveform_type = "dc_sweep".
    """

    # =================================================================
    # SOLVER PARAMETERS
    # =================================================================

    rtol: float = 1e-8
    """Relative tolerance for the ODE solver [dimensionless].

    Controls the accuracy of the adaptive time stepping in solve_ivp.
    Tighter tolerances improve accuracy at the cost of computation time.
    """

    atol: float = 1e-10
    """Absolute tolerance for the ODE solver [dimensionless].

    Prevents the solver from taking excessively large steps when
    state variables are near zero.
    """

    max_step: float = 0.0
    """Maximum step size for the ODE solver [s].

    If 0.0, it is automatically set to 1/(100*frequency) to ensure
    adequate temporal resolution of the voltage waveform.
    """

    # =================================================================
    # INITIAL CONDITIONS
    # =================================================================

    T_initial: float = 300.0
    """Initial device temperature [K].

    Usually set to T_amb (device starts at thermal equilibrium).
    """

    phi_initial: float = 0.0
    """Initial metallic fraction [dimensionless].

    0.0 = fully insulating (device starts in HRS).
    1.0 = fully metallic (device starts in LRS).
    """

    # =================================================================
    # DERIVED QUANTITIES (computed, not user-set)
    # =================================================================

    @property
    def tau_thermal(self) -> float:
        """Thermal time constant [s].

        τ_th = C_th / G_th

        Sets the characteristic thermal response time of the device.
        The device can only switch if the voltage waveform period is
        comparable to or longer than τ_th.
        """
        return self.C_th / self.G_th

    @property
    def resistance_ratio(self) -> float:
        """On/off resistance ratio R_i / R_m [dimensionless].

        A key figure of merit for memristive devices.
        Typical values for VO₂: 10² – 10⁴.
        """
        return self.R_insulating / self.R_metallic

    @property
    def simulation_time(self) -> float:
        """Total simulation time [s].

        Computed from frequency and number of cycles.
        For DC sweep, computed from amplitude and sweep rate.
        """
        if self.waveform_type == "dc_sweep":
            # Full sweep: -V_amp → +V_amp → -V_amp
            return 4.0 * self.V_amplitude / self.dc_sweep_rate
        return self.n_cycles / self.frequency

    @property
    def effective_max_step(self) -> float:
        """Effective maximum ODE solver step size [s].

        Automatically computed if user does not set max_step.
        Ensures at least 100 points per voltage cycle.
        """
        if self.max_step > 0:
            return self.max_step
        if self.waveform_type == "dc_sweep":
            return self.simulation_time / 1000.0
        return 1.0 / (200.0 * self.frequency)

    @property
    def hysteresis_width(self) -> float:
        """Thermal hysteresis width [K].

        ΔT_hyst = T_IMT − T_MIT.
        """
        return self.T_IMT - self.T_MIT

    def summary(self) -> str:
        """Print a formatted summary of all parameters and derived quantities."""
        lines = [
            "=" * 65,
            "VOx Electro-Thermal MIT Memristor — Parameter Summary",
            "=" * 65,
            "",
            "THERMAL PARAMETERS",
            f"  C_th         = {self.C_th:.2e} J/K    (thermal capacitance)",
            f"  G_th         = {self.G_th:.2e} W/K    (thermal conductance)",
            f"  T_amb        = {self.T_amb:.1f} K        (ambient temperature)",
            f"  L_latent     = {self.L_latent:.2e} J      (latent heat)",
            f"  τ_thermal    = {self.tau_thermal:.2e} s      (thermal time const.)",
            "",
            "MIT TRANSITION PARAMETERS",
            f"  T_IMT        = {self.T_IMT:.1f} K        (heating transition)",
            f"  T_MIT        = {self.T_MIT:.1f} K        (cooling transition)",
            f"  ΔT_hyst      = {self.hysteresis_width:.1f} K         (hysteresis width)",
            f"  ΔT (width)   = {self.delta_T:.1f} K          (transition sharpness)",
            f"  τ_φ          = {self.tau_phi:.2e} s      (phase relaxation)",
            f"  hysteresis   = {self.hysteresis_mode}",
            "",
            "ELECTRICAL PARAMETERS",
            f"  R_metallic   = {self.R_metallic:.1f} Ω     (LRS resistance)",
            f"  R_insulating = {self.R_insulating:.1f} Ω  (HRS resistance)",
            f"  R_i / R_m    = {self.resistance_ratio:.1f}       (on/off ratio)",
            f"  R model      = {self.resistance_model}",
            f"  Arrhenius Ri = {self.use_arrhenius_Ri}",
            "",
            "SIMULATION PARAMETERS",
            f"  V_amplitude  = {self.V_amplitude:.2f} V",
            f"  frequency    = {self.frequency:.2e} Hz",
            f"  waveform     = {self.waveform_type}",
            f"  n_cycles     = {self.n_cycles}",
            f"  sim time     = {self.simulation_time:.2e} s",
            f"  max_step     = {self.effective_max_step:.2e} s",
            "",
            "INITIAL CONDITIONS",
            f"  T₀           = {self.T_initial:.1f} K",
            f"  φ₀           = {self.phi_initial:.4f}",
            "=" * 65,
        ]
        return "\n".join(lines)
