# 🤖 Autonomous Web Calculator Agent

Projeto prático de aprendizado focado em **Engenharia de Agentes de IA aplicados ao ciclo de desenvolvimento de software (SDLC)** utilizando **GitHub Actions**.

A proposta é evoluir uma calculadora web de forma incremental — **uma feature ou correção por Issue** — onde uma esteira multi-agente recebe a demanda, implementa o código, valida com testes determinísticos (lógica + contrato de UI), atualiza a documentação, revisa o `git diff` completo e abre um Pull Request pronto para aprovação humana (*Human-in-the-Loop*) com deploy automático via **GitHub Pages**.

🌐 **Demo ao vivo:** `https://VitorAlvs.github.io/calculadora-web-agent/` 

---

## 🎯 Objetivo

Sair do uso manual de LLMs via chat e construir, na prática, uma esteira autônoma ponta a ponta (*Issue → Código → Testes → Docs → Revisão → PR → Deploy*), respondendo a problemas reais de engenharia:

- Onde a IA realmente precisa agir e onde automação determinística comum resolve melhor?
- Como separar responsabilidades entre agentes sem multiplicar falhas em cascata?
- Como impedir que um agente quebre código antigo, trunque documentação, entre em loop infinito ou altere arquivos sensíveis?
- Como manter custo de tokens previsível e lidar com instabilidades reais de API (`503`, `429`, timeouts e cortes de geração)?

---

## 🔄 Workflow Autônomo (Issue → PR → Deploy)

```mermaid
flowchart LR
    A["1. Issue + label agent-ready<br/>(Automação - 0% IA)"] --> B["2. Agente Dev<br/>(IA - Código/Testes)"]
    B --> C["3. Validação & Contrato UI<br/>node --check + node --test<br/>(Automação - 0% IA)"]
    C -- "Falha de código (até 3x)" --> B
    C -- "Erro 503/Timeout (exit 2)" --> R["Auto-retry no Workflow<br/>(espera 60s)"]
    R --> B
    C -- "Passou (exit 0)" --> D["4. Commit de código na branch<br/>(Automação - 0% IA)"]
    D --> E["5. Agente Docs<br/>(IA - README.md, fail-soft)"]
    E --> F["6. Commit de docs & PR<br/>(Automação - 0% IA)"]
    F --> G["7. Agente Revisor<br/>(IA - Somente Leitura)"]
    G --> H["8. Notificação & Merge<br/>(Human-in-the-Loop)"]
    H --> I["9. Deploy Automático<br/>(GitHub Pages)"]
```

1. **Gatilho:** Uma Issue é aberta em inglês e marcada com a label `agent-ready`. O workflow `.github/workflows/agent-dev.yml` só executa se o autor for o dono do repositório.
2. **Agente Dev (`.agent/run_agent.py`):** Lê apenas os arquivos de código permitidos + descrição da Issue e retorna o plano de edição em formato JSON estruturado.
3. **Portão Determinístico (`node --check` + `node --test`):** Verifica sintaxe, executa todos os testes unitários (regressão das operações anteriores) e roda `tests/ui-contract.test.js` para garantir que cada chave em `SUPPORTED_OPERATORS` possui um botão `data-op` correspondente no `index.html`. Se falhar, o erro exato volta para o Agente Dev em um loop *Evaluator-Optimizer* (até `MAX_STEPS = 3`).
4. **Tratamento de Instabilidade (`exit code 2`):** Se todos os modelos falharem por erro transitório (`503`, `RateLimitError`, timeout ou truncamento), o script encerra com código `2` e o workflow aguarda `60s` para uma nova rodada automática antes de reportar na Issue.
5. **Agente Docs (`.agent/run_docs_agent.py`):** Após o commit do código na branch `agent/issue-<N>`, um segundo agente isolado lê o `git diff` + a Issue e atualiza o `README.md` em um commit separado (`docs(agent): ...`). Opera em modo *fail-soft* com guardrail anti-truncamento para nunca derrubar um PR de código válido.
6. **Agente Revisor (`.agent/run_reviewer.py`):** Um terceiro agente, com contexto isolado e **permissão somente leitura**, audita o `git diff main...HEAD` completo (código + `README.md`) contra a Issue original, publica o parecer no PR e marca o mantenedor como *Reviewer*.
7. **Aprovação Humana e Deploy:** Após revisão e merge manual na `main`, o **GitHub Pages** publica a nova versão automaticamente.

---

## 🎨 Arquitetura da Calculadora (UI Orientada por Registro)

A interface segue o formato de uma calculadora moderna em grade (`4x5`) com visor superior e slots fixos para operadores (`+`, `-`, `*`, `/`, `%`):

- **`src/calculator.js` como fonte única da verdade:** exporta `calculate(a, b, operator)` e o mapa `SUPPORTED_OPERATORS`.
- **Desbloqueio automático de botões:** ao carregar, `src/app.js` lê `SUPPORTED_OPERATORS`. Operações implementadas ganham símbolo e ficam clicáveis; operações pendentes permanecem como quadrados cinzas desabilitados.
- **Validação de contrato determinística:** `tests/ui-contract.test.js` impede que um operador seja adicionado na lógica sem o respectivo slot `data-op` no `index.html`.
- **Vantagem para os agentes:** cada nova operação exige alteração apenas em `src/calculator.js` e `tests/calculator.test.js`, reduzindo o consumo de tokens e eliminando o risco de quebrar HTML/CSS.

---

## 🧠 Arquitetura de IA, Modelos e Integração ("Ponte")

Para manter o orquestrador desacoplado de qualquer fornecedor único, a comunicação com os modelos segue o **padrão de API compatível com OpenAI** usando a SDK oficial `openai` em Python apontando diretamente para a **Gemini API do Google**:

- **Provedor / Endpoint ("Ponte"):** Endpoint oficial OpenAI-compatible do Google AI Studio (`https://generativelanguage.googleapis.com/v1beta/openai/`). Trocar para OpenRouter, Groq, OpenAI ou Ollama local exige alterar apenas as *Repository Secrets*, sem modificar o código Python.
- **Modelo Principal:** `gemini-3.8-flash`
- **Cadeia de Fallback Automático (1 tentativa por modelo/rodada):** `gemini-3.7-flash` → `gemini-3.6-flash` → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite`.
- **Controle de Raciocínio e Saídas Estruturadas:** Contratos validados via **Pydantic** (`AgentCodePlan`, `DocsUpdatePlan` e `ReviewVerdict`) com `reasoning_effort="low"` para evitar desperdício de *thinking tokens*, tratamento explícito de `LengthFinishReasonError` e fallback para injeção de JSON Schema.

---

## 📁 Estrutura do Repositório

```text
calculadora-web-agent/
├── .agent/
│   ├── prompts/
│   │   ├── dev_v1.md            # System prompt versionado do Agente Dev (v1.2.0)
│   │   ├── docs_v1.md           # System prompt versionado do Agente Docs (v1.0.0)
│   │   └── reviewer_v1.md       # System prompt versionado do Agente Revisor (v1.1.0)
│   ├── run_agent.py             # Orquestrador Dev + validação + fallback resiliente
│   ├── run_docs_agent.py        # Agente Docs (README.md only, fail-soft + anti-truncamento)
│   └── run_reviewer.py          # Agente Revisor somente leitura (código + README)
├── .github/
│   └── workflows/
│       └── agent-dev.yml        # Esteira CI/CD autônoma disparada por Issues
├── src/
│   ├── app.js                   # Estado do teclado, eventos e leitura de SUPPORTED_OPERATORS
│   └── calculator.js            # Lógica pura e registro SUPPORTED_OPERATORS
├── tests/
│   ├── calculator.test.js       # Testes unitários das operações (node:test)
│   └── ui-contract.test.js      # Validação determinística de contrato (SUPPORTED_OPERATORS ↔ HTML)
├── index.html                   # Interface da calculadora (keypad + display)
├── style.css                    # Estilização (inclui estado bloqueado dos operadores)
└── package.json                 # Configuração ES Modules + script de testes
```

---

## 🛡️ Guardrails e Segurança

- **Allowlists segregadas (*Least Privilege*):**
  - **Dev Agent:** só pode escrever em `index.html`, `style.css`, `src/*.js` e `tests/*.js` (bloqueia *path traversal* e edições em `.github/`, `.agent/` ou `README.md`).
  - **Docs Agent:** permissão travada exclusivamente em `README.md`, com validação anti-truncamento (rejeita atualizações abaixo de 85% do tamanho original ou sem título H1/seção Roadmap) e comportamento *fail-soft*.
  - **Reviewer Agent:** 100% somente leitura; nunca modifica arquivos.
- **Trava de autor no workflow:** Apenas Issues criadas pelo `repository_owner` podem acionar os agentes, mitigando *prompt injection* e consumo indevido de cota em repositório público.
- **Circuit Breakers de custo e tempo:**
  - `max_tokens`: `16.384` por chamada (com `reasoning_effort="low"`).
  - `MAX_RUN_TOKENS`: `60.000` (Dev) e `30.000` (Docs).
  - `timeout`: `90s` por requisição HTTP e `timeout-minutes: 15` no job do GitHub Actions.
  - `MAX_STEPS`: `3` ciclos de auto-correção de código; relatório garantido mesmo em caso de falha ou cancelamento (`failure() || cancelled()`).
- **Human-in-the-Loop (HITL):** Os agentes nunca fazem push direto na `main`; o merge final permanece sob controle humano.

---

## 📚 O que eu aprendi na prática

1. **Automação normal segura a esteira; IA só entra onde precisa pensar:** Criar branches, rodar testes, validar contrato de UI, abrir PRs e fazer deploy são etapas determinísticas (0% IA).
2. **Separação de papéis e menor privilégio entre agentes:** Isolar **Dev** (código), **Docs** (`README.md` em modo *fail-soft*) e **Reviewer** (somente leitura) evita poluição de contexto e impede que uma falha na documentação bloqueie a entrega de código.
3. **Separação entre `/prompts` e código do agente:** Versionar prompts (`dev v1.2.0`, `docs v1.0.0`, `reviewer v1.1.0`) permite auditar na telemetria qual instrução gerou cada PR.
4. **Padronizar código, prompts e Issues em inglês economiza tokens:** Reduz a fragmentação de tokens e elimina conflitos de idioma entre interface e testes.
5. **Evitar *Retry Storms*:** Multiplicar retries internos no Python com retries externos no workflow dispara `RateLimitError` e estoura o tempo do job. O ideal é 1 tentativa por modelo na cadeia de fallback e um retry espaçado único no workflow para erros transitórios (`exit code 2`).
6. **Tokens de raciocínio (*thinking*) consomem o `max_tokens`:** Em tarefas multi-arquivo (como o redesign da UI), modelos com raciocínio podem esgotar o limite de saída antes de concluir o JSON (`LengthFinishReasonError`). Configurar `reasoning_effort="low"` e teto adequado resolve o truncamento e acelera a resposta.
7. **Arquitetura desacoplada reduz erros da IA:** Usar `SUPPORTED_OPERATORS` como fonte única da verdade permite adicionar operações sem que o agente precise reescrever HTML e CSS.
8. **Agentes seguem a especificação ao pé da letra:** Se uma Issue de redesign esquecer de mencionar uma feature anterior (como a subtração), o agente pode removê-la ou travá-la obedecendo literalmente ao escopo escrito.

---

## ⚙️ Como replicar (Configuração no GitHub)

1. **Permissões do Actions:** Em `Settings → Actions → General → Workflow permissions`, habilite **Read and write permissions** e **Allow GitHub Actions to create and approve pull requests**.
2. **Label de gatilho:** Crie a label `agent-ready` em `Issues → Labels`.
3. **Repository Secrets** (`Settings → Secrets and variables → Actions`):

| Secret | Exemplo / Descrição |
|---|---|
| `LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `LLM_API_KEY` | Sua chave da Gemini API (ou outro provedor compatível com OpenAI) |
| `LLM_MODEL` | `gemini-3.8-flash` |
| `LLM_FALLBACK_MODELS` | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite` |

4. **GitHub Pages:** Em `Settings → Pages`, configure **Deploy from a branch** → `main` → `/ (root)`.

---

## 🚀 Evolução Incremental (Roadmap)

- [x] Estrutura base (HTML/CSS/ES Modules + `node --test`) e GitHub Pages
- [x] Esteira autônoma de Issue → Agente Dev → Testes → PR
- [x] Operação de Soma (`+`) — Issue #1
- [x] Agente Revisor somente leitura + notificação de revisão no PR
- [x] Operação de Subtração (`-`) — Issue #3
- [x] Redesign da UI com teclado e slots bloqueados (`SUPPORTED_OPERATORS`) — Issue #5
- [x] Fix: destravar botão de Subtração (`-`) em `SUPPORTED_OPERATORS` — Issue #7
- [x] Operação de Multiplicação (`*`) — Issue #9
- [x] Agente de Documentação (`Docs Agent`) *fail-soft* + auditoria de README no Revisor + teste de contrato de UI
- [x] Operação de Divisão (`/`) com tratamento para divisão por zero — Issue #11
- [ ] Operação de Porcentagem (`%`)
