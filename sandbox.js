/* Exhibit interaction only. Draft aim is geometry, never a physics propagator. */
class OrbitalSandbox {
  constructor(){
    this.draft=null;this.preview=null;this.previewToken=0;this.lastWorld=null;this.rangeInputs=[];
    const $=s=>document.querySelector(s),aside=$('aside');
    // Retain existing controls and IDs, including all recovery/workbench operations.
    aside.insertBefore($('#launchPanel'),$('#inspectPanel'));
    aside.insertBefore($('#presetPanel'),$('#inspectPanel'));
    aside.insertBefore($('#cloudPanel'),$('#inspectPanel'));
    const launch=$('#launchPanel');
    const summary=document.createElement('div');summary.id='launchSummary';summary.className='launchSummary';launch.insertBefore(summary,launch.querySelector('.field'));
    launch.insertAdjacentHTML('beforeend','<div class="previewActions"><label><input id="showDraft" type="checkbox" checked>Draft aim</label><button id="traceLaunch">Trace gravity</button></div><div id="previewStatus" role="status" data-state="stale">Draft geometry only · not a gravitational prediction.</div>');
    const actions=document.createElement('div');actions.className='secondaryActions';actions.append($('#replay'),$('#remember'),$('#recall'));launch.append(actions);
    const worldActions=document.createElement('div');worldActions.className='secondaryActions';worldActions.append($('#reset'),$('#restoreSphere'));$('#cloudPanel').append(worldActions);
    const view=$('#viewPanel'),viewActions=document.createElement('div');viewActions.className='labButtons';viewActions.append($('#cameraReset'));view.append(viewActions);
    for(const id of ['showCloud','showShell','labels','earthTrace'])view.append($('#'+id).closest('label'));
    const archive=document.createElement('details');archive.innerHTML='<summary>Save &amp; recover your universe</summary><p class="help">Physical state saves after each successful action. Private recovery files grant access to your universe; keep them private. Chart history stays in this tab.</p><div class="labButtons"></div>';
    for(const id of ['save','backup','restore'])archive.querySelector('.labButtons').append($('#'+id));aside.append(archive);
    archive.id='archivePanel';
    const scroller=document.createElement('div');scroller.className='controlScroll';
    for(const child of [...aside.children])if(!child.matches('.controlIntro,.panelNav'))scroller.append(child);
    aside.append(scroller);
    const launchDock=document.createElement('div');launchDock.className='launchDock';launchDock.append($('#launch'));launchDock.insertAdjacentHTML('beforeend','<span>External matter insertion · no propulsion or capture</span>');aside.append(launchDock);
    // Matching numerical fields remain available for exact values; logarithmic mass
    // sliders span the full API bounds without obscuring what value will launch.
    const ranges={speed:[.1,300,'log'],impact:[-25,25],angle:[-180,180],arrivalMass:[.000001,1e24,'log'],azimuth:[-180,180],elevation:[-89,89],count:[0,200,'int'],cloudMass:[.000001,1e20,'log'],innerRadius:[.2,19.9],outerRadius:[.3,20],inclination:[0,90]};
    for(const [id,[min,max,kind]] of Object.entries(ranges)){
      const number=$('#'+id),range=document.createElement('input');range.type='range';range.min=0;range.max=1000;range.step=1;range.id=id+'Slider';range.setAttribute('aria-label',number.closest('label').childNodes[0].textContent.trim()+' slider');
      const toUnit=v=>kind==='log'?Math.log(v/min)/Math.log(max/min):(v-min)/(max-min);
      const fromUnit=t=>kind==='log'?min*Math.pow(max/min,t):min+(max-min)*t;
      const sync=()=>{range.value=Math.round(1000*Math.max(0,Math.min(1,toUnit(Number(number.value)))));range.disabled=number.disabled;range.setAttribute('aria-valuetext',number.value)};
      range.addEventListener('input',()=>{let value=fromUnit(Number(range.value)/1000);number.value=kind==='int'?Math.round(value):Number(value.toPrecision(5));range.setAttribute('aria-valuetext',number.value);number.dispatchEvent(new Event('input',{bubbles:true}))});
      number.addEventListener('input',()=>{sync();if(id in Object.fromEntries(Object.values(laboratory.launchFields).map(x=>[x,true])))this.updateDraft()});
      number.closest('label').append(range);this.rangeInputs.push(sync);sync();
    }
    $('#showDraft').onchange=()=>this.updateDraft();$('#traceLaunch').onclick=()=>this.trace();
    $('#geometry').addEventListener('change',()=>this.rangeInputs.forEach(sync=>sync()));
    const frameAim=document.createElement('button');frameAim.id='frameAim';frameAim.textContent='Frame aim';frameAim.onclick=()=>{if(!this.draft)return;explorer.pan=[0,0,0];explorer.distance=Math.min(60,Math.max(13,Math.hypot(...this.draft.start)*2.4));};launch.querySelector('.previewActions').append(frameAim);
    // On phones, put hands-on controls before the longer measurement readout.
    const mobile=matchMedia('(max-width:760px)'),research=$('#researchPanel');
    const arrange=()=>{if(mobile.matches)scroller.insertBefore(research,$('#viewPanel'));else document.querySelector('main').insertBefore(research,document.querySelector('.continuity'))};mobile.addEventListener('change',arrange);arrange();
    for(const button of document.querySelectorAll('[data-jump]'))button.onclick=()=>{const element=$('#'+button.dataset.jump);if(element.tagName==='DETAILS')element.open=true;element.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'})};
    $('#focusView').onclick=()=>{const on=document.body.classList.toggle('focusMode');$('#focusView').setAttribute('aria-pressed',on);$('#focusView').innerHTML=on?'⤡ <span>Controls</span>':'⤢ <span>Focus</span>'};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('focusMode'))$('#focusView').click();if(e.code==='Space'&&!/INPUT|SELECT|BUTTON|TEXTAREA/.test(e.target.tagName)&&!document.querySelector('dialog[open]')){e.preventDefault();if(!$('#play').disabled)$('#play').click()}});
    document.body.insertAdjacentHTML('beforeend','<dialog id="quickStart" aria-labelledby="quickTitle"><span class="eyebrow">WELCOME TO YOUR ORBITAL SANDBOX</span><h2 id="quickTitle">Follow your curiosity.</h2><ol><li><b>Play with time.</b> Press Play or Space. Drag the universe to rotate; scroll or pinch to zoom.</li><li><b>Design an arrival.</b> Drag the launch sliders. Mint dashes show the aim immediately. Trace gravity computes an amber REBOUND path without launching.</li><li><b>Send it.</b> Launch an arrival, click its marker, and follow its trajectory. Slow arrivals can start bound; that is not capture.</li><li><b>Ask a better “what if”.</b> Replay a setup, pin a measured run and compare. Two-year advances are real sequential integrations.</li></ol><p class="help">Newtonian point masses. Body sizes and background stars are decorative. No coupling, capture, collisions or propulsion mechanism is modeled.</p><form method="dialog"><button class="primary">Let’s explore ↗</button></form></dialog><div id="launchToast" class="toast" role="status" hidden></div>');
    $('#tour').onclick=()=>$('#quickStart').showModal();
    this.stars();this.updateDraft();this.tick();
  }
  parameters(){const p={};for(const [key,id] of Object.entries(laboratory.launchFields)){const input=document.querySelector('#'+id);if(!input.checkValidity()||input.value===''||!Number.isFinite(Number(input.value)))return null;p[key]=Number(input.value)}return p}
  fingerprint(){return snapshot?JSON.stringify([snapshot.time_s,snapshot.bodies.length,snapshot.scenario, snapshot.bodies[0].x_m,snapshot.bodies[1].x_m]):null}
  updateDraft(){
    const p=this.parameters();this.previewToken++;this.preview=null;
    if(!p){this.draft=null;document.querySelector('#previewStatus').textContent='Enter valid launch values to see your draft.';return}
    const az=p.azimuth_deg*Math.PI/180,el=p.elevation_deg*Math.PI/180,t=p.offset_degrees*Math.PI/180;
    const direction=[Math.cos(el)*Math.cos(az),Math.cos(el)*Math.sin(az),Math.sin(el)],side=[-Math.sin(az),Math.cos(az),0],up=[-Math.sin(el)*Math.cos(az),-Math.sin(el)*Math.sin(az),Math.cos(el)];
    const start=direction.map((d,i)=>-5.6*d+p.impact_au*(Math.cos(t)*side[i]+Math.sin(t)*up[i]));
    // A 30-day unaccelerated displacement gives speed a truthful visual scale.
    const displacement=p.speed_kms*1000*30*86400/AU;
    this.draft=document.querySelector('#showDraft').checked?{start,direction,end:start.map((v,i)=>v+direction[i]*11.2),velocityEnd:start.map((v,i)=>v+direction[i]*displacement),parameters:p}:null;
    document.querySelector('#launchSummary').textContent=`${p.speed_kms.toLocaleString(undefined,{maximumFractionDigits:2})} km/s · offset ${p.impact_au.toFixed(2)} AU · ${p.mass_kg.toExponential(1)} kg`;
    const status=document.querySelector('#previewStatus');status.dataset.state='stale';status.textContent='Mint dashed = draft aim. Solid arrow = 30 days at initial velocity, without gravity. Trace gravity for the actual N-body forecast.';
  }
  validPreview(){return this.preview&&this.preview.world===this.fingerprint()&&this.preview.parameters===JSON.stringify(this.parameters())?this.preview.result:null}
  async trace(){
    const parameters=this.parameters();if(!parameters||!snapshot)return;
    if(running||busy||advancing||laboratory.pending){document.querySelector('#previewStatus').textContent='Pause and wait for the current action before tracing gravity.';return}
    const token=++this.previewToken,world=this.fingerprint(),encoded=JSON.stringify(parameters),button=document.querySelector('#traceLaunch');
    button.disabled=true;button.textContent='Tracing…';document.querySelector('#previewStatus').textContent='Integrating an isolated REBOUND copy. Your universe is unchanged.';
    laboratory.forecasting=true;const work=api('/api/launch-preview',parameters);laboratory.pending=work;
    try{const result=await work;if(token!==this.previewToken||world!==this.fingerprint()||encoded!==JSON.stringify(this.parameters()))return;this.preview={world,parameters:encoded,result};const status=document.querySelector('#previewStatus');status.dataset.state='ready';status.textContent=`Amber = ${result.positions_m.length} actual IAS15 samples over ${(result.horizon_s/86400).toFixed(0)} days. Preview only; no body inserted. Changing sliders or world invalidates this path.`}
    catch(error){if(token===this.previewToken)document.querySelector('#previewStatus').textContent=error.status===429?'Preview allowance reached. Wait one minute; your universe is unchanged.':'Preview unavailable; change coincident launch coordinates or check connection. Your universe is unchanged.'}
    finally{button.disabled=false;button.textContent='Trace gravity';if(laboratory.pending===work){laboratory.pending=null;laboratory.forecasting=false}}
  }
  stars(){const canvas=document.querySelector('#starfield'),draw=()=>{const box=canvas.getBoundingClientRect();canvas.width=box.width;canvas.height=box.height;const ctx=canvas.getContext('2d');let seed=271828;const rand=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);for(let i=0;i<420;i++){const x=rand()*box.width,y=rand()*box.height,r=rand();ctx.fillStyle=`rgba(175,210,232,${.15+r*.5})`;ctx.beginPath();ctx.arc(x,y,r>.97?1.2:.35+r*.4,0,Math.PI*2);ctx.fill()}};new ResizeObserver(draw).observe(canvas);draw()}
  tick(now=0){
    // Readouts need 10 Hz, not a second stream of per-frame DOM allocations.
    // The WebGL/motion loop remains independent and smooth.
    if(this.lastHud!==undefined&&now-this.lastHud<100){requestAnimationFrame(t=>this.tick(t));return}
    this.lastHud=now;
    const s=snapshot;if(s){
      const key=this.fingerprint();if(this.lastWorld!==key){if(this.preview&&this.preview.world!==key){this.preview=null;document.querySelector('#previewStatus').dataset.state='stale';document.querySelector('#previewStatus').textContent='World changed. Draft remains live; Trace gravity to refresh its N-body path.'}this.lastWorld=key;this.rangeInputs.forEach(sync=>sync());}
      document.querySelector('#hudTime').innerHTML=((motion.time??s.time_s)/86400).toFixed(1)+' <small>days</small>';
      document.querySelector('#hudBodies').textContent=s.bodies.length;
      const body=s.bodies.find(b=>b.id===selected),orbit=s.orbits?.[selected];
      document.querySelector('#hudSpeed').innerHTML=(orbit?.speed_kms?.toFixed(1)||'—')+' <small>km/s</small>';
      const badge=document.querySelector('#selectionBadge');badge.hidden=!body;badge.textContent=body?`${body.name} · ${orbit?.distance_au?.toFixed(2)||'0'} AU from Sun`:'';
      if(this.lastCount!==undefined&&s.bodies.length===this.lastCount+1&&s.bodies.at(-1).role==='tracked'){const toast=document.querySelector('#launchToast');toast.textContent='Arrival launched ↗  Click its amber marker to explore.';toast.hidden=false;clearTimeout(this.toastTimer);this.toastTimer=setTimeout(()=>toast.hidden=true,3500)}this.lastCount=s.bodies.length;
    }
    // Small orientation compass follows the camera; axes are visual, not forces.
    const compass=document.querySelector('#axisCompass');const center=explorer.project([0,0,0],82,82),axes=[[1,0,0,'X','#f4b4a0'],[0,1,0,'Y','#85e6ce'],[0,0,1,'Z','#93bcff']];
    compass.replaceChildren(...axes.flatMap(([x,y,z,label,color])=>{const p=explorer.project([x*2.5,y*2.5,z*2.5],82,82),dx=p.x-center.x,dy=p.y-center.y,len=Math.hypot(dx,dy)||1,scale=Math.min(1,25/len),end=[41+dx*scale,41+dy*scale];const line=document.createElementNS('http://www.w3.org/2000/svg','line');for(const [k,v] of Object.entries({x1:41,y1:41,x2:end[0],y2:end[1],stroke:color,'stroke-width':1.5}))line.setAttribute(k,v);const text=document.createElementNS('http://www.w3.org/2000/svg','text');text.setAttribute('x',end[0]+3);text.setAttribute('y',end[1]-3);text.setAttribute('fill',color);text.setAttribute('font-size','9');text.textContent=label;return[line,text]}));
    requestAnimationFrame(t=>this.tick(t));
  }
}
window.sandbox=new OrbitalSandbox();
