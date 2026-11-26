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

/** Set a native three-state amenity or an optional illustrated single choice through its visible control. */
export async function setAttributeChoice(page, name, value, interact) {
  value = value == null ? '' : String(value);
  const input = await editorField(page, `#f-${name}`, interact);
  const before = await input.inputValue();
  if (before === value) return input;
  const radio = page.locator(`input[type="radio"][name="${name}"][value="${value}"]`);
  if (await radio.count()) {
    await press(page, page.locator('label').filter({has: radio}), interact);
    assert.equal(await radio.isChecked(), true);
    assert.equal(await page.locator(`input[type="radio"][name="${name}"]:checked`).count(), 1);
    assert.equal(await input.inputValue(), value);
    return input;
  }
  const card = page.locator(`[data-attribute-name="${name}"][data-attribute-value="${value || before}"]`);
  await press(page, card, interact);
  assert.equal(await input.inputValue(), value);
  return input;
}

/** Choose exact seller floors through the drawn building, including its top Other row. */
export async function setSellerFloor(page, value, interact) {
  return setFloorCards(page, 'floor', value, interact);
}

export async function setBuildingFloors(page, value, interact) {
  return setFloorCards(page, 'buildingFloors', value, interact);
}

async function setFloorCards(page, name, value, interact) {
  const input = await editorField(page, '#f-' + name, interact), target = value == null ? '' : String(value), before = await input.inputValue();
  if (before === target) return input;
  const choice = Number(target) > 10 ? 'other' : target || (Number(before) > 10 ? 'other' : before);
  const card = page.locator(`.building-floor-row[data-building-number="${name}"][data-building-number-value="${choice}"]`);
  if (!(Number(target) > 10 && Number(before) > 10)) await press(page, card, interact);
  if (target && Number(target) > 10) await page.locator('#f-' + name + 'Other').fill(target);
  assert.equal(await input.inputValue(), target);
  if (target && Number(target) > 10) await assertRequiredFieldLabels(page);
  return input;
}

/** The certificate selector is a real, discrete range control with a textual value. */
export async function setEnergyRating(page, value, interact, {search = false} = {}) {
  const name = search ? 'minEnergyRating' : 'energyRating', input = await editorField(page, '#f-' + name, interact);
  const order = ['', 'I', 'H', 'G', 'F', 'E', 'D', 'C', 'B', 'A', 'A+', 'A++', 'A+++'], index = order.indexOf(value || '');
  assert.ok(index >= 0, 'Choose a current Hungarian certificate category');
  const slider = page.locator('#f-' + name + '-slider');
  assert.equal(await slider.getAttribute('type'), 'range');
  assert.equal(await slider.getAttribute('min'), '0');assert.equal(await slider.getAttribute('max'), '12');
  await slider.focus();if(index===0&&await input.inputValue())await slider.press('ArrowRight');await slider.press('Home');
  for (let step = 0; step < index; step++) await slider.press('ArrowRight');
  assert.equal(await input.inputValue(), value || '');
  assert.equal(await slider.inputValue(), String(index));
  return input;
}

/** Seller construction age remains optional and single-valued; buyer ages retain their multiselect. */
export async function setConstructionAge(page, value, interact) {
  const choice = await editorField(page, `input[name="constructionAge"][value="${value || ''}"]`, interact);
  assert.equal(await choice.getAttribute('type'), 'radio');
  await press(page, page.locator('label').filter({has: choice}), interact);
  assert.equal(await choice.isChecked(), true);
  assert.equal(await page.locator('input[name="constructionAge"]:checked').count(), 1);
  return choice;
}

export async function setAtticPreference(page, value, interact) {
  await editorStep(page, 3, interact);
  const backing = page.locator('#f-atticPreference');
  const choice = value ? page.locator(value === 'only' ? '#f-atticOnly' : '#f-atticExclude') : backing;
  for (const [id, wanted] of [['f-atticOnly', value === 'only'], ['f-atticExclude', value === 'exclude']]) {
    const checkbox = page.locator('#' + id);
    assert.equal(await checkbox.getAttribute('type'), 'checkbox');
    if (await checkbox.isChecked() !== wanted) await press(page, page.locator('label').filter({has: checkbox}), interact);
  }
  assert.equal(await backing.inputValue(), value || '');
  assert.equal(await page.locator('#f-atticOnly:checked,#f-atticExclude:checked').count(), value ? 1 : 0, 'Attic inclusion and exclusion remain mutually exclusive');
  assert.equal(await page.locator('#floors-group .attribute-choices label:last-child input').getAttribute('id'), 'f-atticOnly', 'Attic is the final choice in the floor grid');
  assert.equal(await page.locator('#floors-group input[type="radio"]').count(), 0, 'No extra no-restriction radio occupies the floor section');
  return choice;
}

/** Illustrated buyer heating controls are operated through their visible labels. */
export async function setHeatingRequirement(page, value, checked = true, interact) {
  const choice = await editorField(page, `input[name="heatingTypes"][value="${value}"]`, interact);
  if (await choice.isChecked() !== checked) await press(page, page.locator('label').filter({has: choice}), interact);
  assert.equal(await choice.isChecked(), checked);
}

/** Compact selected city, privacy dependencies and address field removal are shared by owned/guest sellers. */
export async function assertAddressPrivacyControls(page, interact, {city = 'Debrecen', locationId = 'city:Debrecen'} = {}) {
  await editorStep(page, 0, interact);
  assert.equal(await page.locator('#editor-step-button-0').getAttribute('aria-label'), 'Helyszín');
  assert.equal(await page.locator('#f-postalCode').getAttribute('type'), 'hidden', 'Postcode metadata is not an extra user-entry task');assert.equal(await page.locator('label[for="f-postalCode"]').count(), 0);
  assert.equal(await page.locator('#property-location-edit').isVisible(), true);
  assert.equal(await page.locator('#location-input').isVisible(), false, 'A selected seller city has a compact editable caption');
  const street = page.locator('#f-hideStreet'), house = page.locator('#f-hideHouseNumber');
  assert.equal(await street.isChecked(), true);assert.equal(await house.isChecked(), true);assert.equal(await house.isEnabled(), true, 'The house-number privacy choice remains active while the street is hidden');
  await house.uncheck();assert.equal(await house.isChecked(), false);assert.equal(await street.isChecked(), false, 'Showing the house number must automatically show the street');
  await street.check();assert.equal(await house.isChecked(), true);assert.equal(await house.isEnabled(), true, 'Hiding the street checks the house number without disabling it');
  await street.uncheck();assert.equal(await house.isEnabled(), true);assert.equal(await house.isChecked(), true, 'Showing only the street must not silently expose the house number');
  await house.uncheck();assert.equal(await street.isChecked(), false);assert.equal(await house.isChecked(), false);
  await street.check();assert.equal(await house.isChecked(), true);assert.equal(await house.isEnabled(), true);
  const streetBefore = await page.locator('#f-street').inputValue(), numberBefore = await page.locator('#f-houseNumber').inputValue();
  await press(page, page.locator('#property-location-edit'), interact);
  assert.equal(await page.locator('#location-input').isVisible(), true);
  assert.equal(await page.locator('#f-street').inputValue(), streetBefore);assert.equal(await page.locator('#f-houseNumber').inputValue(), numberBefore, 'Opening city editing does not discard the current address');
  await page.locator('#location-input').fill(city);await press(page, page.locator('[data-location-id="' + locationId + '"]'), interact);
  assert.equal(await page.locator('#location-input').isVisible(), false);
}

/** Native three-state choices preserve No versus unknown without a hidden default. */
export async function assertNullableAmenities(page, interact) {
  for (const name of ['balcony', 'airConditioning', 'privateGarden', 'insulated', 'solarPanels']) {
    const input = await editorField(page, '#f-' + name, interact), before = await input.inputValue();
    assert.equal(await input.getAttribute('type'), 'hidden');
    const radios = page.locator(`input[type="radio"][name="${name}"]`);
    assert.deepEqual(await radios.evaluateAll(inputs => inputs.map(input => input.value)), ['', 'true', 'false']);
    assert.equal(await page.locator(`[data-attribute-name="${name}"]`).count(), 0, 'Comfort and equipment no longer use picture cards');
    assert.deepEqual(await radios.evaluateAll(inputs => inputs.map(input => input.labels[0].textContent.trim().toLocaleLowerCase('hu'))), ['nem adom meg', 'van', 'nincs']);
    for (const value of ['true', 'false', '']) {
      await setAttributeChoice(page, name, value, interact);
      assert.equal(await page.locator(`input[type="radio"][name="${name}"][value="${value}"]`).isChecked(), true);
      assert.equal(await page.locator(`input[type="radio"][name="${name}"]:checked`).count(), 1);
      assert.equal(await input.inputValue(), value);
    }
    await setAttributeChoice(page, name, before, interact);
  }
}

/** Buyer budget inputs disclose their audience and keep the public cap beneath the private cap. */
export async function assertSearchBudgetFields(page, interact) {
 const maximum = await editorField(page, '#f-maxPrice', interact), publicMaximum = page.locator('#f-publicMaxPrice');
 assert.equal(await maximum.evaluate(input => input.required), true);assert.equal(await publicMaximum.evaluate(input => input.required), false);
 assert.equal(await maximum.getAttribute('aria-describedby'), 'maxPrice-help');assert.equal(await publicMaximum.getAttribute('aria-describedby'), 'publicMaxPrice-help');
 assert.match(await page.locator('#maxPrice-help').innerText(), /csak te.*algoritmus/iu);assert.match(await page.locator('#publicMaxPrice-help').innerText(), /eladók/iu);
 assert.match(await page.locator('label[for="f-maxPrice"]').innerText(), /Privát/);assert.match(await page.locator('label[for="f-publicMaxPrice"]').innerText(), /Publikus/);
 const privateBox = await maximum.boundingBox(), publicBox = await publicMaximum.boundingBox();assert.ok(privateBox && publicBox && publicBox.y >= privateBox.y + privateBox.height, 'The public maximum remains directly below the private maximum at every viewport');
}

/** The connected building rows stay usable, with cumulative height fill and one exact floor. */
export async function assertBuildingSelectors(page, interact) {
  await editorStep(page, 3, interact);
  const floorBefore = await page.locator('#f-floor').inputValue(), heightBefore = await page.locator('#f-buildingFloors').inputValue();
  const rows = name => page.locator(`.building-floor-row[data-building-number="${name}"]`);
  const values = name => rows(name).evaluateAll(buttons => buttons.map(button => button.dataset.buildingNumberValue));
  assert.deepEqual((await values('floor')).sort(), ['-1', '0', '0.5', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'other'].sort());
  assert.deepEqual((await values('buildingFloors')).sort(), ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'other'].sort());
  assert.equal(await page.locator('.building-selector-height .building-stack').evaluate(element=>getComputedStyle(element).borderLeftStyle),'dashed','Building height uses a dashed outline');
  assert.equal(await page.locator('.building-selector-floor .building-stack').evaluate(element=>getComputedStyle(element).borderLeftStyle),'solid','The exact floor is drawn within a solid building');
  assert.equal(await page.locator('.building-selector-height .building-stack').evaluate(element=>getComputedStyle(element).borderBottomStyle),'solid','Only the sides and upper outline are dashed');
  assert.equal(await page.locator('.building-selector-roof svg').count(),2,'Both buildings have a drawn roof');
  assert.equal(await page.locator('.building-selector .building-ground-tree').count(),6,'Both diagrams illustrate the ground level with trees');
  const ground=await page.locator('.building-selector-floor .building-ground-level').boundingBox(),basement=await rows('floor').filter({hasText:'Szuterén'}).boundingBox();
  assert.ok(ground&&basement&&basement.y>=ground.y+ground.height-1,'The basement sits below the surface line');
  if(page.viewportSize().width>720){const heightGround=await page.locator('.building-selector-height .building-ground-level').boundingBox();assert.ok(heightGround&&Math.abs(heightGround.y-ground.y)<=1,'Side-by-side diagrams share one ground level');}
  for (const name of ['floor', 'buildingFloors']) {
    const boxes = await rows(name).evaluateAll(buttons => buttons.map(button => {const box = button.getBoundingClientRect(); return {value:button.dataset.buildingNumberValue, tag:button.tagName, left:box.left, top:box.top, right:box.right, bottom:box.bottom, width:box.width, text:button.innerText};}));
    assert.ok(boxes.every(box => box.tag === 'BUTTON' && box.width > 50 && box.bottom - box.top >= 24), 'Every drawn floor is a real, readable click target');
    const top = boxes.find(box => box.value === 'other');assert.match(top.text, /egyéb/iu);assert.doesNotMatch(top.text, /11\./);
    assert.ok(boxes.filter(box => box.value !== 'other').every(box => box.top >= top.bottom - 1), 'Other is the top storey of the building');
  }
  await setSellerFloor(page, '2', interact);
  assert.equal(await page.locator('.building-floor-row[data-building-number="floor"][aria-pressed="true"]').count(), 1);
  await setBuildingFloors(page, '4', interact);
  const filled = async () => rows('buildingFloors').evaluateAll(buttons => buttons.filter(button => button.dataset.filled === 'true').map(button => button.dataset.buildingNumberValue));
  assert.deepEqual((await filled()).sort(), ['0', '1', '2', '3', '4'].sort(), 'Height selection fills each storey from the ground to the selected level');
  await press(page, page.locator('.building-floor-row[data-building-number="buildingFloors"][data-building-number-value="4"]'), interact);
  assert.equal(await page.locator('#f-buildingFloors').inputValue(), '');assert.deepEqual(await filled(), [], 'Repeating the selected height clears the whole fill');
  await setBuildingFloors(page, '6', interact);assert.deepEqual((await filled()).sort(), ['0', '1', '2', '3', '4', '5', '6'].sort());
  const third = page.locator('.building-floor-row[data-building-number="floor"][data-building-number-value="3"]');await third.focus();await third.press('Space');assert.equal(await page.locator('#f-floor').inputValue(), '3', 'The building supports keyboard selection as well as touch');
  await third.press('Space');assert.equal(await page.locator('#f-floor').inputValue(), '', 'Repeating the same floor clears its selection');
  await setSellerFloor(page, '12', interact);assert.equal(await page.locator('#f-floorOther').isVisible(), true);assert.equal(await page.locator('#f-floorOther').inputValue(), '12');
  await setSellerFloor(page, floorBefore, interact);await setBuildingFloors(page, heightBefore, interact);
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
   const heading=header.querySelector('h2'),reference=document.getElementById('editor-heading-1'),modalClose=form.closest('.modal')?.querySelector('.modal-close');
   return {mobile:innerWidth<=720,viewport,form:{...rect(form),client:form.clientWidth,scroll:form.scrollWidth},nav:{...rect(nav),background:getComputedStyle(nav).backgroundColor},content:rect(content),section:rect(section),
    header:{...rect(header),hasHeading:!!heading&&content.contains(heading),heading:heading?rect(heading):null,topActionInside:!!header.querySelector('.editor-navigation-top'),eyebrows:form.querySelectorAll('.eyebrow').length},
    modalClose:modalClose&&visible(modalClose)?rect(modalClose):null,
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
 assert.ok(nav.left>=viewport.left-1&&nav.right<=right+1&&nav.top>=viewport.top&&nav.bottom<=bottom+1,'The compact menu must fit the visible viewport: '+JSON.stringify({nav,viewport}));
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
 assert.equal(proof.header.topActionInside,true,'The upper action row belongs inside the main heading row');
 const headerAction=proof.actions[0]?.buttons.at(-1),heading=proof.header.heading;assert.ok(headerAction&&heading&&headerAction.left>=heading.right-1,'The upper primary action sits beside the main heading');assert.ok(headerAction.top<heading.bottom&&headerAction.bottom>heading.top,'The heading and upper primary action share a vertical row on every viewport');
 if(proof.modalClose)for(const button of proof.actions[0].buttons){const overlapWidth=Math.min(button.right,proof.modalClose.right)-Math.max(button.left,proof.modalClose.left),overlapHeight=Math.min(button.bottom,proof.modalClose.bottom)-Math.max(button.top,proof.modalClose.top);assert.ok(overlapWidth<=0||overlapHeight<=0,'The modal close control must not cover any part of the upper Next/Save/Back buttons: '+JSON.stringify({button,close:proof.modalClose}));}
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
 await assertRequiredFieldLabels(page);
 const index=await page.locator('.editor-step:visible').getAttribute('data-editor-step');
 if(index==='5'&&await page.locator('#f-maxPrice').count())assert.equal((await page.locator('label[for="f-title"]').innerText()).trim(),'Keresés neve (ez fog megjelenni az ingatlan-tulajdonosoknak)');
 if(index==='2'){
  const titles=proof.headings.filter(heading=>heading.tag==='H3');
  assert.deepEqual(titles.map(heading=>heading.text),['Ár','Méret'],'Price and size have separate visible section headings');
  for(const title of titles)assert.equal(title.size,proof.referenceHeadingSize,'Price/size headings retain the established topic-title size');
 }else if(index==='3'){
  assert.ok(!proof.headings.some(heading=>heading.text==='Ingatlanjellemzők'),'The generic attribute title must not compete with its subsections');
  const expected=['Állapot','Építés éve','Kilátás','Falazat','Belmagasság'];
  if(await page.locator('#f-type').inputValue()!=='Ház')expected.splice(1,0,'Emelet');
  for(const label of expected){const heading=proof.headings.find(heading=>heading.text.startsWith(label));assert.ok(heading,`The ${label} subsection must retain its accessible label`);assert.equal(heading.size,proof.referenceHeadingSize,`${label} uses the topic-heading size`);}
 }else if(index==='4'){
  assert.equal(await page.locator('#editor-heading-4').evaluate(element=>element.classList.contains('editor-topic-anchor')),true,'The generic comfort title is only a validation focus anchor');
  const comfort=proof.headings.find(heading=>heading.text==='Kényelem');assert.ok(comfort,'Comfort options have their own subsection');assert.equal(comfort.size,proof.referenceHeadingSize);
  if(await page.locator('#f-airConditioning').getAttribute('type')==='checkbox')for(const [name,label]of [['balcony','Legyen erkély'],['airConditioning','Legyen légkondi'],['privateGarden','Legyen saját kert']])if(await page.locator('#f-'+name).isVisible())assert.equal((await page.locator('label:has(#f-'+name+')').innerText()).trim(),label);
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

/** Required fields are marked beside their accessible caption; optional labels stay clean. */
export async function assertRequiredFieldLabels(page){
 const proof=await page.locator('#entity-form').evaluate(form=>{
  const section=form.querySelector('.editor-step:not([hidden])'),shown=element=>element.getClientRects().length>0&&getComputedStyle(element).display!=='none';
  const fields=[...section.querySelectorAll('input:not([type="hidden"]),select,textarea')].filter(control=>shown(control)&&!control.disabled);
  return {text:[...form.querySelectorAll('label,legend,h3')].map(element=>element.innerText).join(' '),mobile:innerWidth<=720,fields:fields.map(control=>{
   const label=control.labels?.[0]||form.querySelector('label[for="'+control.id+'"]'),marker=label?.querySelector('[data-required-for="'+control.id+'"]'),color=marker?getComputedStyle(marker).color:'';
   return{id:control.id,required:control.required||control.getAttribute('aria-required')==='true',kind:control.type,label:label?.innerText,marked:!!marker&&shown(marker)&&marker.textContent.includes('*'),color,font:parseFloat(getComputedStyle(control).fontSize),labelFont:label?parseFloat(getComputedStyle(label).fontSize):null};
  })};
 });
 assert.doesNotMatch(proof.text,/opcionális/iu,'Optional controls do not need a separate optional suffix');
 for(const field of proof.fields){
  if(field.required){assert.equal(field.marked,true,`Required ${field.id} needs an asterisk beside its label`);const color=field.color.match(/[\d.]+/g)?.map(Number)||[];assert.ok(color[0]>color[1]&&color[0]>color[2],`Required ${field.id} uses a red marker`);}
  if(!['checkbox','radio'].includes(field.kind)){assert.ok(field.font>=(proof.mobile?17:15),`The ${field.id} field text is comfortably readable`);if(field.labelFont!==null)assert.ok(field.labelFont>=13,`The ${field.id} caption is comfortably readable`);}
 }
 if(await page.locator('#editor-step-1').isVisible()){
  const marker=page.locator('#required-f-type');assert.equal(await marker.isVisible(),true,'The custom required type group also carries a required marker');
 }
}

/** Single-select move-in illustrations can each be cleared by a repeated click. */
export async function assertMoveInChoices(page,interact){
 const input=await editorField(page,'#f-moveIn',interact),before=await input.inputValue(),cards=page.locator('[data-attribute-name="moveIn"]');
 assert.equal(await input.getAttribute('type'),'hidden');assert.equal(await cards.count(),4);
 // Each card also contains a separate selection-check SVG; count its illustration only.
 const illustrations=cards.locator('.attribute-card-illustration > svg');assert.equal(await illustrations.count(),4);
 assert.equal(new Set(await illustrations.evaluateAll(elements=>elements.map(element=>element.innerHTML))).size,4,'Every moving option has its own distinct illustration');
 for(const card of await cards.all())assert.equal(await card.locator('.attribute-card-illustration > svg').count(),1,'Each of the four choices owns exactly one illustration');
 assert.deepEqual(await cards.evaluateAll(elements=>elements.map(element=>element.dataset.attributeValue)),['Rugalmas','Azonnal','3 hónapon belül','6 hónapon belül']);
 for(const value of ['Rugalmas','Azonnal','3 hónapon belül','6 hónapon belül']){
  await setAttributeChoice(page,'moveIn',value,interact);const card=page.locator('[data-attribute-name="moveIn"][data-attribute-value="'+value+'"]');
  assert.equal(await page.locator('[data-attribute-name="moveIn"][aria-pressed="true"]').count(),1);
  await press(page,card,interact);assert.equal(await input.inputValue(),'');assert.equal(await page.locator('[data-attribute-name="moveIn"][aria-pressed="true"]').count(),0);
 }
 if(before)await setAttributeChoice(page,'moveIn',before,interact);
}

/** Common obfuscated contacts are refused before saving, and correction clears the warning. */
export async function assertDescriptionPrivacy(page,interact){
 const input=await editorField(page,'#f-description',interact),before=await input.inputValue();
 for(const content of ['Elérsz a nulla hat húsz egy kettő három négy öt hat hét számon.','Írj ide: peter kukac pelda pont hu']){
  await input.fill(content);await press(page,page.locator('#editor-save'),interact);
  assert.equal(await page.locator('#entity-form').isVisible(),true,'Contact details must not pass the final save');
  assert.equal(await input.evaluate(element=>element.validity.customError),true);
  const warning=page.locator('#description-contact-warning');assert.equal(await warning.isVisible(),true);assert.match(await warning.innerText(),/Elérhetőséget nem adhatsz meg a leírásban/);
 }
 await input.fill(before);assert.equal(await input.evaluate(element=>element.checkValidity()),true,'Correcting the description removes its contact validation error');
 assert.equal(await page.locator('#description-contact-warning').isVisible(),false);
}

/** Resize events schedule layout work in rAF; measure only after that paint has settled. */
export async function settleEditorLayout(page){
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
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
  await page.setViewportSize({width:original.width,height:Math.max(400,original.height-250)});await settleEditorLayout(page);await assertEditorNavigation(page,{scroll:true,lastField:true});
 }finally{await page.evaluate(()=>globalThis.__editorViewportTest?.setKeyboard(0));await page.setViewportSize(original);await settleEditorLayout(page);}
}

/** Set optional room bounds exclusively through the visible minus/plus controls. */
export async function fillRoomBound(page,name,value,interact){
 assert.ok(['minRooms','maxRooms'].includes(name));
 const input=await editorField(page,'#f-'+name,interact),target=value==null||value===''?null:Number(value);
 assert.ok(target===null||Number.isFinite(target)&&target>=1&&target*2%1===0,'A new room preference starts at one and advances in half rooms');
 for(let count=0;count<80;count++){
  const raw=await input.inputValue(),current=raw===''?null:Number(raw);
  if(current===target)return input;
  const direction=target===null||current!==null&&current>target?'down':'up';
  const button=page.locator('#f-'+name+'-'+direction);
  assert.equal(await revealEditorControl(page,button),true,'Room controls must remain directly reachable above the compact menu');
  await press(page,button,interact);
 }
 assert.fail('The visible room controls did not reach the requested preference');
}

/** Readouts have no editable number box; null, 1 and half-step transitions round-trip. */
export async function assertRoomSteppers(page,interact){
 for(const name of ['minRooms','maxRooms']){
  const input=await editorField(page,'#f-'+name,interact),previous=await input.inputValue(),empty=name==='minRooms'?'Nincs minimum':'Nincs maximum';
  assert.equal(await input.getAttribute('type'),'hidden','Room bounds are serialized without an editable input');
  const output=page.locator('#f-'+name+'-value'),up=page.locator('#f-'+name+'-up'),down=page.locator('#f-'+name+'-down');
  assert.equal(await output.evaluate(element=>element.tagName),'OUTPUT');assert.equal(await output.getAttribute('contenteditable'),null);
  await fillRoomBound(page,name,null,interact);assert.equal(await output.innerText(),empty);
  if(await down.isEnabled())await press(page,down,interact);assert.equal(await input.inputValue(),'','Minus at the unspecified bound stays unspecified');
  await press(page,up,interact);assert.equal(await input.inputValue(),'1');assert.match(await output.innerText(),/1/);
  await press(page,up,interact);assert.equal(await input.inputValue(),'1.5');
  await press(page,down,interact);assert.equal(await input.inputValue(),'1');
  await press(page,down,interact);assert.equal(await input.inputValue(),'');assert.equal(await output.innerText(),empty,'Decrementing one room removes the bound');
  const boxes=await page.evaluate(name=>['down','value','up'].map(suffix=>{const b=document.getElementById('f-'+name+'-'+suffix).getBoundingClientRect();return{left:b.left,right:b.right,top:b.top,bottom:b.bottom};}),name);
  assert.ok(boxes[0].right<=boxes[1].left+1&&boxes[1].right<=boxes[2].left+1,'Minus, readout and plus appear from left to right');
  await fillRoomBound(page,name,previous,interact);assert.equal(await input.inputValue(),previous,'Room-bound testing preserves the original draft');
 }
}

export async function editorField(page, selector, interact) {
  const locator = page.locator(selector);
  const step = await locator.first().evaluate(element => {
    const section = element.closest('[data-editor-step]');
    return section ? Number(section.dataset.editorStep) : null;
  });
  if (step !== null) await editorStep(page, step, interact);
  if (selector === '#location-input' && !await locator.isVisible() && await page.locator('#property-location-edit').isVisible()) await press(page, page.locator('#property-location-edit'), interact);
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
