import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ensure `src` is on sys.path so package imports work when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from memristor.hp import HPMemristor

mem = HPMemristor()
dt = 1e-4        # Time step: 0.0001 seconds (100 microseconds)
f = 0.5          # Frequency: 0.5 Hz (1 cycle every 2 seconds)
A = 1.5          # Amplitude: 1.5 Volts
T = 4 / f        # Total time: 8 seconds (4 full cycles at 0.5 Hz)
t = np.arange(0, T, dt)

V = []
I = []
for ti in t:
    v = A * np.sin(2 * np.pi * f * ti) #voltage signal
    i = mem.current(v)
    mem.update_state(v, dt)
    V.append(v)
    I.append(i)

plt.figure()
plt.plot(V, I)
plt.xlabel("Voltage (V)")
plt.ylabel("Current (A)")
plt.title("HP Memristor V-I Hysteresis")
out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'hp_vi.png'))
plt.savefig(out_file)
print(f"Saved plot to {out_file}")