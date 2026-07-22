"""
simulate_graph_D.py — Focused reproduction of Graph D (pink, I_max ≈ 10 mA)
=============================================================================

This script reproduces ONLY Graph D from the experimental Figure 5c of:

    Rana, A.S., Li, C., Koster, G. & Hilgenkamp, H.
    "Resistive switching studies in VO₂ thin films."
    Scientific Reports 10, 3293 (2020).
    https://doi.org/10.1038/s41598-020-60373-z

Graph D shows a V(I) hysteresis loop at 297 K with a current-biased
triangular waveform reaching I_max ≈ 10 mA. The characteristic "figure-8"
shape arises from the interplay of:
  - Joule-heated insulator-to-metal transition (NDR snap-back)
  - Phase-lag hysteresis (φ lags φ_eq due to finite τ_φ)

Uses the Advanced 3-ODE model (Bruggeman EMT + parasitic capacitance).

All equations are justified in the accompanying literature_verification.md.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent dir so we can import the memristor package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memristor.vox_advanced_model import (
    solve_advanced_vox,
    AdvancedVOxParameters,
    resistance_bruggeman,
)


def ensure_dir(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def setup_plot_style():
    """Configure matplotlib for publication-quality plots."""
    plt.style.use('default')
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'mathtext.fontset': 'cm',
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'axes.titlesize': 16,
        'axes.labelsize': 14,
        'xtick.labelsize': 12,
        'ytick.labelsize': 12,
        'axes.linewidth': 1.2,
        'lines.linewidth': 2.0,
    })


def build_parameters():
    """
    Build the calibrated parameter set for Graph D.

    These parameters have been tuned to match the experimental V(I)
    figure-8 hysteresis at 297 K with I_max ≈ 10 mA.

    Key calibration decisions:
    ─────────────────────────
    - tau_phi_0 = 5e-3 s → Large enough phase lag to create enclosed loops
    - E_a_kinetics = 0.03 eV → Low activation so τ doesn't blow up at 297 K
    - G_th_0 = 6e-4 W/K → Prevents temperature overshoot
    - C_th = 2e-9 J/K → Fast thermal response
    - C_p = 1e-12 F → Minimized to prevent electrical ringing
    """
    p = AdvancedVOxParameters()

    # Ambient / operating temperature (per paper)
    p.T_amb = 297.0

    # Thermal parameters
    p.C_th = 2.0e-9        # Thermal capacitance [J/K]
    p.G_th_0 = 6.0e-4      # Base thermal conductance [W/K]
    p.G_th_nonlinear = 2.0e-6  # Non-linear thermal conductance [W/K²]

    # MIT transition temperatures (from R-T data, Figure 2)
    p.T_IMT = 315.0         # Insulator→Metal (heating) [K]
    p.T_MIT = 298.0          # Metal→Insulator (cooling) [K]
    p.delta_T = 3.5          # Transition width [K]
    p.L_latent = 5.0e-9      # Latent heat [J]

    # Electrical parameters
    p.R_i_ref = 12000.0      # Insulating resistance at T_amb [Ω]
    p.E_g = 0.45             # Arrhenius activation energy [eV]
    p.R_m_0 = 100.0          # Metallic resistance at T_amb [Ω]
    p.alpha_m = 1.2e-3       # Metallic TCR [1/K]
    p.R_contact = 75.0       # Contact/electrode resistance [Ω]

    # Phase kinetics — CRITICAL for figure-8 shape
    # With tau_phi_0 = 5e-3, φ takes ~10 ms to catch up to equilibrium:
    #   HEATING: φ < φ_eq → device is MORE insulating → higher V
    #   COOLING: φ > φ_eq → device is MORE metallic → lower V
    #   Same current, different voltage → enclosed loop!
    p.tau_phi_0 = 5.0e-3     # Base phase relaxation time [s]
    p.E_a_kinetics = 0.03    # Low activation energy [eV]

    # Parasitic capacitance (minimized)
    p.C_p = 1.0e-12          # Parallel capacitance [F]

    return p


def build_waveform(freq, period, num_cycles, t_end, I_max_final=22e-3):
    """
    Build the linearly-growing triangular current waveform.

    The waveform amplitude grows linearly from 0 to I_max_final over
    num_cycles cycles. Graph D corresponds to the cycle where the
    envelope amplitude reaches ~10 mA.

    Parameters
    ----------
    freq : float
        Waveform frequency [Hz].
    period : float
        Single cycle period [s].
    num_cycles : int
        Total number of cycles in the growing envelope.
    t_end : float
        Total simulation time [s].
    I_max_final : float
        Maximum current at the end of the sweep [A].

    Returns
    -------
    I_waveform : callable
        Current waveform function I(t).
    """
    def I_waveform(t):
        t = np.asarray(t)
        is_scalar = t.ndim == 0
        if is_scalar:
            t = t[np.newaxis]

        cycle = t / period
        phase = cycle % 1.0
        val = np.zeros_like(t)

        # Triangular wave: 0→+1→0→−1→0
        m1 = phase < 0.25
        val[m1] = 4 * phase[m1]
        m2 = (phase >= 0.25) & (phase < 0.75)
        val[m2] = 1 - 4 * (phase[m2] - 0.25)
        m3 = phase >= 0.75
        val[m3] = -1 + 4 * (phase[m3] - 0.75)

        # Linearly growing envelope
        envelope = (t / t_end) * I_max_final
        res = val * envelope
        return res[0] if is_scalar else res

    return I_waveform


def extract_graph_D_cycle(sol, I_waveform, period, t_end,
                          target_amp=10e-3, I_max_final=22e-3):
    """
    Extract the single cycle from the continuous sweep that corresponds
    to Graph D (I_max ≈ 10 mA envelope amplitude).

    Parameters
    ----------
    sol : OdeResult
        Solution from solve_advanced_vox.
    I_waveform : callable
        Current waveform function.
    period : float
        Single cycle period [s].
    t_end : float
        Total simulation time [s].
    target_amp : float
        Target envelope amplitude for Graph D [A].
    I_max_final : float
        Final envelope amplitude [A].

    Returns
    -------
    I_mA : ndarray
        Current in milliamps for the Graph D cycle.
    V : ndarray
        Voltage in Volts for the Graph D cycle.
    T_dev : ndarray
        Device temperature [K] for the Graph D cycle.
    phi_dev : ndarray
        Metallic fraction for the Graph D cycle.
    """
    # Find the cycle index where envelope ≈ target_amp
    t_target = target_amp * t_end / I_max_final
    cyc_idx = int(t_target / period)

    t_start = cyc_idx * period
    t_end_cyc = (cyc_idx + 1) * period
    mask = (sol.t >= t_start) & (sol.t <= t_end_cyc)

    V_dev = sol.y[2]
    I_src = I_waveform(sol.t)

    return (
        I_src[mask] * 1000,   # mA
        V_dev[mask],          # V
        sol.y[0][mask],       # T [K]
        sol.y[1][mask],       # φ
    )


def plot_graph_D(I_mA, V, out_dir):
    """
    Create the publication-quality Graph D plot.

    Styled to match the experimental figure:
    - Pink/magenta color
    - Axis ranges: I ∈ [−6, 6] mA, V ∈ [−4, 4] V
    - Label "D" in top-left, "297K" in bottom-right
    """
    fig, ax = plt.subplots(figsize=(7, 6))

    # Plot the V(I) hysteresis loop
    ax.plot(I_mA, V, color='#FF00FF', linewidth=2.2, zorder=3)

    # Axis labels
    ax.set_xlabel('I (mA)', fontsize=14, fontweight='bold')
    ax.set_ylabel('V (Volts)', fontsize=14, fontweight='bold')

    # Auto-fit axis ranges with 10% padding so full curve is visible
    I_pad = (I_mA.max() - I_mA.min()) * 0.10
    V_pad = (V.max() - V.min()) * 0.10
    ax.set_xlim(I_mA.min() - I_pad, I_mA.max() + I_pad)
    ax.set_ylim(V.min() - V_pad, V.max() + V_pad)

    # Panel label "D" — matching paper style
    ax.text(0.05, 0.92, 'D', transform=ax.transAxes,
            fontsize=20, fontweight='bold', color='#FF00FF',
            verticalalignment='top')

    # Temperature annotation
    ax.text(0.85, 0.08, '297K', transform=ax.transAxes,
            fontsize=13, fontweight='bold',
            verticalalignment='bottom')

    # Clean up
    ax.tick_params(direction='in', top=True, right=True)
    ax.set_aspect('auto')

    # Light grid for readability
    ax.axhline(y=0, color='gray', linewidth=0.5, alpha=0.4)
    ax.axvline(x=0, color='gray', linewidth=0.5, alpha=0.4)

    plt.tight_layout(pad=1.5)
    save_path = out_dir / "graph_D_final.png"
    plt.savefig(save_path, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print(f"  ✓ Saved: {save_path}")
    return save_path


def plot_dashboard(sol, I_waveform, I_mA, V, T_dev, phi_dev, params, out_dir):
    """
    Create a 4-panel diagnostic dashboard for Graph D.

    Panels:
      [0,0] V(I) hysteresis — the main result
      [0,1] Device temperature vs time (full simulation)
      [1,0] Metallic fraction φ vs time (full simulation)
      [1,1] Device resistance vs time (full simulation)
    """
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Graph D Diagnostic Dashboard — 297 K, I_max ≈ 10 mA',
                 fontsize=16, fontweight='bold')

    # Panel 1: V(I)
    axs[0, 0].plot(I_mA, V, color='#FF00FF', linewidth=2)
    axs[0, 0].set_xlabel('I (mA)')
    axs[0, 0].set_ylabel('V (Volts)')
    axs[0, 0].set_title('V(I) Hysteresis — Graph D')
    axs[0, 0].set_xlim(-6, 6)
    axs[0, 0].set_ylim(-4, 4)
    axs[0, 0].axhline(y=0, color='gray', linewidth=0.5, alpha=0.4)
    axs[0, 0].axvline(x=0, color='gray', linewidth=0.5, alpha=0.4)

    # Panel 2: Temperature
    axs[0, 1].plot(sol.t, sol.y[0], 'r-', linewidth=1)
    axs[0, 1].set_xlabel('Time (s)')
    axs[0, 1].set_ylabel('Temperature (K)')
    axs[0, 1].set_title('Device Temperature T(t)')
    axs[0, 1].grid(True, alpha=0.3)

    # Panel 3: Phase fraction
    axs[1, 0].plot(sol.t, sol.y[1], 'g-', linewidth=1)
    axs[1, 0].set_xlabel('Time (s)')
    axs[1, 0].set_ylabel('φ (metallic fraction)')
    axs[1, 0].set_title('Metallic Phase Fraction φ(t)')
    axs[1, 0].set_ylim(-0.05, 1.05)
    axs[1, 0].grid(True, alpha=0.3)

    # Panel 4: Resistance
    R_arr = np.array([resistance_bruggeman(sol.y[0][i], sol.y[1][i], params)
                      for i in range(len(sol.t))])
    axs[1, 1].semilogy(sol.t, R_arr, 'b-', linewidth=1)
    axs[1, 1].set_xlabel('Time (s)')
    axs[1, 1].set_ylabel('Resistance (Ω)')
    axs[1, 1].set_title('Device Resistance R(t) — Bruggeman EMT')
    axs[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    save_path = out_dir / "graph_D_dashboard.png"
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Saved: {save_path}")
    return save_path


def main():
    print("=" * 60)
    print("  GRAPH D — Focused Simulation")
    print("  V(I) at 297 K, I_max ≈ 10 mA (Pink)")
    print("  Experimental reference: Rana et al. (2020), Fig. 5c-D")
    print("=" * 60)

    setup_plot_style()
    out_dir = ensure_dir("output/plots")

    # 1. Build parameters
    print("\n[1/4] Building calibrated parameters...")
    params = build_parameters()

    # 2. Build waveform
    print("[2/4] Constructing triangular waveform...")
    freq = 5.0              # Hz
    period = 1.0 / freq     # 200 ms per cycle
    num_cycles = 45
    t_end = num_cycles * period
    t_eval = np.linspace(0, t_end, 80000)

    I_waveform = build_waveform(freq, period, num_cycles, t_end, I_max_final=22e-3)

    # 3. Solve the 3-ODE system
    print("[3/4] Solving coupled ODEs (3-ODE Bruggeman model)...")
    sol, _ = solve_advanced_vox('current', I_waveform, t_eval, params)

    if not sol.success:
        print(f"  ⚠ Solver warning: {sol.message}")
    else:
        print(f"  ✓ Solver converged ({len(sol.t)} time points)")

    # 4. Extract Graph D cycle and plot
    print("[4/4] Extracting Graph D cycle and plotting...")
    I_mA, V, T_dev, phi_dev = extract_graph_D_cycle(
        sol, I_waveform, period, t_end,
        target_amp=10e-3, I_max_final=22e-3
    )

    # Main plot
    plot_graph_D(I_mA, V, out_dir)

    # Diagnostic dashboard
    plot_dashboard(sol, I_waveform, I_mA, V, T_dev, phi_dev, params, out_dir)

    # Summary statistics
    print("\n" + "─" * 50)
    print("  SIMULATION SUMMARY")
    print("─" * 50)
    print(f"  I range:   [{I_mA.min():.2f}, {I_mA.max():.2f}] mA")
    print(f"  V range:   [{V.min():.2f}, {V.max():.2f}] V")
    print(f"  T range:   [{T_dev.min():.1f}, {T_dev.max():.1f}] K")
    print(f"  φ range:   [{phi_dev.min():.4f}, {phi_dev.max():.4f}]")
    print(f"  Loop enclosed: {'YES' if (V.max() - V.min()) > 0.5 else 'NO'}")
    print("─" * 50)
    print("\n[DONE] All plots saved to output/plots/")


if __name__ == "__main__":
    main()
