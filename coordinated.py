"""Minimal coordinated cloud v1. SI, barycentric IAS15 gravity + split central impulses.

Ideal bidirectional finite-range actuators: an explicit interaction model, not
an assertion that AU-range hardware exists. Controllers never teleport bodies.
"""
import math
import rebound

AU=149597870700.; DAY=86400.; G=6.67430e-11; SUN=1.98847e30; C=299792458.
N=48; NODE_MASS=1e18; PACKET_MASS=1e12
RANGE=.65*AU; FORCE=2e9; POWER=2e14; CAPACITY=2e22
DT=1800.; TARGET=1.2*AU

def vec(p): return [p.x,p.y,p.z]
def vel(p): return [p.vx,p.vy,p.vz]
def dot(a,b): return math.fsum(x*y for x,y in zip(a,b))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def norm(a): return math.sqrt(dot(a,a))

class CoordinatedCloud:
    def __init__(self, saved=None):
        self.sim=rebound.Simulation(); self.sim.units=('m','s','kg'); self.sim.integrator='ias15'
        self.sim.ri_ias15.epsilon=1e-10; self.sim.dt=DT; self.sim.ri_ias15.min_dt=1.
        self.sim.add(m=SUN)
        # Three low-mass rings; 48 resolved stations, not 48 microscopic satellites.
        for i in range(N):
            r=(.8+.4*(i//16))*AU; a=2*math.pi*(i%16)/16+.19*(i//16)+.02*math.sin(3.7*i)
            v=math.sqrt(self.sim.G*SUN/r)
            self.sim.add(m=NODE_MASS,x=r*math.cos(a),y=r*math.sin(a),vx=-v*math.sin(a),vy=v*math.cos(a))
        self.sim.move_to_com()
        self.stores=[.5*CAPACITY]*N; self.heat=[0.]*N; self.activity=[0.]*N
        self.mode='Ready'; self.reason='Aim a packet, then launch. Compare the same arrival with coordination off.'
        self.enabled=True; self.packet=None; self.launch_time=0.; self.bound_since=None
        self.plan='Waiting'; self.plan_time=0.; self.launch_state=None; self.observations=[]
        self.initial_energy=self.sim.energy(); self.initial_p=self.momentum(); self.initial_l=self.angular()
        self.work_total=0.; self.exchanged=0.; self.last_error=0.; self.halted=False
        if saved: self.restore(saved)

    def momentum(self): return [math.fsum(p.m*getattr(p,k) for p in self.sim.particles) for k in ('vx','vy','vz')]
    def angular(self): return math.fsum(p.m*(p.x*p.vy-p.y*p.vx) for p in self.sim.particles)

    def launch(self,speed=45.,offset=.65,angle=0.,enabled=True):
        if self.packet is not None: raise ValueError('Reset before another launch')
        if not (5<=speed<=180 and -1.5<=offset<=1.5 and -60<=angle<=60): raise ValueError('Launch outside limits')
        self.enabled=enabled
        a=math.radians(angle); d=[math.cos(a),math.sin(a)]; side=[-d[1],d[0]]
        self.sim.add(m=PACKET_MASS,x=AU*(-2.2*d[0]+offset*side[0]),y=AU*(-2.2*d[1]+offset*side[1]),vx=speed*1000*d[0],vy=speed*1000*d[1])
        self.packet=N+1; self.launch_time=self.sim.t
        p=self.sim.particles[self.packet]; self.launch_state=[vec(p),vel(p)]
        self.initial_energy=self.sim.energy(); self.initial_p=self.momentum(); self.initial_l=self.angular()
        self.work_total=0.; self.exchanged=0.
        # Coarse, explicitly fallible capacity screening. Real decisions remain local.
        r=norm(vec(p)); excess=max(0.,.5*speed**2*1e6-self.sim.G*SUN/r+self.sim.G*SUN/(2*TARGET))
        need=PACKET_MASS*excess
        duration=2*1.6*AU/(speed*1000)
        impulse_capacity=12*FORCE*duration*.35
        required_impulse=PACKET_MASS*max(0.,speed*1000-math.sqrt(self.sim.G*SUN/TARGET))
        if not enabled:
            self.plan='Passive'; self.reason='Coordination is off. Only mutual gravity acts.'
        elif required_impulse>1.5*impulse_capacity or need>sum(CAPACITY-x for x in self.stores)*.7:
            self.plan='Stand aside'; self.reason='Estimated braking demand exceeds this controller’s encounter budget. Packet coupling is disabled.'
        elif required_impulse>impulse_capacity:
            self.plan='Assist only'; self.reason='Full capture looks beyond the estimated impulse budget. Try limited braking while preserving station limits.'
        else:
            self.plan='Attempt capture'; self.reason='Estimated budget is sufficient. Nodes aim for the 1.2 AU parking region; success is not guaranteed.'
        self.plan_time=self.sim.t+r/C
        self.mode='Plan in transit' if enabled else 'Passive'
        return self.state()

    def exchange(self,i,j,impulse,dt,store_id):
        """Central pair impulse; exact kinetic work -> electrical store and heat.

        No extra torque. Negative work regenerates at 90%; positive work draws
        electrical energy at 90%. Reject commands that violate local resources.
        """
        a,b=self.sim.particles[i],self.sim.particles[j]
        r=sub(vec(a),vec(b)); distance=norm(r)
        if distance==0 or distance>RANGE: return False
        u=[x/distance for x in r]
        impulse=max(-FORCE*dt,min(FORCE*dt,impulse))
        relative=dot(sub(vel(a),vel(b)),u)
        def work(q): return q*relative+.5*q*q*(1/a.m+1/b.m)
        delta=work(impulse)
        # Scale for power cap before checking electrical/thermal/orbit resources.
        if abs(delta)>POWER*dt:
            impulse*=POWER*dt/abs(delta); delta=work(impulse)
        if abs(delta)>POWER*dt*(1+1e-12): return False
        electrical=-delta/.9 if delta>=0 else -.9*delta
        heat=-delta-electrical
        k=store_id
        if not (0<=self.stores[k]+electrical<=CAPACITY and self.heat[k]+heat<=.25*CAPACITY): return False
        # Finite station orbit disturbance limit, checked against actual velocity.
        dv=abs(impulse)/b.m
        if dv>2. or norm(vel(b))>60000: return False
        # Refuse commands that push a station outside its initial orbital envelope.
        sun=self.sim.particles[0]
        rb=sub(vec(b),vec(sun)); vb=sub(vel(b),vel(sun)); radius=norm(rb)
        proposed=[v-impulse*x/b.m for v,x in zip(vb,u)]
        initial_radius=(.8+.4*(store_id//16))*AU
        reference=-self.sim.G*SUN/(2*initial_radius)
        specific=dot(proposed,proposed)/2-self.sim.G*SUN/radius
        if abs((specific-reference)/reference)>.05: return False
        for axis,key in enumerate(('vx','vy','vz')):
            setattr(a,key,getattr(a,key)+impulse*u[axis]/a.m)
            setattr(b,key,getattr(b,key)-impulse*u[axis]/b.m)
        self.stores[k]+=electrical; self.heat[k]+=heat
        self.work_total+=delta; self.exchanged+=abs(impulse)
        self.activity[k]=max(self.activity[k],min(1.,abs(impulse)/(FORCE*dt)))
        return True

    def controls(self,dt):
        self.activity=[x*.8 for x in self.activity]
        if not self.enabled or self.packet is None or self.plan not in ('Attempt capture','Assist only'): return
        packet=self.sim.particles[self.packet]; sun=self.sim.particles[0]
        # Each station uses a delayed packet observation, extrapolated linearly.
        # Observations are sampled at control ticks; delayed lookup never reads future state.
        now=self.sim.t
        self.observations.append([now,vec(packet),vel(packet)])
        self.observations=[o for o in self.observations if now-o[0]<4*DAY]
        for k in range(N):
            node=self.sim.particles[k+1]
            distance=norm(sub(vec(node),vec(packet)))
            if now<self.plan_time+norm(vec(node))/C or distance>RANGE: continue
            observed=next((o for o in reversed(self.observations) if o[0]<=now-distance/C),None)
            if observed is None: continue
            lag=now-observed[0]
            estimate=[x+v*lag for x,v in zip(observed[1],observed[2])]
            r=sub(estimate,vec(sun)); radius=norm(r)
            if radius<.2*AU: continue
            v=sub(observed[2],vel(sun)); tangent=[-r[1]/radius,r[0]/radius,0.]
            # Park prograde or retrograde according to incoming angular momentum.
            sign=1 if r[0]*v[1]-r[1]*v[0]>=0 else -1
            circular=math.sqrt(self.sim.G*SUN/radius)
            radial_target=max(-1500.,min(1500.,(TARGET-radius)/(80*DAY)))
            desired=[sign*circular*t+radial_target*x/radius for t,x in zip(tangent,r)]
            error=sub(desired,v)
            line=sub(vec(packet),vec(node)); length=norm(line)
            if not length: continue
            unit=[x/length for x in line]
            # Distributed proportional rule; short local prediction, no optimizer.
            command=PACKET_MASS*dot(error,unit)*dt/(3*DAY)
            self.exchange(self.packet,k+1,command,dt,k)
        # Nearest-neighbor central damping spreads relative radial disturbance.
        # Local relative-velocity sensing only; no global instantaneous state.
        # Neighbor sensing is taken at this control tick; radio plans remain delayed.
        for k in range(N):
            if now<self.plan_time+norm(vec(self.sim.particles[k+1]))/C: continue
            i=k+1; j=(k//16)*16+(k+1)%16+1
            a,b=self.sim.particles[i],self.sim.particles[j]
            line=sub(vec(a),vec(b)); length=norm(line)
            if length>RANGE or not length: continue
            u=[x/length for x in line]
            relative=dot(sub(vel(a),vel(b)),u)
            if abs(relative)>.01:
                self.exchange(i,j,-relative/(1/a.m+1/b.m)*.00001,dt,k)

    def advance(self,days=2.,step=DT):
        if not 0<days<=4: raise ValueError('Step outside limit')
        end=self.sim.t+days*DAY
        while self.sim.t<end-.001:
            if self.packet is not None and norm(sub(vec(self.sim.particles[self.packet]),vec(self.sim.particles[0])))<.06*AU:
                self.halted=True
                break
            if self.halted: break
            dt=min(step,end-self.sim.t); start=self.sim.t
            self.sim.integrate(start+dt/2)
            old_impulse=self.exchanged
            self.controls(dt)
            if self.exchanged!=old_impulse:
                # A finite velocity jump invalidates IAS15's derivative history.
                self.sim.reset_integrator()
                self.sim.integrator='ias15'; self.sim.ri_ias15.epsilon=1e-10
                self.sim.ri_ias15.min_dt=1.; self.sim.dt=dt/2
            self.sim.integrate(start+dt)
        return self.state()

    def state(self):
        sun=self.sim.particles[0]; bodies=[]
        for i,p in enumerate(self.sim.particles):
            bodies.append(dict(id=i,x=p.x/AU,y=p.y/AU,z=p.z/AU,vx=p.vx,vy=p.vy,mass=p.m,
                active=self.activity[i-1] if 1<=i<=N else 0,
                energy=self.stores[i-1]/CAPACITY if 1<=i<=N else None,
                heat=self.heat[i-1]/CAPACITY if 1<=i<=N else None))
        packet=None
        if self.packet is not None:
            p=self.sim.particles[self.packet]; r=sub(vec(p),vec(sun)); v=sub(vel(p),vel(sun)); radius=norm(r)
            energy=dot(v,v)/2-self.sim.G*(sun.m+p.m)/radius
            h=r[0]*v[1]-r[1]*v[0]; mu=self.sim.G*(sun.m+p.m)
            ecc=math.sqrt(max(0.,1+2*energy*h*h/mu**2))
            if energy<0:
                if self.bound_since is None:self.bound_since=self.sim.t
                status='Bound now — keep observing'
            else:
                self.bound_since=None; status='Passing through' if dot(r,v)<0 else 'Departing'
            if radius<.05*AU: status='Inside stellar exclusion region'
            packet=dict(speed=norm(v)/1000,radius=radius/AU,specific_energy=energy,eccentricity=ecc,status=status,
                        periapsis=h*h/mu/(1+ecc)/AU,bound_days=(self.sim.t-self.bound_since)/DAY if self.bound_since is not None else 0)
            self.mode=self.plan if self.sim.t>=self.plan_time else 'Plan in transit'
        if self.halted:
            self.mode='Stellar approach limit'
            self.reason='Paused before the packet enters the near-star region, outside this model’s tested regime. Reset and increase the trajectory offset.'
        residual=self.sim.energy()-self.initial_energy-self.work_total
        # Also report at packet-work scale; Sun-scale relative drift alone hides errors.
        scale=PACKET_MASS*(45000.**2)
        return dict(version='minimal-cloud-v1',engine='REBOUND IAS15',time=self.sim.t/DAY,bodies=bodies,packet=packet,
            decision=self.mode,reason=self.reason,plan=self.plan,enabled=self.enabled,
            target_au=1.2,halted=self.halted,links=[i+1 for i,x in enumerate(self.activity) if x>.01],
            stored_j=sum(self.stores),heat_j=sum(self.heat),work_j=self.work_total,
            exchanged_impulse=self.exchanged,energy_residual_j=residual,energy_residual_packet_scale=residual/scale,
            momentum_residual=norm(sub(self.momentum(),self.initial_p)),angular_residual=self.angular()-self.initial_l,
            inventory_kg=N*NODE_MASS,inventory_earth=N*NODE_MASS/5.9722e24)

    def snapshot(self):
        return dict(time=self.sim.t,bodies=[[p.m,*vec(p),*vel(p)] for p in self.sim.particles],
            **{k:getattr(self,k) for k in ('stores','heat','activity','mode','reason','enabled','packet','launch_time','bound_since','plan','plan_time','launch_state','observations','initial_energy','initial_p','initial_l','work_total','exchanged','halted')})

    def restore(self,saved):
        if len(saved['bodies']) not in (N+1,N+2):raise ValueError('Invalid minimal cloud')
        sim=rebound.Simulation();sim.units=('m','s','kg');sim.integrator='ias15';sim.ri_ias15.epsilon=1e-10;sim.dt=DT;sim.ri_ias15.min_dt=1.
        for row in saved['bodies']:
            if len(row)!=7 or not all(math.isfinite(float(x)) for x in row):raise ValueError('Invalid body')
            m,x,y,z,vx,vy,vz=row;sim.add(m=m,x=x,y=y,z=z,vx=vx,vy=vy,vz=vz)
        sim.t=saved['time'];self.sim=sim
        for k in self.snapshot():
            if k not in ('time','bodies'):setattr(self,k,saved.get(k,False) if k=='halted' else saved[k])
