import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {containsContactDetails,assertDescriptionContactFree,descriptionContactMessage} from '../dist/contact-policy.js';

const cases=JSON.parse(await readFile(new URL('../backend/fixtures/contact-policy-cases.json',import.meta.url),'utf8'));
for(const example of cases)test('description contact policy: '+example.id,()=>{
 assert.equal(containsContactDetails(example.text),example.contact,example.id);
 if(example.contact)assert.throws(()=>assertDescriptionContactFree(example.text),error=>error.message===descriptionContactMessage);
 else assert.doesNotThrow(()=>assertDescriptionContactFree(example.text));
});

test('optional descriptions and surrounding prose retain safe values',()=>{
 for(const value of [null,undefined,'', 'Két szobás, 65 m²-es lakást keresek.'])assert.doesNotThrow(()=>assertDescriptionContactFree(value));
 assert.equal(descriptionContactMessage,'Elérhetőséget nem adhatsz meg a leírásban.');
});
