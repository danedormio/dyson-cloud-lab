"""Dyson Cloud Laboratory: one REBOUND N-body system for every physical object.

All bodies—including Sun, Earth and incoming cloud elements—participate in
one massive-particle IAS15 integration. No body is pinned to the origin.
The 1 kg baseline describes cloud elements, not planets or the Sun.

Coupling/actuation will be implemented as separately verified, symmetric
momentum exchanges. There is deliberately NO arbitrary capture force here.
"""
import math
import threading

import rebound

AU = 149_597_870_700.0
SUN_KG = 1.98847e30
EARTH_KG = 5.9722e24
DAY = 86400.0

class CloudWorld:
    def __init__(self, cloud_count=72):
        self.lock = threading.RLock()
        self.reset(cloud_count)

    def reset(self, cloud_count=72):
        with self.lock:
            self.sim = rebound.Simulation()
            self.sim.units = ("m", "s", "kg")
            self.sim.integrator = "ias15"
            self.sim.dt = 3600.0
            self.names = ["Sun", "Earth"]
            self.roles = ["star", "planet"]
            self.sim.add(m=SUN_KG, x=0, y=0, z=0)
            earth_v = math.sqrt(self.sim.G * (SUN_KG + EARTH_KG) / AU)
            self.sim.add(m=EARTH_KG, x=AU, y=0, z=0, vy=earth_v)
            for i in range(int(cloud_count)):
                # Deterministic, non-coincident orbital phases and radii.
                radius = (0.8 + 3.2 * (i + 0.5) / max(1, cloud_count)) * AU
                phase = i * 2.399963229728653
                speed = math.sqrt(self.sim.G * SUN_KG / radius)
                self.sim.add(m=1.0,
                             x=radius * math.cos(phase),
                             y=radius * math.sin(phase),
                             vx=-speed * math.sin(phase),
                             vy=speed * math.cos(phase))
                self.names.append(f"Cloud {i+1}")
                self.roles.append("cloud")
            self.sim.move_to_com()
            self.initial_energy = self.sim.energy()
            return self.state()

    def add_incoming(self, speed_kms=25, impact_au=0.5, offset_degrees=0):
        with self.lock:
            outer = 4.0 * AU
            theta = math.radians(float(offset_degrees))
            # Angle acts on perpendicular vector; negative impact mirrors it.
            b = float(impact_au) * AU
            self.sim.add(m=1.0, x=-1.4*outer, y=b*math.cos(theta),
                         z=b*math.sin(theta), vx=float(speed_kms)*1000.0)
            self.names.append(f"Tracked {len(self.names)}")
            self.roles.append("tracked")
            return self.state()

    def step(self, seconds=3600):
        seconds = float(seconds)
        if not 0 < seconds <= 30 * DAY:
            raise ValueError("step must be between 0 and 30 days")
        with self.lock:
            self.sim.integrate(self.sim.t + seconds, exact_finish_time=1)
            return self.state()

    def state(self):
        with self.lock:
            particles = [
                {"id":i, "name":self.names[i], "role":self.roles[i],
                 "mass_kg":float(p.m),
                 "x_m":float(p.x), "y_m":float(p.y), "z_m":float(p.z),
                 "vx_ms":float(p.vx), "vy_ms":float(p.vy), "vz_ms":float(p.vz)}
                for i, p in enumerate(self.sim.particles)
            ]
            total_m = sum(p["mass_kg"] for p in particles)
            momentum = [
                sum(p["mass_kg"] * p[k] for p in particles)
                for k in ("vx_ms", "vy_ms", "vz_ms")
            ]
            energy = self.sim.energy()
            return {
                "engine": "REBOUND IAS15", "time_s":float(self.sim.t),
                "gravitational_energy_j":energy,
                "energy_relative_drift":(
                    (energy - self.initial_energy) / abs(self.initial_energy)
                    if self.initial_energy else None
                ),
                "momentum_kg_ms":momentum, "total_mass_kg":total_m,
                "bodies":particles,
                "coupling_enabled":False,
                "note":"Gravity-only REBOUND reference: coupling and capture not enabled."
            }
