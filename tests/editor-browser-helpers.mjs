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

/** Install before app mount so editor viewport listeners see real resize events. */
export async function installEditorViewportMock(context) {
  await context.addInitScript(() => {
    const original = Object.getOwnPropertyDescriptor(window, 'visualViewport');
    const viewport = new EventTarget();
    let keyboardHeight = 0;
    Object.defineProperties(viewport, {
      width: {get: () => innerWidth}, height: {get: () => innerHeight - keyboardHeight},
      offsetTop: {get: () => 0}, offsetLeft: {get: () => 0}, scale: {get: () => 1},
      pageTop: {get: () => scrollY}, pageLeft: {get: () => scrollX}
    });
    Object.defineProperty(window, 'visualViewport', {configurable: true, get: () => viewport});
    window.__editorVisualViewportTest = {
      shrink(height) { keyboardHeight = height; viewport.dispatchEvent(new Event('resize')); },
      restore() { keyboardHeight = 0; viewport.dispatchEvent(new Event('resize')); },
      cleanup() {
        keyboardHeight = 0; viewport.dispatchEvent(new Event('resize'));
        if (original) Object.defineProperty(window, 'visualViewport', original);
        else delete window.visualViewport;
        delete window.__editorVisualViewportTest;
      }
    };
  });
}

/** A keyboard reduces the visible screen; the physical bar must sit at its bottom. */
export async function assertKeyboardNavigation(page) {
  await page.locator('.editor-step:visible input:not([type="hidden"])').first().focus();
  try {
    await page.evaluate(async () => {
      window.__editorVisualViewportTest.shrink(250);
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    await assertEditorNavigation(page);
    const proof = await page.locator('#editor-navigation').evaluate(element => {
      const box = element.getBoundingClientRect(), next = document.getElementById('editor-next'), action = next.getBoundingClientRect();
      const top = document.elementFromPoint(action.x + action.width / 2, action.y + action.height / 2);
      return {bottom: box.bottom, visibleBottom: visualViewport.offsetTop + visualViewport.height,
        actionTop: action.top, actionBottom: action.bottom, hit: next === top || next.contains(top)};
    });
    assert.ok(Math.abs(proof.bottom - proof.visibleBottom) <= 2, `The footer must meet the keyboard viewport bottom without double offset (footer ${proof.bottom}, visible ${proof.visibleBottom})`);
    assert.ok(proof.actionTop >= 0 && proof.actionBottom <= proof.visibleBottom + 1, 'Next must remain within the keyboard-reduced screen');
    assert.equal(proof.hit, true, 'Next must remain directly clickable while the keyboard is open');
    await page.evaluate(async () => {window.__editorVisualViewportTest.restore();await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));});
    const restored = await page.locator('#editor-navigation').evaluate(element => ({bottom:element.getBoundingClientRect().bottom,height:innerHeight}));
    assert.ok(Math.abs(restored.bottom - restored.height) <= 2, 'The footer must return to the ordinary screen bottom after keyboard dismissal');
  } finally {
    await page.evaluate(() => window.__editorVisualViewportTest?.cleanup());
  }
}

// A storage/focus refresh may replace the form between locator resolution and
// evaluation. Query the current document atomically and retry only that brief gap.
async function liveEditorNavigation(page) {
  let proof = null;
  for (let attempt = 0; attempt < 20; attempt++) {
    proof = await page.evaluate(() => {
      const form = document.getElementById('entity-form'), element = document.getElementById('editor-navigation');
      if (!form?.isConnected || !element?.isConnected || !form.contains(element)) return null;
      const box = element.getBoundingClientRect();
      const buttons = [...element.querySelectorAll('button')].filter(button => button.offsetParent !== null && !button.disabled);
      return {position: getComputedStyle(element).position, left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        width: (visualViewport?.offsetLeft || 0) + (visualViewport?.width || innerWidth), height: (visualViewport?.offsetTop || 0) + (visualViewport?.height || innerHeight),
        buttons: buttons.map(button => {const b=button.getBoundingClientRect(),top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return {id:button.id,top:b.top,bottom:b.bottom,hit:button===top||button.contains(top)};})};
    });
    if (proof && proof.position !== '') return proof;
    if (attempt < 19) await page.waitForTimeout(50);
  }
  assert.ok(proof && proof.position !== '', 'The current mounted editor navigation must be measurable within one second');
  return proof;
}

/** Prove that the fixed topic bar and actions remain usable through real scrolling. */
export async function assertEditorNavigation(page, {scroll = false, lastField = false} = {}) {
  const original = await page.evaluate(() => {
    const modal = document.getElementById('entity-form')?.closest('.modal');
    return (modal || document.scrollingElement).scrollTop;
  });
  for (const fraction of scroll ? [0, .5, 1] : [null]) {
    if (fraction !== null) await page.evaluate(async fraction => {
      const modal = document.getElementById('entity-form')?.closest('.modal');
      const element = modal || document.scrollingElement;
      element.scrollTo({top: (element.scrollHeight - element.clientHeight) * fraction, behavior: 'instant'});
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }, fraction);
    const proof = await liveEditorNavigation(page);
    assert.equal(proof.position, 'fixed');
    assert.ok(proof.left >= -1 && proof.right <= proof.width + 1 && proof.top >= 0 && proof.bottom <= proof.height + 1, 'The bottom topic/action bar must fit inside the visible viewport');
    assert.ok(proof.buttons.length >= 7, 'Every named topic and the current action must remain available');
    for (const button of proof.buttons) {assert.ok(button.top >= 0 && button.bottom <= proof.height + 1, `Navigation ${button.id} must stay visible`);assert.equal(button.hit, true, `Navigation ${button.id} must be directly clickable`);}
    if (lastField && fraction === 1) {
      const field = await page.locator('.editor-step:visible').evaluate(element => {
        const controls = [...element.querySelectorAll('input:not([type="hidden"]),select,textarea,button')].filter(control => control.offsetParent !== null && !control.disabled);
        const control = controls.at(-1), box = control?.getBoundingClientRect(), top = box ? document.elementFromPoint(box.x+box.width/2,box.y+box.height/2) : null;
        return box ? {id:control.id,top:box.top,bottom:box.bottom,hit:control===top||control.contains(top)} : null;
      });
      assert.ok(field, 'The scroll proof needs a real last field');
      assert.ok(field.top >= 0 && field.bottom <= proof.top + 1, `The final field ${field.id} must clear the fixed navigation bar`);
      assert.equal(field.hit, true, 'The last field must not be obscured by navigation');
    }
  }
  if (scroll) await page.evaluate(top => {const element=document.getElementById('entity-form')?.closest('.modal')||document.scrollingElement;element.scrollTo({top,behavior:'instant'});},original);
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

export async function editorSave(page, interact) {
  await editorStep(page, 5, interact);
  await press(page, page.locator('#entity-form button[type="submit"]'), interact);
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
