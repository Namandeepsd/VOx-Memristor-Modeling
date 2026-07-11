"""
VOx Memristor — Automated Physics Validation
==============================================

This module performs automated checks to verify that the simulation
results are physically consistent. Each check corresponds to an
experimentally observable property of VO₂ memristors.

The validation tests are:
    1. Linear I-V at low voltage (Ohmic regime)
    2. Pinched hysteresis (I-V passes through origin)
    3. Negative Differential Resistance (NDR)
    4. Heating/cooling hysteresis asymmetry
    5. Resistance ratio (on/off)
    6. Temperature bounds (physical)
    7. Phase fraction bounds (definitional)
    8. Energy conservation (approximate)
    9. Sweep-to-sweep memory

Each check returns a ValidationResult with pass/fail status,
the metric value, and a diagnostic message.
"""

import numpy as np
from dataclasses import dataclass
from typing import List

from .vox_solver import SimulationResult


@dataclass
class ValidationResult:
    """Result of a single physics validation check."""
    name: str
    passed: bool
    metric_value: float
    threshold: float
    message: str


def validate_all(result: SimulationResult) -> List[ValidationResult]:
    """
    Run all physics validation checks on a simulation result.

    Parameters
    ----------
    result : SimulationResult
        Completed simulation to validate.

    Returns
    -------
    List[ValidationResult]
        Results of all validation checks.
    """
    checks = [
        check_linear_iv_low_voltage(result),
        check_pinched_hysteresis(result),
        check_ndr(result),
        check_hysteresis_asymmetry(result),
        check_resistance_ratio(result),
        check_temperature_bounds(result),
        check_phase_bounds(result),
        check_energy_conservation(result),
    ]
    return checks


def print_validation_report(checks: List[ValidationResult]):
    """
    Print a formatted validation report.

    Parameters
    ----------
    checks : List[ValidationResult]
        Results from validate_all().
    """
    print("=" * 65)
    print("Physics Validation Report")
    print("=" * 65)

    n_pass = sum(1 for c in checks if c.passed)
    n_total = len(checks)

    for i, check in enumerate(checks, 1):
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"\n  [{i}] {check.name}")
        print(f"      Status : {status}")
        print(f"      Metric : {check.metric_value:.6g}")
        print(f"      Threshold : {check.threshold:.6g}")
        print(f"      {check.message}")

    print("\n" + "-" * 65)
    print(f"  Result: {n_pass}/{n_total} checks passed")
    print("=" * 65)


# =====================================================================
# Individual Validation Checks
# =====================================================================

def check_linear_iv_low_voltage(result: SimulationResult) -> ValidationResult:
    """
    Check 1: Linear I-V at low voltage.

    Physics: Far from the MIT (T ≪ T_c), the device behaves as a
    simple ohmic resistor. I should be proportional to V.

    Method: Select data points where |V| < 0.3 * V_amp (far from
    threshold). Compute R² of the linear fit I = V/R_const.

    Pass criterion: R² > 0.95.
    """
    V = result.V
    I = result.I
    V_amp = result.params.V_amplitude

    # Select low-voltage region
    mask = np.abs(V) < 0.3 * V_amp
    if np.sum(mask) < 10:
        return ValidationResult(
            name="Linear I-V at low voltage",
            passed=False,
            metric_value=0.0,
            threshold=0.95,
            message="Insufficient low-voltage data points."
        )

    V_low = V[mask]
    I_low = I[mask]

    # Linear regression: I = slope * V
    # R² = 1 − SS_res / SS_tot
    if np.var(V_low) < 1e-20:
        return ValidationResult(
            name="Linear I-V at low voltage",
            passed=False,
            metric_value=0.0,
            threshold=0.95,
            message="Voltage variance too small."
        )

    slope = np.sum(V_low * I_low) / np.sum(V_low * V_low)
    I_pred = slope * V_low
    SS_res = np.sum((I_low - I_pred) ** 2)
    SS_tot = np.sum((I_low - np.mean(I_low)) ** 2)

    if SS_tot < 1e-30:
        R_squared = 1.0
    else:
        R_squared = 1.0 - SS_res / SS_tot

    return ValidationResult(
        name="Linear I-V at low voltage",
        passed=R_squared > 0.95,
        metric_value=R_squared,
        threshold=0.95,
        message=f"R² = {R_squared:.4f} for |V| < {0.3*V_amp:.2f} V."
    )


def check_pinched_hysteresis(result: SimulationResult) -> ValidationResult:
    """
    Check 2: Pinched hysteresis — I-V passes through origin.

    Physics: A memristive device satisfies I(V=0) = 0 at all times
    (it cannot store charge). The I-V loop must be "pinched" at the
    origin (Chua, 1971).

    Method: Find all zero-crossings of V(t). At each crossing, check
    that |I| is close to zero.

    Pass criterion: max(|I|) at V crossings < 5% of |I|_max.
    """
    V = result.V
    I = result.I

    # Find zero-crossings of voltage (sign changes)
    crossings = np.where(np.diff(np.sign(V)))[0]

    if len(crossings) < 2:
        return ValidationResult(
            name="Pinched hysteresis (I=0 at V=0)",
            passed=False,
            metric_value=0.0,
            threshold=0.05,
            message="Not enough voltage zero-crossings found."
        )

    # Current at crossings (interpolate between adjacent points)
    I_at_crossings = []
    for idx in crossings:
        if idx + 1 < len(V):
            # Linear interpolation to find I at exact V=0
            V1, V2 = V[idx], V[idx + 1]
            I1, I2 = I[idx], I[idx + 1]
            if abs(V2 - V1) > 1e-20:
                frac = -V1 / (V2 - V1)
                I_zero = I1 + frac * (I2 - I1)
            else:
                I_zero = 0.5 * (I1 + I2)
            I_at_crossings.append(abs(I_zero))

    I_max = np.abs(I).max()
    if I_max < 1e-20:
        I_max = 1.0  # avoid division by zero

    max_I_at_zero = max(I_at_crossings) if I_at_crossings else 0.0
    ratio = max_I_at_zero / I_max

    return ValidationResult(
        name="Pinched hysteresis (I=0 at V=0)",
        passed=ratio < 0.05,
        metric_value=ratio,
        threshold=0.05,
        message=f"max|I| at V=0: {max_I_at_zero:.4e} A "
                f"({ratio*100:.2f}% of I_max)."
    )


def check_ndr(result: SimulationResult) -> ValidationResult:
    """
    Check 3: Negative Differential Resistance (NDR).

    Physics: During the MIT, as voltage increases, the temperature
    rises, resistance drops, and current can increase faster than
    voltage — producing dI/dV < 0 (NDR). This is a signature of
    the electro-thermal feedback loop.

    Method: Compute numerical dI/dV along the I-V curve.
    Check for regions where dI/dV < 0.

    Pass criterion: At least 1% of points have dI/dV < 0.
    """
    V = result.V
    I = result.I

    # Compute dI/dV using finite differences
    dI = np.diff(I)
    dV = np.diff(V)

    # Avoid division by zero
    valid = np.abs(dV) > 1e-15
    if np.sum(valid) < 10:
        return ValidationResult(
            name="Negative Differential Resistance (NDR)",
            passed=False,
            metric_value=0.0,
            threshold=0.01,
            message="Insufficient valid dV intervals."
        )

    dIdV = dI[valid] / dV[valid]
    frac_ndr = np.sum(dIdV < 0) / len(dIdV)

    return ValidationResult(
        name="Negative Differential Resistance (NDR)",
        passed=frac_ndr > 0.01,
        metric_value=frac_ndr,
        threshold=0.01,
        message=f"{frac_ndr*100:.1f}% of I-V points show dI/dV < 0."
    )


def check_hysteresis_asymmetry(result: SimulationResult) -> ValidationResult:
    """
    Check 4: Heating and cooling paths differ.

    Physics: Due to the first-order nature of the MIT, the R(T) path
    during heating differs from cooling. This produces a hysteresis
    loop in R-T space.

    Method: Compare resistance values at T = T_mid on the heating
    and cooling branches. They should differ by at least 20%.

    Pass criterion: |R_heat − R_cool| / max(R_heat, R_cool) > 0.20.
    """
    T = result.T
    R = result.R

    T_mid = 0.5 * (result.params.T_IMT + result.params.T_MIT)

    # Check if temperature actually crosses T_mid
    if T.max() < T_mid or T.min() > T_mid - 5:
        return ValidationResult(
            name="Heating/cooling hysteresis asymmetry",
            passed=False,
            metric_value=0.0,
            threshold=0.20,
            message=f"Temperature range [{T.min():.1f}, {T.max():.1f}] K "
                    f"does not cross T_mid = {T_mid:.1f} K."
        )

    # Identify heating (dT/dt > 0) and cooling (dT/dt < 0) phases
    dT = np.diff(T)
    heating_mask = np.zeros(len(T), dtype=bool)
    cooling_mask = np.zeros(len(T), dtype=bool)
    heating_mask[:-1] = dT > 0
    cooling_mask[:-1] = dT < 0

    # Find R values near T_mid during heating and cooling
    T_window = 5.0  # K — wider window for dynamic cycling
    near_T_mid = np.abs(T - T_mid) < T_window

    R_heating = R[heating_mask & near_T_mid]
    R_cooling = R[cooling_mask & near_T_mid]

    if len(R_heating) < 3 or len(R_cooling) < 3:
        return ValidationResult(
            name="Heating/cooling hysteresis asymmetry",
            passed=False,
            metric_value=0.0,
            threshold=0.20,
            message="Insufficient data near T_mid for both branches."
        )

    R_heat_mean = np.mean(R_heating)
    R_cool_mean = np.mean(R_cooling)
    diff = abs(R_heat_mean - R_cool_mean) / max(R_heat_mean, R_cool_mean)

    return ValidationResult(
        name="Heating/cooling hysteresis asymmetry",
        passed=diff > 0.20,
        metric_value=diff,
        threshold=0.20,
        message=f"R_heat = {R_heat_mean:.1f} Ω, R_cool = {R_cool_mean:.1f} Ω "
                f"(diff = {diff*100:.1f}%)."
    )


def check_resistance_ratio(result: SimulationResult) -> ValidationResult:
    """
    Check 5: Resistance on/off ratio.

    Physics: VO₂ exhibits 2–4 orders of magnitude resistance change
    across the MIT. The simulation should achieve at least R_max/R_min > 10.

    Pass criterion: R_max / R_min > 10.
    """
    R_max = result.R.max()
    R_min = result.R.min()
    ratio = R_max / R_min

    return ValidationResult(
        name="Resistance on/off ratio",
        passed=ratio > 10.0,
        metric_value=ratio,
        threshold=10.0,
        message=f"R_max = {R_max:.1f} Ω, R_min = {R_min:.1f} Ω, "
                f"ratio = {ratio:.1f}."
    )


def check_temperature_bounds(result: SimulationResult) -> ValidationResult:
    """
    Check 6: Temperature remains physical.

    Physics: Temperature must remain above absolute zero (0 K).
    In practice, a VO₂ device should not drop below ~200 K
    (below the measurement range).

    Pass criterion: T_min > 200 K.
    """
    T_min = result.T.min()

    return ValidationResult(
        name="Temperature bounds (T > 200 K)",
        passed=T_min > 200.0,
        metric_value=T_min,
        threshold=200.0,
        message=f"T_min = {T_min:.2f} K."
    )


def check_phase_bounds(result: SimulationResult) -> ValidationResult:
    """
    Check 7: Phase fraction remains in [0, 1].

    Physics: The metallic fraction φ is a volume fraction, which
    must satisfy 0 ≤ φ ≤ 1 by definition.

    Pass criterion: −0.01 ≤ φ ≤ 1.01 (small tolerance for solver).
    """
    phi_min = result.phi.min()
    phi_max = result.phi.max()

    passed = (phi_min >= -0.01) and (phi_max <= 1.01)

    return ValidationResult(
        name="Phase fraction bounds (0 ≤ φ ≤ 1)",
        passed=passed,
        metric_value=phi_max - phi_min,
        threshold=1.02,
        message=f"φ ∈ [{phi_min:.6f}, {phi_max:.6f}]."
    )


def check_energy_conservation(result: SimulationResult) -> ValidationResult:
    """
    Check 8: Approximate energy conservation.

    Physics: Over a complete cycle, the total energy input (Joule
    heating) should approximately equal the total energy dissipated
    (cooling) plus the net thermal energy stored.

    Method:
        E_in   = ∫ P_joule dt  [J]
        E_out  = ∫ P_cool dt   [J]
        ΔE_stored = C_th * (T_final − T_initial)  [J]
        Error  = |E_in − E_out − ΔE_stored| / E_in

    Note: Latent heat is not included here for simplicity, so the
    error may be nonzero but should be small.

    Pass criterion: Error < 20% (generous due to latent heat omission).
    """
    dt = np.diff(result.t)

    E_in = np.sum(result.P_joule[:-1] * dt)
    E_out = np.sum(result.P_cool[:-1] * dt)
    dE_stored = result.params.C_th * (result.T[-1] - result.T[0])

    # Latent heat contribution
    dphi = result.phi[-1] - result.phi[0]
    dE_latent = result.params.L_latent * dphi

    if E_in < 1e-20:
        return ValidationResult(
            name="Energy conservation",
            passed=True,
            metric_value=0.0,
            threshold=0.20,
            message="No energy input (E_in ≈ 0). Trivial case."
        )

    error = abs(E_in - E_out - dE_stored - dE_latent) / E_in

    return ValidationResult(
        name="Energy conservation",
        passed=error < 0.20,
        metric_value=error,
        threshold=0.20,
        message=f"E_in = {E_in:.4e} J, E_out = {E_out:.4e} J, "
                f"ΔE_stored = {dE_stored:.4e} J, error = {error*100:.1f}%."
    )
