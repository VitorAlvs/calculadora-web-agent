import test from 'node:test';
import assert from 'node:assert/strict';
import { calculate, SUPPORTED_OPERATORS } from '../src/calculator.js';

test('SUPPORTED_OPERATORS registry contains + and - and excludes unhandled ops', () => {
  assert.strictEqual(SUPPORTED_OPERATORS['+'], '+');
  assert.strictEqual(SUPPORTED_OPERATORS['-'], '−');
  assert.strictEqual(SUPPORTED_OPERATORS['*'], undefined);
  assert.strictEqual(SUPPORTED_OPERATORS['/'], undefined);
  assert.strictEqual(SUPPORTED_OPERATORS['%'], undefined);
});

test('throws error for unimplemented operation', () => {
  assert.throws(() => calculate(1, 1, '?'), /not implemented/i);
});

test('addition (+) positive numbers', () => {
  assert.strictEqual(calculate(2, 3, '+'), 5);
});

test('addition (+) negative numbers', () => {
  assert.strictEqual(calculate(-2, -3, '+'), -5);
});

test('addition (+) with zero', () => {
  assert.strictEqual(calculate(5, 0, '+'), 5);
  assert.strictEqual(calculate(0, 0, '+'), 0);
});

test('addition (+) decimals', () => {
  assert.strictEqual(calculate(0.1, 0.2, '+'), 0.30000000000000004);
});

test('subtraction (-) positive numbers', () => {
  assert.strictEqual(calculate(5, 3, '-'), 2);
});

test('subtraction (-) negative results', () => {
  assert.strictEqual(calculate(3, 5, '-'), -2);
});

test('subtraction (-) with zero', () => {
  assert.strictEqual(calculate(5, 0, '-'), 5);
  assert.strictEqual(calculate(0, 5, '-'), -5);
});

test('subtraction (-) decimals', () => {
  assert.strictEqual(calculate(0.3, 0.1, '-'), 0.19999999999999998);
});
