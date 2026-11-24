import test from 'node:test';
import assert from 'node:assert/strict';
import { calculate, SUPPORTED_OPERATORS } from '../src/calculator.js';

test('SUPPORTED_OPERATORS registry contains +, -, *, /, and %', () => {
  assert.strictEqual(SUPPORTED_OPERATORS['+'], '+');
  assert.strictEqual(SUPPORTED_OPERATORS['-'], '−');
  assert.strictEqual(SUPPORTED_OPERATORS['*'], '×');
  assert.strictEqual(SUPPORTED_OPERATORS['/'], '÷');
  assert.strictEqual(SUPPORTED_OPERATORS['%'], '%');
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

test('multiplication (*) positive numbers', () => {
  assert.strictEqual(calculate(3, 4, '*'), 12);
});

test('multiplication (*) negative numbers', () => {
  assert.strictEqual(calculate(-3, 4, '*'), -12);
  assert.strictEqual(calculate(-3, -4, '*'), 12);
});
test('multiplication (*) with zero', () => {
  assert.strictEqual(calculate(5, 0, '*'), 0);
  assert.strictEqual(calculate(0, 5, '*'), 0);
});

test('multiplication (*) decimals', () => {
  assert.strictEqual(calculate(0.2, 0.3, '*'), 0.06);
});

test('division (/) positive numbers', () => {
  assert.strictEqual(calculate(12, 4, '/'), 3);
});

test('division (/) negative numbers', () => {
  assert.strictEqual(calculate(-12, 4, '/'), -3);
  assert.strictEqual(calculate(-12, -4, '/'), 3);
});

test('division (/) decimals', () => {
  assert.strictEqual(calculate(7.5, 2.5, '/'), 3);
});

test('division (/) by zero throws error', () => {
  assert.throws(() => calculate(5, 0, '/'), /Cannot divide by zero/);
});

test('percentage (%) positive numbers', () => {
  assert.strictEqual(calculate(200, 15, '%'), 30);
});

test('percentage (%) negative numbers', () => {
  assert.strictEqual(calculate(-200, 15, '%'), -30);
  assert.strictEqual(calculate(200, -15, '%'), -30);
});

test('percentage (%) with zero', () => {
  assert.strictEqual(calculate(100, 0, '%'), 0);
  assert.strictEqual(calculate(0, 100, '%'), 0);
});

test('percentage (%) decimals', () => {
  assert.strictEqual(calculate(50, 0.5, '%'), 0.25);
});