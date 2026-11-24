/** Original decorative illustrations for form choices; no external assets or user markup. */
const frame = scene => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 104" aria-hidden="true" focusable="false"><ellipse cx="80" cy="54" rx="71" ry="45" fill="#f2f4eb"/><g stroke-linecap="round" stroke-linejoin="round">${scene}</g></svg>`;
const wallOutline = '<rect x="28" y="22" width="104" height="66" rx="3" fill="none" stroke="#647a62" stroke-width="2"/>';
const brickRows = ({color='#d79670',mortar='#fff5e8',x=28,y=22,width=104,height=66}={}) => {
 let result=`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="3" fill="${color}"/>`;
 for(let row=1;row<4;row++)result+=`<path d="M${x} ${y+row*height/4}h${width}" stroke="${mortar}" stroke-width="3"/>`;
 for(let row=0;row<4;row++)for(let column=row%2?1:0;column<4;column++){
  const offset=(column+.5*(row%2===0))*width/4;
  if(offset>0&&offset<width)result+=`<path d="M${x+offset} ${y+row*height/4}v${height/4}" stroke="${mortar}" stroke-width="3"/>`;
 }
 return result;
};
const house = ({wall='#eedac3',roof='#d98d69',detail=''}={}) => `<path d="M41 45h78v44H41z" fill="${wall}" stroke="#74836a" stroke-width="2"/><path d="m31 47 49-32 49 32" fill="${roof}" stroke="#a66849" stroke-width="3"/><rect x="52" y="58" width="18" height="19" rx="2" fill="#fdf7dd" stroke="#70826a" stroke-width="2"/><path d="M61 59v17m-8-9h16" stroke="#70826a" stroke-width="2"/><path d="M87 89V61h17v28" fill="#6d8d73"/><path d="M29 89h102" stroke="#7e9672" stroke-width="3"/>${detail}`;
const conditions = Object.freeze({
 'Felújítandó':'<path d="M37 46h86v43H37z" fill="#d5c7b0" stroke="#8a8374" stroke-width="2"/><path d="m25 48 35-26 15 8 8-14 18 13 8-3 27 22" fill="#a89b8a" stroke="#7d7267" stroke-width="4"/><path d="m84 45-13 13 10 12-13 18m39-46-8 11 10 10" fill="none" stroke="#8b7060" stroke-width="4"/><rect x="45" y="56" width="21" height="22" fill="#716f64"/><path d="m43 57 24 19m-24 1 24-19" stroke="#ad8966" stroke-width="6"/><path d="M97 89V64h15v25" fill="#8d7b68"/><path d="m20 91 9-12 10 12m78 0 9-7 11 7" fill="#b5a590" stroke="#8e806e" stroke-width="2"/>',
 'Átlagos':house({wall:'#ded7c3',roof:'#ab866c',detail:'<path d="M42 81h15v7H42m55-39h20v6H97" fill="#c6bda5"/><path d="M76 52v14m-3-5 7-4m29 20h7" stroke="#b2aa91" stroke-width="3"/><path d="M24 88h13m88 0h12" stroke="#9caa85" stroke-width="3"/>'}),
 'Jó':house({wall:'#f0dfc3',roof:'#c98158',detail:'<path d="M22 86V64" stroke="#688567" stroke-width="3"/><ellipse cx="22" cy="62" rx="11" ry="16" fill="#9dbf85"/><rect x="48" y="78" width="26" height="6" rx="2" fill="#a87858"/><path d="M53 78v-6m15 6v-6" stroke="#758f61" stroke-width="2"/><circle cx="53" cy="71" r="4" fill="#dc9a87"/><circle cx="68" cy="71" r="4" fill="#e5b57c"/><path d="M119 86h19" stroke="#8ca078" stroke-width="3"/>'}),
 'Új/felújított':'<rect x="34" y="34" width="91" height="55" rx="2" fill="#fffaf0" stroke="#83977d" stroke-width="2"/><path d="M29 34h101v-8H29z" fill="#7c9f86"/><path d="M90 34h35v55H90z" fill="#e6c8a9"/><rect x="45" y="47" width="35" height="27" fill="#c7e2df" stroke="#6e958b" stroke-width="2"/><path d="M62 48v25m29 16V51h21v38" stroke="#829e8d" stroke-width="3"/><path d="M44 80h36" stroke="#d9c295" stroke-width="3"/><path d="M17 26v16m-8-8h16m110-20v12m-6-6h12m-2 35v8m-4-4h8" stroke="#dfb255" stroke-width="3"/><circle cx="127" cy="82" r="14" fill="#dbeed0"/><path d="m120 82 5 5 10-12" fill="none" stroke="#6d985b" stroke-width="3"/>'
});
const windowFrame = '<rect x="24" y="15" width="112" height="73" rx="4" fill="none" stroke="#8b8f76" stroke-width="5"/><path d="M80 17v69m-54-35h108M18 91h124" stroke="#8b8f76" stroke-width="5"/>';
const views = Object.freeze({
 'Kertre néző':'<rect x="25" y="17" width="110" height="68" fill="#e8f0ec"/><path d="M26 67q31-18 54-2t54-3v23H26z" fill="#bdd3a6"/><path d="M53 73V43m57 31V36" stroke="#819573" stroke-width="4"/><circle cx="53" cy="40" r="17" fill="#9fbd86"/><circle cx="109" cy="36" r="18" fill="#b2ca91"/><path d="M39 81h7m65-3h8" stroke="#df936d" stroke-width="3"/>'+windowFrame,
 'Utcai':'<rect x="25" y="17" width="110" height="68" fill="#e9f1ef"/><path d="M26 22h41v43H26z" fill="#d6c9b7"/><path d="M95 17h39v48H95z" fill="#dec5ae"/><path d="M35 32h8v10h-8zm15 0h8v10h-8zm54-4h8v10h-8zm15 0h8v10h-8z" fill="#fbf6df"/><path d="M26 66h108v19H26z" fill="#b8beb6"/><path d="M41 76h14m47 0h14" stroke="#fff9e9" stroke-width="3"/>'+windowFrame,
 'Udvari':'<rect x="25" y="17" width="110" height="68" fill="#eaf0e8"/><path d="M26 24h29v47H26zm79 0h29v47h-29z" fill="#d8c6b2"/><path d="M54 33h51v23H54z" fill="#e8d8c2"/><path d="M26 72h108v13H26z" fill="#d7d8c0"/><path d="M66 80 77 58h8l11 22" fill="#ede5d2"/><circle cx="97" cy="67" r="7" fill="#a9c08e"/><path d="M35 35h11v11H35zm79 0h11v11h-11z" fill="#fdf6de"/>'+windowFrame,
 'Panorámás':'<rect x="25" y="17" width="110" height="68" fill="#e1eef0"/><circle cx="111" cy="32" r="9" fill="#edd39b"/><path d="m26 65 27-24 25 21 23-14 33 22v15H26z" fill="#afc7bd"/><path d="m26 79 37-20 26 15 26-17 19 18v10H26z" fill="#8eac9a"/><path d="M41 85V74h9v11m48 0V72h8v13" stroke="#789581" stroke-width="2"/>'+windowFrame
});
const buildings = Object.freeze({
 'Tégla': brickRows()+wallOutline,
 'Panel':'<rect x="28" y="22" width="104" height="66" rx="3" fill="#d0d6ce"/><path d="M80 23v64M29 55h102" stroke="#9da99d" stroke-width="3"/><rect x="43" y="32" width="20" height="16" rx="2" fill="#edf4ee" stroke="#8e9e8d" stroke-width="2"/><rect x="96" y="65" width="20" height="16" rx="2" fill="#edf4ee" stroke="#8e9e8d" stroke-width="2"/>'+wallOutline,
 'Csúsztatott zsalu':'<rect x="28" y="22" width="104" height="66" rx="3" fill="#c4cec3"/><path d="M40 25v59m16-59v59m16-59v59m16-59v59m16-59v59m16-59v59" stroke="#b0bdaf" stroke-width="2"/><path d="M24 17h112m-99-5v10m86-10v10" stroke="#a17f5e" stroke-width="4"/><path d="m38 75 10-8m55-28 13-6" stroke="#d7dfd3" stroke-width="3"/>'+wallOutline,
 'Vályog':brickRows({color:'#c9af87',mortar:'#e5d8bd'})+'<path d="m42 35 7 3m41 7 6-3m-35 29 6 4m42-2 6-3m-78-8 5 3" stroke="#a58d64" stroke-width="2"/>'+wallOutline,
 'Szilikát':brickRows({color:'#e4e5d9',mortar:'#b9c4b3'})+'<path d="M37 31h7m51 18h8m-34 30h8m37-43h7" stroke="#c8cfbf" stroke-width="2"/>'+wallOutline,
 'Vegyes falazat':brickRows({x:28,y:22,width:54,height:66})+'<path d="M82 22h50v66H82z" fill="#c3c7b9"/><path d="m84 41 16-17 18 12 13-5m-47 34 19-10 14 16 15-14m-27-33-2 31m15-19-2 35m-12-14-6 32" fill="none" stroke="#f2f1e6" stroke-width="3"/>'+wallOutline,
 'Fa':'<rect x="28" y="22" width="104" height="66" rx="3" fill="#d5ad7e"/><path d="M46 23v64m17-64v64m18-64v64m17-64v64m17-64v64" stroke="#a77f55" stroke-width="2"/><path d="M35 32q7 17 0 32m17-30q7 15 0 40m18-41q-6 16 0 30m20-29q5 16 0 41m15-37q7 12 0 27m18-38q-5 19 0 34" fill="none" stroke="#be9465" stroke-width="2"/>'+wallOutline,
 'Könnyűszerkezet':'<rect x="28" y="22" width="104" height="66" rx="3" fill="#e8ddbb"/><path d="M32 26h96v58H32zM63 26v58m33-58v58m-63-57 29 57m35-57 30 57" fill="none" stroke="#b88e64" stroke-width="6"/><path d="M99 24h31v62H99z" fill="#e8ecdf" stroke="#a8b59f" stroke-width="2"/><path d="M107 35h15m-15 15h15m-15 15h15" stroke="#c6d0bd" stroke-width="2"/>'+wallOutline,
 'Kő és tégla':brickRows({height:34})+'<path d="M28 56h104v32H28z" fill="#b8c0b1"/><path d="m29 73 16-16 18 14 17-14 18 13 18-13 15 10m-102 7 23 1 10-4 19 2 18-3 18 7 13-10M53 75l7 13m21-15 9 15m27-11-5 11" fill="none" stroke="#f3f2e8" stroke-width="3"/>'+wallOutline,
 'Rönkház':'<rect x="28" y="23" width="104" height="65" rx="5" fill="#bd9368"/>'+[0,1,2,3].map(row=>`<rect x="23" y="${23+row*17}" width="114" height="15" rx="7" fill="${row%2?'#d8b287':'#cda578'}" stroke="#9e774f" stroke-width="2"/><ellipse cx="31" cy="${30+row*17}" rx="5" ry="5" fill="none" stroke="#ad8053" stroke-width="2"/>`).join(''),
 'Passzívház':house({wall:'#e7ebd8',roof:'#8ba778',detail:'<path d="M37 47v38m86-38v38" stroke="#c4d6ad" stroke-width="5"/><path d="M122 59c20-16 23-2 13 9-8 9-18 3-13-9z" fill="#b2ce94" stroke="#749861" stroke-width="2"/><path d="m121 74 14-14" stroke="#749861" stroke-width="2"/><path d="m48 25-6-8m21-2-1-7" stroke="#ceac64" stroke-width="2"/>'}),
 'Egyéb':'<rect x="28" y="22" width="104" height="66" rx="3" fill="#dce3d2"/><path d="M29 55h102m-68-32v64m34-64v64" stroke="#b0c0a5" stroke-width="3"/><path d="m40 34 9-5 9 5v10l-9 5-9-5zm34 32 9-5 9 5v10l-9 5-9-5zm34-32 9-5 9 5v10l-9 5-9-5z" fill="#c6d4b9" stroke="#8da17c" stroke-width="2"/>'+wallOutline
});
const ceilingHeights = Object.freeze({
 '3 m alatti':'<path d="M31 34h99v53H31z" fill="#e8e6d5"/><path d="M30 34h101M30 88h101" stroke="#9aa58c" stroke-width="4"/><rect x="45" y="49" width="25" height="24" rx="2" fill="#eaf2e8" stroke="#a7b69b" stroke-width="2"/><path d="M119 42v37m-4-32 4-5 4 5m-8 27 4 5 4-5" fill="none" stroke="#c48260" stroke-width="2"/><circle cx="89" cy="60" r="6" fill="#d7a980"/><path d="M89 67v16m-7-10 7-6 7 6m-7 10-5 5m5-5 5 5" fill="none" stroke="#738d69" stroke-width="4"/>',
 '3 m feletti':'<path d="M31 14h99v73H31z" fill="#e8e6d5"/><path d="M30 14h101M30 88h101" stroke="#9aa58c" stroke-width="4"/><rect x="45" y="30" width="25" height="43" rx="2" fill="#eaf2e8" stroke="#a7b69b" stroke-width="2"/><path d="M119 22v57m-4-52 4-5 4 5m-8 47 4 5 4-5" fill="none" stroke="#c48260" stroke-width="2"/><circle cx="89" cy="60" r="6" fill="#d7a980"/><path d="M89 67v16m-7-10 7-6 7 6m-7 10-5 5m5-5 5 5" fill="none" stroke="#738d69" stroke-width="4"/>'
});
const moveIn = Object.freeze({
 'Rugalmas':'<circle cx="80" cy="54" r="31" fill="#e8eddd" stroke="#8da27e" stroke-width="4"/><path d="M80 33v23l15 8" fill="none" stroke="#6d8660" stroke-width="5"/><path d="m31 41-10 14 14 8m-12-9h25m81 11 10-14-14-8m12 9h-25" fill="none" stroke="#c89767" stroke-width="4"/>',
 'Azonnal':'<path d="m73 15-27 44h24l-9 31 49-49H85l12-26z" fill="#e0b46c" stroke="#ba8f51" stroke-width="2"/><path d="M113 76h23m-9-9v18" stroke="#7c9c70" stroke-width="4"/><path d="M25 28h18m-12-9 12 9-12 9" fill="none" stroke="#a9bd94" stroke-width="3"/>',
 '3 hónapon belül':'<rect x="35" y="23" width="90" height="66" rx="8" fill="#fffaf0" stroke="#8b9b7e" stroke-width="3"/><path d="M36 44h88V28q0-5-6-5H42q-6 0-6 5z" fill="#c5d7ad"/><path d="M57 16v17m46-17v17" stroke="#7e9670" stroke-width="5"/><text x="80" y="77" text-anchor="middle" font-family="sans-serif" font-size="29" font-weight="700" fill="#6a805e">3</text>',
 '6 hónapon belül':'<rect x="35" y="23" width="90" height="66" rx="8" fill="#fffaf0" stroke="#8b9b7e" stroke-width="3"/><path d="M36 44h88V28q0-5-6-5H42q-6 0-6 5z" fill="#dfc9ab"/><path d="M57 16v17m46-17v17" stroke="#a48969" stroke-width="5"/><text x="80" y="77" text-anchor="middle" font-family="sans-serif" font-size="29" font-weight="700" fill="#967857">6</text>'
});
const scenes = Object.freeze({condition:conditions,view:views,building:buildings,ceilingHeight:ceilingHeights,moveIn});
const fallback = '<rect x="35" y="25" width="90" height="57" rx="6" fill="#e3e9da" stroke="#8fa17f" stroke-width="2"/><path d="m54 65 18-20 13 13 12-15 14 22" fill="none" stroke="#a4b597" stroke-width="4"/>';

/** Choice values select fixed artwork; unknown legacy labels never become SVG markup. */
export function attributeCardIllustration(kind,value){
 const group=Object.hasOwn(scenes,kind)?scenes[kind]:null;
 return frame(group&&Object.hasOwn(group,value)?group[value]:fallback);
}

const materialHelp = Object.freeze({
 'Tégla':'Égetett agyagtéglából falazott szerkezet. Fedetlen részen vöröses vagy narancsbarna elemek és habarcsfugák látszhatnak; a modern tégla üreges is lehet. A vakolat vagy burkolat alapján nem dönthető el biztosan: a terv, az építési dokumentáció vagy szakember segít.',
 'Panel':'Üzemben előregyártott, nagy vasbeton falelemekből épített szerkezet. Jellegzetesek lehetnek a homlokzat vízszintes és függőleges elemillesztései, de ezeket szigetelés is elfedheti. A mintázat önmagában nem bizonyíték; az épület dokumentációjában ellenőrizhető.',
 'Csúsztatott zsalu':'A helyszínen öntött, jellemzően vasbeton fal, amelyet az építéssel együtt felfelé mozgatott zsaluzattal készítenek. Nem nagy előregyártott panelekből áll. A sima vagy vakolt felületből nem különíthető el biztosan más betonépülettől; a szerkezeti terv vagy szakvélemény a mérvadó.',
 'Vályog':'Agyagos földből készült, nem égetett falazat, gyakran növényi rostokkal, például szalmával keverve. Meglévő fedetlen részen földszínű, rostos anyag vagy vályogtéglák látszhatnak. A külső vakolat nem árulja el az anyagot; bizonytalanság esetén dokumentáció vagy szakember szükséges.',
 'Szilikát':'A megnevezés többféle ásványi falazóelemet takarhat, például mészhomoktéglát vagy régebbi gázszilikátot. Az elemek gyakran világosak vagy szürkék, de ebből a pontos anyag nem állapítható meg. Érdemes az építési tervben, az anyag megnevezésében vagy szakértővel ellenőrizni.',
 'Vegyes falazat':'Az épület falai többféle szerkezeti anyagból készültek, például téglából, vályogból és kőből. Fedetlen részeken eltérő elemek vagy építési szakaszok látszhatnak. A különböző festés vagy burkolat még nem jelent vegyes falazatot; a tényleges falszerkezetet kell ellenőrizni.',
 'Fa':'A fal teherhordó szerkezetében fa az alapvető anyag; ide tömörfa és egyes favázas megoldások is tartozhatnak. Látszó faelemek támpontot adhatnak, de a fa homlokzatburkolat önmagában nem bizonyít fa falszerkezetet. A tervből vagy a szerkezet szakértői vizsgálatából derül ki.',
 'Könnyűszerkezet':'Jellemzően fa- vagy acélvázra épülő, lemezburkolatokkal és hőszigeteléssel kialakított falrendszer. Réteges szerkezete dokumentációból vagy már látható csomópontból ismerhető fel. A kész homlokzat könnyen hasonlíthat falazott házra; a külső megjelenés nem biztos azonosítás.',
 'Kő és tégla':'A fal teherhordó részeiben kő és tégla egyaránt jelen van, például eltérő falszakaszokban vagy egymás fölötti rétegekben. Fedetlen részen kődarabok és szabályos téglák látszhatnak. A kőhatású burkolat nem elegendő ehhez a besoroláshoz; a valódi falszerkezetet kell ellenőrizni.',
 'Rönkház':'Tömör, egymásra fektetett rönkökből vagy megmunkált gerendaelemekből épülő fal. Jellegzetesek lehetnek a vízszintes fasorok és az egymásba kapcsolódó sarokvégek. A rönkhatású burkolat más szerkezetet is fedhet, ezért a dokumentációból érdemes meggyőződni róla.',
 'Passzívház':'Nem falazóanyag, hanem nagyon alacsony energiaigényre vonatkozó épületkövetelmény: többféle falszerkezettel is elérhető. A vastag szigetelés vagy a korszerű ablak önmagában nem igazolja. Energetikai számítás, műszaki dokumentáció vagy passzívház-minősítés támaszthatja alá.',
 'Egyéb':'A felsorolt kategóriákba nem illő vagy különleges falszerkezet. A pontos anyag és rendszer a hirdetés leírásából vagy az építési dokumentációból derülhet ki. A kész felületből többnyire nem azonosítható biztosan; az építési dokumentáció és szakember adhat megbízható információt.'
});

/** Plain text: callers must escape it when placing it into HTML. */
export function buildingHelp(value){
 return Object.hasOwn(materialHelp,value)?materialHelp[value]:'A falszerkezet anyagát a kész felület vagy burkolat alapján nem lehet mindig felismerni. Az építési dokumentáció, a műszaki leírás vagy szakember segíthet a pontos azonosításban.';
}
