const {spawnSync}=require('node:child_process');
module.exports=function hydrate(trip) {
 const result=spawnSync('python',['-c','import json,sys; from core.trip_points import enrich_trip_points; print(json.dumps(enrich_trip_points(json.load(sys.stdin))))'],{input:JSON.stringify(trip),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});
 if(result.status!==0) throw new Error(result.stderr);
 Object.assign(trip,JSON.parse(result.stdout));return trip;
};
