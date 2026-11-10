/** Display-only public identity. Keep behavior aligned with PublicProfile.cs. */
const email = /[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_.-]+\.[\p{L}]{2,}/u;
const link = /https?:\/\/|www\.|(?:[\p{L}\p{N}-]+\.)+(?:hu|com|net|org|eu|io|dev|app|test)(?:[/?#\s.,;!)]|$)/iu;
const phone = /(?<!\d)(?:\+\d{1,3}|0036|06)[\s().-]*(?:\d[\s().-]*){6,12}|(?:tel(?:efon)?|mobil|hívj)\s*[:.]?\s*\+?\d(?:[\s().-]*\d){5,14}/iu;
const nameToken = /^[\p{L}\p{M}]+(?:['’\-][\p{L}\p{M}]+)*$/u;
const honorifics = new Set(['dr', 'prof', 'ifj', 'id', 'özv']);
const clean = input => String(input ?? '').slice(0, 2048).replace(/[\p{Cc}\p{Cf}]/gu, ' ').replace(/\s+/gu, ' ').trim();
const hasContact = value => email.test(value) || link.test(value) || phone.test(value);

export function publicFirstName(name) {
  let value = clean(name);
  if (!value || /[@<>]/u.test(value) || hasContact(value)) return '';
  value = value.split(/[·|,;(\[—–]/u, 1)[0].trim();
  if (/\d/u.test(value)) return '';
  const words = value.split(' ').filter(Boolean).filter(word => !honorifics.has(word.replace(/\.+$/u, '').toLocaleLowerCase('hu-HU')));
  if (!words.length || words.some(word => !nameToken.test(word))) return '';
  const firstName = words.at(-1);
  return firstName.length <= 40 ? firstName : '';
}

export function publicTitle(title, fallback) {
  const value = clean(String(title ?? '').replace(/<[^>]*>/gu, ' '));
  if (!value || hasContact(value)) return fallback;
  return value.slice(0, 150).trimEnd();
}
