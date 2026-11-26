const E = require("../web/signals.js");
const P=(x,y,z=0)=>({x,y,z});
const MCPX=[-.02,0,.02,.04];
function finger(x,st){ if(st==="e") return [P(x,-.08),P(x,-.11),P(x,-.13),P(x,-.15)];
  if(st==="h") return [P(x,-.08),P(x,-.11),P(x,-.12,.015),P(x,-.115,.035)];
  if(st==="o") return [P(-.02,-.08),P(-.02,-.11),P(-.03,-.115,.02),P(-.035,-.10,.03)];
  return [P(x,-.08),P(x,-.10,.02),P(x,-.08,.035),P(x,-.065,.02)]; }
const THUMB={out:[P(-.02,-.02),P(-.04,-.03),P(-.06,-.04),P(-.08,-.05)], side:[P(-.02,-.02),P(-.04,-.03),P(-.06,-.035),P(-.085,-.04)],
 up:[P(-.03,-.03),P(-.06,-.05),P(-.07,-.08),P(-.08,-.11)], down:[P(-.02,-.02),P(-.03,0),P(-.035,.03),P(-.04,.06)],
 in:[P(-.02,-.02),P(-.025,-.035),P(-.01,-.045),P(0,-.05)], pinch:[P(-.02,-.02),P(-.035,-.05),P(-.04,-.08),P(-.037,-.098,.028)]};
function hand(f,thumb,{rot=0,dx=0,dy=0}={}){
  let pts=[P(0,0),...THUMB[thumb]]; f.split("").forEach((s,i)=>pts.push(...finger(MCPX[i],s)));
  const c=Math.cos(rot),s=Math.sin(rot);
  pts=pts.map(p=>P(p.x*c-p.y*s+0.5+dx, p.x*s+p.y*c+0.6+dy, p.z));
  return {w:pts,img:pts};
}
function run(name, frames, expectKey){ // frames: fn(i)-> hand(s) or null, 30fps
  const e=new E(); const got=[];
  frames.forEach((f,i)=>{const r=e.update(f? (Array.isArray(f)?f:[f]):[], i*33); if(r) got.push(r.label);});
  const ok = expectKey(got);
  console.log((ok?"PASS ":"FAIL ")+name.padEnd(22), JSON.stringify(got));
}
const seq=(n,fn)=>Array.from({length:n},(_,i)=>fn(i));
const has=l=>g=>g.length&&g.some(x=>x.startsWith(l));
const exact=l=>g=>g.join("|")===l;
const S=0.08; // palm size in image units
run("oxygen OK",   seq(25,()=>hand("oeee","pinch")), exact("OXYGEN CHECK / OK"));
run("BDA",         seq(25,()=>hand("ezzz","out")), exact("BDA CHECK"));
run("echelon turn",seq(25,()=>hand("ezze","in")), exact("ECHELON TURN"));
run("lanyard",     seq(25,()=>hand("hzzz","in")), exact("LANYARD CHECK"));
run("fuel check",  seq(25,()=>hand("zzzz","side")), exact("FUEL CHECK"));
run("numbers 2,_,5 / 7",[...seq(20,()=>hand("eezz","in")),...seq(12,()=>null),...seq(20,()=>hand("eeee","out")),...seq(12,()=>null),...seq(20,()=>hand("eezz","in",{rot:Math.PI/2}))], exact("NUMBERS: 2|NUMBERS: 2 5|NUMBERS: 2 5 7"));
run("HEFOE fuel",  [...seq(20,()=>hand("zzzz","in")),...seq(20,()=>hand("eeez","in"))], exact("SYSTEM FAILURE: FUEL"));
run("gear up",     seq(30,i=>hand("zzzz","up",{dy:-i*0.006})), has("GEAR UP"));
run("gear down",   seq(30,i=>hand("zzzz","down",{dy:i*0.006})), has("GEAR DOWN"));
run("land immed",  seq(45,i=>hand("zzzz","down",{dy:Math.sin(i/2.5)*0.06})), has("I MUST LAND"));
run("jettison",    seq(45,i=>hand("zzzz","in",{dy:Math.sin(i/2.5)*0.06})), has("JETTISON"));
run("afterburner", seq(30,i=>hand("zzzz","in",{dx:i*0.007})), has("AFTERBURNER"));
run("pitchout",    seq(48,i=>hand("ezzz","in",{dx:Math.cos(i/4)*0.05,dy:Math.sin(i/4)*0.05})), has("PITCHOUT"));
run("start engines",seq(48,i=>hand("eeee","out",{dx:Math.cos(i/4)*0.05,dy:Math.sin(i/4)*0.05})), has("START ENGINES"));
run("descend",     seq(30,i=>hand("eeee","in",{rot:Math.PI/2,dy:i*0.007})), has("DESCEND"));
run("loosen",      seq(30,i=>hand("eeee","out",{dx:i*0.008})), has("LOOSEN"));
run("flaps down",  seq(30,i=>hand("eeee","in",{rot:Math.min(i,20)*0.06})), has("FLAPS DOWN"));
run("flaps up",    seq(30,i=>hand("eeee","in",{rot:1.2-Math.min(i,20)*0.06})), has("FLAPS UP"));
run("change lead #2",[...seq(45,i=>hand("ezzz","in",{rot:-Math.PI/2,dx:Math.sin(i/2.5)*0.05})),...seq(25,()=>hand("eezz","in"))], g=>g.join("|").includes("CHANGE LEAD: #2"));
run("bailout",     seq(30,i=>[hand("zzzz","in",{dy:i*0.008}),hand("zzzz","in",{dx:.2,dy:i*0.008})]), has("EJECTING"));
run("speed brakes",seq(48,i=>Math.floor(i/6)%2?hand("eeee","out"):hand("zzzz","in")), has("SPEED BRAKES"));
run("tx fail",     seq(45,i=>hand("eeee","out",{dy:Math.sin(i/2.5)*0.06})), has("RADIO: TRANSMITTER"));
run("still open = 5 only once", seq(60,()=>hand("eeee","out")), exact("NUMBERS: 5"));
