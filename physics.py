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

    def restore(self, checkpoint):
        """Restore a validated checkpoint into a NEW REBOUND simulation atomically.

        This preserves N-body state, not IAS15's internal adaptive-history state.
        It is an accuracy-tested restart, not a bitwise-exact continuation.
        """
        bodies = checkpoint.get("bodies")
        if checkpoint.get("version") != 1 or not isinstance(bodies, list) or not 2 <= len(bodies) <= 2002:
            raise ValueError("invalid checkpoint version or body count")
        try:
            t = float(checkpoint["time_s"])
            if not math.isfinite(t) or t < 0:
                raise ValueError("invalid checkpoint time")
            new = rebound.Simulation()
            new.units = ("m", "s", "kg")
            new.integrator = "ias15"
            new.dt = 3600.0
            names, roles = [], []
            for i, b in enumerate(bodies):
                m = float(b["mass_kg"])
                x, y, z = (float(b[k]) for k in ("x_m", "y_m", "z_m"))
                vx, vy, vz = (float(b[k]) for k in ("vx_ms", "vy_ms", "vz_ms"))
                if not all(map(math.isfinite, (m, x, y, z, vx, vy, vz))) or not m > 0:
                    raise ValueError("invalid particle values")
                role = b["role"]
                if role not in ("star", "planet", "cloud", "tracked"):
                    raise ValueError("unknown particle role")
                if i == 0 and (role != "star" or not math.isclose(m, SUN_KG, rel_tol=1e-10)):
                    raise ValueError("Sun missing or wrong mass")
                if i == 1 and (role != "planet" or not math.isclose(m, EARTH_KG, rel_tol=1e-10)):
                    raise ValueError("Earth missing or wrong mass")
                if i >= 2 and role not in ("cloud", "tracked"):
                    raise ValueError("unsupported body role")
                new.add(m=m, x=x, y=y, z=z, vx=vx, vy=vy, vz=vz)
                names.append(str(b.get("name", f"Body {i}"))[:100])
                roles.append(role)
            new.t = t
            baseline = float(checkpoint.get("initial_energy_j", new.energy()))
            if not math.isfinite(baseline):
                raise ValueError("invalid energy baseline")
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError("malformed checkpoint") from exc
        with self.lock:
            self.sim = new
            self.names, self.roles = names, roles
            self.initial_energy = baseline
            return self.state()

    def checkpoint(self):
        with self.lock:
            return {"version": 1, "time_s": float(self.sim.t),
                    "initial_energy_j": self.initial_energy,
                    "solver": {"name": "ias15", "rebound_version": rebound.__version__,
                               "units": ["m", "s", "kg"], "dt_s": 3600.0},
                    "bodies": self.state()["bodies"],
                    "note": "State restart. IAS15 internal adaptive history is not preserved."}

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
