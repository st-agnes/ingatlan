/** Navigate the real themed editor without unhiding fields or bypassing validation. */
import assert from 'node:assert/strict';

async function press(page, locator, interact) {
  if (interact) return interact(locator);
  return await page.evaluate(() => navigator.maxTouchPoints > 0) ? locator.tap() : locator.click();
}

export async function editorStep(page, index, interact) {
  const target = page.locator(`#editor-step-button-${index}`);
  await press(page, target, interact);
  await page.waitForFunction(expected => {
    const section = document.getElementById(`editor-step-${expected}`);
    return section && !section.hidden;
  }, index);
  assert.equal(await target.getAttribute('aria-current'), 'step');
}

/** Choose a type, retain the selection screen, then explicitly continue. */
export async function choosePropertyType(page, value, interact) {
  await editorStep(page, 1, interact);
  const card = page.locator(`[data-property-type="${value}"]`);
  await press(page, card, interact);
  assert.equal(await page.locator('#f-type').inputValue(), value);
  assert.equal(await card.getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('#editor-step-button-1').getAttribute('aria-current'), 'step', 'Choosing a type must wait for the explicit Next action');
  await press(page, page.locator('#editor-next'), interact);
  await page.waitForFunction(() => !document.getElementById('editor-step-2')?.hidden);
  assert.equal(await page.locator('#editor-step-button-2').getAttribute('aria-current'), 'step');
}

/** Set or clear an optional illustrated single choice through its real card. */
export async function setAttributeChoice(page, name, value, interact) {
  const input = await editorField(page, `#f-${name}`, interact);
  const before = await input.inputValue();
  if (before === value) return input;
  const card = page.locator(`[data-attribute-name="${name}"][data-attribute-value="${value || before}"]`);
  await press(page, card, interact);
  assert.equal(await input.inputValue(), value);
  return input;
}

// Storage/focus refresh can replace the form; inspect only the current connected DOM.
async function liveEditorNavigation(page) {
 for(let attempt=0;attempt<20;attempt++){
  const proof=await page.evaluate(()=>{
   const form=document.getElementById('entity-form'),nav=document.getElementById('editor-navigation'),content=form?.querySelector('.editor-content'),section=form?.querySelector('.editor-step:not([hidden])'),header=content?.querySelector('#editor-header');
   if(!form?.isConnected||!nav?.isConnected||!content?.isConnected||!section?.isConnected||!header?.isConnected)return null;
   const rect=element=>{const b=element.getBoundingClientRect();return{left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,height:b.height,position:getComputedStyle(element).position};};
   const visible=element=>element.getClientRects().length>0&&getComputedStyle(element).visibility!=='hidden';
   const viewport={left:visualViewport?.offsetLeft||0,top:visualViewport?.offsetTop||0,width:visualViewport?.width||innerWidth,height:visualViewport?.height||innerHeight};
   const heading=header.querySelector('h2'),reference=document.getElementById('editor-heading-1');
   return {mobile:innerWidth<=720,viewport,form:{...rect(form),client:form.clientWidth,scroll:form.scrollWidth},nav:{...rect(nav),background:getComputedStyle(nav).backgroundColor},content:rect(content),section:rect(section),
    header:{...rect(header),hasHeading:!!heading&&content.contains(heading),eyebrows:form.querySelectorAll('.eyebrow').length},
    topics:[...nav.querySelectorAll('[data-action="editor-step"]')].map(button=>{const box=rect(button),top=document.elementFromPoint(box.left+box.width/2,box.top+box.height/2);return{...box,hit:button===top||button.contains(top)};}),
    headings:[...section.querySelectorAll('h3,legend,label')].filter(element=>visible(element)&&!element.classList.contains('editor-topic-anchor')).map(element=>({tag:element.tagName,text:element.textContent.trim(),size:parseFloat(getComputedStyle(element).fontSize),weight:Number(getComputedStyle(element).fontWeight)})),
    referenceHeadingSize:parseFloat(getComputedStyle(reference).fontSize),
    actions:['top','bottom'].map(where=>{const group=form.querySelector('.editor-navigation-'+where);return group?{...rect(group),buttons:[...group.querySelectorAll('button')].filter(button=>button.offsetParent!==null).map(button=>({id:button.id,disabled:button.disabled,...rect(button)}))}:null;})};
  });
  if(proof&&proof.nav.position!=='')return proof;
  if(attempt<19)await page.waitForTimeout(50);
 }
 assert.fail('The current responsive navigation, content header and both action groups must mount within one second');
}

function assertMobileMenu(proof){
 const {nav,viewport,topics}=proof,bottom=viewport.top+viewport.height,right=viewport.left+viewport.width;
 assert.equal(nav.position,'fixed','Mobile topics belong in one fixed bottom strip');
 assert.ok(nav.left>=viewport.left-1&&nav.right<=right+1&&nav.top>=viewport.top&&nav.bottom<=bottom+1,'The compact menu must fit the visible viewport');
 assert.ok(Math.abs(nav.bottom-bottom)<=2,'The menu must follow the visible viewport bottom, including the keyboard');
 assert.ok(nav.height<=80,'Six mobile topics must use a compact strip, including safe-area padding');
 for(let i=0;i<topics.length;i++){
  const topic=topics[i];assert.ok(topic.top>=nav.top-1&&topic.bottom<=nav.bottom+1&&topic.left>=nav.left-1&&topic.right<=nav.right+1,'Every mobile topic must fit the compact strip');
  if(i)assert.ok(Math.abs(topic.top-topics[0].top)<=1&&topic.left>=topics[i-1].right-1,'All six topics share one horizontal row');
  assert.equal(topic.hit,true,'Every mobile topic must remain directly clickable');
 }
}

async function revealEditorControl(page,locator){
 await locator.scrollIntoViewIfNeeded();
 await locator.evaluate(async element=>{
  const host=element.closest('.modal')||document.scrollingElement,nav=document.getElementById('editor-navigation'),viewportTop=visualViewport?.offsetTop||0;
  let limit=viewportTop+(visualViewport?.height||innerHeight);
  if(nav&&getComputedStyle(nav).position==='fixed')limit=Math.min(limit,nav.getBoundingClientRect().top);
  const box=element.getBoundingClientRect();
  if(box.bottom>limit-8)host.scrollBy({top:box.bottom-limit+8,behavior:'instant'});
  else if(box.top<viewportTop+8)host.scrollBy({top:box.top-viewportTop-8,behavior:'instant'});
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
 });
 return locator.evaluate(element=>{
  const box=element.getBoundingClientRect(),top=document.elementFromPoint(box.x+box.width/2,box.y+box.height/2),nav=document.getElementById('editor-navigation'),viewportTop=visualViewport?.offsetTop||0;
  const limit=nav&&getComputedStyle(nav).position==='fixed'?nav.getBoundingClientRect().top:viewportTop+(visualViewport?.height||innerHeight);
  return box.top>=viewportTop-1&&box.bottom<=limit+1&&(element===top||element.contains(top));
 });
}

/** Desktop uses a left panel; mobile fixes only compact topics, keeping actions in flow. */
export async function assertEditorNavigation(page,{scroll=false,lastField=false}={}) {
 const original=await page.evaluate(()=>{const host=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;return host.scrollTop;});
 const proof=await liveEditorNavigation(page);
 assert.ok(proof.form.scroll<=proof.form.client+1,'Responsive topics and content must fit without horizontal scrolling');
 assert.ok(proof.header.hasHeading&&proof.header.eyebrows===0,'The main heading belongs only to the content column without a redundant entity-type eyebrow');
 assert.ok(proof.header.left>=proof.content.left-1&&proof.header.right<=proof.content.right+1,'The main heading must stay above the content, not above the topic menu');
 assert.equal(proof.topics.length,6);
 if(proof.mobile)assertMobileMenu(proof);
 else{
  assert.ok(!['fixed','sticky'].includes(proof.nav.position),'Desktop topics remain in a separate left panel');
  assert.ok(proof.nav.right<=proof.content.left-1,'The topic panel must be separated from the form content');
  assert.ok(!['transparent','rgba(0, 0, 0, 0)'].includes(proof.nav.background),'The left-side topic panel needs its own visible background');
  for(let index=1;index<proof.topics.length;index++)assert.ok(proof.topics[index].top>=proof.topics[index-1].bottom-1,'Each desktop topic occupies its own vertical row');
 }
 assert.ok(proof.content.width>=140,'The form content must retain a usable width');
 assert.ok(proof.actions.every(Boolean),'Both top and bottom action groups are required');
 for(const group of proof.actions){
  assert.ok(!['fixed','sticky'].includes(group.position),'Previous/Next/Save controls must follow normal document flow');
  assert.ok(group.left>=proof.content.left-1&&group.right<=proof.content.right+1,'Action groups must stay within the form column');
  assert.ok(group.buttons.length>=1,'The current screen needs an actionable navigation button at both ends');
  for(const button of group.buttons)assert.ok(button.left>=group.left-1&&button.right<=group.right+1,'Action buttons must not overflow their column');
  assert.ok(Math.abs(group.buttons.at(-1).right-group.right)<=2,'The primary action is aligned to the right');
 }
 assert.ok(proof.actions[0].bottom<=proof.section.top+1,'Top actions must precede the current fields');
 assert.ok(proof.actions[1].top>=proof.section.bottom-1,'Bottom actions must follow the current fields');
 for(const name of ['next','back','save']){
  const bottom=page.locator('#editor-'+name),top=page.locator('#editor-'+name+'-top');
  assert.equal(await top.count(),1);assert.equal(await bottom.count(),1);
  assert.equal(await top.isVisible(),await bottom.isVisible(),`Both ${name} actions must reflect the same topic state`);
  if(await bottom.isVisible())assert.equal(await top.isEnabled(),await bottom.isEnabled());
 }
 assert.equal(await page.locator('#editor-step-status').count(),0,'The redundant X-of-Y sentence must be absent');
 assert.doesNotMatch(await page.locator('#entity-form').innerText(),/Később folytatom|Csak azt jelöld meg, ami fontos/);
 const index=await page.locator('.editor-step:visible').getAttribute('data-editor-step');
 if(index==='2'){
  const titles=proof.headings.filter(heading=>heading.tag==='H3');
  assert.deepEqual(titles.map(heading=>heading.text),['Ár','Méret'],'Price and size have separate visible section headings');
  for(const title of titles)assert.equal(title.size,proof.referenceHeadingSize,'Price/size headings retain the established topic-title size');
 }else if(index==='3'){
  assert.ok(!proof.headings.some(heading=>heading.text==='Ingatlanjellemzők'),'The generic attribute title must not compete with its subsections');
  const expected=['Állapot','Építés éve','Kilátás','Falazat','Belmagasság'];
  if(await page.locator('#f-type').inputValue()!=='Ház')expected.splice(1,0,'Emelet');
  for(const label of expected){const heading=proof.headings.find(heading=>heading.text.startsWith(label));assert.ok(heading,`The ${label} subsection must retain its accessible label`);assert.equal(heading.size,proof.referenceHeadingSize,`${label} uses the topic-heading size`);}
 }
 if(scroll&&proof.mobile){
  for(const fraction of [0,.5,1]){
   await page.evaluate(async fraction=>{const host=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;host.scrollTo({top:(host.scrollHeight-host.clientHeight)*fraction,behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));},fraction);
   assertMobileMenu(await liveEditorNavigation(page));
  }
 }
 if(scroll){
  for(const selector of ['.editor-navigation-top','.editor-navigation-bottom']){
   const button=page.locator(selector+' button:visible:not(:disabled)').last();
   assert.equal(await revealEditorControl(page,button),true,'Both normal-flow primary actions must be reachable and directly clickable above the menu');
  }
 }
 if(lastField){
  const field=page.locator('.editor-step:visible input:not([type="hidden"]):visible,.editor-step:visible select:visible,.editor-step:visible textarea:visible,.editor-step:visible button:visible').last();
  assert.equal(await revealEditorControl(page,field),true,'The last field must remain unobscured by navigation');
 }
 if(scroll||lastField)await page.evaluate(top=>{const host=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;host.scrollTo({top,behavior:'instant'});},original);
}

/** A visual viewport signal exercises the real keyboard-offset CSS while layout height stays put. */
export async function installEditorViewportMock(context){
 await context.addInitScript(()=>{
  let keyboard=0;
  const viewport=new EventTarget();Object.defineProperties(viewport,{width:{get:()=>innerWidth},height:{get:()=>innerHeight-keyboard},offsetLeft:{get:()=>0},offsetTop:{get:()=>0},pageLeft:{get:()=>scrollX},pageTop:{get:()=>scrollY},scale:{get:()=>1}});
  Object.defineProperty(window,'visualViewport',{configurable:true,value:viewport});
  globalThis.__editorViewportTest={setKeyboard(height){keyboard=height;viewport.dispatchEvent(new Event('resize'));}};
 });
}

/** Menu follows keyboard and reduced viewport; normal-flow actions remain scrollably reachable. */
export async function assertKeyboardNavigation(page){
 const original=page.viewportSize();await page.locator('.editor-step:visible input:not([type="hidden"])').first().focus();
 try{
  await page.evaluate(async()=>{globalThis.__editorViewportTest.setKeyboard(250);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
  await assertEditorNavigation(page,{scroll:true,lastField:true});
  await page.evaluate(async()=>{globalThis.__editorViewportTest.setKeyboard(0);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
  await page.setViewportSize({width:original.width,height:Math.max(400,original.height-250)});await assertEditorNavigation(page,{scroll:true,lastField:true});
 }finally{await page.evaluate(()=>globalThis.__editorViewportTest?.setKeyboard(0));await page.setViewportSize(original);}
}

/** Exercise actual visible arrows without making optional numeric bounds mandatory. */
export async function assertRoomSteppers(page,interact){
 for(const name of ['minRooms','maxRooms']){
  const input=await editorField(page,'#f-'+name,interact),previous=await input.inputValue(),minimum=name==='maxRooms'?0.5:0;
  assert.equal(Number(await input.getAttribute('min')),minimum);
  assert.equal(await input.getAttribute('step'),'0.5');
  const up=page.locator('#f-'+name+'-up'),down=page.locator('#f-'+name+'-down');
  await input.fill('');await press(page,up,interact);assert.equal(await input.inputValue(),'0.5');
  await press(page,up,interact);assert.equal(await input.inputValue(),'1');await press(page,down,interact);assert.equal(await input.inputValue(),'0.5');
  await press(page,down,interact);assert.equal(Number(await input.inputValue()),minimum);
  if(await down.isEnabled())await press(page,down,interact);assert.equal(Number(await input.inputValue()),minimum,'The lower arrow cannot cross the valid room-count minimum');
  await input.fill('1.5');await press(page,up,interact);assert.equal(await input.inputValue(),'2');
  await input.fill(previous);assert.equal(await input.inputValue(),previous,'Optional empty bounds remain clearable after using arrows');
 }
}

export async function editorField(page, selector, interact) {
  const locator = page.locator(selector);
  const step = await locator.first().evaluate(element => {
    const section = element.closest('[data-editor-step]');
    return section ? Number(section.dataset.editorStep) : null;
  });
  if (step !== null) await editorStep(page, step, interact);
  return locator;
}

export async function editorSave(page, interact, {top = false} = {}) {
  await editorStep(page, 5, interact);
  await press(page, page.locator(top ? '#editor-save-top' : '#editor-save'), interact);
}

/** Use the same compact selected-place disclosure as mobile visitors. */
async function revealSelection(page, interact, landing) {
  const chips = page.locator(landing ? '#landing-location-chips' : '#location-chips');
  const toggle = chips.locator('[data-location-selection-toggle]');
  const opened = await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true';
  if (opened) await press(page, toggle, interact);
  return {chips, toggle, opened};
}

export async function selectedLocationText(page, interact, {landing = false} = {}) {
  const {chips, toggle, opened} = await revealSelection(page, interact, landing);
  const text = await chips.innerText();
  if (opened) await toggle.press('Escape');
  return text;
}

export async function removeSelectedLocation(page, id, interact, {landing = false} = {}) {
  const {chips, toggle, opened} = await revealSelection(page, interact, landing);
  await press(page, chips.locator(`[data-remove-location="${id}"]`), interact);
  if (opened && await toggle.isVisible()) await toggle.press('Escape');
}
