import test from 'node:test';
import assert from 'node:assert/strict';
import {publicFirstName, publicTitle} from '../dist/public-profile.js';

test('public given names use the current Hungarian display name without its family name', () => {
  for (const [name, expected] of [
    ['Kovács Anna', 'Anna'], ['Nagy Péter', 'Péter'], ['Dr. ifj. Szabó Eszter', 'Eszter'],
    ['Anna', 'Anna'], ['Kiss Anna-Mária', 'Anna-Mária'], ["Kiss O’Anna", 'O’Anna'],
    ['Kiss Kata · import-12', 'Kata'], ['Varga Dániel (teszt)', 'Dániel'],
    ['  Tóth\nRéka  ', 'Réka']
  ]) assert.equal(publicFirstName(name), expected, name);
});

test('unsafe owner names cannot become public contact or markup', () => {
  for (const name of [null, '', '   ', 'Anna123', 'Anna anna@example.test', 'Anna +36 30 123 4567',
    'www.example.hu', 'https://example.test/Anna', 'Anna<script>alert</script>', 'Kiss A.', 'A'.repeat(41)]) {
    assert.equal(publicFirstName(name), '', String(name));
  }
});

test('ordinary real titles preserve their price, area, year and room digits', () => {
  for (const title of ['Kertes családi otthont keresünk', 'Felújított lakás 65 m², 2 + 1 fél szoba',
    '2006-ban épült családi ház', '120 m² ház 60 000 000 Ft-ért', '2–3 szobás otthont keresek 80M-ig']) {
    assert.equal(publicTitle(title, 'Biztonságos cím'), title);
  }
  assert.equal(publicTitle('  Világos\n lakás  ', 'Lakás'), 'Világos lakás');
  assert.equal(publicTitle('<b>Világos lakás</b>', 'Lakás'), 'Világos lakás');
  assert.equal(publicTitle('a'.repeat(200), 'Lakás').length, 150);
});

test('missing or contact-bearing titles use a safe generated fallback', () => {
  for (const title of [null, '', ' ', 'Írj: anna@example.test', 'Hívj +36 30 123 4567',
    'Telefon: 555 1234', 'Ház 06 20 123 4567', 'Otthon https://example.test',
    'Otthon www.example.hu', 'További képek: example.hu, érdeklődj!']) {
    assert.equal(publicTitle(title, 'Eladó lakás'), 'Eladó lakás', String(title));
  }
});
