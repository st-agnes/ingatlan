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
   const form=document.getElementById('entity-form'),nav=document.getElementById('editor-navigation'),content=form?.querySelector('.editor-content'),section=form?.querySelector('.editor-step:not([hidden])');
   if(!form?.isConnected||!nav?.isConnected||!content?.isConnected||!section?.isConnected)return null;
   const rect=element=>{const b=element.getBoundingClientRect();return{left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,height:b.height,position:getComputedStyle(element).position};};
   return {form:{...rect(form),client:form.clientWidth,scroll:form.scrollWidth},nav:rect(nav),content:rect(content),section:rect(section),
    topics:[...nav.querySelectorAll('[data-action="editor-step"]')].map(rect),
    actions:['top','bottom'].map(where=>{const group=form.querySelector('.editor-navigation-'+where);return group?{...rect(group),buttons:[...group.querySelectorAll('button')].filter(button=>button.offsetParent!==null).map(button=>({id:button.id,disabled:button.disabled,...rect(button)}))}:null;})};
  });
  if(proof&&proof.nav.position!=='')return proof;
  if(attempt<19)await page.waitForTimeout(50);
 }
 assert.fail('The current left navigation and both action groups must mount within one second');
}

/** The wizard uses a left column and ordinary top/bottom actions, without a viewport dock. */
export async function assertEditorNavigation(page,{scroll=false,lastField=false}={}) {
 const original=await page.evaluate(()=>{const host=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;return host.scrollTop;});
 const proof=await liveEditorNavigation(page);
 assert.ok(proof.form.scroll<=proof.form.client+1,'The left navigation and content must fit without horizontal scrolling');
 assert.notEqual(proof.nav.position,'fixed','Topic navigation must not occupy a fixed bottom bar');
 assert.ok(proof.nav.right<=proof.content.left+1,'The topic menu belongs to the left of the form content');
 assert.ok(proof.content.width>=140,'The topic menu must leave a usable form column on mobile');
 assert.equal(proof.topics.length,6);
 for(let index=1;index<proof.topics.length;index++)assert.ok(proof.topics[index].top>=proof.topics[index-1].bottom-1,'Each named topic must occupy its own vertical row');
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
 assert.doesNotMatch(await page.locator('#entity-form').innerText(),/Később folytatom/);
 if(scroll){
  for(const selector of ['.editor-navigation-top','.editor-navigation-bottom']){
   const button=page.locator(selector+' button:visible:not(:disabled)').last();await button.scrollIntoViewIfNeeded();
   const hit=await button.evaluate(element=>{const b=element.getBoundingClientRect(),top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return b.top>=0&&b.bottom<=innerHeight+1&&(element===top||element.contains(top));});
   assert.equal(hit,true,'Both normal-flow primary actions must be reachable and directly clickable through scrolling');
  }
 }
 if(lastField){
  const field=page.locator('.editor-step:visible input:not([type="hidden"]):visible,.editor-step:visible select:visible,.editor-step:visible textarea:visible,.editor-step:visible button:visible').last();
  await field.scrollIntoViewIfNeeded();
  assert.equal(await field.evaluate(element=>{const b=element.getBoundingClientRect(),top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return element===top||element.contains(top);}),true,'The last field must remain unobscured by navigation');
 }
 if(scroll||lastField)await page.evaluate(top=>{const host=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;host.scrollTo({top,behavior:'instant'});},original);
}

/** Reduced mobile viewport keeps ordinary-flow controls scrollable; there is no keyboard dock. */
export async function assertKeyboardNavigation(page){
 const original=page.viewportSize();await page.locator('.editor-step:visible input:not([type="hidden"])').first().focus();
 try{await page.setViewportSize({width:original.width,height:Math.max(400,original.height-250)});await assertEditorNavigation(page,{scroll:true,lastField:true});}
 finally{await page.setViewportSize(original);}
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
