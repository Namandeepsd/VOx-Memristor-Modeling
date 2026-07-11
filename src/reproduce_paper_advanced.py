import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from memristor.vox_advanced_model import solve_advanced_vox, AdvancedVOxParameters

def setup_plot_style():
    plt.style.use('default')
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['mathtext.fontset'] = 'cm'
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['axes.labelsize'] = 12

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)

def generate_fig3_ndr():
    print("[Advanced Model] Running Fig 3 (V-I at 295K, NDR)...")
    p = AdvancedVOxParameters()
    p.T_amb = 295.0
    p.C_p = 5.0e-9 
    p.R_i_ref = 25000.0
    p.R_m_0 = 100.0
    p.R_contact = 75.0
    
    freq = 0.1
    t_end = 1.0 / freq
    t_eval = np.linspace(0, t_end, 10000)
    I_max = 1.0e-3
    
    def I_waveform(t):
        t = np.asarray(t)
        is_scalar = t.ndim == 0
        if is_scalar: t = t[np.newaxis]
            
        cycle = t / (1.0/freq)
        phase = cycle % 1.0
        val = np.zeros_like(t)
        
        m1 = phase < 0.25
        val[m1] = 4 * phase[m1]
        m2 = (phase >= 0.25) & (phase < 0.75)
        val[m2] = 1 - 4 * (phase[m2] - 0.25)
        m3 = phase >= 0.75
        val[m3] = -1 + 4 * (phase[m3] - 0.75)
        
        result = val * I_max
        return result[0] if is_scalar else result

    sol, _ = solve_advanced_vox('current', I_waveform, t_eval, p)
    V_dev = sol.y[2]
    I_src = I_waveform(sol.t)
    
    plt.figure(figsize=(6, 5))
    plt.plot(I_src * 1000, V_dev, 'k-', linewidth=2)
    plt.title('V(I) at 295 K — NDR (Advanced Model) — cf. Fig 3')
    plt.xlabel('I (mA)')
    plt.ylabel('V (Volts)')
    plt.grid(True, alpha=0.3)
    
    out_dir = ensure_dir("output/plots")
    plt.tight_layout()
    plt.savefig(out_dir / "adv_fig3_NDR.png")
    plt.close()


def generate_fig5_multi_amplitude():
    print("[Advanced Model] Running Fig 5 (continuous sweep at 297K)...")
    p = AdvancedVOxParameters()
    p.T_amb = 297.0
    p.C_p = 1.0e-12     # Minimize C_p to prevent oscillations
    p.R_i_ref = 25000.0  # Insulating resistance
    p.R_m_0 = 100.0      # Metallic resistance
    p.R_contact = 75.0   # Contact resistance
    
    p.T_IMT = 315.0
    p.T_MIT = 298.0
    
    p.G_th_0 = 2.0e-4   # Thermal conductance (device heats up properly)
    p.C_th = 2.0e-9      # Fast thermal response (device reaches steady-state T quickly)
    
    # FIGURE-8 KEY: Phase lag creates the enclosed loops!
    # With tau_phi_0 = 1e-6, phi tracks phi_eq instantly → no lag → no figure-8
    # With tau_phi_0 = 5e-3, phi takes ~10ms to catch up to equilibrium:
    #   HEATING: phi < phi_eq → device is MORE insulating than equilibrium → higher V
    #   COOLING: phi > phi_eq → device is MORE metallic than equilibrium → lower V
    #   Same current, different voltage → enclosed loop!
    p.tau_phi_0 = 5.0e-3   # 5ms base phase relaxation (slow domain growth)
    p.E_a_kinetics = 0.03  # Low activation → tau doesn't blow up at low T
    
    freq = 5.0
    period = 1.0 / freq
    num_cycles = 45
    t_end = num_cycles * period
    t_eval = np.linspace(0, t_end, 80000)
    
    def I_waveform(t):
        t = np.asarray(t)
        is_scalar = t.ndim == 0
        if is_scalar: t = t[np.newaxis]
        
        cycle = t / period
        phase = cycle % 1.0
        val = np.zeros_like(t)
        
        # Triangle waveform (exact match for paper Fig 5a)
        m1 = phase < 0.25
        val[m1] = 4 * phase[m1]
        m2 = (phase >= 0.25) & (phase < 0.75)
        val[m2] = 1 - 4 * (phase[m2] - 0.25)
        m3 = phase >= 0.75
        val[m3] = -1 + 4 * (phase[m3] - 0.75)
        
        envelope = (t / t_end) * 22e-3
        res = val * envelope
        return res[0] if is_scalar else res

    sol, _ = solve_advanced_vox('current', I_waveform, t_eval, p)
    V_dev = sol.y[2]
    I_src = I_waveform(sol.t)
    
    fig, axs = plt.subplots(2, 3, figsize=(12, 8))
    fig.suptitle('V(I) at 297 K — Continuous Sweep (Advanced Model) — cf. Fig 5c', fontsize=14, fontweight='bold')
    axs = axs.flatten()
    
    target_amps = [1e-3, 3e-3, 5e-3, 10e-3, 15e-3, 20e-3]
    colors = ['k', 'r', 'b', 'm', 'orange', 'g']
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    
    for i, (amp, c, label) in enumerate(zip(target_amps, colors, labels)):
        t_target = amp * t_end / 22e-3
        cyc_idx = int(t_target / period)
        
        t_start = cyc_idx * period
        t_end_cyc = (cyc_idx + 1) * period
        mask = (sol.t >= t_start) & (sol.t <= t_end_cyc)
        
        ax = axs[i]
        ax.plot(I_src[mask]*1000, V_dev[mask], color=c, linewidth=1.5)
        
        ax.set_title(label, loc='left', color=c, fontweight='bold')
        ax.set_xlabel('I (mA)')
        ax.set_ylabel('V (Volts)')
        ax.grid(False)
        ax.text(0.85, 0.1, '297K', transform=ax.transAxes, fontweight='bold')
        
        if i == 0: ax.set_xlim(-1, 1); ax.set_ylim(-4, 4)
        elif i == 1: ax.set_xlim(-2, 2); ax.set_ylim(-4, 4)
        elif i == 2: ax.set_xlim(-3, 3); ax.set_ylim(-4, 4)
        elif i == 3: ax.set_xlim(-6, 6); ax.set_ylim(-4, 4)
        elif i == 4: ax.set_xlim(-15, 15); ax.set_ylim(-4, 4)
        elif i == 5: ax.set_xlim(-20, 20); ax.set_ylim(-4, 4)

    out_dir = ensure_dir("output/plots")
    plt.tight_layout()
    plt.savefig(out_dir / "adv_fig5_multi.png")
    plt.close()


def generate_dashboard():
    print("[Advanced Model] Generating dashboard...")
    p = AdvancedVOxParameters()
    p.C_p = 5.0e-9
    
    freq = 1.0
    t_end = 3.0 / freq
    t_eval = np.linspace(0, t_end, 10000)
    
    I_max = 10e-3
    def I_waveform(t):
        return I_max * np.sin(2 * np.pi * freq * t)
        
    sol, _ = solve_advanced_vox('current', I_waveform, t_eval, p)
    T_res = sol.y[0]
    phi_res = sol.y[1]
    V_dev = sol.y[2]
    I_src = I_waveform(sol.t)
    
    from memristor.vox_advanced_model import resistance_bruggeman
    R_dev = np.array([resistance_bruggeman(T, ph, p) for T, ph in zip(T_res, phi_res)])
    
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Advanced VOx Model — 3-ODE Dashboard', fontsize=16, fontweight='bold')
    
    axs[0,0].plot(I_src*1000, V_dev, 'k')
    axs[0,0].set_title('V(I) Characteristic (Snap-backs visible)')
    axs[0,0].set_xlabel('I_src (mA)')
    axs[0,0].set_ylabel('V_dev (Volts)')
    axs[0,0].grid(True, alpha=0.3)
    
    axs[0,1].plot(sol.t, T_res, 'r')
    axs[0,1].set_title('Device Temperature')
    axs[0,1].set_xlabel('Time (s)')
    axs[0,1].set_ylabel('Temperature (K)')
    axs[0,1].grid(True, alpha=0.3)
    
    axs[1,0].semilogy(sol.t, R_dev, 'b')
    axs[1,0].set_title('Device Resistance (Bruggeman Percolation)')
    axs[1,0].set_xlabel('Time (s)')
    axs[1,0].set_ylabel('Resistance (Ω)')
    axs[1,0].grid(True, alpha=0.3)
    
    axs[1,1].plot(sol.t, phi_res, 'g')
    axs[1,1].set_title('Phase Fraction (Rutile Metallic)')
    axs[1,1].set_xlabel('Time (s)')
    axs[1,1].set_ylabel('φ (metallic fraction)')
    axs[1,1].grid(True, alpha=0.3)
    
    out_dir = ensure_dir("output/plots")
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.savefig(out_dir / "adv_dashboard.png")
    plt.close()

if __name__ == "__main__":
    setup_plot_style()
    print("=" * 60)
    print("  ADVANCED VOx Model — Experimental Replication")
    print("  (Bruggeman EMT + Parasitic Capacitance 3-ODE)")
    print("=" * 60)
    generate_fig3_ndr()
    generate_fig5_multi_amplitude()
    generate_dashboard()
    print("\n[DONE] All advanced-model plots saved to output/plots/")
