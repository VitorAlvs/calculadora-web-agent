import { calculate, SUPPORTED_OPERATORS } from './calculator.js';

const prevDisplay = document.getElementById('prev-expression');
const mainDisplay = document.getElementById('main-display');

let firstOperand = null;
let currentOperator = null;
let currentInput = '0';
let isNewInput = true;
let isError = false;

function updateDisplay() {
  mainDisplay.textContent = currentInput;
  if (firstOperand !== null && currentOperator !== null) {
    const opSymbol = SUPPORTED_OPERATORS[currentOperator] || currentOperator;
    prevDisplay.textContent = `${firstOperand} ${opSymbol}`;
  } else {
    prevDisplay.textContent = '';
  }
}

function clearAll() {
  firstOperand = null;
  currentOperator = null;
  currentInput = '0';
  isNewInput = true;
  isError = false;
  updateDisplay();
}

function clearEntry() {
  currentInput = '0';
  isNewInput = true;
  isError = false;
  updateDisplay();
}

function handleDigit(digit) {
  if (isError) {
    clearAll();
  }
  if (digit === '.') {
    if (isNewInput) {
      currentInput = '0.';
      isNewInput = false;
    } else if (!currentInput.includes('.')) {
      currentInput += '.';
    }
  } else {
    if (isNewInput || currentInput === '0') {
      currentInput = digit;
      isNewInput = false;
    } else {
      currentInput += digit;
    }
  }
  updateDisplay();
}

function handleOperator(op) {
  if (isError) return;
  if (!SUPPORTED_OPERATORS || !SUPPORTED_OPERATORS[op]) return;

  const numInput = Number(currentInput);

  if (firstOperand !== null && currentOperator !== null && !isNewInput) {
    try {
      const result = calculate(firstOperand, numInput, currentOperator);
      firstOperand = result;
      currentInput = String(result);
    } catch (err) {
      isError = true;
      currentInput = err.message;
      firstOperand = null;
      currentOperator = null;
      updateDisplay();
      return;
    }
  } else {
    firstOperand = numInput;
  }

  currentOperator = op;
  isNewInput = true;
  updateDisplay();
}

function handleEquals() {
  if (isError || firstOperand === null || currentOperator === null) return;

  const secondOperand = Number(currentInput);
  const opSymbol = SUPPORTED_OPERATORS[currentOperator] || currentOperator;
  prevDisplay.textContent = `${firstOperand} ${opSymbol} ${secondOperand} =`;

  try {
    const result = calculate(firstOperand, secondOperand, currentOperator);
    currentInput = String(result);
    firstOperand = null;
    currentOperator = null;
    isNewInput = true;
    mainDisplay.textContent = currentInput;
  } catch (err) {
    isError = true;
    currentInput = err.message;
    firstOperand = null;
    currentOperator = null;
    mainDisplay.textContent = currentInput;
  }
}

function initKeypad() {
  const opButtons = document.querySelectorAll('button[data-op]');
  opButtons.forEach((btn) => {
    const op = btn.dataset.op;
    if (SUPPORTED_OPERATORS && SUPPORTED_OPERATORS[op]) {
      btn.textContent = SUPPORTED_OPERATORS[op];
      btn.disabled = false;
    } else {
      btn.textContent = '';
      btn.disabled = true;
    }
  });
}

document.querySelectorAll('.btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.dataset.digit !== undefined) {
      handleDigit(btn.dataset.digit);
    } else if (btn.dataset.op !== undefined) {
      handleOperator(btn.dataset.op);
    } else if (btn.dataset.action === 'clear') {
      clearAll();
    } else if (btn.dataset.action === 'ce') {
      clearEntry();
    } else if (btn.dataset.action === 'equals') {
      handleEquals();
    }
  });
});

document.addEventListener('keydown', (event) => {
  const key = event.key;
  if (key >= '0' && key <= '9') {
    handleDigit(key);
  } else if (key === '.') {
    handleDigit('.');
  } else if (key === '+' || key === '-' || key === '*' || key === '/' || key === '%') {
    handleOperator(key);
  } else if (key === 'Enter' || key === '=') {
    event.preventDefault();
    handleEquals();
  } else if (key === 'Escape') {
    clearAll();
  } else if (key === 'Backspace') {
    clearEntry();
  }
});

initKeypad();
updateDisplay();
