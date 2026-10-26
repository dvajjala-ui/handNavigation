const sharp = require('sharp');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
  const dir = path.join(__dirname, 'assets'); fs.mkdirSync(dir, {recursive:true});
  const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"><rect width="256" height="256" rx="58" fill="#192d28"/><path d="M66 61v134h27v-53h70v53h27V61h-27v53H93V61z" fill="#e9f5d7"/><path d="m156 48 34 13-34 13z" fill="#c2e878"/></svg>');
  const png = await sharp(svg).png().toBuffer(); fs.writeFileSync(path.join(dir,'icon.png'),png);
  const header = Buffer.alloc(22); header.writeUInt16LE(1,2); header.writeUInt16LE(1,4); header[6]=0; header[7]=0;
  header.writeUInt16LE(1,10); header.writeUInt16LE(32,12); header.writeUInt32LE(png.length,14); header.writeUInt32LE(22,18);
  fs.writeFileSync(path.join(dir,'icon.ico'),Buffer.concat([header,png]));
}
main().catch(e=>{console.error(e);process.exit(1);});
