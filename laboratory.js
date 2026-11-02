/* Experiment presentation. All authoritative dynamics and diagnostics come from REBOUND. */
class Laboratory {
  constructor(){
    this.reference=null;this.samples=[];this.paths=new Map();this.lastTime=null;this.lastCount=0;
    this.fields={cloud_count:'count',cloud_mass_kg:'cloudMass',inner_au:'innerRadius',outer_au:'outerRadius',inclination_deg:'inclination'};
    this.launchFields={speed_kms:'speed',impact_au:'impact',offset_degrees:'angle',mass_kg:'arrivalMass',azimuth_deg:'azimuth',elevation_deg:'elevation'};
    new ResizeObserver(()=>{if(snapshot)this.inspect()}).observe(document.querySelector('#experimentChart'));
    document.querySelector('#loadPreset').onclick=()=>this.preset();
    document.querySelector('#remember').onclick=()=>{try{const scenario=this.scenario(),launch=this.launch();if(!scenario||!launch)return;localStorage.setItem('dyson-lab-setup-v1',JSON.stringify({scenario,launch}));this.message('Setup remembered on this browser. Physics state is unchanged.')}catch(e){this.message('Setup could not be saved.')}};
    document.querySelector('#recall').onclick=()=>{try{const data=JSON.parse(localStorage.getItem('dyson-lab-setup-v1'));if(!data)throw Error();this.setScenario(data.scenario);this.fill(this.launchFields,data.launch);this.message('Setup recalled. Replay to run it; current world unchanged.')}catch(e){this.message('No readable saved setup on this browser.')}};
    document.querySelector('#pinComparison').onclick=()=>{const points=this.samples.flatMap(x=>{const o=x.objects.find(o=>o.id===selected);return o?[{time_s:x.time_s,...o}]:[]});if(!points.length){this.message('Select a measured body before pinning.');return}this.reference={name:snapshot.bodies.find(b=>b.id===selected).name,scenario:snapshot.scenario,events:snapshot.boundary_events,points:JSON.parse(JSON.stringify(points))};this.inspect();};
    document.querySelector('#exportResults').onclick=()=>this.export();
    document.querySelector('#topView').onclick=()=>{explorer.el=1.5;explorer.az=0};
    document.querySelector('#sideView').onclick=()=>{explorer.el=0;explorer.az=0};
  }
  message(text){document.querySelector('#experimentStatus').textContent=text;}
  fill(fields,values){for(const [key,id] of Object.entries(fields))if(values?.[key]!==undefined)document.querySelector('#'+id).value=values[key]}
  setScenario(values){this.fill(this.fields,values)}
  values(fields){const result={};for(const [key,id] of Object.entries(fields)){const input=document.querySelector('#'+id);if(!input.checkValidity()||!Number.isFinite(Number(input.value))||input.value===''){input.reportValidity();this.message('Enter a finite value inside the displayed bounds.');return null}result[key]=Number(input.value)}return result}
  scenario(){const s=this.values(this.fields);if(s&&s.inner_au>=s.outer_au){this.message('Outer radius must exceed inner radius.');return null}return s}
  launch(){return this.values(this.launchFields)}
  preset(){
    const kind=document.querySelector('#preset').value;
    this.setScenario({cloud_count:32,cloud_mass_kg:1,inner_au:.8,outer_au:4,inclination_deg:25});
    this.fill(this.launchFields,{speed_kms:kind==='bound'?10:40,impact_au:kind==='massive'?1:.5,offset_degrees:30,mass_kg:kind==='massive'?1e23:1,azimuth_deg:0,elevation_deg:kind==='massive'?0:12});
    document.querySelector('#brief').textContent=kind==='bound'?'Test an arrival initialized with negative two-body energy. It starts bound; this is not capture. Compare with the fast flyby.':kind==='massive'?'A hypothetical massive point body. Inspect Sun/Earth motion and the insertion ledger. No collision or hardware model.':'Measure an inclined gravity-only flyby. Select the arrival, step 30 days, follow its trajectory and compare a slower replay.';
    this.message('Parameters loaded. Press Replay scenario + arrival to begin.');
  }
  clear(){this.samples=[];this.paths.clear();this.lastTime=null;this.lastCount=0;}
  accept(s){
    if(this.lastTime!==null&&s.time_s<this.lastTime)this.clear();
    if(s.time_s===this.lastTime&&s.bodies.length===this.lastCount)return;
    this.lastTime=s.time_s;this.lastCount=s.bodies.length;
    const sample={time_s:s.time_s,energy_relative_drift:s.energy_relative_drift,objects:[]};
    for(const b of s.bodies){if(b.role==='cloud'&&b.id!==selected)continue;let path=this.paths.get(b.id)||[];path.push([b.x_m,b.y_m,b.z_m]);if(path.length>500)path.shift();this.paths.set(b.id,path);const o=s.orbits?.[b.id];if(o)sample.objects.push({id:b.id,...o})}
    this.samples.push(sample);if(this.samples.length>500)this.samples.shift();
  }
  selectedTrail(){return (this.paths.get(selected)||[]).slice(-Number(document.querySelector('#trailLength').value));}
  inspect(){
    const s=snapshot,b=s?.bodies.find(b=>b.id===selected),o=s?.orbits?.[selected];
    if(!s)return;
    const events=s.boundary_events||[];
    document.querySelector('#boundaryLedger').textContent=events.length?events.slice(-8).map(e=>`#${e.sequence} t=${(e.time_s/86400).toFixed(2)} d: +${e.mass_kg.toExponential(3)} kg; E=${e.energy_j.toExponential(4)} J; p=[${e.momentum_kg_ms.map(x=>x.toExponential(3)).join(', ')}] kg m/s`).join('\n'):'No insertion events recorded. Older backups may predate this ledger. Reset creates a new scenario.';
    if(!b||!o){this.message(`${this.samples.length}/500 snapshots retained in this tab. Select a body to plot its measurements.`);document.querySelector('#experimentReadout').textContent='Select an arrival, Earth or cloud body to inspect Sun-relative motion.';this.chart([]);return}
    const points=this.samples.flatMap(x=>{const v=x.objects.find(o=>o.id===selected);return v?[[x.time_s/86400,v.distance_au]]:[]});
    const minimum=points.length?Math.min(...points.map(p=>p[1])):o.distance_au;
    document.querySelector('#experimentReadout').textContent=`${b.name} · Sun-relative observables\nDistance ${o.distance_au.toFixed(4)} AU · Speed ${o.speed_kms.toFixed(4)} km/s · Radial ${o.radial_kms?.toFixed(4)} km/s\nTwo-body specific energy ${o.specific_energy_j_kg?.toExponential(4)} J/kg\nOsculating e=${o.eccentricity?.toFixed(5)} · Periapsis ${o.periapsis_au?.toFixed(5)} AU\n${o.specific_energy_j_kg<0?'Instantaneous two-body bound state — not proof of capture':'Instantaneous two-body unbound state'}\nSampled minimum ${minimum.toFixed(4)} AU · ${points.length} retained samples`;
    this.chart(points);
    const ref=this.reference?.points.at(-1);
    document.querySelector('#comparisonReadout').textContent=ref?`Pinned ${this.reference.name}: last sample t=${(ref.time_s/86400).toFixed(1)} d, r=${ref.distance_au.toFixed(4)} AU, v=${ref.speed_kms.toFixed(4)} km/s. Cyan=current, amber=pinned; compare at matched times. Reference stays in this tab until replaced.`:'Pin a measured run, then replay different parameters to compare.';
    this.message(`${this.samples.length}/500 snapshots retained in this tab · ${s.boundary_events?.length||0} external insertions · energy baseline t=${((s.reference_time_s||0)/86400).toFixed(2)} d`);

  }
  chart(points){
    const can=document.querySelector('#experimentChart'),ctx=can.getContext('2d');can.width=Math.max(300,can.clientWidth);can.height=150;ctx.fillStyle='#091b2a';ctx.fillRect(0,0,can.width,150);ctx.fillStyle='#acc8dd';ctx.font='12px system-ui';ctx.fillText('Distance from Sun (AU) vs simulated days',12,18);
    const reference=(this.reference?.points||[]).map(o=>[o.time_s/86400,o.distance_au]),all=[...points,...reference];if(!all.length)return;
    const xs=all.map(p=>p[0]),ys=all.map(p=>p[1]),x0=Math.min(...xs),x1=Math.max(...xs),lo=Math.min(...ys),hi=Math.max(...ys);
    for(const [path,color] of [[reference,'#ffc57a'],[points,'#62dce3']]){ctx.strokeStyle=color;ctx.beginPath();path.forEach(([x,y],i)=>{const px=45+(x-x0)/(x1-x0||1)*(can.width-65),py=115-(y-lo)/(hi-lo||1)*75;i?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.stroke();if(path.length){const [x,y]=path.at(-1);ctx.fillStyle=color;ctx.beginPath();ctx.arc(45+(x-x0)/(x1-x0||1)*(can.width-65),115-(y-lo)/(hi-lo||1)*75,3,0,Math.PI*2);ctx.fill()} }
    ctx.fillStyle='#acc8dd';ctx.fillText(`${lo.toFixed(3)}–${hi.toFixed(3)} AU`,12,140);ctx.fillText(`${x0.toFixed(1)}–${x1.toFixed(1)} d`,can.width-130,140);
  }
  export(){if(!snapshot)return;const s=snapshot;const result={format:'dyson-gravity-experiment-v1',engine:s.engine,solver:s.solver,initial_conditions:'Synthetic Sun–Earth and parameterized cloud; time zero is not an ephemeris epoch',revision:document.querySelector('#buildVersion').textContent.replace('Build: ',''),scenario:s.scenario,boundary_events:s.boundary_events,final:{time_s:s.time_s,bodies:s.bodies,orbits:s.orbits,energy_relative_drift:s.energy_relative_drift,reference_time_s:s.reference_time_s},samples:this.samples,comparison:this.reference,limitations:'Synthetic Newtonian point masses. Two-body diagnostics approximate the full N-body world. No collision, capture, actuation, relativity or hardware validation. Samples/trails are tab-local and bounded; private backups save physical state, not chart history.'};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='dyson-gravity-experiment.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);this.message('Experiment exported without recovery credentials. This is a result record, not a private restore file.');}
}
