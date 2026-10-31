#!/usr/bin/env node
/* Vehicle toggle staleness tests: fresh, 1 session stale (labeled fill), 2+ stale (Spot fallback), file missing, bad value, interior gap.
   usage: node tests/test_vehicle.js [history.json]  (default: tests/fixtures/vehicle/history.json) */
const fs=require('fs'),path=require('path'),R=path.join(__dirname,'..');
const H=JSON.parse(fs.readFileSync(process.argv[2]||path.join(__dirname,'fixtures/vehicle/history.json'),'utf8'));
const VD=JSON.parse(fs.readFileSync(path.join(R,'assets/data/vehicle-daily.json'),'utf8'));
let n=0,f=0;const chk=(name,ok,info)=>{n++;if(!ok){f++;console.log('FAIL',name,info===undefined?'':JSON.stringify(info));}else console.log('PASS',name);};
global.window=global;global.location={search:''};
eval(fs.readFileSync(path.join(R,'assets/js/ledger.js'),'utf8'));
function boot(vdOrErr){
  global.fetch=u=>/history\.json/.test(u)?Promise.resolve({ok:true,json:()=>Promise.resolve(H)}):
    (vdOrErr===404?Promise.resolve({ok:false,status:404}):Promise.resolve({ok:true,json:()=>Promise.resolve(JSON.parse(JSON.stringify(vdOrErr)))}));
  eval(fs.readFileSync(path.join(R,'assets/js/book.js'),'utf8'));return window.PSBook;}
const D=Object.keys(H.closes).sort(),last=D[D.length-1];
const cut=k=>{const v=JSON.parse(JSON.stringify(VD));const keep=D[D.length-1-k];['IBIT','FBTC'].forEach(x=>v.vehicles[x]=v.vehicles[x].filter(p=>p[0]<=keep));return v;};
async function run(name,vd,expect){const B=boot(vd);await B.ready;
  try{await B.loadVehicle();expect(null,B);}catch(e){expect(e,B);}}
(async()=>{
  await run('fresh: loads, as-of = last session, lag 0',cut(0),(e,B)=>chk('fresh',!e&&B.vehicleStatus.end===last&&B.vehicleStatus.lag===0,e&&e.message));
  await run('1 stale: loads with labeled 1-session fill',cut(1),(e,B)=>chk('1 session stale -> loads, lag 1, as-of prior session',!e&&B.vehicleStatus.lag===1&&B.vehicleStatus.end===D[D.length-2]&&B.vehicleMaps.IBIT[last]===B.vehicleMaps.IBIT[D[D.length-2]],e&&e.message));
  await run('2 stale',cut(2),(e)=>chk('2 sessions stale -> stale error (Spot fallback)',e&&e.stale===true&&e.end===D[D.length-3]&&e.lag===2,e&&e.message));
  await run('5 stale',cut(5),(e)=>chk('5 sessions stale -> stale error',e&&e.stale===true));
  await run('missing',404,(e)=>chk('file missing -> error, not stale',e&&!e.stale));
  for(const bad of [0,-1,null,true,'43.1']){const v=cut(0);v.vehicles.IBIT[v.vehicles.IBIT.length-3][1]=bad;
    await run('bad '+bad,v,(e)=>chk('bad value '+JSON.stringify(bad)+' -> error',!!e&&!e.stale,e&&e.message));}
  {const v=cut(0);v.vehicles.FBTC.splice(v.vehicles.FBTC.length-6,2);
    await run('gap',v,(e)=>chk('interior 2-session gap -> error',!!e,e&&e.message));}
  /* label text (vehicle.js) */
  const src=fs.readFileSync(path.join(R,'assets/js/vehicle.js'),'utf8');
  chk('vehicle.js has as-of label',/ETF prices as of the /.test(src));
  chk('vehicle.js has stale fallback label',/out of date \(last close /.test(src));
  console.log('VEHICLE TESTS',n,'FAIL',f);process.exit(f?1:0);})();
