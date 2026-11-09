/** Assertions shared by the real API smoke and its deterministic privacy regressions. */
import assert from 'node:assert/strict';

const privateKeys = new Set(['email','phone','contact','password','passwordhash','accesstoken','refreshtoken']);

export function assertNoContactData(value, privateValues) {
  const secrets = privateValues.filter(item => typeof item === 'string' && item.length > 0);
  function visit(item) {
    if (typeof item === 'string') {
      for (const secret of secrets)
        assert.ok(!item.includes(secret), 'A complete private value appeared in the public feed.');
    } else if (item && typeof item === 'object') {
      for (const [key, child] of Object.entries(item)) {
        assert.ok(!privateKeys.has(key.toLowerCase()), `Private field appeared in the public feed: ${key}`);
        visit(child);
      }
    }
  }
  visit(value);
}
