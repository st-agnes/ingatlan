import {publicFirstName} from './public-profile.js';

export const FEEDBACK_QUESTION='Miért nem tetszett az ingatlan?';
export const FEEDBACK_PACKAGE_SIZES=Object.freeze([10,20,50]);
export const FEEDBACK_DURATION_DAYS=14;
export const FEEDBACK_PROMPT_SPACING=20;
export const FEEDBACK_INVITATION_MINUTES=15;
export const FEEDBACK_OPTIONS=Object.freeze([
  ['insufficient_information','Túl kevés információ van megosztva az ingatlanról'],
  ['layout','Nem tetszik az ingatlan elrendezése'],
  ['lighting','Nem jók a fényviszonyok az ingatlanban'],
  ['location','Az ingatlan elhelyezkedése nem szimpatikus'],
  ['view','Nem tetszik, vagy nem látszik a képeken a kilátás az ablakokból'],
  ['incorrect_parameters','Az ingatlan nem felel meg a róla feltüntetett paramétereknek'],
  ['other','Egyéb'],
  ['decline','Nem szeretnék válaszolni']
].map(([value,label])=>Object.freeze({value,label})));

/** Hungarian name suffixes; contact-bearing or missing names use a neutral title. */
export function feedbackTitle(input){
  const name=publicFirstName(input);
  if(!name)return 'Segíts az eladónak egy visszajelzéssel';
  const vowels=[...name.toLocaleLowerCase('hu')].filter(letter=>'aáoóuúeöőüű'.includes(letter));
  const suffix=name.toLocaleLowerCase('hu')!=='noémi'&&vowels.length&&'aáoóuú'.includes(vowels.at(-1))?'nak':'nek';
  const inflected=name.endsWith('a')?name.slice(0,-1)+'á':name.endsWith('e')?name.slice(0,-1)+'é':name;
  return `Segíts ${inflected}${suffix} egy visszajelzéssel`;
}
