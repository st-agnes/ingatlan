import { randomBytes } from 'node:crypto';
import { writeFile, access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const path=fileURLToPath(new URL('../.env',import.meta.url));
try { await access(path); console.log('A .env már létezik; nem módosítottuk.'); }
catch(error) {
 if(error.code!=='ENOENT')throw error;
 await writeFile(path,`MYSQL_PASSWORD=${randomBytes(24).toString('hex')}\nMYSQL_ROOT_PASSWORD=${randomBytes(24).toString('hex')}\nJWT_KEY=${randomBytes(48).toString('hex')}\nASPNETCORE_ENVIRONMENT=Development\nFRONTEND_ORIGIN=http://localhost:8080\nDATABASE_INITIALIZE=true\nSEED_DEMO=true\nENABLE_DEMO_TOPUP=true\n`,{mode:0o600,flag:'wx'});
 console.log('A helyi .env elkészült egyedi, véletlen kulcsokkal. Indítás: docker compose up --build -d');
}
