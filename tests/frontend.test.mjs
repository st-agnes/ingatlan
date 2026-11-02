/** Offline integration smoke tests with a minimal simulated DOM. These do not replace browser QA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {createModel} from '../dist/model.js';
import {searchLocations,getLocation,resolveLegacyLocations} from '../dist/locations.js';

const source=await fs.readFile(new URL('../dist/app.js',import.meta.url),'utf8');
class Element {
 constructor(id,doc,markup=''){this.id=id;this.doc=doc;this._innerHTML='';this.textContent='';this.className=markup.match(/class="([^"]*)"/)?.[1]||'';this.value=markup.match(/\bvalue="([^"]*)"/)?.[1]||'';this.disabled=/\sdisabled(?:\s|>)/.test(markup);this.hidden=/\shidden(?:\s|>)/.test(markup);this.style={};this.handlers={};this.attributes={};this.scrollHeight=500;this.scrollTop=0;this.validationMessage='';this.classList={toggle:(name,on)=>{const classes=new Set(this.className.split(' ').filter(Boolean));if(on??!classes.has(name))classes.add(name);else classes.delete(name);this.className=[...classes].join(' ');},remove:name=>this.classList.toggle(name,false)};}
 set innerHTML(value){this._innerHTML=value;if(['app','modal-root'].includes(this.id)){for(const id of this.doc.elements.keys())if(!['app','modal-root','toast'].includes(id))this.doc.elements.delete(id);}}
 get innerHTML(){return this._innerHTML;}
 addEventListener(type,handler){this.handlers[type]=handler;}
 setAttribute(name,value){this.attributes[name]=String(value);}
 getAttribute(name){return this.attributes[name]??null;}
 removeAttribute(name){delete this.attributes[name];}
 setCustomValidity(message){this.validationMessage=message;}
 focus(){this.doc.activeElement=this;}
 get parentElement(){return this.doc.parentOf(this.id);}
 contains(node){for(let current=node;current;current=current.parentElement){if(current===this)return true;}return false;}
}
class Document {
 constructor(){this.elements=new Map();this.handlers={};this.listeners=new Map();for(const id of ['app','modal-root','toast'])this.elements.set(id,new Element(id,this));}
 get html(){return [...this.elements.entries()].filter(([id])=>['app','modal-root'].includes(id)).map(([,e])=>e.innerHTML).join('');}
 getElementById(id){if(this.elements.has(id))return this.elements.get(id);const markup=this.html.match(new RegExp(`<[^>]*\\bid=["']${id}["'][^>]*>`))?.[0];if(!markup)return null;const element=new Element(id,this,markup);this.elements.set(id,element);return element;}
 querySelector(selector){if(selector==='.modal')return this.elements.get('modal-root').innerHTML.includes('class="modal ')?this.elements.get('modal-root'):null;if(selector.startsWith('#'))return this.getElementById(selector.slice(1).split(' ')[0]);return null;}
 parentOf(id){const stack=[],voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);for(const token of this.html.matchAll(/<\/?([a-z][\w-]*)\b[^>]*>/gi)){const tag=token[1].toLowerCase(),markup=token[0];if(markup.startsWith('</')){const index=stack.findLastIndex(item=>item.tag===tag);if(index>=0)stack.length=index;continue;}const currentId=markup.match(/\bid=["']([^"']+)["']/)?.[1];if(currentId===id){const parent=stack.findLast(item=>item.id);return parent?this.getElementById(parent.id):null;}if(!voidTags.has(tag)&&!markup.endsWith('/>'))stack.push({tag,id:currentId});}return null;}
 addEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture,list=this.listeners.get(type)||[];if(!list.some(item=>item.handler===handler&&item.capture===capture))list.push({handler,capture});this.listeners.set(type,list);this.handlers[type]=event=>{const pending=[...(this.listeners.get(type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture)).map(item=>item.handler(event)).filter(value=>value?.then);return pending.length?Promise.all(pending):undefined;};}
 removeEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture;this.listeners.set(type,(this.listeners.get(type)||[]).filter(item=>item.handler!==handler||item.capture!==capture));}
 listenerCount(type){return(this.listeners.get(type)||[]).length;}
}
async function setup(){const storage={getItem:()=>null,setItem:()=>{}},model=createModel(storage),document=new Document();const ctx=vm.createContext({document,console,Intl,Date,Promise,URLSearchParams,setTimeout:()=>0,clearTimeout:()=>{},location:{hash:'',search:''},window:{scrollTo:()=>{}},searchLocations,getLocation,resolveLegacyLocations,getModel:()=>model,disconnectApi:()=>model,connectApi:async()=>model,FormData:class {constructor(form){this.values=Object.entries(form.values||{});}get(k){return this.values.find(([key])=>key===k)?.[1]}has(k){return this.values.some(([key])=>key===k)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}});
 const body=source.replace(/^import[^\n]+\n/gm,'');
 await vm.runInContext(`(async()=>{${body}\nglobalThis.ui={render,changePage,openEditor,openDetails,openModal,closeModal,openActivation,getModelState:()=>state};})()`,ctx);
 const click=async(dataset)=>{const target={dataset,closest:()=>target};await document.handlers.click({target,preventDefault(){}})};
 return{model,document,ctx,click,ui:ctx.ui};}
const settle=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};

function chooseLocation(t,id){const input=t.document.getElementById('location-input');input.value=getLocation(id).label;input.handlers.input();const list=t.document.getElementById('location-options');assert.match(list.innerHTML,new RegExp(id.replaceAll('.','\\.')));const target={dataset:{locationId:id},closest:()=>target};list.handlers.click({target});}
function submitEntity(t,values){const form=t.document.getElementById('entity-form');form.values=values;form.handlers.submit({preventDefault(){},currentTarget:form});}
function key(input,key){const event={key,preventDefault(){this.defaultPrevented=true;},stopPropagation(){}};input.handlers.keydown(event);return event;}
const searchValues=title=>({title,type:'Lakás',minPrice:'',maxPrice:'90',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});
async function createSearch(t,title='Új keresési igény'){t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');submitEntity(t,searchValues(title));await settle();return t.model.getState().searches.find(item=>item.title===title);}
test('initial app renders recommendation without private contacts',async()=>{const t=await setup(),html=t.document.getElementById('app').innerHTML;assert.match(html,/Találj rá az igazira/);assert.match(html,/A következő fejezeted/);assert.match(html,/72,9/);assert.equal(html.includes('peter@example.hu'),false);assert.equal(html.includes('+36 30 555 0141'),false);});
test('buyer like opens mutual-match dialog; seller activation and recommendation debit exactly two credits',async()=>{const t=await setup();await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);assert.equal(t.model.getState().credits,24);await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/Ajánlom · 2 kredit/);await t.click({action:'like'});assert.equal(t.model.getState().credits,22);assert.equal(t.model.getState().ledger.filter(x=>x.type==='seller_like').length,1);});
test('passing removes a candidate persistently from current feed',async()=>{const t=await setup(),id=t.model.feed()[0].id;await t.click({action:'pass'});assert.equal(t.model.feed().some(x=>x.id===id),false);assert.equal(t.model.getState().credits,24);});
test('every navigation page renders, settings inputs have unique IDs',async()=>{const t=await setup();for(const page of ['matches','messages','properties','searches','credits','settings']){await t.click({page});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Nem érhető el a munkatér/);}const html=t.document.getElementById('app').innerHTML;const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length,'all IDs within settings must be unique');assert.match(html,/for="api-email"/);});
test('new search form creates a saved entity and profile form persists changes',async()=>{const t=await setup();await t.click({page:'searches'});await t.click({action:'new',kind:'search'});let form=t.document.getElementById('entity-form');chooseLocation(t,'district:Budapest:11');form.values={title:'Kertvárosi terveink',type:'Lakás',minPrice:'30',maxPrice:'65',minArea:'40',maxArea:'75',minRooms:'2',maxRooms:'4',description:'Zöld környezetben keresünk.',moveIn:'Rugalmas'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Kertvárosi terveink'),true);await t.click({page:'settings'});form=t.document.getElementById('profile-form');form.values={name:'Teszt Anna',email:'anna@test.hu',phone:'+36 30 123 4567'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().user.name,'Teszt Anna');});
test('matched conversation accepts a message through the chat form',async()=>{const t=await setup();await t.click({action:'open-chat',id:'m1'});const form=t.document.getElementById('chat-form');form.values={message:'Vasárnap délután megfelel a megtekintés?'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.matches().find(m=>m.id==='m1').messages.at(-1).text,'Vasárnap délután megfelel a megtekintés?');assert.match(t.document.getElementById('app').innerHTML,/Vasárnap délután megfelel/);});
test('card resets drag transform when a horizontal gesture becomes vertical',async()=>{const t=await setup(),card=t.document.getElementById('candidate');const target={closest:s=>s==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:1});t.document.handlers.pointermove({clientX:40,clientY:0,pointerId:1});assert.notEqual(card.style.transform,'');t.document.handlers.pointermove({clientX:40,clientY:100,pointerId:1});assert.equal(card.style.transform,'');assert.equal(card.style.opacity,'');});


test('location picker selects multiple canonical towns, removes chips and accepts keyboard district selection',async()=>{const t=await setup();t.ui.openEditor('search');for(const name of ['Debrecen','Hajdúszoboszló','Hajdúsámson'])chooseLocation(t,`city:${name}`);let chips=t.document.getElementById('location-chips');assert.match(chips.innerHTML,/Hajdúszoboszló/);const target={dataset:{removeLocation:'city:Debrecen'},closest:()=>target};chips.handlers.click({target});assert.doesNotMatch(chips.innerHTML,/Debrecen/);const input=t.document.getElementById('location-input');input.value='Budapest V. kerület';input.handlers.input();key(input,'ArrowDown');assert.equal(input.getAttribute('aria-activedescendant'),'location-option-0');key(input,'Enter');assert.match(chips.innerHTML,/Budapest V\. kerület/);assert.equal(input.value,'');assert.equal(input.getAttribute('aria-expanded'),'false');submitEntity(t,{title:'Több helyen keresünk',type:'Lakás',minPrice:'',maxPrice:'100',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});await settle();const saved=t.model.getState().searches.find(x=>x.title==='Több helyen keresünk');assert.ok(saved);assert.deepEqual([...saved.locationIds],['city:Hajdúszoboszló','city:Hajdúsámson','district:Budapest:5']);for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(saved[name],null);await t.click({page:'searches'});const html=t.document.getElementById('app').innerHTML;assert.match(html,/legalább 40 m²/);assert.match(html,/legfeljebb 100 M Ft/);assert.doesNotMatch(html,/NaN/);});
test('unselected typed location cannot save and Escape closes only autocomplete options',async()=>{const t=await setup();t.ui.openEditor('search');const input=t.document.getElementById('location-input');input.value='Debrceeen';input.handlers.input();assert.equal(key(input,'Escape').defaultPrevented,true);assert.equal(t.document.getElementById('location-options').hidden,true);assert.match(t.document.getElementById('modal-root').innerHTML,/entity-form/);submitEntity(t,{title:'Elírt hely',type:'Lakás',maxPrice:'100',minArea:'40',minRooms:'2'});await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Elírt hely'),false);assert.match(input.validationMessage,/Válassz/);chooseLocation(t,'city:Debrecen');assert.equal(input.validationMessage,'');});
test('property uses a single canonical location and house lot size toggles without replacing other fields',async()=>{const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Solymár');chooseLocation(t,'city:Pilisvörösvár');const chips=t.document.getElementById('location-chips');assert.doesNotMatch(chips.innerHTML,/Solymár/);assert.match(chips.innerHTML,/Pilisvörösvár/);const title=t.document.getElementById('f-title');title.value='Családi ház';const type=t.document.getElementById('f-type'),lot=t.document.getElementById('f-lotArea'),wrapper=t.document.getElementById('lot-area-field');type.value='Ház';type.handlers.change({currentTarget:type});assert.equal(lot.disabled,false);assert.doesNotMatch(wrapper.className,/hidden/);assert.equal(title.value,'Családi ház');submitEntity(t,{title:'Családi ház',type:'Ház',price:'95',area:'120',rooms:'4',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();const saved=t.model.getState().properties.find(x=>x.title==='Családi ház');assert.ok(saved);assert.equal(saved.locationId,'city:Pilisvörösvár');assert.equal(saved.lotArea,650);await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/650 m² telek/);t.ui.openEditor('property',saved.id);const type2=t.document.getElementById('f-type');type2.value='Lakás';type2.handlers.change({currentTarget:type2});assert.equal(t.document.getElementById('f-lotArea').disabled,true);submitEntity(t,{title:'Családi ház',type:'Lakás',price:'95',area:'120',rooms:'4',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();assert.equal(t.model.getState().properties.find(x=>x.id===saved.id).lotArea,null);});

test('creating a search confirms the saved title and offers discovery without changing the active profile',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t,'Kert <és> fény & nyugalom');
 assert.ok(saved);
 assert.deepEqual(t.model.getState().active,before);
 const dialog=t.document.getElementById('modal-root').innerHTML;
 assert.match(dialog,/Kert &lt;és&gt; fény &amp; nyugalom/);
 assert.doesNotMatch(dialog,/Kert <és>/);
 assert.match(dialog,/Ingatlanok felfedezése/);
 assert.match(dialog,/data-action="discover-search"/);
 assert.ok(dialog.includes(`data-id="${saved.id}"`));
 assert.match(dialog,/Később/);
});

test('dismissing a saved search confirmation keeps the search and the previous active profile',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t);
 await t.click({action:'close'});
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.ok(t.model.getState().searches.some(item=>item.id===saved.id));
 assert.deepEqual(t.model.getState().active,before);
});

test('discovering a newly saved search waits for activation then opens its recommended properties',async()=>{
 const t=await setup();
 await t.click({action:'tab',tab:'liked'});
 await t.click({page:'searches'});
 const saved=await createSearch(t),before=t.model.getState().active;
 let release;
 const activation=new Promise(resolve=>{release=resolve;});
 const calls=[],activate=t.model.activate;
 t.model.activate=async(kind,id)=>{calls.push({kind,id});await activation;return activate(kind,id);};
 const clicked=t.click({action:'discover-search',id:saved.id});
 await settle();
 assert.deepEqual(calls,[{kind:'search',id:saved.id}]);
 assert.deepEqual(t.model.getState().active,before);
 assert.equal(t.ctx.location.hash,'searches','navigation must wait for the API activation');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
 release();
 await clicked;
 assert.deepEqual(t.model.getState().active,{kind:'search',id:saved.id});
 assert.equal(t.ctx.location.hash,'discover');
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Neked ajánljuk/);
 assert.match(html,/Új keresési igény/);
 assert.match(html,/class="tab active" data-action="tab" data-tab="recommended"/);
 assert.match(html,/class="property-card"/);
 assert.ok(html.includes(t.model.feed()[0].title));
});

test('a failed activation leaves the saved-search discovery action available to retry',async()=>{
 const t=await setup(),before=t.model.getState().active;
 const saved=await createSearch(t);
 t.model.activate=async()=>{throw new Error('Az aktiválás nem sikerült.');};
 await t.click({action:'discover-search',id:saved.id});
 assert.deepEqual(t.model.getState().active,before);
 const dialog=t.document.getElementById('modal-root').innerHTML;
 assert.match(dialog,/Ingatlanok felfedezése/);
 assert.ok(dialog.includes(`data-id="${saved.id}"`));
 assert.match(t.document.getElementById('toast').textContent,/Az aktiválás nem sikerült/);
});

test('editing an existing search confirms the update without offering a new-search discovery dialog',async()=>{
 const t=await setup(),before=t.model.getState();
 t.ui.openEditor('search','own-s1');
 submitEntity(t,searchValues('Átgondolt keresési igény'));
 await settle();
 assert.equal(t.model.getState().searches.length,before.searches.length);
 assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').title,'Átgondolt keresési igény');
 assert.deepEqual(t.model.getState().active,before.active);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.match(t.document.getElementById('toast').textContent,/módosításokat elmentettük/);
});

test('a failed new search save keeps its editor data and reports the failure',async()=>{
 const t=await setup(),count=t.model.getState().searches.length;
 t.ui.openEditor('search');
 chooseLocation(t,'city:Debrecen');
 const form=t.document.getElementById('entity-form');
 t.model.saveEntity=async()=>{throw new Error('A mentés most nem érhető el.');};
 submitEntity(t,searchValues('Ezt még nem mentettük el'));
 await settle();
 assert.equal(t.model.getState().searches.length,count);
 assert.equal(t.document.getElementById('entity-form'),form);
 assert.equal(form.values.title,'Ezt még nem mentettük el');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/data-action="discover-search"/);
 assert.match(t.document.getElementById('toast').textContent,/A mentés most nem érhető el/);
 assert.match(t.document.getElementById('toast').className,/error/);
});

test('clicking outside location suggestions dismisses them without changing the typed query or selected towns',async()=>{
 const t=await setup();
 t.ui.openEditor('search');
 chooseLocation(t,'city:Debrecen');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Pilis';input.handlers.input();
 assert.equal(list.hidden,false);
 assert.equal(input.value,'Pilis');
 t.document.handlers.pointerdown({target:input,clientX:0,clientY:0,pointerId:1});
 assert.equal(list.hidden,false,'pressing the input must not dismiss its own suggestions');
 t.document.handlers.pointerdown({target:t.document.getElementById('f-title'),clientX:0,clientY:0,pointerId:1});
 assert.equal(list.hidden,true);
 assert.equal(input.getAttribute('aria-expanded'),'false');
 assert.equal(input.value,'Pilis');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 input.handlers.focus();
 assert.equal(list.hidden,false);
 chooseLocation(t,'city:Pilisvörösvár');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Pilisvörösvár/);
});

test('moving focus outside a property picker dismisses suggestions and preserves unselected text',async()=>{
 const t=await setup();
 t.ui.openEditor('property');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Solym';input.handlers.input();
 assert.equal(list.hidden,false);
 t.document.handlers.focusin({target:t.document.getElementById('f-title')});
 assert.equal(list.hidden,true);
 assert.equal(input.value,'Solym');
 assert.equal(t.document.getElementById('location-chips').innerHTML,'');
 input.handlers.focus();
 assert.equal(list.hidden,false);
 chooseLocation(t,'city:Solymár');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Solymár/);
});

test('closing or replacing the editor removes its outside-picker document listeners',async()=>{
 const t=await setup(),pointerListeners=t.document.listenerCount('pointerdown'),focusListeners=t.document.listenerCount('focusin');
 t.ui.openEditor('search');
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners+1);
 assert.equal(t.document.listenerCount('focusin'),focusListeners+1);
 t.ui.openEditor('property');
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners+1);
 assert.equal(t.document.listenerCount('focusin'),focusListeners+1);
 t.ui.closeModal();
 assert.equal(t.document.listenerCount('pointerdown'),pointerListeners);
 assert.equal(t.document.listenerCount('focusin'),focusListeners);
});
