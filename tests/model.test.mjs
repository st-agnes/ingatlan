import test from 'node:test';
import assert from 'node:assert/strict';
import {createModel,isCompatible,STORAGE_KEY} from '../dist/model.js';
const store=()=>{const values=new Map();return{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)}};
const setup=()=>createModel(store(),()=>new Date('2026-10-31T12:00:00Z').toISOString());

test('feed respects every explicit search limit and excludes own or previously judged properties',()=>{
 const m=setup(),s=m.getState(),q=s.searches.find(q=>q.id===s.active.id);
 assert.equal(m.feed()[0].id,'p1');
 for(const p of m.feed())assert.equal(isCompatible(p,q),true);
 assert.equal(m.feed().some(p=>p.id.startsWith('incompatible')||p.ownerId==='me'),false);
 const first=m.feed()[0];m.decide(first,false);assert.equal(m.feed().some(p=>p.id===first.id),false);
 assert.throws(()=>m.decide(first,true),/már döntöttél/);
});
test('buyer like is free; contacts appear only after a reciprocal like',()=>{
 const m=setup();const card=m.feed()[0];assert.equal('email'in card,false);assert.equal('phone'in card,false);
 const before=m.getState().credits;const result=m.decide(card,true);
 assert.equal(result.charged,0);assert.equal(m.getState().credits,before);
 assert.ok(result.match.partner.email);assert.equal(m.matches().length,4);
 const noReciprocal=m.feed().find(p=>!p.likedYou);assert.equal(m.decide(noReciprocal,true).match,null);
});
test('seller is charged exactly once for a compatible like and passing is free',()=>{
 const m=setup();m.activate('property','own-p1');const first=m.feed()[0];assert.ok(first);
 const before=m.getState().credits;assert.equal(m.decide(first,true).charged,2);assert.equal(m.getState().credits,before-2);
 assert.throws(()=>m.decide(first,true),/már döntöttél/);assert.equal(m.getState().credits,before-2);
 const next=m.feed()[0];m.decide(next,false);assert.equal(m.getState().credits,before-2);
 assert.equal(m.getState().ledger.filter(l=>l.type==='seller_like').length,1);
});
test('insufficient balance leaves decisions and ledger untouched',()=>{
 const storage=store();const m=createModel(storage);m.activate('property','own-p1');m.buyDemoCredits(1);
 const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.credits=1;storage.setItem(STORAGE_KEY,JSON.stringify(raw));const reloaded=createModel(storage);
 const before=reloaded.getState();assert.throws(()=>reloaded.decide(reloaded.feed()[0],true),/elegendő/);assert.deepEqual(reloaded.getState(),before);
});
test('judgements persist across reloads, returned objects cannot mutate state',()=>{
 const storage=store();const m=createModel(storage);const first=m.feed()[0];m.decide(first,false);
 const again=createModel(storage);assert.equal(again.feed().some(p=>p.id===first.id),false);
 const state=again.getState();state.credits=999;state.searches[0].title='Tampered';assert.notEqual(again.getState().credits,999);assert.notEqual(again.getState().searches[0].title,'Tampered');
});
test('both profile types can be created, validated, activated, and archived without losing matches',()=>{
 const m=setup();assert.throws(()=>m.saveEntity('search',{title:'Bad',minPrice:80,maxPrice:50}),/minimum/);
 const q=m.saveEntity('search',{title:'Új keresésem',districts:['XI.'],minPrice:55,maxPrice:80,minArea:50,maxArea:70,minRooms:2,maxRooms:3});m.activate('search',q.id);assert.ok(m.feed().length);
 m.deleteEntity('search',q.id);assert.notEqual(m.getState().active.id,q.id);assert.equal(m.matches().length,3);
 assert.throws(()=>m.activate('search',q.id),/aktiválható/);
 assert.throws(()=>m.activate('property','p1'),/aktiválható/);
});
test('messages require a reciprocal match and accept literal text safely',()=>{
 const m=setup();assert.throws(()=>m.sendMessage('fake','hello'),/kölcsönös/);assert.throws(()=>m.sendMessage('m1','  '),/1–4000/);
 m.sendMessage('m1','<script>alert(1)</script>');assert.equal(m.matches().find(m=>m.id==='m1').messages.at(-1).text,'<script>alert(1)</script>');
});
test('compatibility handles required balcony/elevator and exact district/type/size/budget',()=>{
 const p={ownerId:'a',city:'Budapest',district:'XI.',type:'Lakás',price:60,area:60,rooms:2,balcony:false,elevator:true};
 const s={ownerId:'b',city:'Budapest',districts:['XI.'],type:'Lakás',minPrice:55,maxPrice:70,minArea:50,maxArea:75,minRooms:2,maxRooms:3};
 assert.ok(isCompatible(p,s));assert.equal(isCompatible(p,{...s,balcony:true}),false);assert.equal(isCompatible(p,{...s,districts:['XIII.']}),false);assert.equal(isCompatible(p,{...s,minRooms:3}),false);assert.equal(isCompatible(p,{...s,maxPrice:59}),false);assert.equal(isCompatible(p,{...s,type:'Ház'}),false);
});
test('storage failure does not commit mutation',()=>{const m=createModel({getItem:()=>null,setItem:()=>{throw new Error('quota')}});assert.throws(()=>m.buyDemoCredits(20),/tárhely/);assert.equal(m.getState().credits,24)});
