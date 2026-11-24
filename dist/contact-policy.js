/** Bounded, deterministic description checks shared with the API implementation. */
export const descriptionContactMessage = 'Elérhetőséget nem adhatsz meg a leírásban.';

const digits = Object.freeze({nulla:'0',null:'0',nula:'0',zero:'0',o:'0',oh:'0',egy:'1',one:'1',ket:'2',ketto:'2',two:'2',harom:'3',three:'3',negy:'4',four:'4',ot:'5',five:'5',hat:'6',six:'6',het:'7',seven:'7',nyolc:'8',eight:'8',kilenc:'9',nine:'9'});
const tens = Object.freeze({tiz:10,husz:20,harminc:30,negyven:40,otven:50,hatvan:60,hetven:70,nyolcvan:80,kilencven:90,ten:10,eleven:11,twelve:12,thirteen:13,fourteen:14,fifteen:15,sixteen:16,seventeen:17,eighteen:18,nineteen:19,twenty:20,thirty:30,forty:40,fifty:50,sixty:60,seventy:70,eighty:80,ninety:90});
const numberPieces = Object.entries({...digits,...Object.fromEntries(Object.entries(tens).map(([key,value])=>[key,String(value)]))}).sort((a,b)=>b[0].length-a[0].length);
const smallPrefixes = Object.entries(tens).filter(([,value])=>value>=20).concat([['tizen',10],['huszon',20]]).sort((a,b)=>b[0].length-a[0].length);
const entities = Object.freeze({amp:'&',commat:'@',period:'.',plus:'+',nbsp:' ',tab:' ',newline:' ',zerowidthspace:'',shy:''});

function scalar(code, fallback) {return Number.isInteger(code)&&code>=0&&code<=0x10ffff&&!(code>=0xd800&&code<=0xdfff)?String.fromCodePoint(code):fallback;}
function normalize(value) {
 let text=String(value??'').slice(0,6000);
 for(let pass=0;pass<2;pass++) {
  text=text.replace(/&(#x[0-9a-f]{1,6}|#[0-9]{1,7}|amp|commat|period|plus|nbsp|tab|newline|zerowidthspace|shy);?/gi,(match,key)=>key[0]==='#'?scalar(parseInt(key.slice(key[1].toLowerCase()==='x'?2:1),key[1].toLowerCase()==='x'?16:10),match):entities[key.toLowerCase()]);
  text=text.replace(/%([0-9a-f]{2})/gi,(match,hex)=>{const code=parseInt(hex,16);return code>=32&&code<=126?String.fromCharCode(code):match;});
  text=text.replace(/\\u([0-9a-f]{4})|\\x([0-9a-f]{2})/gi,(match,unicode,hex)=>scalar(parseInt(unicode||hex,16),match));
 }
 text=text.replace(/<\/?[a-z][^<>\r\n]{0,120}>/gi,' ').normalize('NFKC').replace(/(^|[^\p{L}\p{N}_])át(?=$|[^\p{L}\p{N}_])/giu,'$1at_hu').normalize('NFD').replace(/[\p{M}\p{Cf}]/gu,'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'').toLowerCase();
 text=text.replace(/[\u0660-\u0669\u06f0-\u06f9\u0966-\u096f]/g,char=>String(char.charCodeAt(0)-(char.charCodeAt(0)>=0x966?0x966:char.charCodeAt(0)>=0x6f0?0x6f0:0x660)));
 return text.replace(/[。｡]/g,'.').replace(/[–—−]/g,'-').replace(/\b(?:plusz|plus)\b/g,'+');
}

function plainAtIsEmail(rest) {
 return /^\s+(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s*(?:\.|dot|pont|\s)\s*(?:hu|com|net|org|eu|de|test)\b/.test(rest)
  || /^\s+[a-z0-9-]{1,63}(?:\s+[a-z0-9-]{1,63}){0,2}\s+(?:dot|pont)\s+[a-z]{2,24}\b/.test(rest)
  || /^\s+[a-z0-9-]{1,63}\.[a-z]{2,24}\b/.test(rest)
  || /^\s+[a-z0-9-]{1,63}\s*\.\s*(?:hu|com|net|org|eu|de|test)\b/.test(rest);
}
function emailLike(text) {
 // Most estate descriptions contain no e-mail marker. Avoid all candidate
 // patterns in that case, especially on maximum-length ordinary prose.
 if(!['@','kukac','arroba','at','email','e-mail','e mail','mailcim'].some(marker=>text.includes(marker)))return false;
 let email=text.replace(/[\[({]\s*(?:kukac|at|arroba)\s*[\])}]/g,'@').replace(/kukac|arroba/g,'@');
 email=email.replace(/\bat\b/g,(match,index,whole)=>plainAtIsEmail(whole.slice(index+2,index+202))?'@':match);
 email=email.replace(/[\[({]\s*(?:pont|dot)\s*[\])}]/g,'.').replace(/pont|dot/g,'.');
 email=email.replace(/(?:\b[a-z]\s+){1,30}[a-z]\b/g,part=>part.replace(/\s/g,'')).replace(/\s+/g,' ');
 // Adjacent @ signs bound disjoint candidate segments. No unanchored address
 // expression repeatedly scans a long local part or a long invalid domain.
 const localEnd=/[\p{L}\p{N}._%+\-]$/u;
 const domain=/^\s*[\p{L}\p{N}\-]{1,63}(?:\s*\.\s*[\p{L}\p{N}\-]{1,63}){0,7}\s*\.\s*[\p{L}]{1,24}/u;
 const spokenHost=/^\s*(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s+(?:hu|com|net|org|eu|de|test)\b/;
 for(let at=email.indexOf('@');at>=0;){
  const next=email.indexOf('@',at+1);let end=at;while(end>0&&email[end-1]===' ')end--;
  if(localEnd.test(email.slice(Math.max(0,end-2),end))){
   const rest=email.slice(at+1,Math.min(at+769,next>=0?next:email.length));
   if(domain.test(rest)||spokenHost.test(rest))return true;
  }
  at=next;
 }
 // A missing @ does not make an explicitly introduced e-mail address safe.
 const introduction=/\b(?:emailcim|mailcim|e-mail|e mail|email)/g;
 const introducedAddress=/^\s*[:=]?\s*[a-z0-9._%+\-]{1,80}\s+(?:gmail|freemail|citromail|outlook|hotmail|yahoo)\s*\.\s*[a-z]{2,12}\b/;
 for(const marker of email.matchAll(introduction))if(introducedAddress.test(email.slice(marker.index+marker[0].length,marker.index+marker[0].length+220)))return true;
 return false;
}

function underHundred(word) {
 if(Object.hasOwn(digits,word))return Number(digits[word]);
 if(Object.hasOwn(tens,word))return tens[word];
 for(const [prefix,value] of smallPrefixes)if(word.startsWith(prefix)){
  const rest=word.slice(prefix.length);if(Object.hasOwn(digits,rest)&&Number(digits[rest])>0)return value+Number(digits[rest]);
 }
 return null;
}
function underThousand(word) {
 const small=underHundred(word);if(small!==null)return small;
 for(const unit of ['szaz','hundred']) {
  const index=word.indexOf(unit);if(index<0)continue;
  const prefix=word.slice(0,index),head=prefix?underHundred(prefix):1,tail=word.slice(index+unit.length).replace(/^and/,'');
  const rest=tail?underHundred(tail):0;
  if(head!==null&&head>=1&&head<=9&&rest!==null)return head*100+rest;
 }
 return null;
}
function numberWord(word) {
 if(!word||word.length>80)return null;
 const small=underThousand(word);if(small!==null)return String(small);
 for(const unit of ['ezer','thousand']) {
  const index=word.indexOf(unit);if(index<0)continue;
  const prefix=word.slice(0,index),head=prefix?underHundred(prefix):1,tail=word.slice(index+unit.length).replace(/^and/,'');
  const rest=tail?underThousand(tail):0;
  if(head!==null&&head>=1&&head<=9&&rest!==null)return String(head*1000+rest);
 }
 // Digit-by-digit spelling is also accepted without spaces: nullahatharom...
 let at=0,result='',count=0;
 while(at<word.length){const piece=numberPieces.find(([name])=>word.startsWith(name,at));if(!piece)return null;result+=piece[1];at+=piece[0].length;count++;}
 return count>=2?result:null;
}
function atomAt(tokens,index,text) {
 const token=tokens[index];if(/^\d+$/.test(token.text))return {start:token.start,end:token.end,digits:token.text,last:index};
 let word='',best=null;
 for(let next=index;next<tokens.length&&next<index+6;next++){
  const current=tokens[next];if(!/^[a-z]+$/.test(current.text)||next>index&&!/^[\s-]+$/.test(text.slice(tokens[next-1].end,current.start)))break;
  word+=current.text;if(word.length>80)break;const value=numberWord(word);if(value!==null)best={start:token.start,end:current.end,digits:value,last:next};
 }
 return best;
}
function phoneContext(text,start,end) {return /\b(?:telefon|tel|mobil|hivj|hivjon|hivhato|elerhetoseg|elerhetsz|whatsapp|viber|sms|phone|call|contact)\b/.test(text.slice(Math.max(0,start-64),start)+' '+text.slice(end,end+24));}
function safeNumberRun(text,run) {
 const start=run[0].start,end=run.at(-1).end;if(phoneContext(text,start,end))return false;
 const before=text.slice(Math.max(0,start-64),start),after=text.slice(end,end+36),raw=text.slice(start,end);
 if(/^\s*(?:ft|huf|eur|euro|usd|forint|millio|milliard|nm|m2|cm|mm|meter|negyzetmeter|hektar|ha|kw|kwh|w|fo|db|szoba|emelet|ev|eves)(?![a-z0-9])/.test(after)||/^\s*[€$%]/.test(after))return true;
 if(/\b(?:ar|ara|iranyar|iranyara|vetelar|vetelara|keret|budget|price|alapterulet|telekmeret|terulet|fogyasztas|hrsz|azonosito|gps|koordinata)\s*[:=]?\s*$/.test(before)||/helyrajzi\s+szam\s*[:=]?\s*$/.test(before))return true;
 if(/\b(?:busz|buszjarat|buszjaratok|jarat|jaratok|villamos|tram)\b/.test(before)&&raw.includes(','))return true;
 const values=run.map(atom=>Number(atom.digits)),sizes=run.map(atom=>atom.digits.length);
 if(run.length===2&&sizes.every(size=>size===4)&&values.every(value=>value>=1800&&value<=2200))return true;
 if(run.length===3&&((sizes[0]===4&&values[0]>=1800&&values[0]<=2200&&values[1]>=1&&values[1]<=12&&values[2]>=1&&values[2]<=31)||(sizes[2]===4&&values[2]>=1800&&values[2]<=2200&&values[1]>=1&&values[1]<=12&&values[0]>=1&&values[0]<=31)))return true;
 if(/^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$/.test(raw))return true;
 return false;
}
function phoneNumber(number,hasPlus) {
 if(hasPlus&&number.length>=8&&number.length<=15&&number[0]!=='0')return true;
 if(number.startsWith('00')&&number.length>=10&&number.length<=17&&number[2]!=='0')return true;
 if((number.startsWith('06')||number.startsWith('36'))&&(number.length===10||number.length===11))return true;
 if(number.length>=7&&number.length<=15)return true;
 return false;
}
function runHasPhone(text,run) {
 if(!run.length)return false;
 const all=run.map(atom=>atom.digits).join(''),start=run[0].start,end=run.at(-1).end;
 const plus=/\+\s*$/.test(text.slice(Math.max(0,start-12),start));
 const explicit=(plus&&all.length>=8&&all.length<=15&&all[0]!=='0')||(all.startsWith('00')&&all.length>=10&&all.length<=17&&all[2]!=='0')||(all.startsWith('06')&&(all.length===10||all.length===11));
 if(explicit)return true;
 if(safeNumberRun(text,run))return false;
 if(phoneNumber(all,plus))return true;
 // A preceding year must not hide an explicit national/international number.
 for(let first=0;first<run.length;first++){
  let number='';for(let last=first;last<run.length&&last<first+15;last++){
   number+=run[last].digits;if(number.length>17)break;
   if((number.startsWith('06')||number.startsWith('36'))&&(number.length===10||number.length===11)||number.startsWith('00')&&number.length>=10)return true;
  }
 }
 return false;
}
function phoneLike(text) {
 const tokens=[...text.matchAll(/[a-z]+|[0-9]+/g)].map(match=>({text:match[0],start:match.index,end:match.index+match[0].length}));
 let run=[];
 for(let index=0;index<tokens.length;index++){
  const atom=atomAt(tokens,index,text);
  if(!atom){if(runHasPhone(text,run))return true;run=[];continue;}
  if(run.length&&!/^[^a-z0-9]{0,16}$/.test(text.slice(run.at(-1).end,atom.start))){if(runHasPhone(text,run))return true;run=[];}
  run.push(atom);index=atom.last;
 }
 return runHasPhone(text,run);
}
export function containsContactDetails(value) {const text=normalize(value);return emailLike(text)||phoneLike(text);}
export function assertDescriptionContactFree(value) {if(containsContactDetails(value))throw new Error(descriptionContactMessage);}
