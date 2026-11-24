export const SUPPORTED_OPERATORS = {
  '+': '+',
  '-': '−',
  '*': '×',
  '/': '÷',
  '%': '%'
};

export function calculate(a, b, operator) {
  if (operator === '+') {
    return a + b;
  }
  if (operator === '-') {
    return a - b;
  }
  if (operator === '*') {
    return a * b;
  }
  if (operator === '/') {
    if (b === 0) {
      throw new Error('Cannot divide by zero');
    }
    return a / b;
  }
  if (operator === '%') {
    return (a * b) / 100;
  }
  throw new Error(`Operation not implemented: ${operator}`);
}