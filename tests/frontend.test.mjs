/** Offline integration smoke tests with a minimal simulated DOM. These do not replace browser QA. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import {createModel} from '../dist/model.js';
import {searchLocations,getLocation,resolveLegacyLocations} from '../dist/locations.js';
import * as propertyAttributes from '../dist/attributes.js';
import * as accountHelpers from '../dist/accounts.js';
import * as feedbackHelpers from '../dist/feedback.js';


const landingRegions=[{id:'HU110',label:'Budapest'},{id:'HU321',label:'Hajdú-Bihar'},{id:'HU232',label:'Somogy'}];
function landingFixture(region){const selected=landingRegions.find(item=>item.id===region)||null;return {regions:landingRegions,region:selected,scope:selected?'region':'national',searches:region==='HU232'?[]:[{key:'s-public',title:'Kertes otthont keresünk',ownerFirstName:'Anna',type:'Lakás',locations:[region==='HU321'?'Debrecen':'Budapest XIII. kerület'],minPrice:null,maxPrice:90,minArea:50,maxArea:null,minRooms:2,maxRooms:null,ownerAccountType:'private'}],properties:region==='HU232'?[]:[{key:'p-public',title:'Napfényes erkélyes otthon',ownerFirstName:'Péter',type:'Lakás',location:region==='HU321'?'Debrecen':'Budapest',price:82,area:60,wholeRooms:2,halfRooms:1,rooms:2.5,lotArea:null,ownerAccountType:'agent'}]};}

const source=await fs.readFile(new URL('../dist/app.js',import.meta.url),'utf8');
class Element {
 constructor(id,doc,markup='') {
  this.id=id;this.doc=doc;this.markup=markup;this._innerHTML='';this.textContent='';
  this.tagName=(markup.match(/^<([a-z][\w-]*)/i)?.[1]||'div').toUpperCase();
  this.attributes=Object.fromEntries([...markup.split('>')[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(match=>[match[1],match[2]]));
  this.dataset=new Proxy(Object.fromEntries(Object.entries(this.attributes).filter(([name])=>name.startsWith('data-')).map(([name,value])=>[name.slice(5).replace(/-([a-z])/g,(_match,letter)=>letter.toUpperCase()),value])),{set:(target,key,value)=>{target[key]=String(value);this.attributes['data-'+String(key).replace(/[A-Z]/g,letter=>'-'+letter.toLowerCase())]=String(value);return true;}});
  this.className=this.attributes.class||'';this.value=this.attributes.value||'';this.name=this.attributes.name||'';this.step=this.attributes.step||'';this.type=this.attributes.type||'';
  this.required=/\srequired(?:\s|>)/.test(markup);this.validity={badInput:false};
  if(markup.startsWith('<select')) {const option=[...markup.matchAll(/<option\b([^>]*)>([^<]*)/g)],selected=option.find(match=>/\bselected\b/.test(match[1]))||option[0];this.value=selected?.[1].match(/\bvalue="([^"]*)"/)?.[1]??selected?.[2]??'';}
  if(markup.startsWith('<textarea'))this.value=markup.match(/^[^>]*>([\s\S]*?)<\/textarea>/)?.[1]||'';
  this.checked=/\schecked(?:\s|>)/.test(markup);this.disabled=/\sdisabled(?:\s|>)/.test(markup);this.hidden=/\shidden(?:\s|>)/.test(markup);
  this.style={};this.handlers={};this.scrollHeight=500;this.scrollTop=0;this.validationMessage='';this.reportedValidity=0;
  this.classList={toggle:(name,on)=>{const classes=new Set(this.className.split(' ').filter(Boolean));if(on??!classes.has(name))classes.add(name);else classes.delete(name);this.className=[...classes].join(' ');},remove:name=>this.classList.toggle(name,false),add:name=>this.classList.toggle(name,true),contains:name=>this.className.split(' ').includes(name)};
 }
 set innerHTML(value){this._innerHTML=value;if(['app','modal-root'].includes(this.id)){for(const id of this.doc.elements.keys())if(!['app','modal-root','toast'].includes(id))this.doc.elements.delete(id);}}
 get innerHTML(){return this._innerHTML;}
 addEventListener(type,handler){const prior=this.handlers[type];this.handlers[type]=prior?event=>{prior(event);return handler(event);}:handler;}
 querySelectorAll(selector){assert.equal(selector,'input[type="number"]');return [...this.doc.html.matchAll(/<input\b[^>]*\btype="number"[^>]*>/g)].map(match=>this.doc.getElementById(match[0].match(/\bid="([^"]*)"/)[1])).filter(input=>this.contains(input));}
 setAttribute(name,value){this.attributes[name]=String(value);if(name==='hidden')this.hidden=true;}
 getAttribute(name){return this.attributes[name]??null;}
 removeAttribute(name){delete this.attributes[name];if(name==='hidden')this.hidden=false;}
 setCustomValidity(message){this.validationMessage=message;}
 checkValidity(){
  if(this.disabled)return true;
  if(this.validationMessage||this.validity.badInput)return false;
  const value=String(this.value??'');
  if(this.required&&((this.type==='checkbox'||this.type==='radio')?!this.checked:!value))return false;
  if(!value)return true;
  if(this.type==='number'){
   const number=Number(value);if(!Number.isFinite(number))return false;
   const min=this.getAttribute('min'),max=this.getAttribute('max');if(min!==null&&number<Number(min)||max!==null&&number>Number(max))return false;
   const step=this.step&&this.step!=='any'?Number(this.step):1,base=min===null?0:Number(min);
   if(Number.isFinite(step)&&step>0&&Math.abs((number-base)/step-Math.round((number-base)/step))>1e-7)return false;
  }
  const minlength=this.getAttribute('minlength'),maxlength=this.getAttribute('maxlength');
  return !(minlength!==null&&value.length<Number(minlength)||maxlength!==null&&value.length>Number(maxlength));
 }
 reportValidity(){this.reportedValidity++;return this.checkValidity();}
 focus(){this.doc.activeElement=this;}
 scrollIntoView(){}
 get parentElement(){return this.doc.parentOf(this.id);}
 contains(node){for(let current=node;current;current=current.parentElement){if(current===this)return true;}return false;}
}

class Document {
 constructor(){this.elements=new Map();this.handlers={};this.listeners=new Map();for(const id of ['app','modal-root','toast'])this.elements.set(id,new Element(id,this));}
 get html(){return [...this.elements.entries()].filter(([id])=>['app','modal-root'].includes(id)).map(([,e])=>e.innerHTML).join('');}
 getElementById(id){if(this.elements.has(id))return this.elements.get(id);const markup=this.html.match(new RegExp(`<[^>]*\\bid=["']${id}["'][^>]*>`))?.[0];if(!markup)return null;const full=markup.startsWith('<select')||markup.startsWith('<textarea')?this.html.match(new RegExp(`<${markup.startsWith('<select')?'select':'textarea'}[^>]*\\bid=["']${id}["'][^>]*>[\\s\\S]*?</${markup.startsWith('<select')?'select':'textarea'}>`))?.[0]||markup:markup;const element=new Element(id,this,full);this.elements.set(id,element);return element;}
 querySelector(selector){if(selector==='.modal')return this.elements.get('modal-root').innerHTML.includes('class="modal ')?this.elements.get('modal-root'):null;if(selector.startsWith('#'))return this.getElementById(selector.slice(1).split(' ')[0]);return null;}
 parentOf(id){const stack=[],voidTags=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);for(const token of this.html.matchAll(/<\/?([a-z][\w-]*)\b[^>]*>/gi)){const tag=token[1].toLowerCase(),markup=token[0];if(markup.startsWith('</')){const index=stack.findLastIndex(item=>item.tag===tag);if(index>=0)stack.length=index;continue;}const currentId=markup.match(/\bid=["']([^"']+)["']/)?.[1];if(currentId===id){const parent=stack.findLast(item=>item.id);return parent?this.getElementById(parent.id):null;}if(!voidTags.has(tag)&&!markup.endsWith('/>'))stack.push({tag,id:currentId});}return null;}
 addEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture,list=this.listeners.get(type)||[];if(!list.some(item=>item.handler===handler&&item.capture===capture))list.push({handler,capture});this.listeners.set(type,list);this.handlers[type]=event=>{const pending=[...(this.listeners.get(type)||[])].sort((a,b)=>Number(b.capture)-Number(a.capture)).map(item=>item.handler(event)).filter(value=>value?.then);return pending.length?Promise.all(pending):undefined;};}
 removeEventListener(type,handler,options){const capture=typeof options==='boolean'?options:!!options?.capture;this.listeners.set(type,(this.listeners.get(type)||[]).filter(item=>item.handler!==handler||item.capture!==capture));}
 listenerCount(type){return(this.listeners.get(type)||[]).length;}
}
async function setup(options={}){
 const storage={getItem:()=>options.initialRaw?JSON.stringify(options.initialRaw):null,setItem:()=>{}},demoModel=createModel(storage),document=new Document();
 const apiModel=Object.assign({...demoModel},{mode:'api'},options.apiOverrides||{});
 if(options.apiOverrides?.feed&&!options.apiOverrides?.recommendations)apiModel.recommendations=async request=>{const items=await apiModel.feed(request);return {items,stage:items.length?'exact':'empty'};};
 let selected=options.hosted?(options.authenticated?apiModel:null):demoModel;
 const connected=[],disconnected=[],landingCalls=[],windowEvents={},regionStorage=new Map(Object.entries(options.regionStorage||{}));
 let currentHash=options.hash??(options.hosted&&!options.authenticated?'#login':'');
 const ctx=vm.createContext({
  document,console,Intl,Date,Promise,URLSearchParams,IntersectionObserver:options.IntersectionObserver,setTimeout:()=>0,clearTimeout:()=>{},
  location:{get hash(){return currentHash;},set hash(value){currentHash=value?(value.startsWith('#')?value:'#'+value):'';},search:'',origin:'https://test.example'},window:{scrollTo:()=>{},addEventListener:(type,handler)=>{windowEvents[type]=handler;}},
  OTTHONRA_CONFIG:options.hosted?{mode:'api',environment:options.environment||'test'}:{mode:'demo',environment:'local'},
  searchLocations,getLocation,resolveLegacyLocations,...propertyAttributes,...accountHelpers,...feedbackHelpers,
  hostedMode:()=>!!options.hosted,deploymentEnvironment:()=>options.hosted?(options.environment||'test'):'local',
  getModel:()=>selected,
  fetchLanding:async(input={})=>{landingCalls.push(input);if(options.fetchLanding)return options.fetchLanding(input);return landingFixture(input.region);},
  detectLandingRegion:options.detectLandingRegion||(async()=>null),
  localStorage:{getItem:key=>regionStorage.get(key)||null,setItem:(key,value)=>regionStorage.set(key,value),removeItem:key=>regionStorage.delete(key)},
  disconnectApi:()=>{disconnected.push(true);selected=options.hosted?null:demoModel;return selected;},
  connectApi:async(...args)=>{connected.push(args);if(options.connectApi)await options.connectApi(...args);selected=apiModel;return apiModel;},
  FormData:class {constructor(form){this.values=form.values===undefined?mountedFormValues(document,form):Array.isArray(form.values)?form.values:Object.entries(form.values||{});}get(k){return this.values.find(([key])=>key===k)?.[1]}has(k){return this.values.some(([key])=>key===k)}[Symbol.iterator](){return this.values[Symbol.iterator]()}}
 });
 const body=source.replace(/^import[^\n]+\n/gm,'');
 await vm.runInContext(`(async()=>{${body}\nglobalThis.ui={render,changePage,openEditor,openDetails,openModal,closeModal,openActivation,matchingTags,openFeedbackPackages,openFeedbackPurchase,openFeedbackPrompt,propertyInsightsPage,getFeedbackPrompt:()=>feedbackPrompt,getModelState:()=>state};})()`,ctx);
 const click=async(dataset)=>{const target={dataset,closest:()=>target};await document.handlers.click({target,preventDefault(){}})};
 return{model:options.hosted?apiModel:demoModel,document,ctx,click,ui:ctx.ui,connected,disconnected,getSelectedModel:()=>selected,landingCalls,regionStorage,windowEvents};
}
const settle=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};

function chooseLocation(t,id){const input=t.document.getElementById('location-input');input.value=getLocation(id).label;input.handlers.input();const list=t.document.getElementById('location-options');assert.match(list.innerHTML,new RegExp(id.replaceAll('.','\\.')));const target={dataset:{locationId:id},closest:()=>target};list.handlers.click({target});}
function mountedFormValues(document,form){
 const values=[];
 for(const match of document.html.matchAll(/<(?:input|select|textarea)\b[^>]*\bid="([^"]+)"[^>]*>/g)){
  const input=document.getElementById(match[1]);
  if(!input?.name||!form.contains(input)||input.disabled)continue;
  let disabledByGroup=false;for(let parent=input.parentElement;parent&&parent!==form;parent=parent.parentElement)if(parent.disabled)disabledByGroup=true;
  if(disabledByGroup||['checkbox','radio'].includes(input.type)&&!input.checked)continue;
  values.push([input.name,input.type==='checkbox'?(input.value||'on'):input.value]);
 }
 return values;
}
function setEditorValues(t,values){
 const entries=Array.isArray(values)?values:Object.entries(values);
 for(const [name,value] of entries){
  const control=t.document.getElementById(name==='images'?'property-images':'f-'+name);
  if(control&&control.type!=='checkbox')control.value=String(value??'');
 }
 const type=t.document.getElementById('f-type');type?.handlers.change?.({target:type,currentTarget:type});
 for(const name of ['wholeRooms','halfRooms']){const control=t.document.getElementById('f-'+name);control?.handlers.input?.({target:control,currentTarget:control,inputType:'insertText'});}
}
function editorStep(t){return Array.from({length:5},(_value,index)=>t.document.getElementById('editor-step-'+index)).findIndex(step=>step&&!step.hidden);}
function editorAction(t,id){const button=t.document.getElementById(id);assert.ok(button,`Missing editor control ${id}`);assert.equal(button.disabled,false,`${id} must be enabled`);return button.handlers.click({target:button,currentTarget:button,preventDefault(){}});}
function submitEditor(t){const form=t.document.getElementById('entity-form');return form.handlers.submit({preventDefault(){},currentTarget:form});}
function submitEntity(t,values){
 const form=t.document.getElementById('entity-form');form.values=values;setEditorValues(t,values);
 if(!t.document.getElementById('editor-step-0')){submitEditor(t);return;}
 for(let attempts=0;attempts<5;attempts++){
  const before=editorStep(t);submitEditor(t);
  if(before===4||editorStep(t)===before)return;
 }
}

function key(input,key){const event={key,preventDefault(){this.defaultPrevented=true;},stopPropagation(){}};input.handlers.keydown(event);return event;}
const searchValues=title=>({title,type:'Lakás',minPrice:'',maxPrice:'90',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});
async function createSearch(t,title='Új keresési igény'){t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');submitEntity(t,searchValues(title));await settle();return t.model.getState().searches.find(item=>item.title===title);}
test('initial app renders recommendation without private contacts',async()=>{const t=await setup(),html=t.document.getElementById('app').innerHTML;assert.match(html,/page-heading/);assert.match(html,/A következő fejezeted/);assert.match(html,/72,9/);assert.equal(html.includes('peter@example.hu'),false);assert.equal(html.includes('+36 30 555 0141'),false);});
test('buyer like opens mutual-match dialog; seller activation and recommendation debit exactly two credits',async()=>{const t=await setup();await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);assert.equal(t.model.getState().credits,24);await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/<span class="decision-like-caption"><span>Kedvelés<\/span><small>2 kredit<\/small>/);await t.click({action:'like'});assert.equal(t.model.getState().credits,22);assert.equal(t.model.getState().ledger.filter(x=>x.type==='seller_like').length,1);});
test('passing removes a candidate persistently from current feed',async()=>{const t=await setup(),id=t.model.feed()[0].id;await t.click({action:'pass'});assert.equal(t.model.feed().some(x=>x.id===id),false);assert.equal(t.model.getState().credits,24);});
test('every navigation page renders, settings inputs have unique IDs',async()=>{const t=await setup();for(const page of ['matches','messages','properties','searches','credits','settings']){await t.click({page});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Nem érhető el a munkatér/);}const html=t.document.getElementById('app').innerHTML;const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length,'all IDs within settings must be unique');assert.match(html,/for="api-email"/);});
test('new search form creates a saved entity and profile form persists changes',async()=>{const t=await setup();await t.click({page:'searches'});await t.click({action:'new',kind:'search'});let form=t.document.getElementById('entity-form');chooseLocation(t,'district:Budapest:11');form.values={title:'Kertvárosi terveink',type:'Lakás',minPrice:'30',maxPrice:'65',minArea:'40',maxArea:'75',minRooms:'2',maxRooms:'4',description:'Zöld környezetben keresünk.',moveIn:'Rugalmas'};submitEntity(t,form.values);await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Kertvárosi terveink'),true);await t.click({page:'settings'});form=t.document.getElementById('profile-form');form.values={name:'Teszt Anna',email:'anna@test.hu',phone:'+36 30 123 4567'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.getState().user.name,'Teszt Anna');});
test('matched conversation accepts a message through the chat form',async()=>{const t=await setup();await t.click({action:'open-chat',id:'m1'});const form=t.document.getElementById('chat-form');form.values={message:'Vasárnap délután megfelel a megtekintés?'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(t.model.matches().find(m=>m.id==='m1').messages.at(-1).text,'Vasárnap délután megfelel a megtekintés?');assert.match(t.document.getElementById('app').innerHTML,/Vasárnap délután megfelel/);});
test('card resets drag transform when a horizontal gesture becomes vertical',async()=>{const t=await setup(),card=t.document.getElementById('candidate');const target={closest:s=>s==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:1});t.document.handlers.pointermove({clientX:40,clientY:0,pointerId:1});assert.notEqual(card.style.transform,'');t.document.handlers.pointermove({clientX:40,clientY:100,pointerId:1});assert.equal(card.style.transform,'');assert.equal(card.style.opacity,'');});


test('location picker selects multiple canonical towns, removes chips and accepts keyboard district selection',async()=>{const t=await setup();t.ui.openEditor('search');for(const name of ['Debrecen','Hajdúszoboszló','Hajdúsámson'])chooseLocation(t,`city:${name}`);let chips=t.document.getElementById('location-chips');assert.match(chips.innerHTML,/Hajdúszoboszló/);const target={dataset:{removeLocation:'city:Debrecen'},closest:()=>target};chips.handlers.click({target});assert.doesNotMatch(chips.innerHTML,/Debrecen/);const input=t.document.getElementById('location-input');input.value='Budapest V. kerület';input.handlers.input();key(input,'ArrowDown');assert.equal(input.getAttribute('aria-activedescendant'),'location-option-0');key(input,'Enter');assert.match(chips.innerHTML,/Budapest V\. kerület/);assert.equal(input.value,'');assert.equal(input.getAttribute('aria-expanded'),'false');submitEntity(t,{title:'Több helyen keresünk',type:'Lakás',minPrice:'',maxPrice:'100',minArea:'40',maxArea:'',minRooms:'2',maxRooms:'',moveIn:'Rugalmas'});await settle();const saved=t.model.getState().searches.find(x=>x.title==='Több helyen keresünk');assert.ok(saved);assert.deepEqual([...saved.locationIds],['city:Hajdúszoboszló','city:Hajdúsámson','district:Budapest:5']);for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(saved[name],null);await t.click({page:'searches'});const html=t.document.getElementById('app').innerHTML;assert.match(html,/legalább 40 m²/);assert.match(html,/legfeljebb 100 M Ft/);assert.doesNotMatch(html,/NaN/);});
test('unselected typed location cannot save and Escape closes only autocomplete options',async()=>{const t=await setup();t.ui.openEditor('search');const input=t.document.getElementById('location-input');input.value='Debrceeen';input.handlers.input();assert.equal(key(input,'Escape').defaultPrevented,true);assert.equal(t.document.getElementById('location-options').hidden,true);assert.match(t.document.getElementById('modal-root').innerHTML,/entity-form/);submitEntity(t,{title:'Elírt hely',type:'Lakás',maxPrice:'100',minArea:'40',minRooms:'2'});await settle();assert.equal(t.model.getState().searches.some(x=>x.title==='Elírt hely'),false);assert.match(input.validationMessage,/Válassz/);chooseLocation(t,'city:Debrecen');assert.equal(input.validationMessage,'');});
test('property uses a single canonical location and house lot size toggles without replacing other fields',async()=>{const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Solymár');chooseLocation(t,'city:Pilisvörösvár');const chips=t.document.getElementById('location-chips');assert.doesNotMatch(chips.innerHTML,/Solymár/);assert.match(chips.innerHTML,/Pilisvörösvár/);const title=t.document.getElementById('f-title');title.value='Családi ház';const type=t.document.getElementById('f-type'),lot=t.document.getElementById('f-lotArea'),wrapper=t.document.getElementById('lot-area-field');type.value='Ház';type.handlers.change({currentTarget:type});assert.equal(lot.disabled,false);assert.doesNotMatch(wrapper.className,/hidden/);assert.equal(title.value,'Családi ház');submitEntity(t,{title:'Családi ház',type:'Ház',price:'95',area:'120',wholeRooms:'4',halfRooms:'0',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();const saved=t.model.getState().properties.find(x=>x.title==='Családi ház');assert.ok(saved);assert.equal(saved.locationId,'city:Pilisvörösvár');assert.equal(saved.lotArea,650);await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/650 m² telek/);t.ui.openEditor('property',saved.id);const type2=t.document.getElementById('f-type');type2.value='Lakás';type2.handlers.change({currentTarget:type2});assert.equal(t.document.getElementById('f-lotArea').disabled,true);submitEntity(t,{title:'Családi ház',type:'Lakás',price:'95',area:'120',wholeRooms:'4',halfRooms:'0',floor:'0',lotArea:'650',images:'',condition:'Jó állapotú',building:'Tégla'});await settle();assert.equal(t.model.getState().properties.find(x=>x.id===saved.id).lotArea,null);});

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
 assert.equal(t.ctx.location.hash,'#searches','navigation must wait for the API activation');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
 release();
 await clicked;
 assert.deepEqual(t.model.getState().active,{kind:'search',id:saved.id});
 assert.equal(t.ctx.location.hash,'#discover');
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

function submitHostedAuth(t,values){
 const form=t.document.getElementById('hosted-auth-form');
 assert.ok(form,'a hosted authentication form must be available');
 form.values=values;
 return form.handlers.submit({preventDefault(){},currentTarget:form});
}
const hostedCredentials={email:'anna@test.example',password:'HostedTestPassword2026!'};
const apiError=(message,status)=>Object.assign(new Error(message),{status});

test('hosted visitors can open labelled login without a demo workspace or API address selector',async()=>{
 const t=await setup({hosted:true});
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Tesztkörnyezet/);
 assert.match(html,/Jelentkezz be az Otthonrába/);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.ok(t.document.getElementById('f-email'));
 assert.ok(t.document.getElementById('f-password'));
 assert.doesNotMatch(html,/name="baseUrl"|api-form|Demó munkatér|Vissza a demóhoz|A következő fejezeted/);
 assert.equal(t.getSelectedModel(),null);
});

test('hosted login uses the current origin and waits for authentication before opening the API workspace',async()=>{
 let release;
 const login=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,connectApi:()=>login});
 const submitted=submitHostedAuth(t,hostedCredentials);
 await settle();
 assert.equal(t.connected.length,1);
 assert.deepEqual(t.connected[0].slice(0,3),['https://test.example',hostedCredentials.email,hostedCredentials.password]);
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'),'the login page must remain while the API is pending');
 release();await submitted;await settle();
 assert.equal(t.getSelectedModel(),t.model);
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Tesztkörnyezet/);
 assert.match(html,/page-heading/);
 assert.doesNotMatch(html,/Demó munkatér|Vissza a demóhoz/);
});

test('hosted registration sends profile details to the same-origin API without server selection',async()=>{
 const t=await setup({hosted:true});
 await t.click({action:'auth-mode',mode:'register'});
 const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Hozd létre a fiókodat/);
 assert.ok(t.document.getElementById('f-name'));
 assert.ok(t.document.getElementById('f-phone'));
 assert.doesNotMatch(html,/name="baseUrl"/);
 await submitHostedAuth(t,{...hostedCredentials,name:'Új Teszt Anna',phone:'+36 30 123 4567'});await settle();
 assert.equal(t.connected.length,1);
 assert.equal(t.connected[0][0],'https://test.example');
 assert.deepEqual(JSON.parse(JSON.stringify(t.connected[0][3])),{name:'Új Teszt Anna',phone:'+36 30 123 4567',accountType:'private'});
 assert.equal(t.getSelectedModel(),t.model);
});

test('failed hosted authentication stays on the form and reports the failure without opening demo data',async()=>{
 const t=await setup({hosted:true,connectApi:async()=>{throw apiError('Hibásak a bejelentkezési adatok.',401);}});
 await submitHostedAuth(t,hostedCredentials);await settle();
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 const error=t.document.getElementById('auth-error');
 assert.ok(error);assert.match(error.textContent,/Hibásak a bejelentkezési adatok/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Demó munkatér|A következő fejezeted/);
});

test('hosted settings omit the developer API selector and explicit logout returns to the public landing',async()=>{
 const t=await setup({hosted:true,authenticated:true});
 await t.click({page:'settings'});
 const settings=t.document.getElementById('app').innerHTML;
 assert.match(settings,/Kijelentkezés/);
 assert.doesNotMatch(settings,/id="api-form"|name="baseUrl"|vissza a demóhoz/i);
 await t.click({action:'disconnect'});
 assert.equal(t.getSelectedModel(),null);
 assert.equal(t.disconnected.length,1);
 assert.equal(t.ctx.location.hash,'#landing');
 assert.equal(t.document.getElementById('hosted-auth-form'),null);
 assert.ok(t.document.getElementById('landing-region'));
 assert.match(t.document.getElementById('app').innerHTML,/landing-search-card/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/sidebar|Demó munkatér/);
 assert.ok(t.landingCalls.length>0,'Explicit logout loads the anonymous public preview');
 await t.click({action:'auth-mode',mode:'login'});
 assert.equal(t.ctx.location.hash,'#login');assert.ok(t.document.getElementById('hosted-auth-form'));
});

test('an expired hosted session detected during workspace loading clears the session and requests login',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>{throw apiError('A munkameneted lejárt.',401);}}});
 assert.equal(t.getSelectedModel(),null);
 assert.equal(t.disconnected.length,1);
 const html=t.document.getElementById('app').innerHTML;
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.match(html,/lejárt/);
 assert.doesNotMatch(html,/Vissza a demóhoz|Demó munkatér/);
});

test('an expired hosted session during an action also returns to login without switching to the local demo',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{decide:async()=>{throw apiError('A munkameneted lejárt.',401);}}});
 await t.click({action:'pass'});
 assert.equal(t.getSelectedModel(),null);
 assert.ok(t.document.getElementById('hosted-auth-form'));
 assert.match(t.document.getElementById('app').innerHTML,/lejárt/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Vissza a demóhoz|Demó munkatér/);
});

test('a hosted API outage offers retry and keeps the authenticated API mode instead of substituting demo data',async()=>{
 const fixture=createModel({getItem:()=>null,setItem:()=>{}}).getState();
 let attempts=0;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>{if(++attempts===1)throw apiError('A szerver átmenetileg nem érhető el.',503);return fixture;}}});
 const failed=t.document.getElementById('app').innerHTML;
 assert.match(failed,/A szerver átmenetileg nem érhető el/);
 assert.match(failed,/data-action="retry"/);
 assert.doesNotMatch(failed,/Vissza a demóhoz|Demó munkatér|A következő fejezeted/);
 assert.equal(t.getSelectedModel(),t.model);
 assert.equal(t.disconnected.length,0);
 await t.click({action:'retry'});
 assert.equal(t.getSelectedModel(),t.model);
 assert.match(t.document.getElementById('app').innerHTML,/page-heading/);
 assert.match(t.document.getElementById('app').innerHTML,/Tesztkörnyezet/);
});

test('hosted test credits use the server method and wait for its persisted balance before confirming success',async()=>{
 const persisted=createModel({getItem:()=>null,setItem:()=>{}}).getState();
 const before=persisted.credits,calls=[];
 let release;
 const granted=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{
  getState:async()=>JSON.parse(JSON.stringify(persisted)),
  buyDemoCredits:async amount=>{calls.push(amount);await granted;persisted.credits+=amount;persisted.ledger.unshift({id:'server-test-grant',amount,description:'Szerveren mentett tesztfeltöltés',createdAt:'2026-11-03T10:00:00Z'});return{credits:persisted.credits};}
 }});
 await t.click({page:'credits'});
 const credits=t.document.getElementById('app').innerHTML;
 assert.match(credits,/Tesztkreditek feltöltése/);
 assert.doesNotMatch(credits,/Demófeltöltés|Stripe|data-action="checkout"|1 990|4 990|9 990/);
 await t.click({action:'buy',amount:'50'});
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ez ingyenes/);
 const clicked=t.click({action:'confirm-test-credits',amount:'50'});
 await settle();
 assert.deepEqual(calls,[50]);
 assert.equal(persisted.credits,before,'credits must not be changed before the API grant succeeds');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Tesztkreditek hozzáadása/);
 release();await clicked;
 assert.equal(persisted.credits,before+50);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 const updated=t.document.getElementById('app').innerHTML;
 assert.match(updated,new RegExp(`${before+50} <small>tesztkredit`));
 assert.match(updated,/Szerveren mentett tesztfeltöltés/);
 assert.match(t.document.getElementById('toast').textContent,/tesztkrediteket jóváírtuk/);
});

test('a rejected hosted test-credit grant preserves the balance and confirmation instead of reporting success',async()=>{
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{buyDemoCredits:async()=>{throw apiError('A tesztfeltöltés most nem sikerült.',503);}}});
 const before=t.model.getState();
 await t.click({page:'credits'});
 await t.click({action:'buy',amount:'20'});
 await t.click({action:'confirm-test-credits',amount:'20'});
 assert.equal(t.model.getState().credits,before.credits);
 assert.equal(t.model.getState().ledger.length,before.ledger.length);
 assert.match(t.document.getElementById('modal-root').innerHTML,/Tesztkreditek hozzáadása/);
 assert.match(t.document.getElementById('toast').textContent,/A tesztfeltöltés most nem sikerült/);
 assert.doesNotMatch(t.document.getElementById('toast').textContent,/jóváírtuk/);
});


test('new property attributes are optional and unknown floor or amenities do not become false defaults',async()=>{
 const t=await setup();t.ui.openEditor('property');
 const html=t.document.getElementById('modal-root').innerHTML;
 for(const name of ['condition','building','constructionAge','view','ceilingHeight','floor','insulated','airConditioning','solarPanels']){
  const select=html.match(new RegExp(`<select id="f-${name}"[^>]*>([\\s\\S]*?)</select>`))?.[1];
  assert.ok(select,`${name} select must be present`);
  assert.match(select,/<option value="" selected>Nincs megadva<\/option>/);
 }
 assert.match(html,/<select id="f-heatingType"/);assert.match(html,/<select id="f-secondaryHeatingType"/);assert.match(html,/>Nincs fűtés<\/option>/);assert.equal((html.match(/name="parkingTypes"/g)||[]).length,propertyAttributes.PARKING_OPTIONS.length);
 chooseLocation(t,'city:Solymár');
 submitEntity(t,{title:'Opcionális jellemzők',type:'Lakás',price:'82',area:'64',wholeRooms:'3',halfRooms:'0',floor:'',condition:'',building:'',constructionAge:'',view:'',ceilingHeight:'',insulated:'',airConditioning:'',solarPanels:'',images:''});
 await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Opcionális jellemzők');
 assert.ok(saved);
 for(const name of ['floor','insulated','airConditioning','solarPanels'])assert.equal(saved[name],null,name);
 for(const name of ['condition','building','constructionAge','view','ceilingHeight'])assert.equal(saved[name],'',name);
});

test('search checkboxes serialize several choices per category and can all be cleared',async()=>{
 const t=await setup();t.ui.openEditor('search');chooseLocation(t,'district:Budapest:13');
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/<fieldset id="conditions-group" class="attribute-group"><legend>Állapot/);
 assert.match(html,/Többet is megjelölhetsz/);
 assert.equal((html.match(/name="buildings"/g)||[]).length,12);
 submitEntity(t,[...Object.entries(searchValues('Részletes keresés')),['conditions','Jó'],['conditions','Új/felújított'],['buildings','Tégla'],['buildings','Panel'],['constructionAges','10 évnél fiatalabb'],['constructionAges','10–30 év közötti'],['views','Kertre néző'],['views','Panorámás'],['ceilingHeight','3 m feletti'],['floors','-1'],['floors','0'],['floors','11']]);
 await settle();
 let saved=t.model.getState().searches.find(item=>item.title==='Részletes keresés');assert.ok(saved);
 assert.deepEqual([...saved.conditions],['Jó','Új/felújított']);assert.deepEqual([...saved.buildings],['Tégla','Panel']);
 assert.deepEqual([...saved.constructionAges],['10 évnél fiatalabb','10–30 év közötti']);assert.deepEqual([...saved.views],['Kertre néző','Panorámás']);
 assert.deepEqual([...saved.floors],[-1,0,11]);assert.equal(saved.ceilingHeight,'3 m feletti');
 t.ui.openEditor('search',saved.id);
 const edited=t.document.getElementById('modal-root').innerHTML;
 assert.match(edited,/name="conditions" value="Jó" checked/);assert.match(edited,/name="floors" value="-1" checked/);
 submitEntity(t,searchValues('Részletes keresés'));await settle();
 saved=t.model.getState().searches.find(item=>item.id===saved.id);
 for(const name of ['conditions','buildings','constructionAges','views','heatingTypes','floors'])assert.equal(saved[name].length,0,name);
 assert.equal(saved.ceilingHeight,'');
});

test('seller inputs preserve explicit no, unknown amenities and existing higher floor values',async()=>{
 const t=await setup();t.ui.openEditor('property');chooseLocation(t,'district:Budapest:13');
 submitEntity(t,{title:'Részletes eladó lakás',type:'Lakás',price:'78',area:'65',wholeRooms:'3',halfRooms:'0',floor:'12',condition:'Jó',building:'Csúsztatott zsalu',constructionAge:'31–40 év közötti',view:'Panorámás',ceilingHeight:'3 m feletti',heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',energyRating:'A+',parkingTypes:'Mélygarázs',insulated:'false',airConditioning:'true',solarPanels:'',images:''});await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Részletes eladó lakás');assert.ok(saved);
 assert.equal(saved.floor,12);assert.equal(saved.insulated,false);assert.equal(saved.airConditioning,true);assert.equal(saved.solarPanels,null);
 assert.equal(saved.building,'Csúsztatott zsalu');assert.equal(saved.energyRating,'A+');
 t.ui.openEditor('property',saved.id);
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/<option value="12" selected>12\. emelet<\/option>/);
 assert.match(html,/<option value="false" selected>Nem<\/option>/);
 assert.match(html,/value="Hőszivattyú" selected/);
});

test('candidate details show chosen attributes and amenities without inventing an unknown floor',async()=>{
 const item={id:'detail-p',kind:'property',title:'Részletes jelölt',city:'Budapest',locationId:'district:Budapest:13',type:'Lakás',price:75,area:60,rooms:3,condition:'Felújított',building:'Tégla',floor:null,constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m alatti',heatingType:'Hőszivattyú',insulated:false,energyRating:'A+',airConditioning:true,solarPanels:null,parkingType:'Fedett beálló',images:[]};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{feed:async()=>[item]}});
 let html=t.document.getElementById('app').innerHTML;assert.doesNotMatch(html,/Földszint|0\. emelet/);
 t.ui.openDetails();html=t.document.getElementById('modal-root').innerHTML;
 for(const value of ['Új/felújított','Kertre néző','10–30 év közötti','3 m alatti','Hőszivattyú','Fedett beálló','Szigetelés az épületen','Nincs','Légkondi','Van'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/Napelem/,'unknown solar panels must not be rendered as no');
});

test('search city-region choices show settlement counts and preserve compact IDs beside exact towns through edit and removal',async()=>{
 const t=await setup();t.ui.openEditor('search');
 const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/A településszám a központot is tartalmazza/);
 assert.match(html,/Városkörnyékek: <a href="https:\/\/www\.ksh\.hu\/teruleti_szamjel_menu"/);
 chooseLocation(t,'area:Debrecen');chooseLocation(t,'city:Solymár');
 let chips=t.document.getElementById('location-chips');
 assert.match(chips.innerHTML,/Debrecen és környéke \(13 település\)/);
 assert.match(chips.innerHTML,/Solymár/);
 submitEntity(t,searchValues('Városkörnyék és másik település'));await settle();
 let saved=t.model.getState().searches.find(item=>item.title==='Városkörnyék és másik település');
 assert.ok(saved);assert.deepEqual([...saved.locationIds],['area:Debrecen','city:Solymár']);
 assert.equal(saved.locationIds.length,2,'a region remains one selected location instead of expanding its members');
 await t.click({page:'searches'});
 assert.match(t.document.getElementById('app').innerHTML,/Debrecen és környéke \(13 település\)/);
 t.ui.openEditor('search',saved.id);chips=t.document.getElementById('location-chips');
 assert.match(chips.innerHTML,/Debrecen és környéke \(13 település\)/);
 const target={dataset:{removeLocation:'area:Debrecen'},closest:()=>target};chips.handlers.click({target});
 assert.doesNotMatch(chips.innerHTML,/Debrecen/);assert.match(chips.innerHTML,/Solymár/);
 submitEntity(t,searchValues('Városkörnyék és másik település'));await settle();
 saved=t.model.getState().searches.find(item=>item.id===saved.id);
 assert.deepEqual([...saved.locationIds],['city:Solymár']);
});

test('a city-region is selectable by keyboard as one counted search location',async()=>{
 const t=await setup();t.ui.openEditor('search');
 const input=t.document.getElementById('location-input');input.value='Budapest és környéke';input.handlers.input();
 assert.match(t.document.getElementById('location-options').innerHTML,/Budapest és környéke \(81 település\)/);
 key(input,'ArrowDown');key(input,'Enter');
 assert.equal(input.value,'');assert.equal(input.getAttribute('aria-expanded'),'false');
 assert.match(t.document.getElementById('location-chips').innerHTML,/Budapest és környéke \(81 település\)/);
 submitEntity(t,searchValues('Főváros és környéke'));await settle();
 const saved=t.model.getState().searches.find(item=>item.title==='Főváros és környéke');
 assert.ok(saved);assert.deepEqual([...saved.locationIds],['area:Budapest']);
});

test('seller suggestions and a forged picker action cannot assign a broad city-region to a property',async()=>{
 const t=await setup();t.ui.openEditor('property');
 const input=t.document.getElementById('location-input'),list=t.document.getElementById('location-options');
 input.value='Debrecen';input.handlers.input();
 assert.match(list.innerHTML,/data-location-id="city:Debrecen"/);
 assert.doesNotMatch(list.innerHTML,/data-location-id="area:/);
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/Városkörnyékek:/);
 const target={dataset:{locationId:'area:Debrecen'},closest:()=>target};list.handlers.click({target});
 assert.equal(t.document.getElementById('location-chips').innerHTML,'');
 assert.equal(input.value,'Debrecen','rejecting a forged region action must not silently consume the typed query');
 chooseLocation(t,'city:Debrecen');
 submitEntity(t,{title:'Pontos településen lévő lakás',type:'Lakás',price:'65',area:'62',wholeRooms:'3',halfRooms:'0',floor:'',images:'',condition:'',building:''});await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Pontos településen lévő lakás');
 assert.ok(saved);assert.equal(saved.locationId,'city:Debrecen');
});

test('seller heating lists, supplemental heating and multiple parking choices persist together with exact room counts',async()=>{
 const t=await setup();t.ui.openEditor('property');chooseLocation(t,'city:Debrecen');
 const html=t.document.getElementById('modal-root').innerHTML;
 const options=name=>[...html.match(new RegExp(`<select id="f-${name}"[^>]*>([\\s\\S]*?)</select>`))[1].matchAll(/<option value="([^"]*)"/g)].map(match=>match[1]);
 assert.deepEqual(options('heatingType'),['',...propertyAttributes.HEATING_OPTIONS]);assert.deepEqual(options('secondaryHeatingType'),options('heatingType'));
 assert.doesNotMatch(html,/id="f-rooms"|id="f-parkingType"/);
 submitEntity(t,[...Object.entries({title:'Egész és fél szobák',type:'Lakás',price:'82.5',area:'64.5',wholeRooms:'2',halfRooms:'3',floor:'-1',heatingType:'Nincs fűtés',secondaryHeatingType:'Klíma',images:''}),['parkingTypes','Garázs'],['parkingTypes','Udvari beálló']]);await settle();
 const saved=t.model.getState().properties.find(item=>item.title==='Egész és fél szobák');assert.ok(saved);assert.equal(saved.wholeRooms,2);assert.equal(saved.halfRooms,3);assert.equal(saved.rooms,3.5);assert.equal(saved.floor,-1);assert.equal(saved.heatingType,'Nincs fűtés');assert.equal(saved.secondaryHeatingType,'Klíma');assert.deepEqual([...saved.parkingTypes],['Garázs','Udvari beálló']);
 t.ui.openEditor('property',saved.id);assert.equal(t.document.getElementById('f-wholeRooms').value,'2');assert.equal(t.document.getElementById('f-halfRooms').value,'3');
 assert.match(t.document.getElementById('modal-root').innerHTML,/name="parkingTypes" value="Garázs" checked/);
 await t.click({page:'properties'});assert.match(t.document.getElementById('app').innerHTML,/2 egész \+ 3 fél szoba/);
});

function guardedEvent(values={}){return {...values,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};}
test('all entity numeric inputs block signs through keys, mobile beforeinput, paste and input fallback while preserving decimals and empty bounds',async()=>{
 const t=await setup();
 for(const kind of ['property','search']){
  t.ui.openEditor(kind);
  const inputs=t.document.getElementById('entity-form').querySelectorAll('input[type="number"]');assert.ok(inputs.length>=5);
  for(const input of inputs){
   for(const character of ['-','−','+','e','E'])assert.equal(key(input,character).defaultPrevented,true,`${kind} ${input.id} blocks ${character}`);
   const mobile=guardedEvent({data:'-12',inputType:'insertText'});input.handlers.beforeinput(mobile);assert.equal(mobile.defaultPrevented,true);
   const paste=guardedEvent({clipboardData:{getData:()=>'-12'}});input.handlers.paste(paste);assert.equal(paste.defaultPrevented,true);
   input.value='12';input.handlers.input();input.value='-12';input.handlers.input();assert.equal(input.value,'12');input.value='1e-2';input.handlers.input();assert.equal(input.value,'12');
   input.value='';input.handlers.input();assert.equal(input.value,'');
  }
  const decimal=t.document.getElementById(kind==='property'?'f-price':'f-minPrice');decimal.value='12.5';decimal.handlers.input();assert.equal(decimal.value,'12.5');
 }
 t.ui.openEditor('property');const whole=t.document.getElementById('f-wholeRooms'),half=t.document.getElementById('f-halfRooms');
 assert.equal(key(whole,'.').defaultPrevented,true);assert.equal(key(half,',').defaultPrevented,true);
 whole.value='0';whole.handlers.input();half.value='0';half.handlers.input();assert.match(whole.validationMessage,/legalább egy/);half.value='1';half.handlers.input();assert.equal(whole.validationMessage,'');
 assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/negatív/);
});

test('house forms require lot area only for sellers and hide or disable floor, balcony and elevator on both sides',async()=>{
 const t=await setup();
 for(const kind of ['property','search']){
  t.ui.openEditor(kind);const type=t.document.getElementById('f-type');type.value='Ház';type.handlers.change();
  assert.match(t.document.getElementById('entity-amenities').className,/hidden/);for(const name of ['balcony','elevator'])assert.equal(t.document.getElementById(`f-${name}`).disabled,true);
  if(kind==='property'){assert.equal(t.document.getElementById('f-lotArea').required,true);assert.equal(t.document.getElementById('f-lotArea').disabled,false);assert.equal(t.document.getElementById('f-floor').disabled,true);assert.match(t.document.getElementById('property-floor-field').className,/hidden/);}
  else{assert.equal(t.document.getElementById('floors-group').disabled,true);assert.match(t.document.getElementById('floors-group').className,/hidden/);}
  type.value='Lakás';type.handlers.change();assert.doesNotMatch(t.document.getElementById('entity-amenities').className,/hidden/);assert.equal(t.document.getElementById('f-balcony').disabled,false);
  if(kind==='property'){assert.equal(t.document.getElementById('f-lotArea').required,false);assert.equal(t.document.getElementById('f-lotArea').disabled,true);assert.equal(t.document.getElementById('f-floor').disabled,false);}else assert.equal(t.document.getElementById('floors-group').disabled,false);
 }
 t.ui.openEditor('property');chooseLocation(t,'city:Debrecen');submitEntity(t,{title:'Ház mezőtisztítás',type:'Ház',price:'99.5',area:'120.5',wholeRooms:'2',halfRooms:'3',lotArea:'650',floor:'3',balcony:'on',elevator:'on',images:''});await settle();
 const property=t.model.getState().properties.find(item=>item.title==='Ház mezőtisztítás');assert.ok(property);assert.equal(property.floor,null);assert.equal(property.balcony,false);assert.equal(property.elevator,false);
 t.ui.openEditor('search');chooseLocation(t,'city:Debrecen');submitEntity(t,[...Object.entries({...searchValues('Ház keresési mezőtisztítás'),type:'Ház',balcony:'on',elevator:'on'}),['floors','-1'],['heatingTypes','Gázkazán'],['heatingTypes','Hőszivattyú']]);await settle();
 const search=t.model.getState().searches.find(item=>item.title==='Ház keresési mezőtisztítás');assert.ok(search);assert.deepEqual([...search.floors],[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);assert.deepEqual([...search.heatingTypes],['Gázkazán','Hőszivattyú']);
});

test('legacy arbitrary room totals are never rounded and existing heating or parking text remains selectable',async()=>{
 const demo=createModel({getItem:()=>null,setItem:()=>{}}).getState();demo.properties[0]={...demo.properties[0],id:'legacy-property',rooms:3.2,wholeRooms:null,halfRooms:null,heatingType:'Régi vegyes rendszer',parkingType:'Régi garázs és beálló',parkingTypes:undefined};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>demo}});t.ui.openEditor('property','legacy-property');const html=t.document.getElementById('modal-root').innerHTML;
 assert.equal(t.document.getElementById('f-wholeRooms').value,'');assert.equal(t.document.getElementById('f-halfRooms').value,'');assert.match(html,/<option value="Régi vegyes rendszer" selected>Meglévő érték: Régi vegyes rendszer<\/option>/);assert.match(html,/name="parkingTypes" value="Régi garázs és beálló" checked/);
});


function chooseReport(t,reason){for(const option of accountHelpers.REPORT_REASON_OPTIONS){const input=t.document.getElementById('f-reportReason-'+option.value);if(input)input.checked=option.value===reason;}}
function accountFixture(mutate){let raw;const local=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});local.activate('search','own-s1');mutate(raw);return raw;}
test('hosted and settings registration both offer account types and send the selected agent role',async()=>{
 const hosted=await setup({hosted:true});await hosted.click({action:'auth-mode',mode:'register'});
 const registration=hosted.document.getElementById('app').innerHTML;assert.match(registration,/id="f-accountType"/);assert.match(registration,/value="private">Magánszemély/);assert.match(registration,/value="agent">Ingatlanközvetítő/);
 await submitHostedAuth(hosted,{...hostedCredentials,name:'Közvetítő Anna',accountType:'agent'});await settle();assert.equal(hosted.connected[0][3].accountType,'agent');
 const legacy=await setup();await legacy.click({page:'settings'});const select=legacy.document.getElementById('api-accountType');assert.ok(select);assert.equal(select.value,'private');
 legacy.document.getElementById('register-toggle').handlers.change({target:{checked:true}});assert.doesNotMatch(legacy.document.getElementById('register-name').className,/hidden/);
 const form=legacy.document.getElementById('api-form');form.values={baseUrl:'https://api.example.test',email:'agent@example.test',password:'LongPassword2026!',register:'on',registerName:'Közvetítő Eszter',accountType:'agent'};form.handlers.submit({preventDefault(){},currentTarget:form});await settle();assert.equal(legacy.connected[0][3].accountType,'agent');
});
test('foreign owner labels are explicit while agent-owned workspace cards, summaries and activation choices hide them',async()=>{
 const t=await setup();assert.match(t.document.getElementById('app').innerHTML,/account-badge private-badge/);
 while(t.model.feed()[0]?.ownerAccountType!=='agent'){t.model.decide(t.model.feed()[0],false);await t.ui.render();}
 assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);t.ui.openDetails();assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanközvetítő/);await t.click({action:'close'});
 await t.click({action:'like'});await t.click({action:'close'});await t.click({action:'tab',tab:'liked'});assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);await t.click({page:'matches'});assert.match(t.document.getElementById('app').innerHTML,/account-badge agent-badge/);
 const raw=accountFixture(raw=>{raw.users.find(user=>user.id==='me').accountType='agent';});const agent=await setup({initialRaw:raw});assert.ok(agent.model.feed().every(item=>item.ownerAccountType==='private'));
 for(const page of ['properties','searches']){await agent.click({page});assert.doesNotMatch(agent.document.getElementById('app').innerHTML,/account-badge/);}
 agent.ui.openActivation();assert.doesNotMatch(agent.document.getElementById('modal-root').innerHTML,/account-badge/);await agent.click({action:'close'});
 await agent.click({action:'activate-one',kind:'property',id:'own-p1'});assert.ok(agent.model.feed().every(item=>item.ownerAccountType==='private'));assert.match(agent.document.getElementById('app').innerHTML,/account-badge private-badge/);
 await agent.click({page:'settings'});const html=agent.document.getElementById('app').innerHTML;assert.match(html,/Fióktípus: <strong>Ingatlanközvetítő/);assert.doesNotMatch(html.match(/<form[^>]*id="profile-form"[\s\S]*?<\/form>/)[0],/name="accountType"/);
});
test('reporting requires one reason, awaits persistence and allows another reason without revealing timestamps',async()=>{
 const t=await setup(),before=t.model.getState();await t.click({action:'report-account',kind:'property',id:'p1'});let html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/Milyen szabálytalanságot tapasztaltál\?/);assert.doesNotMatch(html,/<select|Jelentés oka|Korábban jelzett ok/);for(const option of accountHelpers.REPORT_REASON_OPTIONS)assert.ok(html.includes(`value="${option.value}"`));
 await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.document.activeElement.id,'f-reportReason-suspected_agent');assert.deepEqual(t.model.getState().reportedEntities,[]);await t.click({action:'close'});
 let release;const wait=new Promise(resolve=>{release=resolve;});const original=t.model.reportAccount;t.model.reportAccount=async(...args)=>{await wait;return original(...args);};
 await t.click({action:'report-account',kind:'property',id:'p1'});chooseReport(t,'suspected_agent');const sending=t.click({action:'confirm-report',kind:'property',id:'p1'});await settle();assert.deepEqual(t.model.getState().reportedEntities,[]);assert.match(t.document.getElementById('modal-root').innerHTML,/Jelentés elküldése/);
 release();await sending;assert.deepEqual(t.model.getState().reportedEntities,[{entityKind:'property',entityId:'p1',reason:'suspected_agent'}]);assert.equal(t.model.getState().credits,before.credits);assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.match(t.document.getElementById('toast').textContent,/A jelentésedet elmentettük/);
 html=t.document.getElementById('app').innerHTML;assert.match(html,/data-action="report-account" data-kind="property" data-id="p1">/);assert.doesNotMatch(html,/\d{4}-\d{2}-\d{2}T|reportedAt|CreatedAt/);
 await t.click({action:'report-account',kind:'property',id:'p1'});assert.doesNotMatch(t.document.getElementById('modal-root').innerHTML,/Korábban jelzett ok|Jelentés oka/);chooseReport(t,'misleading_content');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities.length,2);
 await t.click({action:'report-account',kind:'property',id:'p1'});chooseReport(t,'misleading_content');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities.length,2);assert.match(t.document.getElementById('toast').textContent,/már jelentetted/);
});
test('agent listings offer applicable report reasons and failed saves retain the selected reason for retry',async()=>{
 const t=await setup(),original=t.model.reportAccount;await t.click({action:'report-account',kind:'property',id:'own-p1'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 while(t.model.feed()[0]?.id!=='p2'){t.model.decide(t.model.feed()[0],false);await t.ui.render();}
 await t.click({action:'report-account',kind:'property',id:'p2'});const html=t.document.getElementById('modal-root').innerHTML;assert.doesNotMatch(html,/value="suspected_agent"/);assert.match(html,/value="misleading_content"/);assert.match(html,/value="other_violation"/);
 chooseReport(t,'misleading_content');t.model.reportAccount=async()=>{throw new Error('A jelentés mentése most nem sikerült.');};await t.click({action:'confirm-report',kind:'property',id:'p2'});assert.match(t.document.getElementById('modal-root').innerHTML,/Jelentés elküldése/);assert.match(t.document.getElementById('toast').textContent,/mentése most nem sikerült/);assert.equal(t.document.getElementById('f-reportReason-misleading_content').checked,true);assert.deepEqual(t.model.getState().reportedEntities,[]);
 t.model.reportAccount=original;await t.click({action:'confirm-report',kind:'property',id:'p2'});assert.deepEqual(t.model.getState().reportedEntities,[{entityKind:'property',entityId:'p2',reason:'misleading_content'}]);
});
test('agent search likes show one credit and button, keyboard and swipe cannot consume an unaffordable candidate',async()=>{
 const raw=accountFixture(raw=>{raw.users.find(user=>user.id==='me').accountType='agent';raw.credits=1;});const t=await setup({initialRaw:raw});assert.match(t.document.getElementById('app').innerHTML,/<span class="decision-like-caption"><span>Kedvelés<\/span><small>1 kredit<\/small>/);t.ui.openDetails();assert.match(t.document.getElementById('modal-root').innerHTML,/Tetszik · 1 kredit/);await t.click({action:'close'});await t.click({action:'like'});assert.equal(t.model.getState().credits,0);await t.click({action:'close'});
 const before=t.model.getState(),candidate=t.model.feed()[0].id;await t.click({action:'like'});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.equal(t.model.feed()[0].id,candidate);assert.equal(t.model.getState().decisions.length,before.decisions.length);await t.click({action:'close'});
 await t.document.handlers.keydown({key:'ArrowRight',target:{closest:()=>null},preventDefault(){}});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);await t.click({action:'close'});
 const card=t.document.getElementById('candidate'),target={closest:selector=>selector==='#candidate'?card:null};t.document.handlers.pointerdown({target,clientX:0,clientY:0,pointerId:7});await t.document.handlers.pointerup({clientX:130,clientY:3,pointerId:7});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.equal(t.model.feed()[0].id,candidate);assert.equal(t.model.getState().credits,0);assert.equal(t.model.getState().ledger.length,before.ledger.length);await t.click({action:'close'});await t.click({action:'pass'});assert.notEqual(t.model.feed()[0]?.id,candidate);assert.equal(t.model.getState().credits,0);
});

function incomingFixture(type='private') {return accountFixture(raw=>{
 raw.users.find(user=>user.id==='me').accountType=type;raw.matches=[];raw.reports=[];
 // Keep the incoming-action target distinct from the best-value discovery card.
 raw.properties.find(item=>item.id==='p2').area=50;
 const received=(id,actorKind,actorId,propertyId,searchId)=>({id,actorKind,actorId,propertyId,searchId,liked:true,createdAt:'2026-11-07T10:00:00.000Z'});
 raw.decisions=[received('in-p1','property','p1','p1','own-s1'),received('in-p2','property','p2','p2','own-s1'),received('in-p4','property','p4','p4','own-s2'),received('in-s1','search','s1','own-p1','s1')];
 const second=raw.searches.find(search=>search.id==='own-s2');Object.assign(second,{locationIds:['district:Budapest:13'],city:'Budapest',districts:['XIII.']});
});}
test('Kedveltek uses the active profile and reciprocal actions target the chosen pair instead of the discovery first card',async()=>{
 const t=await setup({initialRaw:incomingFixture()});await t.click({page:'incoming'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Kedveltek/);assert.match(html,/incoming-card/);assert.match(html,/data-id="p1"/);assert.match(html,/data-id="p2"/);assert.doesNotMatch(html,/peter@example.hu|eszter@example.hu|\+36 30/);
 const before=t.model.getState();assert.equal(t.model.feed()[0].id,'p1');await t.click({action:'incoming-details',kind:'property',id:'p2'});assert.match(t.document.getElementById('modal-root').innerHTML,/Zöldre néző otthon/);await t.click({action:'close'});
 await t.click({action:'incoming-like',kind:'property',id:'p2'});assert.equal(t.model.getState().credits,before.credits);assert.ok(t.model.getState().decisions.some(decision=>decision.actorKind==='search'&&decision.propertyId==='p2'&&decision.liked));assert.equal(t.model.getState().decisions.some(decision=>decision.actorKind==='search'&&decision.propertyId==='p1'),false);assert.match(t.document.getElementById('modal-root').innerHTML,/Egymásra találtatok/);await t.click({action:'close'});assert.match(t.document.getElementById('app').innerHTML,/Beszélgetés megnyitása/);
 await t.click({action:'incoming-pass',kind:'property',id:'p1'});html=t.document.getElementById('app').innerHTML;assert.match(html,/korábban elutasítottad/);assert.ok(t.model.incomingLikes().items.find(item=>item.id==='p1').myDecision==='passed');
 await t.click({action:'activate-one',kind:'search',id:'own-s2'});assert.equal(t.ctx.location.hash,'#incoming');assert.match(t.document.getElementById('app').innerHTML,/data-id="p4"/);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-card" data-id="p1"/);
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/incoming-card" data-id="s1"/);await t.click({action:'incoming-like',kind:'search',id:'s1'});assert.equal(t.model.getState().credits,before.credits-2);
});
test('incoming likes are free to inspect and agent reciprocity checks credit before changing the received pair',async()=>{
 const raw=incomingFixture('agent');raw.credits=0;const t=await setup({initialRaw:raw});await t.click({page:'incoming'});const before=t.model.getState();assert.equal(t.model.incomingLikes().items.length,1);assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-card" data-id="p2"/);await t.click({action:'incoming-like',kind:'property',id:'p1'});assert.match(t.document.getElementById('modal-root').innerHTML,/Kreditekre van szükséged/);assert.deepEqual(t.model.getState(),before);await t.click({action:'close'});
 t.model.buyDemoCredits(1);await t.ui.render();await t.click({action:'incoming-like',kind:'property',id:'p1'});assert.equal(t.model.getState().credits,0);assert.equal(t.model.getState().ledger.filter(entry=>entry.amount===-1).length,1);
});
test('incoming pagination appends unique rows and discards an old load after navigation',async()=>{
 const local=createModel({getItem:()=>JSON.stringify(incomingFixture()),setItem:()=>{}}),all=local.incomingLikes().items,calls=[];let release;
 const more=new Promise(resolve=>{release=resolve;});const active=local.getState().active;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),incomingLikes:async({offset=0,limit=50}={})=>{calls.push({offset,limit});return offset?more:{active,items:[all[0]],total:2,offset:0,limit:1,hasMore:true,likeCost:0};}}});
 await t.click({page:'incoming'});assert.match(t.document.getElementById('app').innerHTML,/incoming-more/);const loading=t.click({action:'incoming-more'});await settle();assert.deepEqual(calls,[{offset:0,limit:50},{offset:1,limit:1}]);await t.click({page:'settings'});release({active,items:[all[1]],total:2,offset:1,limit:1,hasMore:false,likeCost:0});await loading;assert.equal(t.ctx.location.hash,'#settings');assert.doesNotMatch(t.document.getElementById('app').innerHTML,/incoming-grid/);
 const appended=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),incomingLikes:({offset=0}={})=>({active,items:offset?[all[0],all[1]]:[all[0]],total:2,offset,limit:1,hasMore:offset===0,likeCost:0})}});await appended.click({page:'incoming'});await appended.click({action:'incoming-more'});const html=appended.document.getElementById('app').innerHTML;assert.equal((html.match(/class="entity-card incoming-card"/g)||[]).length,2);assert.doesNotMatch(html,/data-action="incoming-more"/);
});
test('incoming view handles no active profile and incompatible interests without actionable likes',async()=>{
 const empty=createModel({getItem:()=>null,setItem:()=>{}}).getState();empty.active={kind:'search',id:null};const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>empty,incomingLikes:()=>({active:null,items:[],total:0,offset:0,limit:50,hasMore:false,likeCost:0})}});await t.click({page:'incoming'});assert.match(t.document.getElementById('app').innerHTML,/Válassz aktív profilt/);
 const raw=incomingFixture();raw.properties.find(item=>item.id==='p1').area=999;const incompatible=await setup({initialRaw:raw});await incompatible.click({page:'incoming'});assert.match(incompatible.document.getElementById('app').innerHTML,/Részleges egyezés/);assert.match(incompatible.document.getElementById('app').innerHTML,/engedélyezd a részleges egyezéseket/);const before=incompatible.model.getState();await incompatible.click({action:'incoming-like',kind:'property',id:'p1'});assert.deepEqual(incompatible.model.getState(),before);
});

test('hosted root is a public demand-focused landing with independent login and registration routes',async()=>{
 const t=await setup({hosted:true,hash:''}),html=t.document.getElementById('app').innerHTML;
 assert.match(html,/Unod a passzív várakozást és a kéretlen telefonokat\?/);assert.match(html,/Érd el a vevőidet egy kattintással!/);assert.match(html,/Tedd közzé a keresési igényed és maradj inkognitóban!/);assert.match(html,/Nézd meg, mit keresnek a vevők/);assert.ok(html.indexOf('landing-search-card')<html.indexOf('landing-property-card'));assert.match(html,/Megtalálom a vevőmet/);assert.match(html,/Megtalálom az otthonom/);assert.match(html,/Illusztráció/);assert.match(html,/geojs.io\/privacy/);assert.ok(html.indexOf('landing-property-card')<html.indexOf('class="landing-how"'),'Both teaser types precede the longer explanation');assert.doesNotMatch(html,/landing-region-status|landing-region-note|aria-describedby="landing-region-note"|Hozzávetőleges régió|Bármikor választhatsz másikat/);assert.equal(t.document.getElementById('hosted-auth-form'),null);assert.equal(t.getSelectedModel(),null);assert.doesNotMatch(html,/sidebar|api-email|Demó munkatér/);
 await t.click({action:'auth-mode',mode:'register'});assert.equal(t.ctx.location.hash,'#register');assert.ok(t.document.getElementById('f-name'));await t.click({action:'landing'});assert.equal(t.ctx.location.hash,'#landing');assert.ok(t.document.getElementById('landing-region'));await t.click({action:'auth-mode',mode:'login'});assert.equal(t.ctx.location.hash,'#login');assert.equal(t.document.getElementById('f-name'),null);assert.ok(t.document.getElementById('hosted-auth-form'));
});
test('local landing preview does not alter the saved demo workspace',async()=>{
 const t=await setup({hash:'#landing'}),before=t.model.getState();assert.ok(t.document.getElementById('landing-region'));await t.click({page:'discover'});assert.match(t.document.getElementById('app').innerHTML,/A következő fejezeted/);assert.deepEqual(t.model.getState(),before);
});
test('landing uses public structured teaser fields only, escapes markup and bounds demand and property cards',async()=>{
 const data=landingFixture();data.searches=Array.from({length:12},(_,i)=>({...data.searches[0],key:'s'+i,title:'Lakást <keresnek>',description:'hidden@example.hu',ownerId:'secret-owner',ownerName:'Titkos Név'}));data.properties=Array.from({length:6},(_,i)=>({...data.properties[0],key:'p'+i,title:'Eladó <lakás>',address:'Titkos utca 42.',images:['https://tracker.test/photo.jpg'],ownerEmail:'hidden@example.hu'}));
 const t=await setup({hosted:true,hash:'',fetchLanding:async()=>data}),html=t.document.getElementById('app').innerHTML;assert.equal((html.match(/class="landing-search-card"/g)||[]).length,8);assert.equal((html.match(/class="landing-property-card"/g)||[]).length,4);assert.match(html,/Lakást &lt;keresnek&gt;/);assert.doesNotMatch(html,/hidden@example|secret-owner|Titkos|tracker.test|<keresnek>/);assert.doesNotMatch(source,/navigator\s*\.\s*geolocation|watchPosition|getCurrentPosition/);
});
test('manual region choice wins a delayed approximate lookup and only its canonical ID is remembered',async()=>{
 let detected;const geo=new Promise(resolve=>{detected=resolve});const t=await setup({hosted:true,hash:'',detectLandingRegion:()=>geo});assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{}]);let select=t.document.getElementById('landing-region');select.value='HU321';select.handlers.change({currentTarget:select});await settle();assert.equal(t.regionStorage.get('otthonra.landing.region'),'HU321');assert.match(t.document.getElementById('app').innerHTML,/Debrecen/);detected('HU110');await settle();assert.deepEqual(JSON.parse(JSON.stringify(t.landingCalls)),[{},{region:'HU321'}]);assert.equal(t.document.getElementById('landing-region').value,'HU321');
});
test('approximate region is optional and not persisted; saved manual region bypasses lookup',async()=>{
 const auto=await setup({hosted:true,hash:'',detectLandingRegion:async()=> 'HU321'});await settle();assert.deepEqual(JSON.parse(JSON.stringify(auto.landingCalls)),[{},{region:'HU321'}]);assert.equal(auto.regionStorage.size,0);
 let lookups=0;const saved=await setup({hosted:true,hash:'',regionStorage:{'otthonra.landing.region':'HU321'},detectLandingRegion:async()=>{lookups++;return 'HU110'}});assert.deepEqual(JSON.parse(JSON.stringify(saved.landingCalls)),[{},{region:'HU321'}]);assert.equal(lookups,0);assert.match(saved.document.getElementById('app').innerHTML,/Debrecen/);
});
test('regional empty results remain honest and national fallback clears remembered choice',async()=>{
 const t=await setup({hosted:true,hash:''});const select=t.document.getElementById('landing-region');select.value='HU232';select.handlers.change({currentTarget:select});await settle();let html=t.document.getElementById('app').innerHTML;assert.match(html,/Ebben a régióban még nincs keresési igény/);assert.match(html,/Somogy/);assert.doesNotMatch(html,/class="landing-search-card"|class="landing-property-card"/);await t.click({action:'landing-national'});html=t.document.getElementById('app').innerHTML;assert.match(html,/Országos válogatás/);assert.match(html,/class="landing-search-card"/);assert.equal(t.regionStorage.has('otthonra.landing.region'),false);
});
test('public API failure offers retry without substituting demo or erasing regional choices',async()=>{
 let requests=0;const t=await setup({hosted:true,hash:'',fetchLanding:async input=>{if(++requests===1)throw new Error('Átmeneti hálózati hiba.');return landingFixture(input.region)}});let html=t.document.getElementById('app').innerHTML;assert.match(html,/A válogatás most nem elérhető/);assert.doesNotMatch(html,/class="landing-search-card"|sidebar/);assert.equal(t.getSelectedModel(),null);await t.click({action:'landing-retry'});html=t.document.getElementById('app').innerHTML;assert.match(html,/class="landing-search-card"/);
});
test('a late public response cannot replace the authentication page',async()=>{
 let release,requests=0;const pending=new Promise(resolve=>{release=resolve}),t=await setup({hosted:true,hash:'',fetchLanding:()=>++requests===1?landingFixture():pending});const retry=t.click({action:'landing-retry'});await settle();await t.click({action:'auth-mode',mode:'register'});assert.ok(t.document.getElementById('hosted-auth-form'));release(landingFixture('HU321'));await retry;assert.ok(t.document.getElementById('hosted-auth-form'));assert.equal(t.ctx.location.hash,'#register');
});
test('refund notifications show unread balance feedback, escape text, and await persisted mark-read',async()=>{
 let readAt=null,resolveRead;const wait=new Promise(resolve=>{resolveRead=resolve});const item={id:'notice-1',kind:'like_refund',amount:2,text:'A 2 kreditedet visszatérítettük. <b>biztonságos</b>',decisionId:'decision-1',createdAt:'2026-11-08T10:00:00Z',readAt:null};const state=createModel({getItem:()=>null,setItem:()=>{}}).getState();const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>({...state,unreadNotificationCount:readAt?0:1}),notifications:async()=>({items:[{...item,readAt}],total:1,unreadCount:readAt?0:1,offset:0,limit:50,hasMore:false}),markNotificationRead:async()=>{await wait;readAt='2026-11-08T11:00:00Z';return {...item,readAt}}}});
 assert.match(t.document.getElementById('app').innerHTML,/aria-label="Értesítések, 1 olvasatlan"/);await t.click({page:'notifications'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Kreditvisszatérítés/);assert.match(html,/\+2 kredit/);assert.match(html,/&lt;b&gt;biztonságos&lt;\/b&gt;/);assert.match(html,/is-unread/);const marking=t.click({action:'notification-read',id:item.id});await settle();assert.match(t.document.getElementById('app').innerHTML,/is-unread/);resolveRead();await marking;html=t.document.getElementById('app').innerHTML;assert.doesNotMatch(html,/is-unread|notification-count/);assert.match(html,/Elolvasva/);assert.equal((await t.model.getState()).credits,24);
});
test('notification paging appends unique items and ignores late results after navigation',async()=>{
 const first={id:'n1',kind:'like_refund',amount:1,text:'Első visszatérítés.',createdAt:'2026-11-08T10:00:00Z',readAt:null},second={...first,id:'n2',text:'Második visszatérítés.'};let release;const pending=new Promise(resolve=>{release=resolve});const t=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async({offset=0}={})=>offset?pending:{items:[first],total:2,unreadCount:2,offset:0,limit:1,hasMore:true}}});await t.click({page:'notifications'});const loading=t.click({action:'notifications-more'});await settle();await t.click({page:'settings'});release({items:[first,second],total:2,unreadCount:2,offset:1,limit:1,hasMore:false});await loading;assert.equal(t.ctx.location.hash,'#settings');assert.doesNotMatch(t.document.getElementById('app').innerHTML,/Második visszatérítés/);
 const appended=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async({offset=0}={})=>({items:offset?[first,second]:[first],total:2,unreadCount:2,offset,limit:1,hasMore:!offset})}});await appended.click({page:'notifications'});await appended.click({action:'notifications-more'});const html=appended.document.getElementById('app').innerHTML;assert.equal((html.match(/data-notification-id=/g)||[]).length,2);assert.doesNotMatch(html,/notifications-more/);
});
test('empty notifications explain the response window and failed read preserves the unread state',async()=>{
 const empty=await setup();await empty.click({page:'notifications'});assert.match(empty.document.getElementById('app').innerHTML,/Még nincs értesítésed/);assert.match(empty.document.getElementById('app').innerHTML,/14 napig/);
 const item={id:'n1',kind:'like_refund',amount:1,text:'Visszatérítés',createdAt:'2026-11-08T10:00:00Z',readAt:null};const t=await setup({hosted:true,authenticated:true,apiOverrides:{notifications:async()=>({items:[item],total:1,offset:0,limit:50,hasMore:false}),markNotificationRead:async()=>{throw new Error('Nem sikerült menteni.')}}});await t.click({page:'notifications'});await t.click({action:'notification-read',id:'n1'});assert.match(t.document.getElementById('app').innerHTML,/is-unread/);assert.match(t.document.getElementById('toast').textContent,/Nem sikerült menteni/);
});
test('refund ledger and saved paid interest show the credited amount without hiding the original like',async()=>{
 const state=createModel({getItem:()=>null,setItem:()=>{}}).getState();state.decisions=[{id:'refunded',actorKind:'search',actorId:'own-s1',propertyId:'p1',searchId:'own-s1',liked:true,charged:1,createdAt:'2026-10-01T00:00:00Z',refundedAt:'2026-10-15T00:00:00Z',property:{id:'p1',ownerId:'u1',ownerAccountType:'private',title:'Visszatérített otthon',city:'Budapest',price:70,area:60,rooms:2,images:[]}}];state.matches=[];state.ledger=[{id:'refund-ledger',kind:'like_refund',amount:1,description:'Kreditvisszatérítés: 14 napig nem érkezett válasz.',createdAt:'2026-10-15T00:00:00Z'}];const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:async()=>state,matches:async()=>[]}});await t.click({action:'tab',tab:'liked'});let html=t.document.getElementById('app').innerHTML;assert.match(html,/Kredit visszatérítve/);assert.match(html,/\+1 kredit visszatérítve/);assert.match(html,/Visszatérített otthon/);await t.click({page:'credits'});html=t.document.getElementById('app').innerHTML;assert.match(html,/14 nap után visszatérítve/);assert.match(html,/\+1 kredit/);
});

test('public and authentication routes cannot act on a hidden paid discovery candidate',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});const before=t.model.getState();
 for(const route of ['landing','login','register']){
  if(route==='landing')await t.click({action:'landing'});else await t.click({action:'auth-mode',mode:route});
  for(const key of ['ArrowLeft','ArrowRight'])await t.document.handlers.keydown({key,target:{closest:()=>null},preventDefault(){}});
  await t.click({action:'like'});assert.deepEqual(t.model.getState(),before,'A hidden candidate must never make a decision or spend credits');
 }
});

test('a delayed auth route event preserves entered registration details while browser navigation still switches forms',async()=>{
 const t=await setup({hosted:true});await t.click({action:'auth-mode',mode:'register'});
 t.document.getElementById('f-name').value='Teszt Név';t.document.getElementById('f-email').value='teszt@example.test';
 t.windowEvents.hashchange();await settle();assert.equal(t.document.getElementById('f-name').value,'Teszt Név');assert.equal(t.document.getElementById('f-email').value,'teszt@example.test');
 t.ctx.location.hash='#login';t.windowEvents.hashchange();await settle();assert.equal(t.document.getElementById('f-name'),null);assert.ok(t.document.getElementById('hosted-auth-form'));
});

function partialOnlyFixture(){return accountFixture(raw=>{
 raw.matches=[];raw.decisions=[];raw.reports=[];
 raw.properties=raw.properties.filter(item=>item.ownerId==='me'||['p1','p2'].includes(item.id));
 Object.assign(raw.searches.find(item=>item.id==='own-s1'),{minPrice:null,maxPrice:10,minArea:50,maxArea:85,minRooms:2,maxRooms:4,conditions:[],buildings:[],heatingTypes:[],balcony:false,elevator:false});
});}

test('partial recommendations remain hidden without clicking the single consent action',async()=>{
 const t=await setup({initialRaw:partialOnlyFixture()}),before=t.model.getState();
 assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/approximate-decline|Csak tökéletes egyezések|Nem, csak/);
 assert.equal((t.document.getElementById('app').innerHTML.match(/data-action="approximate-accept"/g)||[]).length,1);
 await t.ui.render();assert.deepEqual(t.model.getState(),before);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 await t.click({action:'approximate-accept'});assert.ok(t.document.getElementById('candidate'));assert.match(t.document.getElementById('app').innerHTML,/Részleges egyezések/);
 const candidate=t.model.feed({includeApproximate:true})[0];await t.click({action:'pass'});
 assert.ok(t.model.getState().decisions.some(item=>item.propertyId===candidate.id&&item.actorKind==='search'&&item.liked===false));
});

test('partial consent resets when the active profile or its criteria change',async()=>{
 const t=await setup({initialRaw:partialOnlyFixture()});await t.click({action:'approximate-accept'});assert.ok(t.document.getElementById('candidate'));
 await t.click({action:'activate-one',kind:'search',id:'own-s2'});
 await t.click({action:'activate-one',kind:'search',id:'own-s1'});assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
 await t.click({action:'approximate-accept'});const search=t.model.getState().searches.find(item=>item.id==='own-s1');t.model.saveEntity('search',{...search,maxPrice:11},search.id);await t.ui.render();
 assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
});

test('zero-percent partial cards stay zero and describe deviations without positive hardcoded tags',async()=>{
 const seed=createModel({getItem:()=>null,setItem:()=>{}}).feed()[0];
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:({includeApproximate=false}={})=>includeApproximate?{items:[{...seed,score:0,isExact:false,reasons:['Az ár meghaladja a keretet'],matchDetails:[]}],stage:'approximate'}:{items:[],stage:'empty',requiresApproximateConsent:true,hasApproximate:true}}});
 await t.click({action:'approximate-accept'});const html=t.document.getElementById('app').innerHTML;
 assert.match(html,/0% egyezés/);assert.doesNotMatch(html,/97% egyezés|Árkereten belül|Kedvenc környékeden/);assert.match(html,/Az ár meghaladja a keretet/);
});

test('a late partial response cannot transfer consent or recommendations to another active profile',async()=>{
 const local=createModel({getItem:()=>JSON.stringify(partialOnlyFixture()),setItem:()=>{}}),seed=local.feed({includeApproximate:true})[0];let release;
 const pending=new Promise(resolve=>{release=resolve;});
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>local.getState(),activate:(kind,id)=>local.activate(kind,id),recommendations:({includeApproximate=false}={})=>{
  const active={...local.getState().active};return includeApproximate?pending.then(()=>({active,items:[{...seed,score:15,isExact:false}],stage:'approximate'})):{active,items:[],stage:'empty',requiresApproximateConsent:true,hasApproximate:true};
 }}});
 const accepting=t.click({action:'approximate-accept'});await settle();local.activate('search','own-s2');await t.ui.render();release();await accepting;
 assert.equal(t.ui.getModelState().active.id,'own-s2');assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/Elfogytak a tökéletes egyezések/);
});

test('search specialization appears on seller recommendation cards and own searches',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.match(t.document.getElementById('app').innerHTML,/[\d,]+%-ban fókuszált keresés/);
 await t.click({page:'searches'});assert.match(t.document.getElementById('app').innerHTML,/[\d,]+%-ban fókuszált keresés/);
});


test('discovery shows concise fulfilled conditions and only the other party value for unmet conditions',async()=>{
 const local=createModel({getItem:()=>null,setItem:()=>{}}),seed=local.feed()[0],matchDetails=[
  {key:'rooms',label:'Szobaszám',expected:'legalább 3 szoba',actual:'2 szoba',matches:false},
  {key:'area',label:'Alapterület',expected:'50–80 m²',actual:'65 m²',matches:true},
  {key:'price',label:'Ár',expected:'legfeljebb 85 M Ft',actual:'72,9 M Ft',matches:true},
  {key:'building',label:'Falazat',expected:'Tégla <és> kő',actual:'Panel',matches:false},
  {key:'location',label:'Helyszín',expected:'PRIVATE-LOCATION',actual:'PRIVATE-LOCATION',matches:true},
  {key:'type',label:'Ingatlantípus',expected:'PRIVATE-TYPE',actual:'PRIVATE-TYPE',matches:true}];
 for(const kind of ['property','search']){
  const own=local.getState();own.active={kind:kind==='property'?'search':'property',id:kind==='property'?'own-s1':'own-p1'};
  const card={...seed,kind,score:77,isExact:false,ownerFirstName:'Anna <teszt>',matchDetails};
  const t=await setup({hosted:true,authenticated:true,apiOverrides:{getState:()=>own,recommendations:({includeApproximate=false}={})=>includeApproximate?{items:[card],stage:'approximate'}:{items:[],stage:'empty',requiresApproximateConsent:true}}});
  await t.click({action:'approximate-accept'});
  const html=t.ui.matchingTags(card);
  assert.match(html,/Eltérő feltételek/);assert.match(html,/Teljesülő feltételek/);
  assert.match(html,/Árban megfelelő/);assert.match(html,/Megfelelő alapterület/);
  assert.doesNotMatch(html,/PRIVATE-LOCATION|PRIVATE-TYPE|data-criterion="(?:location|type)"/);
  assert.doesNotMatch(html,/50–80|65 m²|85 M Ft|72,9 M Ft|Keresés:|Ingatlan:/,'Fulfilled criteria never repeat detailed bounds or listing values');
  assert.match(html,/criterion-passed/);assert.match(html,/criterion-different/);
  if(kind==='property'){
   assert.match(html,/2 szoba/);assert.match(html,/Panel/);
   assert.doesNotMatch(html,/legalább 3 szoba|Tégla/,'A buyer sees only the foreign property values, not their own search');
  }else{
   assert.match(html,/legalább 3 szoba/);assert.match(html,/Tégla &lt;és&gt; kő/);
   assert.doesNotMatch(html,/2 szoba|Panel|<és>/,'A seller sees only the foreign search values, escaped as plain text');
  }
  assert.match(t.document.getElementById('app').innerHTML,/Anna &lt;teszt&gt;/);
 }
});

test('hard-only match details do not produce a fulfilled condition section or revive legacy hard-gate reasons',async()=>{
 const t=await setup(),card={kind:'property',isExact:true,reasons:['Megfelelő elhelyezkedés','Megfelelő ingatlantípus'],matchDetails:[
  {key:'location',label:'Helyszín',expected:'Debrecen',actual:'Debrecen',matches:true},
  {key:'type',label:'Ingatlantípus',expected:'Lakás',actual:'Lakás',matches:true}]};
 assert.equal(t.ui.matchingTags(card),'');
});

test('public cards display listing titles, discreet types and first names',async()=>{
 const t=await setup({hosted:true,hash:''}),html=t.document.getElementById('app').innerHTML;
 for(const text of ['Kertes otthont keresünk','Napfényes erkélyes otthon','Anna','Péter','lakást keres','landing-ad-title','landing-type','owner-first-name'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/Lakást keresnek|Eladó lakás/);
});

test('seller insights are property scoped, anonymous and show an active package without another purchase',async()=>{
 const m=createModel({getItem:()=>null,setItem:()=>{}}),own=m.getState(),property=own.properties[0],calls=[];
 const insights={propertyId:property.id,stats:{uniqueViewers:24,buyerLikes:7,sellerLikes:5,matchedViewers:3,matchRate:12.5},feedback:{total:2,items:[{id:'r1',reason:'layout',label:'Elrendezés',createdAt:'2026-11-10T10:00:00Z'}],reasonCounts:[{reason:'layout',label:'Elrendezés',count:2}],offset:0,limit:50,hasMore:false},activePackage:{id:'pack',size:10,receivedCount:2,remaining:8,enabled:true,createdAt:'2026-11-10T10:00:00Z',expiresAt:'2026-11-24T10:00:00Z',status:'active'},packages:[]};
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getPropertyInsights:async(id)=>{calls.push(id);return insights;}}});
 await t.click({action:'property-insights',id:property.id});const html=t.document.getElementById('app').innerHTML;
 assert.equal(calls.at(-1),property.id);for(const text of ['Statisztikák és visszajelzések','Látták','Kedvelték','Kedvelt keresések','12,5','2 db','2 / 10','8 még hiányzik','név nélkül'])assert.ok(html.includes(text),text);
 assert.doesNotMatch(html,/data-action="feedback-packages"/,'An active package cannot offer another purchase');
 assert.doesNotMatch(html,/data-action="feedback-toggle"|szüneteltet|folytathatod/,'An active paid package cannot be paused');
 await t.click({action:'feedback-toggle',id:property.id,enabled:'false'});assert.equal(insights.activePackage.enabled,true,'An obsolete pause action cannot alter the package');
 assert.doesNotMatch(t.document.getElementById('app').innerHTML,/buyerId|searchRequestId|PRIVATE-CONTACT/);
});

test('package purchase shows sizes and cost, and retains its UUID when a failed payment is retried',async()=>{
 const attempts=[],t=await setup({hosted:true,authenticated:true,apiOverrides:{buyFeedbackPackage:async(id,size,request)=>{attempts.push({id,size,request});throw new Error('Átmeneti hiba');}}});
 const property=t.model.getState().properties[0];t.ui.openFeedbackPackages(property.id);let html=t.document.getElementById('modal-root').innerHTML;
 for(const size of [10,20,50])assert.match(html,new RegExp('data-size="'+size+'"'));assert.match(html,/két hétig/);assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/válaszok árát|visszajelzések árát/);
 await t.click({action:'feedback-plan',id:property.id,size:'10'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/Csomag indítása · 10 kredit/);
 const request=html.match(/data-request="([^"]+)"/)[1];assert.match(request,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
 await t.click({action:'feedback-buy',id:property.id,size:'10',request});await t.click({action:'feedback-buy',id:property.id,size:'10',request});
 assert.equal(attempts.length,2);assert.equal(attempts[0].request,request);assert.equal(attempts[1].request,request);assert.match(t.document.getElementById('modal-root').innerHTML,/Csomag indítása/);
});

test('pending feedback blocks the next card and sends a single button choice before closing',async()=>{
 const options=feedbackHelpers.FEEDBACK_OPTIONS,prompt={id:'invitation',propertyId:'p1',title:'Segíts Péternek egy visszajelzéssel',question:'Miért nem tetszett az ingatlan?',options},impressions=[],answers=[];let pending=prompt,finish;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:async()=>({feedbackPrompt:pending}),recordImpression:async(...args)=>{impressions.push(args);},answerFeedback:async(id,reason)=>{answers.push({id,reason});await new Promise(resolve=>{finish=resolve;});pending=null;return{accepted:true,alreadyAnswered:false};}}});
 let html=t.document.getElementById('modal-root').innerHTML;assert.equal(t.document.getElementById('candidate'),null);assert.equal(impressions.length,0);
 assert.match(html,/Segíts Péternek egy visszajelzéssel/);assert.match(html,/Miért nem tetszett az ingatlan/);assert.equal((html.match(/data-action="feedback-answer"/g)||[]).length,8);assert.doesNotMatch(html,/modal-close|data-action="close"/);
 await t.click({action:'close'});assert.match(t.document.getElementById('modal-root').innerHTML,/feedback-survey/);
 const answering=t.click({action:'feedback-answer',reason:'layout'});await settle();assert.deepEqual(answers,[{id:'invitation',reason:'layout'}]);assert.match(t.document.getElementById('modal-root').innerHTML,/feedback-survey/,'The window stays until persistence succeeds');
 finish();await answering;await settle();assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.ok(t.document.getElementById('candidate'));assert.equal(impressions.length,1);
});

test('feedback decline and expired requests continue discovery without sending a paid response',async()=>{
 for(const expired of [false,true]){let pending={id:'survey',propertyId:'p1',title:'Segíts Annának egy visszajelzéssel',options:feedbackHelpers.FEEDBACK_OPTIONS},answer;
  const t=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:async()=>pending,answerFeedback:async(id,reason)=>{answer={id,reason};pending=null;if(expired)throw Object.assign(new Error('Lejárt'),{status:410});return {accepted:false,alreadyAnswered:false};}}});
  await t.document.handlers.keydown({key:'Escape',preventDefault(){this.defaultPrevented=true;}});assert.deepEqual(answer,{id:'survey',reason:'decline'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.ok(t.document.getElementById('candidate'));
 }
});

test('discovery records only the visible buyer card once and ignores stale visibility callbacks',async()=>{
 const observers=[],calls=[];class Observer{constructor(callback){this.callback=callback;observers.push(this);}observe(){}disconnect(){}}
 const t=await setup({hosted:true,authenticated:true,IntersectionObserver:Observer,apiOverrides:{recordImpression:async(...args)=>calls.push(args)}});
 assert.equal(calls.length,0);const first=observers.at(-1);first.callback([{isIntersecting:false,intersectionRatio:0}]);await settle();assert.equal(calls.length,0);
 first.callback([{isIntersecting:true,intersectionRatio:.5}]);await settle();assert.equal(calls.length,1);assert.equal(calls[0][1],t.model.getState().active.id);
 await t.ui.render();observers.at(-1).callback([{isIntersecting:true,intersectionRatio:.5}]);await settle();assert.equal(calls.length,1,'Repaints do not add another viewer');
 await t.click({page:'properties'});first.callback([{isIntersecting:true,intersectionRatio:1}]);await settle();assert.equal(calls.length,1,'A stale callback cannot count a hidden candidate');
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});assert.equal(calls.length,1,'Seller-side search cards never count as property exposure');
});

test('focused-search badge opens a plain explanation and separates focus from the match percentage',async()=>{
 const t=await setup();await t.click({action:'activate-one',kind:'property',id:'own-p1'});
 let html=t.document.getElementById('app').innerHTML;assert.match(html,/[\d,]+%-ban fókuszált keresés/);assert.match(html,/data-action="focus-info"/);assert.doesNotMatch(html,/Specializáltság:/);
 await t.click({action:'focus-info'});html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/Mit jelent a fókuszált keresés\?/);assert.match(html,/szűkebb ár-, méret- és szobatartomány/);assert.match(html,/kártya tetején látható egyezési százalék/);
});

test('the report dialog contains ordered radios only and a duplicate report persists as its own reason',async()=>{
 const t=await setup();await t.click({action:'report-account',kind:'property',id:'p1'});const html=t.document.getElementById('modal-root').innerHTML;
 assert.match(html,/aria-labelledby="report-question"/);assert.equal((html.match(/type="radio"/g)||[]).length,accountHelpers.REPORT_REASON_OPTIONS.length);assert.doesNotMatch(html,/<select|Jelentés oka|A következő fejezeted|profilnál|Korábban jelzett/);
 const values=[...html.matchAll(/type="radio" name="reportReason" value="([^"]+)"/g)].map(match=>match[1]);assert.deepEqual(values,accountHelpers.REPORT_REASON_OPTIONS.map(option=>option.value));
 chooseReport(t,'duplicate_listing');await t.click({action:'confirm-report',kind:'property',id:'p1'});assert.equal(t.model.getState().reportedEntities[0].reason,'duplicate_listing');
});

test('seller insights omit measurement and frequency boilerplate and express refunds only as credits',async()=>{
 const t=await setup();await t.click({action:'property-insights',id:'own-p1'});let html=t.document.getElementById('app').innerHTML;
 assert.doesNotMatch(html,/A megjelenések mérése|1 visszajelzés = 1 kredit|A keresők csak ritkán kapnak/);
 await t.click({action:'feedback-packages',id:'own-p1'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/hiányzó.*árát/);
 await t.click({action:'feedback-plan',id:'own-p1',size:'10'});html=t.document.getElementById('modal-root').innerHTML;assert.match(html,/kreditet írunk jóvá/);assert.doesNotMatch(html,/hiányzó.*árát/);
});

test('feedback trial controls require explicit hosted-test capability and reset through the model',async()=>{
 const scenario={available:true,role:'buyer',propertyId:'own-p1',searchId:'own-s1',buyerEmail:'visszajelzes-kereso@otthonra.local',sellerEmail:'visszajelzes-elado@otthonra.local'};let resets=0,release;
 const t=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>scenario,resetFeedbackScenario:()=>{resets++;return new Promise(resolve=>{release=resolve;});}}});
 assert.match(t.document.getElementById('app').innerHTML,/Visszajelzés-próba|visszajelzes-kereso@otthonra.local/);
 assert.ok(t.document.getElementById('candidate'));const pending=t.click({action:'feedback-scenario-reset'});await settle();assert.equal(resets,1);assert.equal(t.document.getElementById('candidate'),null);assert.match(t.document.getElementById('app').innerHTML,/feedback-scenario-resetting/);release();await pending;assert.equal(t.ctx.location.hash,'#discover');assert.ok(t.document.getElementById('candidate'));
 const selected=[];const seller=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>({...scenario,role:'seller'}),resetFeedbackScenario:()=>{},getPropertyInsights:id=>{selected.push(id);return {stats:{},feedback:{items:[],reasonCounts:[]}};}}});await seller.click({action:'feedback-scenario-reset'});assert.equal(seller.ctx.location.hash,'#insights');assert.equal(selected.at(-1),scenario.propertyId);
 const ordinary=await setup({hosted:true,authenticated:true,apiOverrides:{getFeedbackScenario:()=>({available:false})}});assert.doesNotMatch(ordinary.document.getElementById('app').innerHTML,/feedback-scenario-reset/);
 const production=await setup({hosted:true,authenticated:true,environment:'production',apiOverrides:{getFeedbackScenario:()=>{throw new Error('No test endpoint in production');}}});assert.doesNotMatch(production.document.getElementById('app').innerHTML,/feedback-scenario-reset|Nem érhető el a munkatér/);
});

function editorChoice(t,name,value){
 const ids=[...t.document.html.matchAll(new RegExp('<input\\b[^>]*\\bid="([^\"]+)"[^>]*\\bname="'+name+'"[^>]*>','g'))].map(match=>match[1]);
 const choice=ids.map(id=>t.document.getElementById(id)).find(input=>input.value===String(value));assert.ok(choice,`Missing ${name} choice ${value}`);return choice;
}
async function advanceEditor(t,target){
 for(let attempt=0;editorStep(t)<target&&attempt<5;attempt++){
  const before=editorStep(t);await editorAction(t,'editor-next');assert.equal(editorStep(t),before+1,'A valid step must advance exactly once');
 }
 assert.equal(editorStep(t),target);
}

test('search editor exposes named stages, validates the current topic and retains all mounted values when revisiting',async()=>{
 const t=await setup(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('search');const form=t.document.getElementById('entity-form'),html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Helyszín és típus','Ár és méret','Ingatlanjellemzők','Kényelem és felszereltség','További elképzelések'])assert.ok(html.includes(label),label);
 assert.equal(editorStep(t),0);assert.equal(t.document.getElementById('editor-back').hidden,true);
 await editorAction(t,'editor-next');assert.equal(editorStep(t),0);assert.equal(t.document.activeElement.id,'f-title');
 assert.ok(t.document.getElementById('f-title').reportedValidity>0);assert.equal(saved.length,0);
 t.document.getElementById('f-title').value='Megőrzött keresési elképzelés';chooseLocation(t,'city:Debrecen');chooseLocation(t,'city:Hajdúszoboszló');
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);
 assert.equal(t.document.getElementById('editor-step-button-1').getAttribute('aria-current'),'step');
 assert.equal(t.document.getElementById('editor-step-button-0').getAttribute('data-editor-state'),'completed');
 t.document.getElementById('f-maxPrice').value='125';t.document.getElementById('f-minArea').value='65';t.document.getElementById('f-minRooms').value='3';
 for(const name of ['minPrice','maxArea','maxRooms'])t.document.getElementById('f-'+name).value='';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 editorChoice(t,'conditions','Jó').checked=true;editorChoice(t,'conditions','Új/felújított').checked=true;editorChoice(t,'buildings','Tégla').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 editorChoice(t,'heatingTypes','Hőszivattyú').checked=true;editorChoice(t,'floors','0').checked=true;t.document.getElementById('f-ceilingHeight').value='3 m feletti';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);t.document.getElementById('f-description').value='Fényes, csendes otthont szeretnénk.';
 await editorAction(t,'editor-back');assert.equal(editorStep(t),3);assert.equal(editorChoice(t,'heatingTypes','Hőszivattyú').checked,true);
 await editorAction(t,'editor-step-button-0');assert.equal(editorStep(t),0);
 assert.match(t.document.getElementById('location-chips').innerHTML,/Debrecen/);assert.match(t.document.getElementById('location-chips').innerHTML,/Hajdúszoboszló/);
 assert.equal(t.document.getElementById('f-title').value,'Megőrzött keresési elképzelés');assert.equal(t.document.getElementById('f-maxPrice').value,'125');
 assert.equal(editorChoice(t,'conditions','Új/felújított').checked,true);assert.equal(t.document.getElementById('f-description').value,'Fényes, csendes otthont szeretnénk.');
 assert.equal(t.document.getElementById('entity-form'),form,'Step navigation must preserve the mounted form');assert.equal(saved.length,0,'Navigation never saves a draft entity');
 await editorAction(t,'editor-step-button-4');assert.equal(editorStep(t),4);submitEditor(t);await settle();
 assert.equal(saved.length,1);const result=t.model.getState().searches.find(item=>item.title==='Megőrzött keresési elképzelés');assert.ok(result);
 assert.deepEqual([...result.locationIds],['city:Debrecen','city:Hajdúszoboszló']);assert.equal(result.maxPrice,125);assert.equal(result.minArea,65);assert.equal(result.minRooms,3);
 for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(result[name],null);
 assert.deepEqual([...result.conditions],['Jó','Új/felújított']);assert.deepEqual([...result.heatingTypes],['Hőszivattyú']);assert.deepEqual([...result.floors],[0]);assert.equal(result.description,'Fényes, csendes otthont szeretnénk.');
 assert.match(t.document.getElementById('modal-root').innerHTML,/Ingatlanok felfedezése/);
});

test('seller wizard preserves required house plot, nullable amenities, image URLs and multiple parking choices through backtracking',async()=>{
 const t=await setup(),before=t.model.getState(),saved=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{saved.push(args);return save(...args);};
 t.ui.openEditor('property');const html=t.document.getElementById('modal-root').innerHTML;
 for(const label of ['Alapadatok','Ár és méret','Ingatlanjellemzők','Felszereltség','Képek és leírás'])assert.ok(html.includes(label),label);
 t.document.getElementById('f-title').value='Lépésenként megőrzött családi ház';chooseLocation(t,'city:Solymár');
 const type=t.document.getElementById('f-type');type.value='Ház';type.handlers.change({target:type,currentTarget:type});
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1);
 for(const [name,value] of Object.entries({price:'110.5',area:'130.5',wholeRooms:'3',halfRooms:'1'}))t.document.getElementById('f-'+name).value=value;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),1,'A house cannot advance without its plot');assert.equal(t.document.activeElement.id,'f-lotArea');
 t.document.getElementById('f-lotArea').value='720';await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 t.document.getElementById('f-condition').value='Jó';t.document.getElementById('f-building').value='Tégla';
 await editorAction(t,'editor-next');assert.equal(editorStep(t),3);
 for(const [name,value] of Object.entries({heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',insulated:'false',airConditioning:'true',solarPanels:'',energyRating:'A+'}))t.document.getElementById('f-'+name).value=value;
 editorChoice(t,'parkingTypes','Garázs').checked=true;editorChoice(t,'parkingTypes','Udvari beálló').checked=true;
 await editorAction(t,'editor-next');assert.equal(editorStep(t),4);
 t.document.getElementById('property-images').value='https://example.test/elol.jpg\nhttps://example.test/kert.jpg';t.document.getElementById('f-description').value='Az eddig bevitt részletek maradjanak meg.';
 await editorAction(t,'editor-step-button-1');assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('f-lotArea').value,'720');
 await editorAction(t,'editor-step-button-3');assert.equal(t.document.getElementById('f-insulated').value,'false');assert.equal(t.document.getElementById('f-solarPanels').value,'');assert.equal(editorChoice(t,'parkingTypes','Garázs').checked,true);
 await editorAction(t,'editor-step-button-4');assert.match(t.document.getElementById('property-images').value,/kert\.jpg/);assert.equal(saved.length,0);
 submitEditor(t);await settle();assert.equal(saved.length,1);
 const result=t.model.getState().properties.find(item=>item.title==='Lépésenként megőrzött családi ház');assert.ok(result);assert.equal(result.lotArea,720);assert.equal(result.insulated,false);assert.equal(result.airConditioning,true);assert.equal(result.solarPanels,null);assert.equal(result.wholeRooms,3);assert.equal(result.halfRooms,1);
 assert.deepEqual([...result.parkingTypes],['Udvari beálló','Garázs']);assert.deepEqual([...result.images],['https://example.test/elol.jpg','https://example.test/kert.jpg']);assert.equal(result.floor,null);assert.equal(result.balcony,false);assert.equal(result.elevator,false);
 assert.deepEqual(t.model.getState().active,before.active);
});

test('final wizard submission revisits an invalid earlier topic instead of silently saving hidden invalid controls',async()=>{
 const t=await setup(),calls=[],save=t.model.saveEntity;t.model.saveEntity=(...args)=>{calls.push(args);return save(...args);};
 t.ui.openEditor('search','own-s1');await advanceEditor(t,4);
 t.document.getElementById('f-maxPrice').value='';submitEditor(t);await settle();
 assert.equal(editorStep(t),1);assert.equal(t.document.activeElement.id,'f-maxPrice');assert.equal(calls.length,0);assert.equal(t.document.getElementById('f-maxPrice').hidden,false);
 t.document.getElementById('f-maxPrice').value='95';await advanceEditor(t,4);submitEditor(t);await settle();assert.equal(calls.length,1);assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').maxPrice,95);
 assert.equal(t.document.getElementById('modal-root').innerHTML,'','An edit does not open the new-search activation offer');
});

test('wizard range errors stay in the price and size topic and future-step clicks cannot bypass validation',async()=>{
 const t=await setup();t.ui.openEditor('search');
 await editorAction(t,'editor-step-button-4');assert.equal(editorStep(t),0,'A future topic cannot bypass missing required earlier details');assert.equal(t.document.activeElement.id,'f-title');
 t.document.getElementById('f-title').value='Ártartomány ellenőrzése';chooseLocation(t,'city:Debrecen');await editorAction(t,'editor-next');
 t.document.getElementById('f-minPrice').value='100';t.document.getElementById('f-maxPrice').value='80';await editorAction(t,'editor-next');assert.equal(editorStep(t),1);assert.ok(t.document.activeElement.validationMessage);
 t.document.getElementById('f-minPrice').value='';await editorAction(t,'editor-next');assert.equal(editorStep(t),2);
 await editorAction(t,'editor-back');assert.equal(editorStep(t),1);assert.equal(t.document.getElementById('f-maxPrice').value,'80');
});

test('wizard editing and cancellation preserve the saved entity and clean up location listeners',async()=>{
 const t=await setup(),before=t.model.getState(),pointers=t.document.listenerCount('pointerdown'),focus=t.document.listenerCount('focusin');
 t.ui.openEditor('search','own-s1');const originalTitle=t.document.getElementById('f-title').value;assert.equal(originalTitle,before.searches.find(item=>item.id==='own-s1').title);
 t.document.getElementById('f-title').value='Ez még csak piszkozat';await advanceEditor(t,3);await editorAction(t,'editor-step-button-0');assert.equal(t.document.getElementById('f-title').value,'Ez még csak piszkozat');
 await t.click({action:'close'});assert.equal(t.document.getElementById('modal-root').innerHTML,'');assert.deepEqual(t.model.getState(),before);
 assert.equal(t.document.listenerCount('pointerdown'),pointers);assert.equal(t.document.listenerCount('focusin'),focus);
});

test('discovery dock follows the active candidate and disappears for empty feeds, partial consent and pending feedback',async()=>{
 const t=await setup();let html=t.document.getElementById('app').innerHTML;assert.match(html,/discovery-decision-dock/);assert.match(html,/class="card-actions"/);
 await t.click({action:'activate-one',kind:'property',id:'own-p1'});html=t.document.getElementById('app').innerHTML;assert.match(html,/discovery-decision-dock/);assert.match(html,/Kedvelés<\/span><small>2 kredit/);
 await t.click({page:'properties'});assert.doesNotMatch(t.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const empty=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:()=>({items:[],stage:'empty'})}});assert.doesNotMatch(empty.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const partial=await setup({hosted:true,authenticated:true,apiOverrides:{recommendations:()=>({items:[],stage:'empty',requiresApproximateConsent:true})}});assert.doesNotMatch(partial.document.getElementById('app').innerHTML,/discovery-decision-dock/);
 const pending=await setup({hosted:true,authenticated:true,apiOverrides:{pendingFeedback:()=>({feedbackPrompt:{id:'pending',title:'Segíts egy visszajelzéssel',options:feedbackHelpers.FEEDBACK_OPTIONS}})}});assert.doesNotMatch(pending.document.getElementById('app').innerHTML,/discovery-decision-dock/);
});

test('wizard final-save retries cannot duplicate a pending write or navigate away from the submitted topic',async()=>{
 const t=await setup(),save=t.model.saveEntity,calls=[];let release;
 t.ui.openEditor('search','own-s1');await advanceEditor(t,4);
 t.document.getElementById('f-description').value='Egyetlen mentésből létrejövő módosítás.';
 t.model.saveEntity=async(...args)=>{calls.push(args);await new Promise(resolve=>{release=resolve;});return save(...args);};
 submitEditor(t);await settle();assert.equal(calls.length,1);
 submitEditor(t);await editorAction(t,'editor-back');assert.equal(editorStep(t),4);assert.equal(calls.length,1);
 release();await settle();assert.equal(calls.length,1);assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 assert.equal(t.model.getState().searches.find(item=>item.id==='own-s1').description,'Egyetlen mentésből létrejövő módosítás.');
});

test('editing a saved holiday-home property or search preserves its existing type throughout the wizard and final save',async()=>{
 let raw;const seed=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});seed.activate('search','own-s1');
 raw.properties.find(item=>item.id==='own-p1').type='Nyaraló';raw.searches.find(item=>item.id==='own-s1').type='Nyaraló';
 for(const kind of ['property','search']){
  const t=await setup({initialRaw:raw}),id=kind==='property'?'own-p1':'own-s1';
  t.ui.openEditor(kind,id);const type=t.document.getElementById('f-type');assert.equal(type.value,'Nyaraló','A saved type outside the creation choices must remain selected');
  await advanceEditor(t,4);await editorAction(t,'editor-step-button-0');assert.equal(t.document.getElementById('f-type'),type);assert.equal(type.value,'Nyaraló');
  await editorAction(t,'editor-step-button-4');submitEditor(t);await settle();
  const collection=kind==='property'?t.model.getState().properties:t.model.getState().searches;
  assert.equal(collection.find(item=>item.id===id).type,'Nyaraló','Saving unrelated edits must not silently convert a holiday home into a flat');
  assert.equal(t.document.getElementById('modal-root').innerHTML,'');
 }
});
