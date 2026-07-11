import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
import os

from memristor.vox_advanced_model import solve_advanced_vox, AdvancedVOxParameters

def setup_plot_style():
    plt.style.use('default')
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['mathtext.fontset'] = 'cm'

def generate_fig5_continuous():
    p = AdvancedVOxParameters()
    p.T_amb = 297.0
    p.C_p = 5.0e-9      # Parasitic cap for snap-back
    p.R_i_ref = 25000.0 # Higher initial resistance to reach ~4V peak
    p.R_m_0 = 100.0     # Metallic resistance
    p.R_contact = 75.0  # Total R_m ~ 175 Ohms (3.5V at 20mA)
    p.G_th_0 = 2.0e-4   # Adjust thermal conductance
    p.C_th = 5.0e-6     # Adjust thermal mass
    p.tau_phi_0 = 1e-6
    
    # Paper Fig 5(a) shows ~40-50 cycles over 14 units of time.
    # If time is seconds, freq ~ 3.5 Hz. Let's use 5 Hz.
    freq = 5.0 
    period = 1.0 / freq
    num_cycles = 45
    t_end = num_cycles * period
    t_eval = np.linspace(0, t_end, 50000)
    
    def I_waveform(t):
        t = np.asarray(t)
        is_scalar = t.ndim == 0
        if is_scalar: t = t[np.newaxis]
        
        cycle = t / period
        phase = cycle % 1.0
        val = np.zeros_like(t)
        
        # Triangle wave 0 -> 1 -> 0 -> -1 -> 0
        m1 = phase < 0.25
        val[m1] = 4 * phase[m1]
        m2 = (phase >= 0.25) & (phase < 0.75)
        val[m2] = 1 - 4 * (phase[m2] - 0.25)
        m3 = phase >= 0.75
        val[m3] = -1 + 4 * (phase[m3] - 0.75)
        
        # Envelope grows from 0 to 22 mA
        envelope = (t / t_end) * 22e-3
        res = val * envelope
        return res[0] if is_scalar else res

    print("Simulating continuous sweep...")
    sol, _ = solve_advanced_vox('current', I_waveform, t_eval, p)
    print("Simulation done.")
    
    V_dev = sol.y[2]
    I_src = I_waveform(sol.t)
    
    # Plotting exactly like the paper's 6 panels
    fig, axs = plt.subplots(2, 3, figsize=(12, 8))
    fig.suptitle('V(I) at 297 K — Continuous Sweep (Advanced Model) — cf. Fig 5c', fontsize=14)
    axs = axs.flatten()
    
    # The paper labels are roughly at these amplitudes
    target_amps = [1e-3, 3e-3, 5e-3, 10e-3, 15e-3, 20e-3]
    colors = ['k', 'r', 'b', 'm', 'orange', 'g']
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    
    for i, (amp, c, label) in enumerate(zip(target_amps, colors, labels)):
        # Find which cycle reaches this amplitude
        t_target = amp * t_end / 22e-3
        cyc_idx = int(t_target / period)
        
        t_start = cyc_idx * period
        t_end_cyc = (cyc_idx + 1) * period
        mask = (sol.t >= t_start) & (sol.t <= t_end_cyc)
        
        ax = axs[i]
        ax.plot(I_src[mask]*1000, V_dev[mask], color=c, linewidth=1.5)
        
        # Formatting to match paper style
        ax.set_title(label, loc='left', color=c, fontweight='bold')
        ax.set_xlabel('I (mA)')
        ax.set_ylabel('V (Volts)')
        ax.grid(False)
        ax.text(0.85, 0.1, '297K', transform=ax.transAxes, fontweight='bold')
        
        # Set symmetric limits
        max_I = np.max(np.abs(I_src[mask]*1000))
        max_V = np.max(np.abs(V_dev[mask]))
        
        # Paper ranges:
        if i == 0: ax.set_xlim(-1, 1); ax.set_ylim(-4, 4)
        elif i == 1: ax.set_xlim(-2, 2); ax.set_ylim(-4, 4)
        elif i == 2: ax.set_xlim(-3, 3); ax.set_ylim(-4, 4)
        elif i == 3: ax.set_xlim(-6, 6); ax.set_ylim(-4, 4)
        elif i == 4: ax.set_xlim(-15, 15); ax.set_ylim(-4, 4)
        elif i == 5: ax.set_xlim(-20, 20); ax.set_ylim(-4, 4)

    plt.tight_layout()
    plt.savefig('output/plots/fig5_continuous_exact.png')
    print("Saved output/plots/fig5_continuous_exact.png")

if __name__ == '__main__':
    setup_plot_style()
    generate_fig5_continuous()
