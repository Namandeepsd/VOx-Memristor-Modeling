"""
Reproduce all experimental figures using the REAL VOx model.

Generates side-by-side ready comparison plots for:
  - Figure 3: V(I) at 295K with NDR (current bias)
  - Figure 5: Multi-amplitude current sweeps at 297K
  - Figure 6: Multi-cycle voltage sweeps at 297K
  - Figure 2: R-T characteristic (temperature sweep)
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from memristor.vox_real_model import (
    RealVOxParameters, solve_real_vox,
    resistance, R_insulating, R_metallic, phi_equilibrium,
)


OUT_DIR = Path(__file__).parent.parent / "output" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Consistent styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.linewidth': 1.2,
    'lines.linewidth': 1.5,
})


# =================================================================
# Figure 2: R-T Characteristic (Quasi-Static Temperature Sweep)
# =================================================================

def run_fig2():
    """Reproduce the R-T hysteresis loop from Figure 2."""
    print("[Real Model] Running R-T sweep (Figure 2)...")

    params = RealVOxParameters()

    # Heating sweep: 290K → 325K with phi starting at 0
    T_heat = np.linspace(290, 325, 500)
    R_heat = []
    phi = 0.0
    for T in T_heat:
        phi_eq = phi_equilibrium(T, phi, params)
        phi = phi + 0.05 * (phi_eq - phi)  # relaxation step
        R_heat.append(resistance(T, phi, params))

    # Cooling sweep: 325K → 290K with phi starting at 1
    T_cool = np.linspace(325, 290, 500)
    R_cool = []
    phi = 1.0
    for T in T_cool:
        phi_eq = phi_equilibrium(T, phi, params)
        phi = phi + 0.05 * (phi_eq - phi)
        R_cool.append(resistance(T, phi, params))

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.semilogy(T_heat, R_heat, 'r-', linewidth=2, label='Heating')
    ax.semilogy(T_cool, R_cool, 'b-', linewidth=2, label='Cooling')
    ax.set_xlabel("Temperature (K)", fontsize=13)
    ax.set_ylabel("Resistance (Ω)", fontsize=13)
    ax.set_title("R-T Characteristic (Real Model) — cf. Fig 2", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xlim(288, 325)

    fig.savefig(OUT_DIR / "real_fig2_RT.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: real_fig2_RT.png")


# =================================================================
# Figure 3: V(I) at 295K (Current Bias, NDR)
# =================================================================

def run_fig3():
    """Reproduce the S-shaped NDR from Figure 3 (295K cooling)."""
    print("[Real Model] Running Fig 3 (V-I at 295K, NDR)...")

    params = RealVOxParameters(
        bias_mode="current",
        waveform_type="triangular",
        V_amplitude=0.8e-3,   # 0.8 mA peak
        frequency=0.5,
        n_cycles=1,
        T_amb=295.0,
        T_initial=295.0,
        phi_initial=0.0,      # cooled from high T, but below T_MIT
    )

    result = solve_real_vox(params, n_eval=3000)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(result['I'] * 1e3, result['V'], 'k-', linewidth=1.8)
    ax.set_xlabel("I (mA)", fontsize=13)
    ax.set_ylabel("V (Volts)", fontsize=13)
    ax.set_title("V(I) at 295 K — NDR (Real Model) — cf. Fig 3", fontsize=14)
    ax.grid(True, alpha=0.3)

    fig.savefig(OUT_DIR / "real_fig3_NDR.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: real_fig3_NDR.png")


# =================================================================
# Figure 5: Multi-Amplitude Current Sweeps at 297K
# =================================================================

def run_fig5():
    """Reproduce amplitude-dependent V(I) from Figure 5c."""
    print("[Real Model] Running Fig 5 (multi-amplitude at 297K)...")

    amplitudes = [1e-3, 3e-3, 5e-3, 10e-3, 15e-3, 20e-3]
    colors = ['black', 'red', 'blue', 'magenta', 'orange', 'green']
    labels = ['A', 'B', 'C', 'D', 'E', 'F']

    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    axes_flat = axes.flatten()

    for idx, (amp, color, label) in enumerate(zip(amplitudes, colors, labels)):
        params = RealVOxParameters(
            bias_mode="current",
            waveform_type="triangular",
            V_amplitude=amp,
            frequency=0.5,
            n_cycles=1,
            T_amb=297.0,
            T_initial=297.0,
            phi_initial=0.0,
        )

        result = solve_real_vox(params, n_eval=3000)

        ax = axes_flat[idx]
        ax.plot(result['I'] * 1e3, result['V'], color=color, linewidth=1.5)
        ax.set_xlabel("I (mA)", fontsize=10)
        ax.set_ylabel("V (Volts)", fontsize=10)
        ax.set_title(f"{label}  (I_max = {amp*1e3:.0f} mA)", fontsize=11)
        ax.text(0.95, 0.05, "297K", transform=ax.transAxes,
                fontsize=10, ha='right', va='bottom')
        ax.grid(True, alpha=0.3)

    fig.suptitle("V(I) at 297 K — Multi-Amplitude (Real Model) — cf. Fig 5c",
                 fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_DIR / "real_fig5_multi.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: real_fig5_multi.png")


# =================================================================
# Figure 6: Multi-Cycle Voltage Sweeps at 297K
# =================================================================

def run_fig6():
    """Reproduce sweep-to-sweep evolution from Figure 6."""
    print("[Real Model] Running Fig 6 (multi-cycle voltage sweeps)...")

    params = RealVOxParameters(
        bias_mode="voltage",
        waveform_type="triangular",
        V_amplitude=10.0,
        frequency=0.5,
        n_cycles=10,
        T_amb=297.0,
        T_initial=297.0,
        phi_initial=0.0,
    )

    result = solve_real_vox(params, n_eval=8000)

    fig, ax = plt.subplots(figsize=(6, 5))

    period = 1.0 / params.frequency
    cmap = plt.cm.viridis
    for i in range(params.n_cycles):
        mask = (result['t'] >= i * period) & (result['t'] < (i + 1) * period)
        if i == 0:
            c, lw, label = 'black', 2.0, 'Cycle 1'
        elif i == params.n_cycles - 1:
            c, lw, label = 'red', 2.0, f'Cycle {params.n_cycles}'
        else:
            c, lw, label = cmap(i / params.n_cycles), 0.8, None

        ax.plot(result['V'][mask], result['I'][mask] * 1e3,
                color=c, linewidth=lw, label=label, alpha=0.8)

    ax.set_xlabel("V (Volts)", fontsize=13)
    ax.set_ylabel("I (mA)", fontsize=13)
    ax.set_title("I(V) at 297 K — 10 Sweeps (Real Model) — cf. Fig 6",
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.savefig(OUT_DIR / "real_fig6_sweeps.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: real_fig6_sweeps.png")


# =================================================================
# Comparison Dashboard
# =================================================================

def run_dashboard():
    """Generate a 4-panel dashboard of the real model."""
    print("[Real Model] Generating dashboard...")

    # Run a multi-cycle current-bias simulation
    params = RealVOxParameters(
        bias_mode="current",
        waveform_type="triangular",
        V_amplitude=5e-3,
        frequency=0.5,
        n_cycles=3,
        T_amb=297.0,
        T_initial=297.0,
        phi_initial=0.0,
    )
    r = solve_real_vox(params, n_eval=5000)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # V-I
    ax = axes[0, 0]
    ax.plot(r['I'] * 1e3, r['V'], 'k-', linewidth=1.2)
    ax.set_xlabel("I (mA)")
    ax.set_ylabel("V (Volts)")
    ax.set_title("V(I) Characteristic")
    ax.grid(True, alpha=0.3)

    # Temperature
    ax = axes[0, 1]
    ax.plot(r['t'], r['T'], 'r-', linewidth=1.2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (K)")
    ax.set_title("Device Temperature")
    ax.grid(True, alpha=0.3)

    # Resistance
    ax = axes[1, 0]
    ax.semilogy(r['t'], r['R'], 'b-', linewidth=1.2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Resistance (Ω)")
    ax.set_title("Device Resistance")
    ax.grid(True, alpha=0.3, which='both')

    # Phase fraction
    ax = axes[1, 1]
    ax.plot(r['t'], r['phi'], 'g-', linewidth=1.2)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("φ (metallic fraction)")
    ax.set_title("Phase Fraction")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.3)

    fig.suptitle("Real VOx Model — Dashboard", fontsize=15, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_DIR / "real_dashboard.png", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: real_dashboard.png")


# =================================================================
# MAIN
# =================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  REAL VOx Model — Experimental Reproduction")
    print("=" * 60)

    run_fig2()
    run_fig3()
    run_fig5()
    run_fig6()
    run_dashboard()

    print("\n[DONE] All real-model plots saved to output/plots/")
