import { randomInt } from 'node:crypto';
const username = process.argv[2] || 'wcs';
if (!/^[A-Za-z0-9_-]{1,64}$/.test(username)) throw new Error('Use um nome simples sem espaços');
const password = String(randomInt(100000000)).padStart(8, '0');
console.log(`Usuário: ${username}\nSenha: ${password}\n`);
console.log('Configure SESSIONS_JSON no ambiente privado do servidor:');
console.log(JSON.stringify({ [username]: password }));
