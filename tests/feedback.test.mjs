import test from 'node:test';
import assert from 'node:assert/strict';
import {FEEDBACK_OPTIONS,FEEDBACK_QUESTION,FEEDBACK_PACKAGE_SIZES,FEEDBACK_DURATION_DAYS,FEEDBACK_PROMPT_SPACING,FEEDBACK_INVITATION_MINUTES,feedbackTitle} from '../dist/feedback.js';

test('feedback choices are one-click categories with an explicit uncharged opt-out',()=>{
 assert.deepEqual(FEEDBACK_PACKAGE_SIZES,[10,20,50]);assert.equal(FEEDBACK_DURATION_DAYS,14);assert.equal(FEEDBACK_PROMPT_SPACING,20);assert.equal(FEEDBACK_INVITATION_MINUTES,15);
 assert.equal(FEEDBACK_QUESTION,'Miért nem tetszett az ingatlan?');assert.equal(FEEDBACK_OPTIONS.length,8);assert.equal(new Set(FEEDBACK_OPTIONS.map(item=>item.value)).size,8);
 assert.equal(FEEDBACK_OPTIONS.at(-1).value,'decline');assert.equal(FEEDBACK_OPTIONS.at(-1).label,'Nem szeretnék válaszolni');assert.ok(Object.isFrozen(FEEDBACK_OPTIONS));
});
test('feedback request titles use safe Hungarian given names with the appropriate suffix',()=>{
 for(const [name,expected] of [['Anna','Annának'],['Eszter','Eszternek'],['Péter','Péternek'],['Bence','Bencének'],['Júlia','Júliának'],['Máté','Máténak'],['Zsófi','Zsófinak'],['Noémi','Noéminek'],['Kovács Anna','Annának']])assert.equal(feedbackTitle(name),`Segíts ${expected} egy visszajelzéssel`);
 for(const name of ['',null,'PRIVATE@EXAMPLE.HU','<script>','+36 30 123 4567'])assert.equal(feedbackTitle(name),'Segíts az eladónak egy visszajelzéssel');
});
