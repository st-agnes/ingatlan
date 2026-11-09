import test from 'node:test';
import assert from 'node:assert/strict';
import {assertNoContactData} from '../backend/smoke-privacy.mjs';

const privateValues = ['+36 30 555 9999','seller@example.test','Private street 12'];
function publicCard() {
  return {
    propertyId:'00009999-0000-4000-8000-000000000001',
    searchRequestId:'00000000-9999-4000-8000-000000000002',
    property:{id:'00009999-0000-4000-8000-000000000001',ownerId:'00000000-0000-4000-9999-000000000003',
      title:'Public listing',address:'',price:9999,area:60,rooms:3},
    searchRequest:{id:'00000000-9999-4000-8000-000000000002',description:'Public search'},
    reasons:['Matching location']
  };
}

test('a public card remains private when UUIDs and unrelated numbers contain the phone suffix',()=>{
  const card=publicCard();
  assert.ok(JSON.stringify(card).includes('9999'),'The old substring assertion would reject this valid card');
  assert.doesNotThrow(()=>assertNoContactData(card,privateValues));
});

test('contact and credential fields fail at any nesting level, even without a known private value',()=>{
  for(const key of ['email','Phone','contact','password','PasswordHash','accessToken','refreshToken']){
    for(const nested of [false,true]){
      const card=publicCard();
      if(nested)card.reasons.push({owner:{[key]:null}});else card.property[key]='unlisted-private-value';
      assert.throws(()=>assertNoContactData(card,privateValues),/Private field appeared/);
    }
  }
});

test('complete private phone, email and address values cannot leak under an unexpected public field',()=>{
  for(const value of privateValues){
    const card=publicCard();card.reasons.push({text:'Accidental leak: '+value});
    assert.throws(()=>assertNoContactData(card,privateValues),/complete private value/);
  }
});

test('an absent optional contact value does not reject every public string',()=>{
  assert.doesNotThrow(()=>assertNoContactData(publicCard(),[undefined,null,'',...privateValues]));
});
