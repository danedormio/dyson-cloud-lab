/* SPDX-License-Identifier: GPL-3.0-or-later
 * Browser physics executable: REBOUND gravity + finite-resource central actuators.
 * Corresponding upstream source and license are in engine/vendor; see README.md.
 */
#include "rebound.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
#define MAX_N 1800
#define MAX_P 32
#define HIST 96
#define AU 149597870700.0
#define DAY 86400.0
#define YEAR (365.25*DAY)
#define GRAV 6.67430e-11
#define SUN 1.98847e30
#define C 299792458.0
#define PM 1e12
#define MASS 9e20
#define REF (PM*45000.0*45000.0)
#define PI 3.14159265358979323846
#define OUTPUT_SIZE 40000
#define SNAP_SIZE 80000

typedef struct { double t,r[3],v[3]; } Observation;
typedef struct { int body,plan,nh; double birth,target,plan_t,speed,offset,az,el,roll; Observation h[HIST]; } Packet;
static struct reb_simulation* sim;
static int count,np,enabled=1,halted,exact_mode;
static double inner,outer,capacity,force,power,reach;
static double store[MAX_N],heat[MAX_N],base[MAX_N],activity[MAX_N],packet_activity[MAX_N],used[MAX_N],work_used[MAX_N];
static Packet packet[MAX_P];
static double initial_e,boundary_e,work_total,impulse_total,initial_p[3],boundary_p[3],initial_l[3],boundary_l[3];
static double output[OUTPUT_SIZE],snapshot[SNAP_SIZE];
static int links[MAX_N],neighbors[MAX_N],retry_count;
static uint32_t random_state;

static double now_ms(void){
#ifdef __EMSCRIPTEN__
 return emscripten_get_now();
#else
 struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.+t.tv_nsec/1e6;
#endif
}
static double rand01(void){random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return (random_state+.5)/4294967296.;}
static double norm3(const double* v){return sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);}
static double dot3(const double*a,const double*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void cross3(const double*a,const double*b,double*c){c[0]=a[1]*b[2]-a[2]*b[1];c[1]=a[2]*b[0]-a[0]*b[2];c[2]=a[0]*b[1]-a[1]*b[0];}
static double clamp(double x,double lo,double hi){return fmax(lo,fmin(hi,x));}
static void position(struct reb_particle p,double*v){v[0]=p.x;v[1]=p.y;v[2]=p.z;}
static void velocity(struct reb_particle p,double*v){v[0]=p.vx;v[1]=p.vy;v[2]=p.vz;}
static void relative(struct reb_particle a,struct reb_particle b,double*r,double*v){r[0]=a.x-b.x;r[1]=a.y-b.y;r[2]=a.z-b.z;v[0]=a.vx-b.vx;v[1]=a.vy-b.vy;v[2]=a.vz-b.vz;}
static void momentum(double*p,double*l){p[0]=p[1]=p[2]=l[0]=l[1]=l[2]=0;for(unsigned i=0;i<sim->N;i++){struct reb_particle a=sim->particles[i];p[0]+=a.m*a.vx;p[1]+=a.m*a.vy;p[2]+=a.m*a.vz;l[0]+=a.m*(a.y*a.vz-a.z*a.vy);l[1]+=a.m*(a.z*a.vx-a.x*a.vz);l[2]+=a.m*(a.x*a.vy-a.y*a.vx);}}
static double sum_store(void){double e=0;for(int i=0;i<count;i++)e+=store[i];return e;}
static double sum_heat(void){double e=0;for(int i=0;i<count;i++)e+=heat[i];return e;}
static double residual(void){return reb_simulation_energy(sim)+sum_store()+sum_heat()-initial_e-boundary_e;}
static void make_sim(void){if(sim)reb_simulation_free(sim);sim=reb_simulation_create();sim->G=GRAV;sim->integrator=exact_mode?REB_INTEGRATOR_IAS15:REB_INTEGRATOR_WHFAST;sim->ri_whfast.safe_mode=0;sim->ri_whfast.corrector=0;sim->ri_ias15.epsilon=1e-10;sim->save_messages=1;}

int cloud_reset(int n,double ri,double ro,int seed){
 if(n<1||n>MAX_N||!isfinite(ri)||!isfinite(ro)||ri<.3||ro<=ri||ro>60)return 0;
 count=n;inner=ri;outer=ro;np=halted=retry_count=0;enabled=1;random_state=seed?seed:122333;
 capacity=2e22*900./n;force=2e9*900./n;power=2e14*900./n;reach=2.*AU;
 memset(packet,0,sizeof(packet));memset(activity,0,sizeof(activity));memset(packet_activity,0,sizeof(packet_activity));
 for(int i=0;i<MAX_N;i++){links[i]=neighbors[i]=-1;}
 make_sim();struct reb_particle star={0};star.m=SUN;reb_simulation_add(sim,star);
 for(int i=0;i<n;i++){
  double radius=(ri+(ro-ri)*(i+rand01())/n)*AU,z=2*rand01()-1,phi=2*PI*rand01();
  double r[3]={sqrt(1-z*z)*cos(phi),sqrt(1-z*z)*sin(phi),z};
  double a=2*PI*rand01(),h=2*rand01()-1,axis[3]={sqrt(1-h*h)*cos(a),sqrt(1-h*h)*sin(a),h},v[3];cross3(r,axis,v);
  double length=norm3(v),speed=sqrt(GRAV*SUN/radius);struct reb_particle node={0};node.m=MASS/n;
  node.x=r[0]*radius;node.y=r[1]*radius;node.z=r[2]*radius;node.vx=v[0]*speed/length;node.vy=v[1]*speed/length;node.vz=v[2]*speed/length;
  reb_simulation_add(sim,node);base[i]=radius;store[i]=.5*capacity;heat[i]=0;
 }
 reb_simulation_move_to_com(sim);initial_e=reb_simulation_energy(sim)+sum_store();boundary_e=work_total=impulse_total=0;
 memset(boundary_p,0,sizeof(boundary_p));memset(boundary_l,0,sizeof(boundary_l));momentum(initial_p,initial_l);return 1;
}
void cloud_exact(int flag){exact_mode=flag!=0;}
void cloud_coordination(int flag){enabled=flag!=0;}
int cloud_launch(double speed,double offset,double az,double el,double roll){
 if(!sim||np>=MAX_P||!isfinite(speed)||!isfinite(offset)||!isfinite(az)||!isfinite(el)||!isfinite(roll)||speed<5||speed>300||fabs(offset)>outer*1.5||fabs(az)>180||fabs(el)>90||fabs(roll)>180)return 0;
 reb_simulation_synchronize(sim);double before=reb_simulation_energy(sim),p0[3],l0[3],p1[3],l1[3];momentum(p0,l0);
 double a=az*PI/180,e=el*PI/180,q=roll*PI/180,d[3]={cos(e)*cos(a),cos(e)*sin(a),sin(e)},s[3]={-sin(a),cos(a),0},u[3]={-sin(e)*cos(a),-sin(e)*sin(a),cos(e)};
 struct reb_particle star=sim->particles[0],body={0};body.m=PM;
 body.x=star.x+AU*(-1.35*outer*d[0]+offset*(cos(q)*s[0]+sin(q)*u[0]));body.y=star.y+AU*(-1.35*outer*d[1]+offset*(cos(q)*s[1]+sin(q)*u[1]));body.z=star.z+AU*(-1.35*outer*d[2]+offset*(cos(q)*s[2]+sin(q)*u[2]));
 body.vx=star.vx+speed*1000*d[0];body.vy=star.vy+speed*1000*d[1];body.vz=star.vz+speed*1000*d[2];
 reb_simulation_add(sim,body);reb_simulation_reset_integrator(sim);sim->integrator=exact_mode?REB_INTEGRATOR_IAS15:REB_INTEGRATOR_WHFAST;sim->ri_whfast.safe_mode=0;sim->ri_ias15.epsilon=1e-10;
 boundary_e+=reb_simulation_energy(sim)-before;momentum(p1,l1);for(int k=0;k<3;k++){boundary_p[k]+=p1[k]-p0[k];boundary_l[k]+=l1[k]-l0[k];}
 Packet*b=&packet[np];memset(b,0,sizeof(*b));b->body=count+1+np;b->birth=sim->t;b->target=clamp(fabs(offset),inner*1.5,outer*.7)*AU;b->speed=speed;b->offset=offset;b->az=az;b->el=el;b->roll=roll;
 double r[3],v[3];relative(body,star,r,v);b->plan_t=sim->t+norm3(r)/C;
 double estimate=fmin(count, count*4./(4.*(outer-inner))*PI/fmax(inner,fabs(offset)));double available=estimate*force*(4*AU/(speed*1000))*.35;
 double need=PM*fmax(0,speed*1000-sqrt(GRAV*SUN/b->target));b->plan=need>1.5*available?3:need>available?2:1;np++;return np;
}

static int exchange(int i,int j,double J,double dt,int owner){
 struct reb_particle*a=&sim->particles[i],*b=&sim->particles[j];double r[3],v[3];relative(*a,*b,r,v);double distance=norm3(r);if(distance==0||distance>reach)return 0;
 double left=force*dt-used[owner];if(i>=1&&i<=count)left=fmin(left,force*dt-used[i-1]);if(j>=1&&j<=count)left=fmin(left,force*dt-used[j-1]);if(left<=0)return 0;
 J=clamp(J,-left,left);double u[3]={r[0]/distance,r[1]/distance,r[2]/distance},relative_v=dot3(v,u),reduced=1/a->m+1/b->m;
 double delta=J*relative_v+.5*J*J*reduced,available_work=power*dt-work_used[owner];if(available_work<=0)return 0;
 if(fabs(delta)>available_work){J*=available_work/fabs(delta);delta=J*relative_v+.5*J*J*reduced;}
 if(fabs(delta)>available_work*(1+1e-12))return 0;
 double electrical=delta>=0?-delta/.9:-.9*delta,thermal=-delta-electrical;
 if(store[owner]+electrical<0||store[owner]+electrical>capacity||heat[owner]+thermal>.25*capacity)return 0;
 for(int index=0;index<2;index++){
  int id=index?j:i;if(id<1||id>count)continue;struct reb_particle node=sim->particles[id],sun=sim->particles[0];double nr[3],nv[3];relative(node,sun,nr,nv);
  double direction=index?-1:1;for(int k=0;k<3;k++)nv[k]+=direction*J*u[k]/node.m;
  double ref=-GRAV*SUN/(2*base[id-1]),specific=.5*dot3(nv,nv)-GRAV*SUN/norm3(nr);
  if(fabs((specific-ref)/ref)>.05||fabs(J)/node.m>2)return 0;
 }
 a->vx+=J*u[0]/a->m;a->vy+=J*u[1]/a->m;a->vz+=J*u[2]/a->m;b->vx-=J*u[0]/b->m;b->vy-=J*u[1]/b->m;b->vz-=J*u[2]/b->m;
 store[owner]+=electrical;heat[owner]+=thermal;work_total+=delta;impulse_total+=fabs(J);work_used[owner]+=fabs(delta);
 if(i>=1&&i<=count)used[i-1]+=fabs(J);if(j>=1&&j<=count)used[j-1]+=fabs(J);
 activity[owner]=fmax(activity[owner],fabs(J)/(force*dt));
 if(i>count){packet_activity[owner]=fmax(packet_activity[owner],fabs(J)/(force*dt));links[owner]=i;}else neighbors[owner]=j;
 return 1;
}
static void controls(double dt){
 double decay=exp(-dt/(.5*DAY));for(int k=0;k<count;k++){activity[k]*=decay;packet_activity[k]*=decay;used[k]=work_used[k]=0;links[k]=neighbors[k]=-1;}
 if(!enabled||!np)return;
 struct reb_particle sun=sim->particles[0];int active=0;
 for(int p=0;p<np;p++){
  Packet*b=&packet[p];struct reb_particle cargo=sim->particles[b->body];if(b->plan==3)continue;active=1;
  if(b->nh==HIST){memmove(b->h,b->h+1,(HIST-1)*sizeof(Observation));b->nh--;}
  Observation*o=&b->h[b->nh++];o->t=sim->t;position(cargo,o->r);velocity(cargo,o->v);
  for(int k=0;k<count;k++){
   struct reb_particle node=sim->particles[k+1];double node_pos[3];position(node,node_pos);double from_sun[3]={node.x-sun.x,node.y-sun.y,node.z-sun.z};
   if(sim->t<b->plan_t+norm3(from_sun)/C)continue;
   Observation*seen=NULL;for(int h=b->nh-1;h>=0;h--){double dr[3]={b->h[h].r[0]-node.x,b->h[h].r[1]-node.y,b->h[h].r[2]-node.z};if(norm3(dr)<=C*(sim->t-b->h[h].t)){seen=&b->h[h];break;}}
   if(!seen)continue;
   double lag=sim->t-seen->t,r[3],v[3],line[3];for(int j=0;j<3;j++){r[j]=seen->r[j]+seen->v[j]*lag;line[j]=r[j]-node_pos[j];}r[0]-=sun.x;r[1]-=sun.y;r[2]-=sun.z;v[0]=seen->v[0]-sun.vx;v[1]=seen->v[1]-sun.vy;v[2]=seen->v[2]-sun.vz;
   double distance=norm3(line),radius=norm3(r);if(distance>reach||distance==0||radius<.08*AU)continue;
   double radial=dot3(r,v)/radius,tangent[3];for(int j=0;j<3;j++)tangent[j]=v[j]-radial*r[j]/radius;
   double tn=norm3(tangent);if(tn<1e-6){double z[3]={0,0,1};cross3(z,r,tangent);tn=norm3(tangent);if(tn<1e-6){double x[3]={1,0,0};cross3(x,r,tangent);tn=norm3(tangent);}}
   double circular=sqrt(GRAV*SUN/radius),radial_target=clamp((b->target-radius)/(120*DAY),-3000,3000),projected=0;
   for(int j=0;j<3;j++){double desired=circular*tangent[j]/tn+radial_target*r[j]/radius;projected+=(desired-v[j])*line[j]/distance;}
   exchange(b->body,k+1,PM*projected*dt/(3*DAY),dt,k);
  }
 }
 if(!active)return;
 for(int k=0;k<count;k++){
  int i=k+1,j=-1;double closest=reach*reach;struct reb_particle a=sim->particles[i];
  for(int n=1;n<=count;n++){if(n==i)continue;struct reb_particle b=sim->particles[n];double dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z,d2=dx*dx+dy*dy+dz*dz;if(d2<closest){closest=d2;j=n;}}
  if(j<0||closest==0)continue;struct reb_particle b=sim->particles[j];double r[3],v[3];relative(a,b,r,v);double rel=dot3(r,v)/sqrt(closest);
  exchange(i,j,-rel/(1/a.m+1/b.m)*(1-exp(-dt/(7200./.00001))),dt,k);
 }
}

static int write_snapshot(double*out){
 int q=0;out[q++]=24001;out[q++]=count;out[q++]=np;out[q++]=enabled;out[q++]=halted;out[q++]=inner;out[q++]=outer;out[q++]=sim->t;
 out[q++]=initial_e;out[q++]=boundary_e;out[q++]=work_total;out[q++]=impulse_total;
 for(int j=0;j<3;j++){out[q++]=initial_p[j];out[q++]=boundary_p[j];out[q++]=initial_l[j];out[q++]=boundary_l[j];}
 for(unsigned i=0;i<sim->N;i++){struct reb_particle p=sim->particles[i];out[q++]=p.m;out[q++]=p.x;out[q++]=p.y;out[q++]=p.z;out[q++]=p.vx;out[q++]=p.vy;out[q++]=p.vz;}
 for(int i=0;i<count;i++){out[q++]=store[i];out[q++]=heat[i];out[q++]=base[i];out[q++]=activity[i];out[q++]=packet_activity[i];out[q++]=links[i];out[q++]=neighbors[i];}
 for(int i=0;i<np;i++){Packet*b=&packet[i];out[q++]=b->body;out[q++]=b->plan;out[q++]=b->birth;out[q++]=b->target;out[q++]=b->plan_t;out[q++]=b->speed;out[q++]=b->offset;out[q++]=b->az;out[q++]=b->el;out[q++]=b->roll;out[q++]=b->nh;for(int h=0;h<b->nh;h++){out[q++]=b->h[h].t;for(int k=0;k<3;k++)out[q++]=b->h[h].r[k];for(int k=0;k<3;k++)out[q++]=b->h[h].v[k];}}
 return q;
}
static int read_snapshot(const double*in,int length){
 if(length<24||length>SNAP_SIZE||in[0]!=24001)return 0;for(int i=0;i<length;i++)if(!isfinite(in[i]))return 0;
 int n=(int)in[1],p=(int)in[2];if(n<1||n>MAX_N||p<0||p>MAX_P||length<24+7*(1+n+p)+7*n+11*p)return 0;
 int q=0;q++;count=in[q++];np=in[q++];enabled=in[q++];halted=in[q++];inner=in[q++];outer=in[q++];double t=in[q++];if(inner<.3||outer<=inner||outer>60)return 0;
 capacity=2e22*900./count;force=2e9*900./count;power=2e14*900./count;reach=2*AU;
 initial_e=in[q++];boundary_e=in[q++];work_total=in[q++];impulse_total=in[q++];for(int j=0;j<3;j++){initial_p[j]=in[q++];boundary_p[j]=in[q++];initial_l[j]=in[q++];boundary_l[j]=in[q++];}
 make_sim();for(int i=0;i<1+count+np;i++){struct reb_particle a={0};a.m=in[q++];a.x=in[q++];a.y=in[q++];a.z=in[q++];a.vx=in[q++];a.vy=in[q++];a.vz=in[q++];if(a.m<=0)return 0;reb_simulation_add(sim,a);}sim->t=t;
 for(int i=0;i<count;i++){store[i]=in[q++];heat[i]=in[q++];base[i]=in[q++];activity[i]=in[q++];packet_activity[i]=in[q++];links[i]=in[q++];neighbors[i]=in[q++];if(store[i]<0||store[i]>capacity||heat[i]<0||heat[i]>.25*capacity||base[i]<=0)return 0;}
 for(int i=0;i<np;i++){Packet*b=&packet[i];b->body=in[q++];b->plan=in[q++];b->birth=in[q++];b->target=in[q++];b->plan_t=in[q++];b->speed=in[q++];b->offset=in[q++];b->az=in[q++];b->el=in[q++];b->roll=in[q++];b->nh=in[q++];if(b->body!=count+1+i||b->nh<0||b->nh>HIST||q+7*b->nh>length)return 0;for(int h=0;h<b->nh;h++){b->h[h].t=in[q++];for(int k=0;k<3;k++)b->h[h].r[k]=in[q++];for(int k=0;k<3;k++)b->h[h].v[k]=in[q++];}}
 return q==length;
}
int cloud_save(void){reb_simulation_synchronize(sim);return write_snapshot(snapshot);}
double* cloud_snapshot(void){return snapshot;}
int cloud_restore(int length){return read_snapshot(snapshot,length);}

static int step_once(double dt,int coupled){
 if(exact_mode){sim->integrator=REB_INTEGRATOR_IAS15;sim->ri_ias15.epsilon=1e-10;}else{sim->integrator=REB_INTEGRATOR_WHFAST;sim->ri_whfast.safe_mode=0;sim->ri_whfast.corrector=0;}
 sim->status=REB_STATUS_SUCCESS;sim->dt=dt/(coupled?2:1);double start=sim->t;
 if(coupled){reb_simulation_integrate(sim,start+dt/2);reb_simulation_synchronize(sim);double before=impulse_total;controls(dt);if(impulse_total!=before){reb_simulation_reset_integrator(sim);sim->integrator=exact_mode?REB_INTEGRATOR_IAS15:REB_INTEGRATOR_WHFAST;sim->ri_whfast.safe_mode=0;sim->ri_ias15.epsilon=1e-10;sim->dt=dt/2;}reb_simulation_integrate(sim,start+dt);}
 else reb_simulation_integrate(sim,start+dt);
 reb_simulation_synchronize(sim);return 1;
}
double cloud_advance(double days,double wall_ms){
 if(!sim||halted||!isfinite(days)||days<=0)return 0;days=fmin(days,3652.5);double start=sim->t,end=start+days*DAY,wall=now_ms();
 while(sim->t<end-1e-5){
  struct reb_particle sun=sim->particles[0];int coupled=0;double min_radius=outer*AU;
  for(int i=0;i<np;i++){double r[3],v[3];relative(sim->particles[packet[i].body],sun,r,v);double radius=norm3(r);min_radius=fmin(min_radius,radius);if(radius<.08*AU){halted=1;break;}if(enabled&&packet[i].plan!=3&&radius<(outer+2.5)*AU)coupled=1;}
  if(halted)break;
  double dt=coupled?clamp(.05*pow(min_radius/AU,1.5),.125,1)*DAY:32*pow(inner,1.5)*DAY;
  dt=fmin(dt,end-sim->t);int length=write_snapshot(snapshot);double accepted=dt;
  int valid=0;for(int attempt=0;attempt<9;attempt++){
   step_once(accepted,coupled);
   if(isfinite(residual())&&fabs(residual()/REF)<1e-4){valid=1;break;}
   if(!read_snapshot(snapshot,length)){halted=2;break;}accepted*=.5;retry_count++;
  }
  if(!valid){halted=2;break;}
  if(now_ms()-wall>=wall_ms)break;
 }
 return (sim->t-start)/DAY;
}
int cloud_state(void){
 if(!sim)return 0;reb_simulation_synchronize(sim);int q=0;output[q++]=sim->t/DAY;output[q++]=count;output[q++]=np;output[q++]=enabled;output[q++]=halted;output[q++]=inner;output[q++]=outer;output[q++]=sum_store();output[q++]=sum_heat();output[q++]=work_total;output[q++]=impulse_total;output[q++]=residual()/REF;output[q++]=capacity;output[q++]=force;output[q++]=retry_count;
 double p[3],l[3],dp[3],dl[3];momentum(p,l);for(int i=0;i<3;i++){dp[i]=p[i]-initial_p[i]-boundary_p[i];dl[i]=l[i]-initial_l[i]-boundary_l[i];}output[q++]=norm3(dp);output[q++]=norm3(dl);output[q++]=boundary_e;output[q++]=MASS;output[q++]=1+count+np;
 for(unsigned i=0;i<sim->N;i++){struct reb_particle a=sim->particles[i];output[q++]=a.x/AU;output[q++]=a.y/AU;output[q++]=a.z/AU;output[q++]=a.vx;output[q++]=a.vy;output[q++]=a.vz;output[q++]=a.m;output[q++]=(i>0&&i<=count)?store[i-1]/capacity:-1;output[q++]=(i>0&&i<=count)?heat[i-1]/capacity:0;output[q++]=(i>0&&i<=count)?activity[i-1]:0;output[q++]=(i>0&&i<=count)?links[i-1]:-1;output[q++]=(i>0&&i<=count)?neighbors[i-1]:-1;}
 struct reb_particle sun=sim->particles[0];for(int i=0;i<np;i++){Packet*b=&packet[i];double r[3],v[3],h[3];relative(sim->particles[b->body],sun,r,v);double radius=norm3(r),mu=GRAV*(SUN+PM),energy=.5*dot3(v,v)-mu/radius;cross3(r,v,h);double h2=dot3(h,h),ecc=sqrt(fmax(0,1+2*energy*h2/(mu*mu)));output[q++]=b->body;output[q++]=b->plan;output[q++]=norm3(v)/1000;output[q++]=radius/AU;output[q++]=energy;output[q++]=ecc;output[q++]=h2/mu/(1+ecc)/AU;output[q++]=energy<0?-mu/(2*energy)*(1+ecc)/AU:-1;output[q++]=b->target/AU;output[q++]=dot3(r,v)/radius;output[q++]=b->birth/DAY;}
 return q;
}
double* cloud_output(void){return output;}
