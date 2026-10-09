"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path='modules/web_workbench/web/place_names.js';
assert.ok(fs.existsSync(path),'Shared place formatter must exist');
const listeners={},ctx={console,state:{pois:[{poi_id:'park',names:{'zh-Hans':'世纪公园',en:'Century Park'}}],anchors:{hotels:[],hubs:[]}},window:{IRLanguage:{getLanguage:()=> 'en'},addEventListener:(k,f)=>listeners[k]=f}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path,'utf8'),ctx);
assert.equal(ctx.placeDisplayName({poi_id:'park'}),'世纪公园 / Century Park');
assert.equal(ctx.placeDisplayName({name_zh:'新名称',name_en:'Old Name',name_en_for_zh:'旧名称'}),'新名称');
assert.equal(ctx.placeDisplayName({name_zh:'世纪公园',name_en:'Century Park'},'zh-CN'),'世纪公园');
assert.equal(ctx.placeDisplayName({name_zh:'新天地 / Xintiandi',name_en:'Xintiandi'}),'新天地 / Xintiandi');
assert.ok(listeners['inboundroute:languagechange'],'Language switch must refresh shared name nodes');
console.log('Shared place names: POI lookup, rename invalidation, locale and duplicate suppression passed');

vm.runInContext("placeNames.entries.set(placeClientKey({name_zh:'测试旅馆'}),{name_en:'Ce Shi Inn',status:'candidate'})",ctx);
assert.ok(ctx.placeDisplayName({name_zh:'测试旅馆'}).includes('Unconfirmed'),'Candidate display must be visibly marked before offline export');
