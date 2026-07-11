import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ensure `src` is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from memristor.hp import HPMemristor


def run_simulation(A, f, dt, T_mult=4, name_prefix="set"):
    mem = HPMemristor()
    T = T_mult / f
    t = np.arange(0, T, dt)

    V = np.zeros_like(t)
    I = np.zeros_like(t)
    X = np.zeros_like(t)
    R = np.zeros_like(t)

    for idx, ti in enumerate(t):
        v = A * np.sin(2 * np.pi * f * ti)
        i = mem.current(v)
        V[idx] = v
        I[idx] = i
        X[idx] = mem.state()
        R[idx] = mem.resistance()
        mem.update_state(v, dt)

    # V-I hysteresis
    plt.figure(figsize=(6,4))
    plt.plot(V, I, lw=0.5)
    plt.xlabel('Voltage (V)')
    plt.ylabel('Current (A)')
    plt.title(f'HP Memristor V-I Hysteresis (A={A}, f={f} Hz)')
    out_vi = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'hp_vi_{name_prefix}.png'))
    plt.savefig(out_vi, dpi=150)
    plt.close()

    # x vs time
    plt.figure(figsize=(6,3))
    plt.plot(t, X)
    plt.xlabel('Time (s)')
    plt.ylabel('State x')
    plt.title(f'State x vs Time (A={A}, f={f} Hz)')
    out_x = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'hp_x_{name_prefix}.png'))
    plt.savefig(out_x, dpi=150)
    plt.close()

    # R vs time
    plt.figure(figsize=(6,3))
    plt.plot(t, R)
    plt.xlabel('Time (s)')
    plt.ylabel('Resistance (Ohm)')
    plt.title(f'Memristance vs Time (A={A}, f={f} Hz)')
    out_r = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', f'hp_r_{name_prefix}.png'))
    plt.savefig(out_r, dpi=150)
    plt.close()

    print(f"Saved: {out_vi}, {out_x}, {out_r}")


if __name__ == '__main__':
    # Three different input parameter sets
    sets = [
        (1.5, 0.5, 1e-4, 4, 'set1'),
        (2.5, 1.0, 5e-5, 4, 'set2'),
        (0.8, 0.2, 2e-4, 4, 'set3'),
    ]

    for A, f, dt, mult, name in sets:
        run_simulation(A, f, dt, T_mult=mult, name_prefix=name)
