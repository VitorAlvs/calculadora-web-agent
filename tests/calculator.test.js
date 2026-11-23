import test from 'node:test';
import assert from 'node:assert/strict';
import { calculate } from '../src/calculator.js';

test('throws error for unimplemented operation', () => {
  assert.throws(() => calculate(1, 1, '?'), /not implemented/i);
});