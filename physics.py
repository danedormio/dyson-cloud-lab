"""Dyson Cloud Laboratory: one REBOUND N-body system for every physical object.

All bodies—including Sun, Earth and incoming cloud elements—participate in
one massive-particle IAS15 integration. No body is pinned to the origin.
The 1 kg baseline describes cloud elements, not planets or the Sun.

Coupling/actuation will be implemented as separately verified, symmetric
momentum exchanges. There is deliberately NO arbitrary capture force here.
"""
import math
import copy
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

    def reset(self, cloud_count=72, cloud_mass_kg=1.0, inner_au=0.8, outer_au=4.0, inclination_deg=0.0, geometry="sphere"):
        with self.lock:
            values = (cloud_mass_kg, inner_au, outer_au, inclination_deg)
            if (not all(math.isfinite(float(v)) for v in values)
                    or not 0 <= int(cloud_count) <= 200
                    or not 0 < cloud_mass_kg <= 1e20
                    or not 0.2 <= inner_au < outer_au <= 20
                    or not 0 <= inclination_deg <= 90 or geometry not in ("sphere", "disk")):
                raise ValueError("invalid bounded cloud scenario")
            self.scenario = dict(cloud_count=int(cloud_count), cloud_mass_kg=cloud_mass_kg,
                                 inner_au=inner_au, outer_au=outer_au, inclination_deg=inclination_deg, geometry=geometry)
            self.boundary_events = []
            self.sim = rebound.Simulation()
            self.sim.units = ("m", "s", "kg")
            self.sim.integrator = "ias15"
            self.sim.dt = 3600.0
            self.scenario_version = 4 if geometry == "sphere" else 3
            self.names = ["Sun", "Earth"]
            self.roles = ["star", "planet"]
            self.sim.add(m=SUN_KG, x=0, y=0, z=0)
            earth_v = math.sqrt(self.sim.G * (SUN_KG + EARTH_KG) / AU)
            self.sim.add(m=EARTH_KG, x=AU, y=0, z=0, vy=earth_v)
            seed = 122333
            def random_unit():
                nonlocal seed
                seed = (1664525*seed + 1013904223) & 0xffffffff
                z = 2*seed/4294967296 - 1
                seed = (1664525*seed + 1013904223) & 0xffffffff
                a = 2*math.pi*seed/4294967296
                r = math.sqrt(1-z*z)
                return [r*math.cos(a), r*math.sin(a), z]
            for i in range(int(cloud_count)):
                # Deterministic, non-coincident orbital phases and radii.
                radius = (inner_au + (outer_au-inner_au) * (i + 0.5) / max(1, cloud_count)) * AU
                # Half a golden-angle phase step avoids the Earth-at-(AU,0)
                # coincidence for cloud_count=8, without changing any forces.
                phase = (i + 0.5) * 2.399963229728653
                speed = math.sqrt(self.sim.G * SUN_KG / radius)
                # Deterministic tilted orbital planes; exact old fixture at zero tilt.
                inc = math.radians(inclination_deg) * math.sin(phase)
                if geometry == "sphere":
                    radial, axis = random_unit(), random_unit()
                    tangent = [radial[1]*axis[2]-radial[2]*axis[1],
                               radial[2]*axis[0]-radial[0]*axis[2],
                               radial[0]*axis[1]-radial[1]*axis[0]]
                    norm = math.hypot(*tangent)
                    position = [radius*x for x in radial]
                    velocity = [speed*x/norm for x in tangent]
                else:
                    position = [radius*math.cos(phase), radius*math.sin(phase)*math.cos(inc),
                                radius*math.sin(phase)*math.sin(inc)]
                    velocity = [-speed*math.sin(phase), speed*math.cos(phase)*math.cos(inc),
                                speed*math.cos(phase)*math.sin(inc)]
                self.sim.add(m=cloud_mass_kg, x=position[0], y=position[1], z=position[2],
                             vx=velocity[0], vy=velocity[1], vz=velocity[2])
                self.names.append(f"Cloud {i+1}")
                self.roles.append("cloud")
            self.sim.move_to_com()
            self.initial_energy = self.sim.energy()
            self.reference_time = 0.0
            return self.state()

    def add_incoming(self, speed_kms=25, impact_au=0.5, offset_degrees=0,
                     mass_kg=1.0, azimuth_deg=0.0, elevation_deg=0.0):
        with self.lock:
            values = (speed_kms, impact_au, offset_degrees, mass_kg, azimuth_deg, elevation_deg)
            if (not all(math.isfinite(float(v)) for v in values)
                    or not 0 < speed_kms <= 300 or not 0 < mass_kg <= 1e24
                    or not -25 <= impact_au <= 25 or not -180 <= offset_degrees <= 180
                    or not -180 <= azimuth_deg <= 180 or not -89 <= elevation_deg <= 89
                    or len(self.sim.particles) >= 202):
                raise ValueError("invalid bounded Newtonian arrival")
            az, el, theta = map(math.radians, (azimuth_deg, elevation_deg, offset_degrees))
            direction = [math.cos(el)*math.cos(az), math.cos(el)*math.sin(az), math.sin(el)]
            side = [-math.sin(az), math.cos(az), 0.0]
            up = [-math.sin(el)*math.cos(az), -math.sin(el)*math.sin(az), math.cos(el)]
            position = [-5.6*AU*d + impact_au*AU*(math.cos(theta)*u+math.sin(theta)*v)
                        for d, u, v in zip(direction, side, up)]
            velocity = [speed_kms*1000*d for d in direction]
            # External matter injection: explicit open-boundary event, not free thrust.
            if any(math.dist(position, (p.x,p.y,p.z)) < 1.0 for p in self.sim.particles):
                raise ValueError("arrival overlaps an existing point mass; step or change geometry")
            potential = math.fsum(-self.sim.G*mass_kg*p.m / math.dist(position, (p.x,p.y,p.z))
                                  for p in self.sim.particles)
            energy_in = 0.5*mass_kg*sum(v*v for v in velocity) + potential
            momentum = [mass_kg*v for v in velocity]
            angular = [mass_kg*(position[1]*velocity[2]-position[2]*velocity[1]),
                       mass_kg*(position[2]*velocity[0]-position[0]*velocity[2]),
                       mass_kg*(position[0]*velocity[1]-position[1]*velocity[0])]
            self.sim.add(m=mass_kg, x=position[0], y=position[1], z=position[2],
                         vx=velocity[0], vy=velocity[1], vz=velocity[2])
            self.names.append(f"Tracked {len(self.names)}")
            self.roles.append("tracked")
            self.boundary_events.append(dict(sequence=len(self.boundary_events)+1, time_s=self.sim.t,
                parameters=dict(speed_kms=speed_kms, impact_au=impact_au, offset_degrees=offset_degrees,
                    mass_kg=mass_kg, azimuth_deg=azimuth_deg, elevation_deg=elevation_deg),
                kind="external_matter_insertion", body_id=len(self.names)-1, mass_kg=mass_kg,
                energy_j=energy_in, momentum_kg_ms=momentum, angular_momentum_kg_m2_s=angular))
            # Monitor each closed integration segment against its own baseline.
            self.initial_energy = self.sim.energy()
            self.reference_time = self.sim.t
            return self.state()

    def step(self, seconds=3600, samples=1):
        seconds = float(seconds)
        if not 0 < seconds <= 30 * DAY or not 1 <= samples <= 32:
            raise ValueError("step must be between 0 and 30 days; 1–32 samples")
        with self.lock:
            start = self.sim.t
            frames = []
            for i in range(samples+1):
                if i:
                    self.sim.integrate(start + seconds*i/samples, exact_finish_time=1)
                if samples > 1:
                    frames.append({"time_s":float(self.sim.t),
                        "positions_m":[[p.x,p.y,p.z] for p in self.sim.particles]})
            result = self.state()
            if frames:
                result["motion_frames"] = frames
            return result

    def trajectory(self, body_id):
        """Bounded no-intervention N-body forecast on an isolated REBOUND copy."""
        if not 0 <= body_id < len(self.sim.particles):
            raise ValueError("unknown body")
        with self.lock:
            simulation = self.sim.copy()
            orbit = self.state()['orbits'][body_id]
        horizon = 365.25*DAY
        if orbit and orbit['specific_energy_j_kg'] < 0:
            mu = simulation.G*(simulation.particles[0].m+simulation.particles[body_id].m)
            a = -mu/(2*orbit['specific_energy_j_kg'])
            horizon = min(2*365.25*DAY,2*math.pi*math.sqrt(a*a*a/mu))
        elif orbit:
            horizon = 180*DAY
        start = simulation.t
        points = []
        for i in range(97):
            simulation.integrate(start+horizon*i/96,exact_finish_time=1)
            p = simulation.particles[body_id]
            points.append([float(p.x),float(p.y),float(p.z)])
        return {"body_id":body_id,"start_time_s":start,"horizon_s":horizon,
                "positions_m":points,"model":"REBOUND IAS15 N-body forecast; no future insertions/control"}

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
            self.scenario_version = checkpoint.get("scenario_version", 1)
            self.scenario = checkpoint.get("scenario", None)
            self.boundary_events = checkpoint.get("boundary_events", [])
            self.reference_time = checkpoint.get("reference_time_s", 0.0)
            return self.state()

    def checkpoint(self):
        with self.lock:
            return {"version": 1, "time_s": float(self.sim.t),
                    "scenario_version": self.scenario_version,
                    "initial_energy_j": self.initial_energy,
                    "scenario": self.scenario, "boundary_events": copy.deepcopy(self.boundary_events),
                    "reference_time_s": self.reference_time,
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
            sun = self.sim.particles[0]
            orbits = []
            for i, p in enumerate(self.sim.particles):
                if i == 0:
                    orbits.append(None)
                    continue
                r = [p.x-sun.x, p.y-sun.y, p.z-sun.z]
                v = [p.vx-sun.vx, p.vy-sun.vy, p.vz-sun.vz]
                radius, speed = math.hypot(*r), math.hypot(*v)
                mu = self.sim.G*(sun.m+p.m)
                h = [r[1]*v[2]-r[2]*v[1], r[2]*v[0]-r[0]*v[2], r[0]*v[1]-r[1]*v[0]]
                specific = speed*speed/2 - mu/radius if radius else None
                ecc = math.sqrt(max(0, 1+2*specific*sum(x*x for x in h)/(mu*mu))) if radius else None
                orbits.append(dict(distance_au=radius/AU, speed_kms=speed/1000,
                    radial_kms=sum(a*b for a,b in zip(r,v))/radius/1000 if radius else None,
                    specific_energy_j_kg=specific, eccentricity=ecc,
                    periapsis_au=sum(x*x for x in h)/mu/(1+ecc)/AU if ecc is not None else None))
            angular = [math.fsum(b['mass_kg']*(b[a]*b[d]-b[c]*b[e]) for b in particles)
                       for a,d,c,e in [('y_m','vz_ms','z_m','vy_ms'),
                                       ('z_m','vx_ms','x_m','vz_ms'),('x_m','vy_ms','y_m','vx_ms')]]
            return {
                "engine": "REBOUND IAS15", "time_s":float(self.sim.t),
                "solver": {"name": "ias15", "rebound_version": rebound.__version__,
                           "units": ["m", "s", "kg"], "dt_s": 3600.0},
                "gravitational_energy_j":energy,
                "energy_relative_drift":(
                    (energy - self.initial_energy) / abs(self.initial_energy)
                    if self.initial_energy else None
                ),
                "momentum_kg_ms":momentum, "total_mass_kg":total_m,
                "bodies":particles, "orbits": orbits, "scenario": self.scenario,
                "boundary_events": copy.deepcopy(self.boundary_events), "reference_time_s": self.reference_time,
                "angular_momentum_kg_m2_s": angular,
                "coupling_enabled":False,
                "note":"Gravity-only REBOUND reference: coupling and capture not enabled."
            }
