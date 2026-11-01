/** Offline integration smoke tests with a minimal simulated DOM. These do not replace browser QA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {createModel} from '../dist/model.js';

const source=await fs.readFile(new URL('../dist/app.js',import.meta.url),'utf8');
class Element {
 constructor(id,doc){this.id=id;this.doc=doc;this.innerHTML='';this.textContent='';this.className='';this.style={};this.handlers={};this.scrollHeight=500;this.scrollTop=0;this.classList={toggle:()=>{},remove:()=>{}};}
 addEventListener(type,handler){this.handlers[type]=handler;}
 focus(){this.doc.activeElement=this;}
}
class Document {
 constructor(){this.elements=new Map();this.handlers={};for(const id of ['app','modal-root','toast'])this.elements.set(id,new Element(id,this));}
 get html(){return [...this.elements.entries()].filter(([id])=>['app','modal-root'].includes(id)).map(([,e])=>e.innerHTML).join('');}
 getElementById(id){if(this.elements.has(id)&&['app','modal-root','toast'].includes(id))return this.elements.get(id);if(!new RegExp(`id=["']${id}["']`).test(this.html))return null;if(!this.elements.has(id))this.elements.set(id,new Element(id,this));return this.elements.get(id);}
 querySelector(selector){if(selector==='.modal')return this.elements.get('modal-root').innerHTML.includes('class="modal ')?this.elements.get('modal-root'):null;if(selector.startsWith('#'))return this.getElementById(selector.slice(1).split(' ')[0]);return null;}
 addEventListener(type,handler){this.handlers[type]=handler;}
}
async function setup(){const storage={getItem:()=>null,setItem:()=>{}},model=createModel(storage),document=new Document();const ctx=vm.createContext({document,console,Intl,Date,Promise,URLSearchParams,setTimeout:()=>0,clearTimeout:()=>{},location:{hash:'',search:''},window:{scrollTo:()=>{}},getModel:()=>model,disconnectApi:()=>model,connectApi:async()=>model,FormData:class {constructor(form){this.values=Object.entries(form.values||{});}get(k){return this.values.find(([key])=>key===k)?.[1]}has(k){return this.values.some(([key])=>key===k)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}});
 const body=source.replace(/^import[^\n]+\n/,'');
 await vm.runInContext(`(async()=>{${body}\nglobalThis.ui={render,changePage,openEditor,openDetails,openModal,closeModal,openActivation,getModelState:()=>state};})()`,ctx);
 const click=async(dataset)=>{const target={dataset,closest:()=>target};await document.handlers.click({target,preventDefault(){}})};
 return{model,document,ctx,click,ui:ctx.ui};}
const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};

test('initial app renders recommendation without private contacts',async()=>{const t=await setup(),html=t.document.getElementById('app').innerHTML;assert.match(html,/Találj rá az igazira/);assert.match(html,/A következő fejezeted/);assert.match(html,/72,9/);assert.equal(html.includes('peter@example.hu'),false);assert.equal(html.includes('+36 30 555 0141'),false);});
test('buyer like opens mutual-match dialog; seller activation and recommendation debit exactly two credits',async()=>{const t=await setup();await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);assert.equal(t.model.getState().credits,24);await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/Ajánlom · 2 kredit/);await t.click({action:'like'});assert.equal(t.model.getState().credits,22);assert.equal(t.model.getState().ledger.filter(x=>x.type==='seller_like').length,1);});
test('passing removes a candidate persistently from current feed',async()=>{const t=await setup(),id=t.model.feed()[0].id;await t.click({action:'pass'});assert.equal(t.model.feed().some(x=>x.id===id),false);assert.equal(t.model.getState().credits,24);});
test('every navigation page renders, settings inputs have unique IDs',async()=>{const t=await setup();for(const page of ['matches','messages','properties','searches','credits','settings']){await t.click({page});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Nem érhető el a munkatér/);}const html=t.document.getElementById('app').innerHTML;const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length,'all IDs within settings must be unique');assert.match(html,/for="api-email"/);});
test('new search form creates a saved entity and profile form persists changes',async()=>{const t=await setup();await t.click({page:'searches'});await t.click({action:'new',kind:'search'});let form=t.document.getElementById('entity-form');form.values={title:'Kertvárosi terveink',city:'Budapest',type:'Lakás',districts:'XI.',minPrice:'30',maxPrice:'65',minArea:'40',maxArea:'75',minRooms:'2',maxRooms:'4',description:'Zöld környezetben keresünk.',moveIn:'Rugalmas'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Kertvárosi terveink'),true);await t.click({page:'settings'});form=t.document.getElementById('profile-form');form.values={name:'Teszt Anna',email:'anna@test.hu',phone:'+36 30 123 4567'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().user.name,'Teszt Anna');});
test('matched conversation accepts a message through the chat form',async()=>{const t=await setup();await t.click({action:'open-chat',id:'m1'});const form=t.document.getElementById('chat-form');form.values={message:'Vasárnap délután megfelel a megtekintés?'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.matches().find(m=>m.id==='m1').messages.at(-1).text,'Vasárnap délután megfelel a megtekintés?');assert.match(t.document.getElementById('app').innerHTML,/Vasárnap délután megfelel/);});
test('card resets drag transform when a horizontal gesture becomes vertical',async()=>{const t=await setup(),card=t.document.getElementById('candidate');const target={closest:s=>s==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:1});t.document.handlers.pointermove({clientX:40,clientY:0,pointerId:1});assert.notEqual(card.style.transform,'');t.document.handlers.pointermove({clientX:40,clientY:100,pointerId:1});assert.equal(card.style.transform,'');assert.equal(card.style.opacity,'');});
