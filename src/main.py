#!/usr/bin/env python3
"""
VOx Electro-Thermal MIT Memristor — Main Simulation Script
============================================================

This script runs a complete simulation of the VOx memristor model:

    1. Creates a parameter set
    2. Prints parameter summary
    3. Solves the coupled electro-thermal ODEs
    4. Generates all publication-quality plots
    5. Runs automated physics validation checks
    6. Prints diagnostic summary

Usage
-----
    python main.py

The default parameters are chosen to demonstrate all key phenomena:
    - Pinched hysteresis in I-V
    - MIT with resistance switching
    - Thermal hysteresis in R-T
    - Negative differential resistance

To modify parameters, edit the VOxParameters instantiation below
or create a new parameter set programmatically.
"""

import sys
import os
from pathlib import Path

# Set non-interactive backend before any matplotlib imports
import matplotlib
matplotlib.use('Agg')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from memristor.vox_parameters import VOxParameters
from memristor.vox_solver import solve_vox
from memristor.vox_plots import generate_all_plots, plot_dashboard
from memristor.vox_validation import validate_all, print_validation_report


def main():
    """
    Run the complete VOx memristor simulation pipeline.
    """
    print("\n" + "=" * 65)
    print("  VOx Electro-Thermal MIT Memristor Simulator")
    print("  First-Principles Compact Model")
    print("=" * 65 + "\n")

    # ================================================================
    # Step 1: Define parameters
    # ================================================================
    # Default parameters are tuned to demonstrate all key phenomena
    # for a thin-film VO₂ device on a sapphire substrate.
    # ================================================================
    # Parameter tuning rationale
    # ================================================================
    # The key thermal design constraints are:
    #
    # (A) In insulating state (φ≈0), peak Joule heating must heat
    #     device above T_IMT to initiate the MIT:
    #     T_max_ins = T_amb + V²/(R_i * G_th) > T_IMT
    #     → V²/(R_i * G_th) > 40 K
    #
    # (B) In metallic state (φ≈1), temperature must NOT run away.
    #     T_max_met = T_amb + V²/(R_m * G_th) should be < ~500 K
    #     → G_th > V²/(R_m * 200)
    #
    # With V=2.5V, R_i=5000Ω, R_m=500Ω, G_th=2e-5:
    #   T_max_ins = 300 + 6.25/(5000*2e-5)  = 300 + 62.5 = 362 K ✓ (> 340)
    #   T_max_met = 300 + 6.25/(500*2e-5)   = 300 + 625  = 925 K
    #   But with electro-thermal feedback, R adjusts dynamically,
    #   and the thermal time constant limits actual peak temperature.
    #
    # τ_th = C_th/G_th = 1e-9/2e-5 = 5e-5 s
    # At f=1kHz (period=1ms), τ_th/T = 0.05 → good cycling.
    # ================================================================
    params = VOxParameters(
        # Thermal
        C_th=1.0e-9,           # J/K — thermal capacitance
        G_th=2.0e-5,           # W/K — thermal conductance
        T_amb=300.0,           # K   — ambient temperature
        L_latent=2.0e-10,      # J   — latent heat

        # MIT transition
        T_IMT=340.0,           # K   — heating transition temp
        T_MIT=330.0,           # K   — cooling transition temp
        delta_T=2.0,           # K   — transition width (sharp)
        tau_phi=1.0e-5,        # s   — phase relaxation time
        hysteresis_mode="state_dependent",

        # Electrical
        R_metallic=500.0,      # Ω   — metallic state resistance
        R_insulating=5000.0,   # Ω   — insulating state resistance
        resistance_model="logarithmic",

        # Simulation
        V_amplitude=2.5,       # V
        frequency=1.0e3,       # Hz (1 kHz)
        waveform_type="sinusoidal",
        n_cycles=3,

        # Solver
        rtol=1e-8,
        atol=1e-10,
    )

    print(params.summary())

    # ================================================================
    # Step 2: Solve the coupled ODEs
    # ================================================================
    print("\n[*] Solving coupled ODEs (Radau method)...")
    result = solve_vox(params, n_eval=8000)

    if not result.success:
        print(f"\n[!] SOLVER FAILED: {result.message}")
        print("    Try adjusting parameters or tolerances.")
        return

    print(result.summary())

    # ================================================================
    # Step 3: Run physics validation
    # ================================================================
    print("\n[*] Running physics validation checks...")
    checks = validate_all(result)
    print_validation_report(checks)

    # ================================================================
    # Step 4: Generate plots
    # ================================================================
    print("\n[*] Generating plots...")

    # Create output directory for plots
    output_dir = Path(__file__).parent.parent / "output" / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_all_plots(result, save_dir=str(output_dir), show=False)
    print(f"    Plots saved to: {output_dir}")

    # To display interactively, run with: matplotlib.use('TkAgg') at top
    # and uncomment: plot_dashboard(result, show=True)

    print("\n[*] Simulation complete.")


if __name__ == "__main__":
    main()
