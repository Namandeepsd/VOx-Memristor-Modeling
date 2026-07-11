"""
VOx Memristor — Unit Tests
============================

Tests for the electro-thermal MIT memristor model.
Verifies mathematical correctness, dimensional consistency,
and physical behavior of all model components.

Run with:
    cd ProjectMemristor
    python -m pytest tests/test_vox.py -v
"""

import numpy as np
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memristor.vox_parameters import VOxParameters
from memristor.vox_model import (
    phi_equilibrium,
    resistance,
    current,
    system_rhs,
    _resistance_metallic,
    _resistance_insulating,
)
from memristor.vox_waveforms import (
    sinusoidal,
    triangular,
    pulse,
    dc_sweep,
    get_waveform,
)
from memristor.vox_solver import solve_vox


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def default_params():
    """Default parameter set for testing."""
    return VOxParameters()


@pytest.fixture
def fast_params():
    """Parameters for fast simulation (fewer cycles, coarser tolerances)."""
    return VOxParameters(
        V_amplitude=3.0,
        frequency=1e4,
        n_cycles=1,
        rtol=1e-6,
        atol=1e-8,
    )


# =====================================================================
# Parameter Tests
# =====================================================================

class TestParameters:
    """Tests for VOxParameters."""

    def test_default_creation(self, default_params):
        """Parameters should be created with valid defaults."""
        p = default_params
        assert p.C_th > 0, "C_th must be positive"
        assert p.G_th > 0, "G_th must be positive"
        assert p.T_amb > 0, "T_amb must be positive"
        assert p.T_IMT > p.T_MIT, "T_IMT must exceed T_MIT"
        assert p.R_insulating > p.R_metallic, "R_i must exceed R_m"

    def test_thermal_time_constant(self, default_params):
        """τ_th = C_th / G_th should be positive and finite."""
        tau = default_params.tau_thermal
        assert tau > 0
        assert np.isfinite(tau)

    def test_resistance_ratio(self, default_params):
        """R_i / R_m should be > 1."""
        ratio = default_params.resistance_ratio
        assert ratio > 1.0

    def test_simulation_time_positive(self, default_params):
        """Simulation time should be positive."""
        assert default_params.simulation_time > 0

    def test_hysteresis_width(self, default_params):
        """Hysteresis width should be positive."""
        assert default_params.hysteresis_width > 0

    def test_summary_runs(self, default_params):
        """Summary should produce a non-empty string."""
        s = default_params.summary()
        assert len(s) > 100


# =====================================================================
# Sigmoid Equilibrium Tests
# =====================================================================

class TestPhiEquilibrium:
    """Tests for the sigmoid equilibrium function."""

    def test_low_temperature_limit(self, default_params):
        """φ_eq → 0 as T → 0 (fully insulating at low T)."""
        phi_eq = phi_equilibrium(200.0, 0.0, default_params)
        assert phi_eq < 0.01, f"Expected φ_eq ≈ 0 at T=200K, got {phi_eq}"

    def test_high_temperature_limit(self, default_params):
        """φ_eq → 1 as T → ∞ (fully metallic at high T)."""
        phi_eq = phi_equilibrium(500.0, 1.0, default_params)
        assert phi_eq > 0.99, f"Expected φ_eq ≈ 1 at T=500K, got {phi_eq}"

    def test_monotonically_increasing(self, default_params):
        """φ_eq should increase with temperature."""
        T_values = np.linspace(300, 380, 50)
        phi_values = [phi_equilibrium(T, 0.5, default_params) for T in T_values]
        for i in range(len(phi_values) - 1):
            assert phi_values[i+1] >= phi_values[i], \
                f"φ_eq not monotonic at T={T_values[i]:.1f} K"

    def test_output_range(self, default_params):
        """φ_eq should always be in [0, 1]."""
        for T in [0, 100, 300, 340, 400, 1000]:
            phi_eq = phi_equilibrium(float(T), 0.5, default_params)
            assert 0.0 <= phi_eq <= 1.0, \
                f"φ_eq = {phi_eq} out of [0,1] at T = {T} K"

    def test_state_dependent_hysteresis(self):
        """State-dependent T_c should differ between φ=0 and φ=1."""
        params = VOxParameters(hysteresis_mode="state_dependent")
        T_mid = 0.5 * (params.T_IMT + params.T_MIT)

        # At T_mid: φ_eq should differ depending on current φ
        phi_eq_ins = phi_equilibrium(T_mid, 0.0, params)  # insulating state
        phi_eq_met = phi_equilibrium(T_mid, 1.0, params)  # metallic state

        # φ=0 → T_c = T_IMT (higher) → harder to transition → lower φ_eq
        # φ=1 → T_c = T_MIT (lower) → harder to revert → higher φ_eq
        assert phi_eq_met > phi_eq_ins, \
            "State-dependent hysteresis: φ_eq(φ=1) should exceed φ_eq(φ=0)"


# =====================================================================
# Resistance Model Tests
# =====================================================================

class TestResistance:
    """Tests for the resistance mixing models."""

    def test_fully_insulating(self, default_params):
        """R(φ=0) should equal R_insulating."""
        R = resistance(300.0, 0.0, default_params)
        assert np.isclose(R, default_params.R_insulating, rtol=0.01)

    def test_fully_metallic(self, default_params):
        """R(φ=1) should equal R_metallic (at T_amb)."""
        R = resistance(default_params.T_amb, 1.0, default_params)
        assert np.isclose(R, default_params.R_metallic, rtol=0.01)

    def test_resistance_decreases_with_phi(self, default_params):
        """R should decrease as φ increases (more metallic → lower R)."""
        phi_values = np.linspace(0, 1, 20)
        R_values = [resistance(300.0, phi, default_params) for phi in phi_values]
        for i in range(len(R_values) - 1):
            assert R_values[i+1] <= R_values[i], \
                f"R not monotonically decreasing at φ={phi_values[i]:.2f}"

    def test_resistance_positive(self, default_params):
        """R should always be positive."""
        for phi in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for T in [250.0, 300.0, 350.0, 400.0]:
                R = resistance(T, phi, default_params)
                assert R > 0, f"R = {R} ≤ 0 at T={T}, φ={phi}"

    def test_logarithmic_model(self):
        """Logarithmic mixing: R = R_m^φ * R_i^(1-φ)."""
        params = VOxParameters(resistance_model="logarithmic")
        phi = 0.5
        R = resistance(params.T_amb, phi, params)
        R_expected = np.sqrt(params.R_metallic * params.R_insulating)
        assert np.isclose(R, R_expected, rtol=0.05)

    def test_parallel_model(self):
        """Parallel mixing: 1/R = φ/R_m + (1-φ)/R_i."""
        params = VOxParameters(resistance_model="parallel")
        R = resistance(params.T_amb, 0.5, params)
        R_expected = 1.0 / (0.5 / params.R_metallic + 0.5 / params.R_insulating)
        assert np.isclose(R, R_expected, rtol=0.01)

    def test_bruggeman_model(self):
        """Bruggeman EMT should produce a positive result."""
        params = VOxParameters(resistance_model="bruggeman")
        R = resistance(params.T_amb, 0.5, params)
        assert R > 0
        assert params.R_metallic < R < params.R_insulating


# =====================================================================
# Current (Ohm's Law) Tests
# =====================================================================

class TestCurrent:
    """Tests for Ohm's law current computation."""

    def test_zero_voltage_zero_current(self, default_params):
        """I(V=0) = 0 (no spontaneous current generation)."""
        I = current(0.0, 300.0, 0.5, default_params)
        assert I == 0.0

    def test_positive_voltage_positive_current(self, default_params):
        """Positive V → positive I (passive device)."""
        I = current(1.0, 300.0, 0.5, default_params)
        assert I > 0

    def test_ohms_law(self, default_params):
        """I = V / R."""
        V = 2.0
        T = 300.0
        phi = 0.3
        I = current(V, T, phi, default_params)
        R = resistance(T, phi, default_params)
        assert np.isclose(I, V / R, rtol=1e-10)


# =====================================================================
# ODE RHS Tests
# =====================================================================

class TestSystemRHS:
    """Tests for the coupled ODE right-hand side."""

    def test_output_shape(self, default_params):
        """RHS should return a 2-element array [dT/dt, dφ/dt]."""
        V_func = lambda t: 1.0
        state = np.array([300.0, 0.0])
        dydt = system_rhs(0.0, state, V_func, default_params)
        assert dydt.shape == (2,)

    def test_zero_voltage_cooling(self, default_params):
        """With V=0 and T > T_amb, the device should cool (dT/dt < 0)."""
        V_func = lambda t: 0.0
        state = np.array([350.0, 0.0])  # hot, insulating
        dydt = system_rhs(0.0, state, V_func, default_params)
        assert dydt[0] < 0, "Device should cool when V=0 and T > T_amb"

    def test_equilibrium_at_ambient(self, default_params):
        """At V=0, T=T_amb, φ=0: system should be near equilibrium."""
        V_func = lambda t: 0.0
        state = np.array([default_params.T_amb, 0.0])
        dydt = system_rhs(0.0, state, V_func, default_params)
        # dT/dt should be ≈ 0 (at thermal equilibrium)
        # dφ/dt should be ≈ 0 (φ_eq(300K) ≈ 0 when φ=0)
        assert abs(dydt[0]) < 1e3, \
            f"dT/dt = {dydt[0]:.2e} too large at equilibrium"
        assert abs(dydt[1]) < 1e3, \
            f"dφ/dt = {dydt[1]:.2e} too large at equilibrium"

    def test_joule_heating(self, default_params):
        """Applying voltage at T_amb should heat the device (dT/dt > 0)."""
        V_func = lambda t: 3.0  # constant voltage
        state = np.array([default_params.T_amb, 0.0])
        dydt = system_rhs(0.0, state, V_func, default_params)
        assert dydt[0] > 0, "Device should heat up when voltage is applied"

    def test_dimensional_consistency(self, default_params):
        """Verify dT/dt has units of K/s (order of magnitude check)."""
        V_func = lambda t: 3.0
        state = np.array([300.0, 0.0])
        dydt = system_rhs(0.0, state, V_func, default_params)
        # dT/dt = P / C_th ≈ V²/R / C_th
        # ≈ 9/50000 / 3e-10 ≈ 6e5 K/s — reasonable for thin-film device
        assert 1e2 < abs(dydt[0]) < 1e10, \
            f"dT/dt = {dydt[0]:.2e} K/s seems unphysical"


# =====================================================================
# Waveform Tests
# =====================================================================

class TestWaveforms:
    """Tests for voltage waveform generators."""

    def test_sinusoidal_amplitude(self):
        """Peak of sinusoidal should equal amplitude."""
        V = sinusoidal(5.0, 1e3)
        t = np.linspace(0, 1e-3, 10000)
        V_vals = np.array([V(ti) for ti in t])
        assert np.isclose(V_vals.max(), 5.0, rtol=0.01)

    def test_sinusoidal_zero_at_t0(self):
        """Sinusoidal starts at V=0 (phase=0)."""
        V = sinusoidal(5.0, 1e3)
        assert np.isclose(V(0.0), 0.0, atol=1e-10)

    def test_triangular_amplitude(self):
        """Peak of triangular should equal amplitude."""
        V = triangular(5.0, 1e3)
        t = np.linspace(0, 1e-3, 10000)
        V_vals = np.array([V(ti) for ti in t])
        assert np.isclose(V_vals.max(), 5.0, rtol=0.02)

    def test_pulse_levels(self):
        """Pulse should alternate between amplitude and 0."""
        V = pulse(5.0, 1e3, duty_cycle=0.5)
        assert np.isclose(V(0.0), 5.0)  # start of ON phase
        assert np.isclose(V(0.7e-3), 0.0)  # in OFF phase

    def test_dc_sweep_symmetric(self):
        """DC sweep should be symmetric: max = +amp, min = −amp."""
        V = dc_sweep(5.0, 100.0)
        t = np.linspace(0, 0.2, 10000)
        V_vals = np.array([V(ti) for ti in t])
        assert np.isclose(V_vals.max(), 5.0, rtol=0.02)
        assert np.isclose(V_vals.min(), -5.0, rtol=0.02)

    def test_get_waveform_factory(self):
        """Factory function should return callables for all types."""
        for wtype in ["sinusoidal", "triangular", "pulse", "dc_sweep"]:
            V = get_waveform(wtype, 1.0, 1e3, sweep_rate=10.0)
            assert callable(V)

    def test_get_waveform_invalid(self):
        """Factory should raise ValueError for unknown type."""
        with pytest.raises(ValueError):
            get_waveform("unknown_type", 1.0, 1e3)


# =====================================================================
# Integration / Solver Tests
# =====================================================================

class TestSolver:
    """Integration tests for the ODE solver."""

    def test_solver_converges(self, fast_params):
        """Solver should converge with default parameters."""
        result = solve_vox(fast_params, n_eval=1000)
        assert result.success, f"Solver failed: {result.message}"

    def test_output_shapes(self, fast_params):
        """All output arrays should have the same length."""
        result = solve_vox(fast_params, n_eval=1000)
        n = len(result.t)
        assert len(result.T) == n
        assert len(result.phi) == n
        assert len(result.V) == n
        assert len(result.I) == n
        assert len(result.R) == n

    def test_initial_conditions(self, fast_params):
        """State should start at specified initial conditions."""
        result = solve_vox(fast_params, n_eval=1000)
        assert np.isclose(result.T[0], fast_params.T_initial, rtol=0.01)
        assert np.isclose(result.phi[0], fast_params.phi_initial, atol=0.01)

    def test_temperature_rises(self, fast_params):
        """Temperature should rise above T_amb during simulation."""
        result = solve_vox(fast_params, n_eval=1000)
        assert result.T.max() > fast_params.T_amb + 5.0, \
            "Temperature should rise due to Joule heating"

    def test_summary_runs(self, fast_params):
        """Summary method should produce a string."""
        result = solve_vox(fast_params, n_eval=1000)
        s = result.summary()
        assert len(s) > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
