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
    
    C_th=1.0e-8,
    G_th=5.0e-5,
    T_amb=297.0,
    T_IMT=315.0,
    T_MIT=298.0,
    delta_T=4.0,
    R_insulating=25000.0,
    R_metallic=300.0,
    
    T_initial=297.0,
    phi_initial=0.0
)

res = solve_vox(params, n_eval=5000)
V = res.V
I = res.I

# Check if there is drift between Cycle 1 and Cycle 10
period = 1.0 / params.frequency
cycle1_mask = (res.t >= 0) & (res.t < period)
cycle10_mask = (res.t >= 9 * period) & (res.t < 10 * period)

V1 = V[cycle1_mask]
I1 = I[cycle1_mask]
V10 = V[cycle10_mask]
I10 = I[cycle10_mask]

# Find the switching voltage (where current jumps)
diff1 = np.diff(np.abs(I1))
switch_idx1 = np.argmax(diff1)
V_switch1 = V1[switch_idx1]

diff10 = np.diff(np.abs(I10))
switch_idx10 = np.argmax(diff10)
V_switch10 = V10[switch_idx10]

print(f"Cycle 1 switch V: {V_switch1:.2f} V")
print(f"Cycle 10 switch V: {V_switch10:.2f} V")
