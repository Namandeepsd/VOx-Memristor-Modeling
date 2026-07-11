import sys
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from memristor.vox_parameters import VOxParameters
from memristor.vox_solver import solve_vox

def run_fig3():
    print("Running simulation for Figure 3 (V-I at 295K, Current Bias, NDR)...")
    params = VOxParameters(
        bias_mode="current",
        # Triangular current waveform
        waveform_type="triangular",
        V_amplitude=1.5e-3, # 1.5 mA peak current
        frequency=1.0, # slow sweep
        n_cycles=1,
        
        # Extracted parameters
        C_th=1.0e-9,
        G_th=5.0e-5,
        T_amb=295.0, # 295K cooling
        T_IMT=308.0,
        T_MIT=302.0,
        delta_T=4.0,
        R_insulating=25000.0,
        R_metallic=100.0,
        
        T_initial=295.0,
        phi_initial=0.0
    )
    
    result = solve_vox(params, n_eval=1000)
    
    plt.figure(figsize=(6, 5))
    # Note: paper plots V vs I, but typical V-I is I vs V. 
    # Let's plot V (y-axis) vs I (x-axis) in mA to match Fig 3
    plt.plot(result.I * 1e3, result.V, 'k-', linewidth=1.5)
    plt.xlabel("I (mA)", fontsize=12)
    plt.ylabel("V (Volts)", fontsize=12)
    plt.title("Reproduced Fig 3 (295 K Cooling)", fontsize=14)
    plt.grid(True, alpha=0.3)
    
    out_path = Path(__file__).parent.parent / "output" / "plots" / "reproduced_fig3.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved to {out_path}")


def run_fig5():
    print("Running simulation for Figure 5 (Current Bias Sweeps at 297K)...")
    
    plt.figure(figsize=(6, 5))
    
    # Amplitudes matching ranges A-F roughly
    amplitudes = [1e-3, 3e-3, 5e-3, 10e-3, 15e-3, 20e-3]
    colors = ['black', 'red', 'blue', 'magenta', 'orange', 'green']
    
    for amp, color in zip(amplitudes, colors):
        params = VOxParameters(
            bias_mode="current",
            waveform_type="triangular",
            V_amplitude=amp,
            frequency=1.0,
            n_cycles=1,
            
            C_th=1.0e-9,
            G_th=5.0e-5,
            T_amb=297.0,
            T_IMT=308.0,
            T_MIT=302.0,
            delta_T=4.0,
            R_insulating=25000.0,
            R_metallic=100.0,
            
            T_initial=297.0,
            phi_initial=0.0
        )
        
        result = solve_vox(params, n_eval=1000)
        plt.plot(result.I * 1e3, result.V, color=color, linewidth=1.5, label=f"Max I={amp*1000:.0f}mA")
        
    plt.xlabel("I (mA)", fontsize=12)
    plt.ylabel("V (Volts)", fontsize=12)
    plt.title("Reproduced Fig 5 (297 K)", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    out_path = Path(__file__).parent.parent / "output" / "plots" / "reproduced_fig5.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved to {out_path}")

def run_fig6():
    print("Running simulation for Figure 6 (32 Voltage Sweeps)...")
    
    params = VOxParameters(
        bias_mode="voltage",
        waveform_type="triangular",
        V_amplitude=10.0, # 10 V peak
        frequency=1.0,
        n_cycles=10, # Doing 10 cycles to show evolution
        
        C_th=1.0e-9,
        G_th=5.0e-5,
        T_amb=297.0,
        T_IMT=308.0,
        T_MIT=302.0,
        delta_T=4.0,
        R_insulating=25000.0,
        R_metallic=100.0,
        
        T_initial=297.0,
        phi_initial=0.0
    )
    
    result = solve_vox(params, n_eval=5000)
    
    plt.figure(figsize=(6, 5))
    
    # Split by cycle
    period = 1.0 / params.frequency
    for i in range(params.n_cycles):
        mask = (result.t >= i * period) & (result.t < (i + 1) * period)
        if i == 0:
            color = 'black'
            lw = 2.0
            label = 'Cycle 1'
        elif i == params.n_cycles - 1:
            color = 'red'
            lw = 1.5
            label = f'Cycle {params.n_cycles}'
        else:
            color = plt.cm.viridis(i / params.n_cycles)
            lw = 1.0
            label = None
            
        plt.plot(result.V[mask], result.I[mask] * 1e3, color=color, linewidth=lw, label=label, alpha=0.7)
        
    plt.xlabel("V (Volts)", fontsize=12)
    plt.ylabel("I (mA)", fontsize=12)
    plt.title("Reproduced Fig 6 (Voltage Bias, 10 Sweeps)", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    out_path = Path(__file__).parent.parent / "output" / "plots" / "reproduced_fig6.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    out_dir = Path(__file__).parent.parent / "output" / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    run_fig3()
    run_fig5()
    run_fig6()
