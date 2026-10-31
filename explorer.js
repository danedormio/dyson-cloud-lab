/* WebGL viewing only. Float64 SI state stays in the backend snapshot; rendering
 * converts to AU. Enlarged sphere glyphs and guide rings have no physics effect.
 * No external assets or network dependencies. */
class ExplorerView {
  constructor(canvas, onSelect) {
    this.canvas=canvas; this.onSelect=onSelect; this.home(); this.selected=null;
    this.labels=document.querySelector('#sceneLabels');
    this.status=document.querySelector('#renderStatus');
    this.gl=canvas.getContext('webgl', {antialias:true, preserveDrawingBuffer:true});
    if(!this.gl){this.status.textContent='WebGL unavailable. Use the object list to inspect state; enable WebGL for 3D.';return;}
    try{this.init()}catch(error){this.status.textContent="3D graphics initialization failed. Object inspection remains available.";this.gl=null;return;}
    canvas.addEventListener('webglcontextlost', e=>{e.preventDefault();this.lost=true;this.status.textContent='3D graphics interrupted. Waiting for WebGL recovery; simulation state is preserved.'});
    canvas.addEventListener('webglcontextrestored', ()=>{this.init();this.lost=false;this.status.textContent=''});
    const pointers=new Map(); let moved=false, start=null, pinch=null;
    canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);start=[e.clientX,e.clientY];moved=false;pinch=null});
    canvas.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;const old=pointers.get(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);if(pointers.size===2){const [a,b]=[...pointers.values()],d=Math.hypot(a[0]-b[0],a[1]-b[1]);if(pinch&&d)this.zoom(pinch/d);pinch=d;moved=true}else{const dx=e.clientX-old[0],dy=e.clientY-old[1];if(Math.hypot(e.clientX-start[0],e.clientY-start[1])>4)moved=true;if(moved){this.az+=dx*.008;this.el=Math.max(-1.5,Math.min(1.5,this.el+dy*.008));}}});
    const end=(e,cancel=false)=>{if(!pointers.has(e.pointerId))return;if(!cancel&&!moved&&pointers.size===1){const rect=canvas.getBoundingClientRect();this.pick(e.clientX-rect.left,e.clientY-rect.top)}pointers.delete(e.pointerId);pinch=null};
    canvas.addEventListener('pointerup',e=>end(e));canvas.addEventListener('pointercancel',e=>end(e,true));
    canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom(Math.exp(Math.max(-200,Math.min(200,e.deltaY))*.003))},{passive:false});
    canvas.addEventListener('keydown',e=>{if(e.key==='Home'){this.home();e.preventDefault()}if(e.key==='+'||e.key==='=')this.zoom(.85);if(e.key==='-')this.zoom(1.15);if(e.key==='ArrowLeft')this.az-=.1;if(e.key==='ArrowRight')this.az+=.1;if(e.key==='ArrowUp')this.el=Math.min(1.5,this.el+.1);if(e.key==='ArrowDown')this.el=Math.max(-1.5,this.el-.1);if(e.key.startsWith('Arrow'))e.preventDefault()});
  }
  home(){this.az=.45;this.el=.65;this.distance=13;}
  zoom(factor){this.distance=Math.max(2,Math.min(60,this.distance*factor));}
  select(id){this.selected=id;}
  init(){
    const gl=this.gl;
    const shader=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s};
    const vs=shader(gl.VERTEX_SHADER,`attribute vec3 aPosition; attribute vec3 aNormal;
      uniform vec3 uCenter; uniform float uRadius,uAz,uEl,uDistance,uAspect;
      varying vec3 vNormal;
      void main(){vec3 p=uCenter+aPosition*uRadius;
        float x=p.x*cos(uAz)-p.y*sin(uAz),y=p.x*sin(uAz)+p.y*cos(uAz);
        float up=y*sin(uEl)+p.z*cos(uEl),depth=uDistance+y*cos(uEl)-p.z*sin(uEl);
        gl_Position=vec4(2.0*x/uAspect,2.0*up,1.002*depth-0.2002,depth);
        vNormal=aNormal;}`);
    const fs=shader(gl.FRAGMENT_SHADER,`precision mediump float;uniform vec3 uColor;uniform float uLit;varying vec3 vNormal;
      void main(){float light=mix(1.0,0.32+0.68*max(0.0,dot(normalize(vNormal),normalize(vec3(-1.0,-1.0,2.0)))),uLit);gl_FragColor=vec4(uColor*light,1.0);}`);
    this.program=gl.createProgram();gl.attachShader(this.program,vs);gl.attachShader(this.program,fs);gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('WebGL program link failed');
    this.uniform={};for(const key of ['Center','Radius','Az','El','Distance','Aspect','Color','Lit'])this.uniform[key]=gl.getUniformLocation(this.program,'u'+key);
    this.position=gl.getAttribLocation(this.program,'aPosition');this.normal=gl.getAttribLocation(this.program,'aNormal');
    const vertices=[],normals=[];const point=(lat,lon)=>[Math.cos(lat)*Math.cos(lon),Math.cos(lat)*Math.sin(lon),Math.sin(lat)];
    for(let i=0;i<12;i++)for(let j=0;j<20;j++){const a=point(-Math.PI/2+i*Math.PI/12,j*Math.PI/10),b=point(-Math.PI/2+(i+1)*Math.PI/12,j*Math.PI/10),c=point(-Math.PI/2+(i+1)*Math.PI/12,(j+1)*Math.PI/10),d=point(-Math.PI/2+i*Math.PI/12,(j+1)*Math.PI/10);for(const p of [a,b,c,a,c,d]){vertices.push(...p);normals.push(...p)}}
    this.sphere=this.buffer(vertices);this.normals=this.buffer(normals);this.sphereCount=vertices.length/3;this.lines=gl.createBuffer();
    gl.enable(gl.DEPTH_TEST);gl.clearColor(.02,.045,.08,1);
  }
  buffer(data){const gl=this.gl,b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);return b;}
  project(p,w,h){const x=p[0]*Math.cos(this.az)-p[1]*Math.sin(this.az),y=p[0]*Math.sin(this.az)+p[1]*Math.cos(this.az),up=y*Math.sin(this.el)+p[2]*Math.cos(this.el),depth=this.distance+y*Math.cos(this.el)-p[2]*Math.sin(this.el);return {x:w/2+x*h/depth,y:h/2-up*h/depth,depth};}
  pick(x,y){const hits=(this.projected||[]).filter(p=>p.depth>.1&&Math.hypot(x-p.x,y-p.y)<Math.max(9,p.radius));// Prefer an actual glyph hit over a nearby body's generous touch target.
    // Within overlapping glyphs, depth resolves the visible front body.
    hits.sort((a,b)=>{const da=Math.hypot(x-a.x,y-a.y),db=Math.hypot(x-b.x,y-b.y),ia=da<=a.radius,ib=db<=b.radius;return Number(ib)-Number(ia)||(ia&&ib?a.depth-b.depth:da-db)});if(hits.length)this.onSelect(hits[0].id);}
  render(snapshot,options){
    if(!this.gl||this.lost)return;const gl=this.gl,w=this.canvas.clientWidth,h=this.canvas.clientHeight;if(!w||!h)return;
    const d=Math.min(2,window.devicePixelRatio||1);if(this.canvas.width!==Math.round(w*d)||this.canvas.height!==Math.round(h*d)){this.canvas.width=Math.round(w*d);this.canvas.height=Math.round(h*d)}
    gl.viewport(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);if(!snapshot)return;
    gl.useProgram(this.program);gl.uniform1f(this.uniform.Az,this.az);gl.uniform1f(this.uniform.El,this.el);gl.uniform1f(this.uniform.Distance,this.distance);gl.uniform1f(this.uniform.Aspect,w/h);
    gl.enableVertexAttribArray(this.position);gl.bindBuffer(gl.ARRAY_BUFFER,this.sphere);gl.vertexAttribPointer(this.position,3,gl.FLOAT,false,0,0);gl.enableVertexAttribArray(this.normal);gl.bindBuffer(gl.ARRAY_BUFFER,this.normals);gl.vertexAttribPointer(this.normal,3,gl.FLOAT,false,0,0);
    this.projected=[];const labels=[];
    for(const b of snapshot.bodies){if(b.role==='cloud'&&!options.cloud)continue;const p=[b.x_m/149597870700,b.y_m/149597870700,b.z_m/149597870700],r=b.role==='star'?.15:b.role==='planet'?.085:b.role==='tracked'?.07:.045;
      const color=b.id===this.selected?[1,.95,.5]:b.role==='star'?[1,.72,.26]:b.role==='planet'?[.2,.72,1]:b.role==='tracked'?[1,.42,.16]:[.48,.72,.86];
      gl.uniform3fv(this.uniform.Center,p);gl.uniform1f(this.uniform.Radius,r);gl.uniform3fv(this.uniform.Color,color);gl.uniform1f(this.uniform.Lit,1);gl.drawArrays(gl.TRIANGLES,0,this.sphereCount);
      const q={...this.project(p,w,h),id:b.id};q.radius=r*h/q.depth;this.projected.push(q);if((options.labels&&b.role!=='cloud')||b.id===this.selected){if(q.depth>.1&&q.x>=0&&q.x<w&&q.y>=0&&q.y<h){const label=document.createElement('span');label.textContent=b.name;label.style.left=(q.x+10)+'px';label.style.top=(q.y-10)+'px';labels.push(label)}}
    }
    this.labels.replaceChildren(...labels);
    const line=(points,color)=>{if(!points.length)return;gl.bindBuffer(gl.ARRAY_BUFFER,this.lines);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(points.flat()),gl.DYNAMIC_DRAW);gl.vertexAttribPointer(this.position,3,gl.FLOAT,false,0,0);gl.disableVertexAttribArray(this.normal);gl.vertexAttrib3f(this.normal,0,0,1);gl.uniform3f(this.uniform.Center,0,0,0);gl.uniform1f(this.uniform.Radius,1);gl.uniform1f(this.uniform.Lit,0);gl.uniform3fv(this.uniform.Color,color);gl.drawArrays(gl.LINE_STRIP,0,points.length)};
    if(options.shell)for(const r of [.8,4])line(Array.from({length:181},(_,i)=>[r*Math.cos(i*Math.PI/90),r*Math.sin(i*Math.PI/90),0]),[.18,.3,.43]);
    line(options.trail.map(p=>p.slice(0,3).map(v=>v/149597870700)),[.15,.5,.68]);
  }
}
