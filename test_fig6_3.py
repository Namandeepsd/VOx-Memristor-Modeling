import sys
sys.path.append('.')
from src.memristor.vox_parameters import VOxParameters
from src.memristor.vox_solver import solve_vox
import numpy as np

params = VOxParameters(
    bias_mode="voltage",
    waveform_type="triangular",
    V_amplitude=10.0,
    frequency=1.0,
    n_cycles=10,
    
    C_th=1.0e-9,
    G_th=5.0e-5,
    T_amb=297.0,
    T_IMT=315.0,
    T_MIT=298.0,
    delta_T=4.0,
    R_insulating=25000.0,
    R_metallic=300.0,
    tau_phi=50.0e-3,
    
    T_initial=297.0,
    phi_initial=0.0
)

res = solve_vox(params, n_eval=5000)
V = res.V
I = res.I

period = 1.0 / params.frequency
for i in range(params.n_cycles):
    mask = (res.t >= i * period) & (res.t < i * period + period/2)
    V_half = V[mask]
    I_half = I[mask]
    diff = np.diff(np.abs(I_half))
    switch_idx = np.argmax(diff)
    V_switch = V_half[switch_idx]
    print(f"Cycle {i+1}: Negative Switch V = {V_switch:.2f} V")
