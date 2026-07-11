import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass

@dataclass
class AdvancedVOxParameters:
    # ---------------- Thermal Parameters ----------------
    C_th: float = 5.0e-9            # Thermal mass [J/K]
    G_th_0: float = 3.0e-4          # Base thermal conductance [W/K]
    G_th_nonlinear: float = 5.0e-7  # Non-linear thermal conductance [W/K^2]
    T_amb: float = 297.0            # Ambient temperature [K]
    
    # ---------------- Transition Parameters ----------------
    T_IMT: float = 308.0            # Heating transition temp [K]
    T_MIT: float = 300.0            # Cooling transition temp [K]
    delta_T: float = 3.5            # Transition width parameter [K]
    L_latent: float = 5.0e-9        # Latent heat [J]
    
    # ---------------- Resistance (Bruggeman) Parameters ----------------
    R_i_ref: float = 12000.0        # Insulating resistance at T_amb [Ohms]
    E_g: float = 0.45               # Activation energy for semiconductor [eV]
    R_m_0: float = 80.0             # Metallic resistance at T_amb [Ohms]
    alpha_m: float = 1.2e-3         # Metallic TCR [1/K]
    R_contact: float = 50.0         # Series contact resistance [Ohms]
    
    # ---------------- Kinetics ----------------
    tau_phi_0: float = 5.0e-7       # Base relaxation time [s]
    E_a_kinetics: float = 0.15      # Activation energy for domain nucleation [eV]

    # ---------------- Parasitics (3-ODE Specific) ----------------
    C_p: float = 2.0e-9             # Parasitic parallel capacitance [F] (2 nF for strong snap-back)
    R_series: float = 50.0          # Additional series load/contact resistance outside device loop [Ohms]

k_B = 8.617333262145e-5 # eV/K

def R_insulating(T: float, p: AdvancedVOxParameters) -> float:
    return p.R_i_ref * np.exp((p.E_g / (2 * k_B)) * (1/T - 1/p.T_amb))

def R_metallic(T: float, p: AdvancedVOxParameters) -> float:
    return p.R_m_0 * (1 + p.alpha_m * (T - p.T_amb))

def resistance_bruggeman(T: float, phi: float, p: AdvancedVOxParameters) -> float:
    """
    Computes effective resistance using 2D Symmetric Bruggeman Effective Medium Theory.
    phi * (sigma_m - sigma_e)/(sigma_m + sigma_e) + (1-phi) * (sigma_i - sigma_e)/(sigma_i + sigma_e) = 0
    where sigma = 1/rho. For lumped resistance we can use R instead of rho if dimensions are assumed 1:1.
    Solving the quadratic equation for sigma_e (effective conductivity) and converting back to R_e.
    """
    # Clip phi strictly to avoid math errors
    phi = np.clip(phi, 0.0, 1.0)
    
    Ri = R_insulating(T, p)
    Rm = R_metallic(T, p)
    
    si = 1.0 / Ri
    sm = 1.0 / Rm
    
    # In 2D, the equation simplifies to a quadratic for effective conductivity s_e:
    # A * s_e^2 + B * s_e + C = 0
    # Actually, the 2D Bruggeman equation for conductivity is:
    # s_e = 0.5 * [ (2*phi - 1)*sm + (1 - 2*phi)*si + sqrt( ((2*phi - 1)*sm + (1 - 2*phi)*si)^2 + 4*sm*si ) ]
    
    term = (2*phi - 1)*sm + (1 - 2*phi)*si
    s_e = 0.5 * (term + np.sqrt(term**2 + 4*sm*si))
    
    R_device = 1.0 / s_e
    
    return R_device + p.R_contact

def G_thermal(T: float, p: AdvancedVOxParameters) -> float:
    return p.G_th_0 + p.G_th_nonlinear * (T - p.T_amb)

def tau_phi(T: float, p: AdvancedVOxParameters) -> float:
    # Arrhenius-accelerated kinetics at high temperatures
    return p.tau_phi_0 * np.exp(p.E_a_kinetics / (k_B * T))

def phi_eq(T: float, phi: float, p: AdvancedVOxParameters) -> float:
    T_c = p.T_MIT + (p.T_IMT - p.T_MIT) * (1.0 - phi)
    arg = -(T - T_c) / p.delta_T
    # Prevent overflow
    arg = np.clip(arg, -500, 500)
    return 1.0 / (1.0 + np.exp(arg))

def system_rhs_3ode_current(t: float, state, I_src_func, p: AdvancedVOxParameters):
    """
    3-ODE system for CURRENT-BIASED mode with parasitic capacitance.
    State vector: [T, phi, V_dev]
    I_src_func(t) returns the current forced into the (Device || C_p) network.
    """
    T, phi, V_dev = state
    phi = np.clip(phi, 0.0, 1.0)
    
    I_src = I_src_func(t)
    
    # Calculate resistance
    R_dev = resistance_bruggeman(T, phi, p)
    
    # 1. Voltage ODE (Parasitic Capacitor)
    # I_src = I_cap + I_dev = C_p * (dV_dev/dt) + V_dev / R_dev
    dV_dt = (I_src - (V_dev / R_dev)) / p.C_p
    
    # 2. Thermal ODE
    P_joule = (V_dev**2) / R_dev
    dT_dt = (P_joule - G_thermal(T, p) * (T - p.T_amb)) / p.C_th
    
    # 3. Phase ODE
    phieq = phi_eq(T, phi, p)
    dphi_dt = (phieq - phi) / tau_phi(T, p)
    
    # Latent heat correction
    dT_dt -= (p.L_latent * dphi_dt) / p.C_th
    
    return [dT_dt, dphi_dt, dV_dt]

def system_rhs_3ode_voltage(t: float, state, V_src_func, p: AdvancedVOxParameters):
    """
    3-ODE system for VOLTAGE-BIASED mode with parasitic capacitance and series resistor R_s.
    State vector: [T, phi, V_dev]
    V_src_func(t) returns the voltage applied to the series combination of R_s and (Device || C_p).
    """
    T, phi, V_dev = state
    phi = np.clip(phi, 0.0, 1.0)
    
    V_src = V_src_func(t)
    
    R_dev = resistance_bruggeman(T, phi, p)
    
    # Current through series resistor
    I_rs = (V_src - V_dev) / p.R_series
    
    # I_rs splits into C_p and Device
    # I_rs = C_p * (dV_dev/dt) + (V_dev / R_dev)
    dV_dt = (I_rs - (V_dev / R_dev)) / p.C_p
    
    P_joule = (V_dev**2) / R_dev
    dT_dt = (P_joule - G_thermal(T, p) * (T - p.T_amb)) / p.C_th
    
    phieq = phi_eq(T, phi, p)
    dphi_dt = (phieq - phi) / tau_phi(T, p)
    
    dT_dt -= (p.L_latent * dphi_dt) / p.C_th
    
    return [dT_dt, dphi_dt, dV_dt]

def solve_advanced_vox(bias_type, source_func, t_eval, p=None):
    if p is None:
        p = AdvancedVOxParameters()
        
    t_span = [t_eval[0], t_eval[-1]]
    
    # Initial state: T = T_amb, phi = 0, V_dev = 0
    y0 = [p.T_amb, 0.0, 0.0]
    
    if bias_type == 'current':
        rhs = lambda t, y: system_rhs_3ode_current(t, y, source_func, p)
    elif bias_type == 'voltage':
        rhs = lambda t, y: system_rhs_3ode_voltage(t, y, source_func, p)
    else:
        raise ValueError("bias_type must be 'current' or 'voltage'")
        
    sol = solve_ivp(
        rhs, 
        t_span, 
        y0, 
        t_eval=t_eval, 
        method='Radau', # Radau is critical for highly stiff 3-ODE system
        rtol=1e-5, 
        atol=1e-8
    )
    
    return sol, p
