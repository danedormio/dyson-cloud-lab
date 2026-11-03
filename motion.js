/* Playback between acknowledged IAS15 samples only; never extrapolate physics. */
class AcknowledgedMotion {
  constructor(){this.frames=[];this.time=null;this.count=0;}
  accept(state){
    if(this.count!==state.bodies.length||this.time===null||state.time_s<this.time){this.frames=[];this.time=state.time_s;this.count=state.bodies.length;}
    const frames=state.motion_frames||[{time_s:state.time_s,positions_m:state.bodies.map(b=>[b.x_m,b.y_m,b.z_m])}];
    for(const f of frames)if(!this.frames.length||f.time_s>this.frames.at(-1).time_s)this.frames.push(f);
    if(this.frames.length>512)this.frames.splice(0,this.frames.length-512);
  }
  view(state,elapsed,rate,playing){
    if(!state||!this.frames.length)return state;
    this.time=playing?Math.min(state.time_s,Math.max(this.frames[0].time_s,this.time+elapsed*Math.min(rate,Math.max(0,state.time_s-this.time)/.16))):state.time_s;
    while(this.frames.length>2&&this.frames[1].time_s<this.time)this.frames.shift();
    let a=this.frames[0],b=this.frames[1]||a;
    if(this.time>=this.frames.at(-1).time_s)a=b=this.frames.at(-1);
    const t=Math.max(0,Math.min(1,(this.time-a.time_s)/(b.time_s-a.time_s||1)));
    return {...state,bodies:state.bodies.map((body,i)=>({...body,
      x_m:a.positions_m[i][0]+(b.positions_m[i][0]-a.positions_m[i][0])*t,
      y_m:a.positions_m[i][1]+(b.positions_m[i][1]-a.positions_m[i][1])*t,
      z_m:a.positions_m[i][2]+(b.positions_m[i][2]-a.positions_m[i][2])*t}))};
  }
}
