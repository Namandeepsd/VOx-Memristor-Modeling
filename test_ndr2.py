import sys
sys.path.append('.')
from src.memristor.vox_advanced_model import solve_advanced_vox, AdvancedVOxParameters
import numpy as np

p = AdvancedVOxParameters()
p.T_amb = 295.0
p.C_p = 1.0e-12 
p.R_i_ref = 12000.0
p.R_m_0 = 100.0
p.R_contact = 75.0
p.tau_phi_0 = 4.0e-5

freq = 1.0
t_end = 1.0 / freq
t_eval = np.linspace(0, t_end, 10000)
I_max = 1.5e-3

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
I_src = I_waveform(sol.t)
V = sol.y[2]

# check if there is snap back (V decreases while I increases)
# during the first quarter cycle (I increasing)
idx_quarter = len(t_eval)//4
I_inc = I_src[:idx_quarter]
V_inc = V[:idx_quarter]
diff_V = np.diff(V_inc)
if np.any(diff_V < -0.01):
    print("SNAP-BACK DETECTED in forward branch!")
else:
    print("NO SNAP-BACK in forward branch (monotonically increasing V).")
