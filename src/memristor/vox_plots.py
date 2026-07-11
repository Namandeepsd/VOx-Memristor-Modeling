"""
VOx Memristor — Publication-Quality Plotting
==============================================

Generates all standard plots for the electro-thermal MIT memristor
simulation. Each plot function takes a SimulationResult object and
produces a matplotlib figure.

Plot catalog:
    1.  Voltage vs Time
    2.  Current vs Time
    3.  Temperature vs Time
    4.  Resistance vs Time (log scale)
    5.  Metallic Fraction vs Time
    6.  Power vs Time (Joule heating and cooling)
    7.  I-V Curve (pinched hysteresis)
    8.  R-T Curve (MIT hysteresis)
    9.  Phase Fraction vs Temperature
    10. Complete dashboard (all subplots)

Style conventions:
    - LaTeX-formatted axis labels
    - Consistent color palette
    - Grid lines for readability
    - 300 DPI for publication quality
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
from typing import Optional

# =====================================================================
# Plot Style Configuration
# =====================================================================

# Publication-quality settings
STYLE = {
    'figure.figsize': (8, 5),
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'font.size': 12,
    'axes.labelsize': 14,
    'axes.titlesize': 14,
    'legend.fontsize': 10,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'lines.linewidth': 1.8,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'axes.spines.top': False,
    'axes.spines.right': False,
}

# Color palette (colorblind-friendly)
COLORS = {
    'voltage': '#2196F3',     # blue
    'current': '#FF5722',     # deep orange
    'temperature': '#E91E63', # pink-red
    'resistance': '#4CAF50',  # green
    'phi': '#9C27B0',         # purple
    'power': '#FF9800',       # orange
    'cooling': '#00BCD4',     # cyan
    'iv_trace': '#1A237E',    # dark blue
    'hysteresis': '#D32F2F',  # red
}


def _apply_style():
    """Apply publication-quality matplotlib style."""
    mpl.rcParams.update(STYLE)


def _save_fig(fig, filename: str, save_dir: Optional[str] = None):
    """Save figure to file if save_dir is provided."""
    if save_dir is not None:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        fig.savefig(path / filename, dpi=300, bbox_inches='tight')


# =====================================================================
# Individual Plot Functions
# =====================================================================

def plot_voltage_vs_time(result, save_dir=None, show=True):
    """
    Plot applied voltage V(t) vs time.

    Shows the driving input waveform used to excite the memristor.
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.plot(result.t * 1e3, result.V, color=COLORS['voltage'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Voltage [V]')
    ax.set_title('Applied Voltage Waveform')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    fig.tight_layout()
    _save_fig(fig, 'voltage_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_current_vs_time(result, save_dir=None, show=True):
    """
    Plot device current I(t) vs time.

    The current response reveals how the resistance switching
    modifies the I(t) waveform relative to the voltage input.
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.plot(result.t * 1e3, result.I * 1e3, color=COLORS['current'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Current [mA]')
    ax.set_title('Device Current Response')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    fig.tight_layout()
    _save_fig(fig, 'current_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_temperature_vs_time(result, save_dir=None, show=True):
    """
    Plot device temperature T(t) vs time.

    Shows the Joule-heating-driven temperature oscillations.
    Horizontal lines mark T_IMT and T_MIT for reference.
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.plot(result.t * 1e3, result.T, color=COLORS['temperature'])

    # Mark transition temperatures
    ax.axhline(y=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{IMT}}$ = {result.params.T_IMT:.0f} K')
    ax.axhline(y=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{MIT}}$ = {result.params.T_MIT:.0f} K')

    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Temperature [K]')
    ax.set_title('Device Temperature')
    ax.legend(loc='best')

    fig.tight_layout()
    _save_fig(fig, 'temperature_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_resistance_vs_time(result, save_dir=None, show=True):
    """
    Plot device resistance R(t) vs time on a logarithmic scale.

    The log scale is essential because R changes by orders of magnitude
    across the MIT (from ~10⁴ Ω insulating to ~10² Ω metallic).
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.semilogy(result.t * 1e3, result.R, color=COLORS['resistance'])

    # Mark resistance bounds
    ax.axhline(y=result.params.R_metallic, color=COLORS['iv_trace'],
               linestyle=':', linewidth=1.0, alpha=0.5,
               label=f'$R_m$ = {result.params.R_metallic:.0f} Ω')
    ax.axhline(y=result.params.R_insulating, color=COLORS['hysteresis'],
               linestyle=':', linewidth=1.0, alpha=0.5,
               label=f'$R_i$ = {result.params.R_insulating:.0f} Ω')

    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Resistance [Ω]')
    ax.set_title('Device Resistance (log scale)')
    ax.legend(loc='best')

    fig.tight_layout()
    _save_fig(fig, 'resistance_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_phi_vs_time(result, save_dir=None, show=True):
    """
    Plot metallic fraction φ(t) vs time.

    Shows how the metallic phase nucleates and grows in response
    to Joule-heating-driven temperature changes.
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.plot(result.t * 1e3, result.phi, color=COLORS['phi'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Metallic Fraction $\\phi$')
    ax.set_title('Metallic Phase Evolution')
    ax.set_ylim(-0.05, 1.05)

    fig.tight_layout()
    _save_fig(fig, 'phi_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_power_vs_time(result, save_dir=None, show=True):
    """
    Plot Joule heating power and cooling power vs time.

    The competition between P_joule and P_cool determines whether
    the device heats up (toward MIT) or cools down (away from MIT).
    """
    _apply_style()
    fig, ax = plt.subplots()

    ax.plot(result.t * 1e3, result.P_joule * 1e6,
            color=COLORS['power'], label='$P_{Joule} = V^2/R$')
    ax.plot(result.t * 1e3, result.P_cool * 1e6,
            color=COLORS['cooling'], label='$P_{cool} = G_{th}(T-T_{amb})$')

    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('Power [μW]')
    ax.set_title('Power Balance')
    ax.legend(loc='best')

    fig.tight_layout()
    _save_fig(fig, 'power_vs_time.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_iv_curve(result, save_dir=None, show=True):
    """
    Plot I-V characteristic (pinched hysteresis loop).

    The I-V Lissajous figure is the hallmark of memristive behavior.
    For a true memristor:
        1. The curve passes through the origin (V=0 ⟹ I=0)
        2. The loop is "pinched" at the origin
        3. The loop collapses to a straight line at high frequency

    The color gradient indicates time progression.
    """
    _apply_style()
    fig, ax = plt.subplots()

    # Plot with time-based color gradient
    n = len(result.t)
    colors = plt.cm.viridis(np.linspace(0, 1, n))

    for i in range(n - 1):
        ax.plot(result.V[i:i+2], result.I[i:i+2] * 1e3,
                color=colors[i], linewidth=1.5)

    # Add colorbar for time
    sm = plt.cm.ScalarMappable(
        cmap='viridis',
        norm=plt.Normalize(vmin=result.t[0]*1e3, vmax=result.t[-1]*1e3)
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, label='Time [ms]')

    ax.set_xlabel('Voltage [V]')
    ax.set_ylabel('Current [mA]')
    ax.set_title('I-V Characteristic (Pinched Hysteresis)')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    ax.axvline(x=0, color='gray', linestyle='--', linewidth=0.5)

    fig.tight_layout()
    _save_fig(fig, 'iv_curve.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_rt_curve(result, save_dir=None, show=True):
    """
    Plot R-T characteristic showing MIT hysteresis.

    This is the fundamental signature of the metal-insulator transition:
    resistance drops abruptly at T_IMT during heating and recovers
    at T_MIT during cooling, with T_MIT < T_IMT creating hysteresis.
    """
    _apply_style()
    fig, ax = plt.subplots()

    # Plot with time-based color gradient
    n = len(result.t)
    colors = plt.cm.coolwarm(np.linspace(0, 1, n))

    for i in range(n - 1):
        ax.plot(result.T[i:i+2], result.R[i:i+2],
                color=colors[i], linewidth=1.5)

    ax.set_yscale('log')

    # Mark transition temperatures
    ax.axvline(x=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{IMT}}$ = {result.params.T_IMT:.0f} K')
    ax.axvline(x=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{MIT}}$ = {result.params.T_MIT:.0f} K')

    ax.set_xlabel('Temperature [K]')
    ax.set_ylabel('Resistance [Ω]')
    ax.set_title('R-T Characteristic (MIT Hysteresis)')
    ax.legend(loc='best')

    fig.tight_layout()
    _save_fig(fig, 'rt_curve.png', save_dir)
    if show:
        plt.show()
    return fig


def plot_phi_vs_temperature(result, save_dir=None, show=True):
    """
    Plot metallic fraction φ vs temperature T.

    Shows the hysteretic phase fraction evolution — the heating
    and cooling paths are different, creating a loop whose width
    is the thermal hysteresis ΔT_hyst = T_IMT − T_MIT.
    """
    _apply_style()
    fig, ax = plt.subplots()

    # Plot with time-based color gradient
    n = len(result.t)
    colors = plt.cm.coolwarm(np.linspace(0, 1, n))

    for i in range(n - 1):
        ax.plot(result.T[i:i+2], result.phi[i:i+2],
                color=colors[i], linewidth=1.5)

    # Mark transition temperatures
    ax.axvline(x=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{IMT}}$')
    ax.axvline(x=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=1.0, alpha=0.7,
               label=f'$T_{{MIT}}$')

    ax.set_xlabel('Temperature [K]')
    ax.set_ylabel('Metallic Fraction $\\phi$')
    ax.set_title('Phase Fraction vs Temperature')
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc='best')

    fig.tight_layout()
    _save_fig(fig, 'phi_vs_temperature.png', save_dir)
    if show:
        plt.show()
    return fig


# =====================================================================
# Dashboard — All Plots in One Figure
# =====================================================================

def plot_dashboard(result, save_dir=None, show=True):
    """
    Generate a comprehensive dashboard with all key plots.

    Layout: 3 rows × 3 columns = 9 subplots covering all
    time-domain and phase-space representations.
    """
    _apply_style()
    fig, axes = plt.subplots(3, 3, figsize=(18, 14))

    t_ms = result.t * 1e3  # convert to ms for display

    # (0,0) Voltage vs Time
    ax = axes[0, 0]
    ax.plot(t_ms, result.V, color=COLORS['voltage'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('V [V]')
    ax.set_title('Voltage')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    # (0,1) Current vs Time
    ax = axes[0, 1]
    ax.plot(t_ms, result.I * 1e3, color=COLORS['current'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('I [mA]')
    ax.set_title('Current')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    # (0,2) Temperature vs Time
    ax = axes[0, 2]
    ax.plot(t_ms, result.T, color=COLORS['temperature'])
    ax.axhline(y=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.axhline(y=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('T [K]')
    ax.set_title('Temperature')

    # (1,0) Resistance vs Time (log)
    ax = axes[1, 0]
    ax.semilogy(t_ms, result.R, color=COLORS['resistance'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('R [Ω]')
    ax.set_title('Resistance')

    # (1,1) Metallic Fraction vs Time
    ax = axes[1, 1]
    ax.plot(t_ms, result.phi, color=COLORS['phi'])
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('$\\phi$')
    ax.set_title('Metallic Fraction')
    ax.set_ylim(-0.05, 1.05)

    # (1,2) Power vs Time
    ax = axes[1, 2]
    ax.plot(t_ms, result.P_joule * 1e6, color=COLORS['power'],
            label='$P_{Joule}$')
    ax.plot(t_ms, result.P_cool * 1e6, color=COLORS['cooling'],
            label='$P_{cool}$')
    ax.set_xlabel('Time [ms]')
    ax.set_ylabel('P [μW]')
    ax.set_title('Power Balance')
    ax.legend(loc='best', fontsize=8)

    # (2,0) I-V Curve
    ax = axes[2, 0]
    n = len(result.t)
    colors = plt.cm.viridis(np.linspace(0, 1, n))
    for i in range(n - 1):
        ax.plot(result.V[i:i+2], result.I[i:i+2] * 1e3,
                color=colors[i], linewidth=1.0)
    ax.set_xlabel('V [V]')
    ax.set_ylabel('I [mA]')
    ax.set_title('I-V Curve')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    ax.axvline(x=0, color='gray', linestyle='--', linewidth=0.5)

    # (2,1) R-T Curve
    ax = axes[2, 1]
    colors_rt = plt.cm.coolwarm(np.linspace(0, 1, n))
    for i in range(n - 1):
        ax.plot(result.T[i:i+2], result.R[i:i+2],
                color=colors_rt[i], linewidth=1.0)
    ax.set_yscale('log')
    ax.axvline(x=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.axvline(x=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.set_xlabel('T [K]')
    ax.set_ylabel('R [Ω]')
    ax.set_title('R-T Curve')

    # (2,2) φ vs T
    ax = axes[2, 2]
    for i in range(n - 1):
        ax.plot(result.T[i:i+2], result.phi[i:i+2],
                color=colors_rt[i], linewidth=1.0)
    ax.axvline(x=result.params.T_IMT, color=COLORS['hysteresis'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.axvline(x=result.params.T_MIT, color=COLORS['iv_trace'],
               linestyle='--', linewidth=0.8, alpha=0.7)
    ax.set_xlabel('T [K]')
    ax.set_ylabel('$\\phi$')
    ax.set_title('Phase Fraction vs T')
    ax.set_ylim(-0.05, 1.05)

    fig.suptitle('VOx Electro-Thermal MIT Memristor — Simulation Dashboard',
                 fontsize=16, fontweight='bold', y=1.01)
    fig.tight_layout()
    _save_fig(fig, 'dashboard.png', save_dir)
    if show:
        plt.show()
    return fig


def generate_all_plots(result, save_dir=None, show=False):
    """
    Generate all individual plots and the dashboard.

    Parameters
    ----------
    result : SimulationResult
        Simulation results from solve_vox().
    save_dir : str, optional
        Directory to save plot images. If None, plots are not saved.
    show : bool, optional
        Whether to display plots interactively. Default: False.

    Returns
    -------
    dict
        Dictionary of figure objects keyed by plot name.
    """
    figs = {}
    figs['voltage_vs_time'] = plot_voltage_vs_time(result, save_dir, show)
    figs['current_vs_time'] = plot_current_vs_time(result, save_dir, show)
    figs['temperature_vs_time'] = plot_temperature_vs_time(result, save_dir, show)
    figs['resistance_vs_time'] = plot_resistance_vs_time(result, save_dir, show)
    figs['phi_vs_time'] = plot_phi_vs_time(result, save_dir, show)
    figs['power_vs_time'] = plot_power_vs_time(result, save_dir, show)
    figs['iv_curve'] = plot_iv_curve(result, save_dir, show)
    figs['rt_curve'] = plot_rt_curve(result, save_dir, show)
    figs['phi_vs_temperature'] = plot_phi_vs_temperature(result, save_dir, show)
    figs['dashboard'] = plot_dashboard(result, save_dir, show)
    return figs
