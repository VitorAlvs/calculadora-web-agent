import { calculate } from './calculator.js';

const form = document.getElementById('calc-form');
const resultEl = document.getElementById('result');

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const a = Number(document.getElementById('num-a').value);
  const b = Number(document.getElementById('num-b').value);
  const op = document.getElementById('operator').value;

  try {
    resultEl.textContent = `Resultado: ${calculate(a, b, op)}`;
  } catch (err) {
    resultEl.textContent = `Erro: ${err.message}`;
  }
});