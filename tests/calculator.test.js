import test from 'node:test';
import assert from 'node:assert/strict';
import { calculate } from '../src/calculator.js';

test('lança erro para operação ainda não implementada', () => {
  assert.throws(() => calculate(1, 1, '?'), /não implementada/i);
});