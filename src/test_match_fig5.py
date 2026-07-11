import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# Parameters
T_amb = 297.0
T_IMT = 308.0
T_MIT = 300.0
delta_T = 1.5
R_i_ref = 25000.0
R_m_0 = 150.0
R_contact = 25.0
G_th = 8.5e-5
C_th = 1.5e-9
tau_0 = 1e-6
L = 1e-9

def R_ins(T):
    # mild arrhenius
    return R_i_ref * np.exp(0.1 / (2 * 8.617e-5) * (1/T - 1/T_amb))

def R_tot(T, phi):
    phi = np.clip(phi, 0, 1)
    Ri = R_ins(T)
    Rm = R_m_0
    R_mix = (Rm**phi) * (Ri**(1-phi))
    return R_mix + R_contact

def phi_eq(T, phi):
    Tc = T_MIT + (T_IMT - T_MIT) * (1 - phi)
    return 1.0 / (1.0 + np.exp(-(T - Tc) / delta_T))

def rhs(t, state, I_func):
    T, phi = state
    phi = np.clip(phi, 0, 1)
    I = I_func(t)
    
    R = R_tot(T, phi)
    P = (I**2) * R
    
    # phi kinetics
    phieq = phi_eq(T, phi)
    dphi = (phieq - phi) / tau_0
    
    # thermal
    dT = (P - G_th * (T - T_amb) - L * dphi) / C_th
    
    return [dT, dphi]

# Generate continuous growing triangle waveform
frequency = 100 # Hz
period = 1 / frequency
num_cycles = 25
t_end = num_cycles * period
t_eval = np.linspace(0, t_end, 10000)

def I_waveform(t):
    # Vectorized
    t = np.asarray(t)
    cycle = t / period
    phase = cycle % 1.0
    val = np.zeros_like(t)
    
    m1 = phase < 0.25
    val[m1] = 4 * phase[m1]
    
    m2 = (phase >= 0.25) & (phase < 0.75)
    val[m2] = 1 - 4 * (phase[m2] - 0.25)
    
    m3 = phase >= 0.75
    val[m3] = -1 + 4 * (phase[m3] - 0.75)
    
    envelope = (t / t_end) * 22e-3
    return val * envelope

sol = solve_ivp(rhs, [0, t_end], [T_amb, 0.0], t_eval=t_eval, method='Radau', args=(I_waveform,))

T_res = sol.y[0]
phi_res = sol.y[1]
I_res = I_waveform(sol.t)
V_res = I_res * np.array([R_tot(T_res[i], phi_res[i]) for i in range(len(sol.t))])

# Plotting
fig, axs = plt.subplots(2, 3, figsize=(15, 10))
axs = axs.flatten()

target_amps = [1e-3, 3e-3, 5e-3, 10e-3, 15e-3, 20e-3]
cycle_indices = []
for amp in target_amps:
    t_target = amp * t_end / 22e-3
    cycle_idx = int(t_target / period)
    cycle_indices.append(cycle_idx)

colors = ['k', 'r', 'b', 'm', 'orange', 'g']
labels = ['A (1mA)', 'B (3mA)', 'C (5mA)', 'D (10mA)', 'E (15mA)', 'F (20mA)']

for i, (cyc_idx, c, label) in enumerate(zip(cycle_indices, colors, labels)):
    t_start = cyc_idx * period
    t_end_cyc = (cyc_idx + 1) * period
    mask = (sol.t >= t_start) & (sol.t <= t_end_cyc)
    
    ax = axs[i]
    ax.plot(I_res[mask]*1000, V_res[mask], color=c)
    ax.set_title(label)
    ax.set_xlabel('I (mA)')
    ax.set_ylabel('V (Volts)')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('output/plots/test_fig5_continuous.png')
print("Saved test_fig5_continuous.png")
