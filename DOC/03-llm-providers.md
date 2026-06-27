# 3. LLM providers

**Package:** `src/agentic_kris/llm/`

This layer is the reason the system can run *fully local* or *via the Claude API*
without any agent code changing. Agents only ever see the abstract
`LLMProvider`.

## 3.1 The interface — `base.py`

```python
class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def stream(self, system: str, messages: List[Message]) -> Iterator[str]: ...

    def complete(self, system, messages) -> str:      # derived from stream
        return "".join(self.stream(system, messages))

    def health_check(self) -> str: ...                # cheap reachability probe
```

- A `Message` is just `{"role": "user" | "assistant", "content": "..."}`.
- Only `stream` is abstract. `complete` is **derived** from it, so every backend
  gets blocking and streaming use for the price of one method.
- `health_check` returns a human string on success and raises on failure; the UI
  uses it for the "✅ Backend ready" message.

## 3.2 Ollama (local) — `ollama_provider.py`

`OllamaProvider(host, model, timeout=120)` talks to a running Ollama server over
plain HTTP (`POST /api/chat` with `stream=True`), parsing the newline-delimited
JSON stream and yielding each `message.content` chunk. No SDK beyond `requests`,
so the whole system can run offline.

`health_check` hits `GET /api/tags` and reports whether the chosen model is
pulled.

## 3.3 Anthropic (external) — `anthropic_provider.py`

`AnthropicProvider(api_key, model, max_tokens=4096)` uses the official
`anthropic` SDK. Notable details:

- The `anthropic` package is imported **lazily inside `__init__`**, so the
  project imports cleanly even if the SDK isn't installed and you only want
  Ollama.
- A missing key raises a clear `ValueError` immediately (fail fast, with a
  message telling you to set `.env` or the in-app field).
- `stream` uses the SDK's `messages.stream(...).text_stream`.
- `health_check` makes a 1-token call to confirm key + model + connectivity
  cheaply.

## 3.4 The factory — `factory.py`

```python
AVAILABLE = ["anthropic", "ollama"]
def available_providers() -> List[str]: ...
def get_provider(provider=None, *, model=None, api_key=None) -> LLMProvider: ...
```

`get_provider` resolves the provider name (argument **or** `settings.llm_provider`),
then constructs the right backend. **Precedence for each value is: explicit
argument > `.env`.** That is exactly how the UI lets a user type a model/key into
chat settings and have it win over the file.

An unknown name raises `ValueError` listing the valid options.

### 🧪 Experiment — build providers without a network

```bash
python -c "
from agentic_kris.llm.factory import available_providers, get_provider
print('available:', available_providers())

# Ollama provider constructs without contacting anything:
o = get_provider('ollama', model='llama3.1')
print(o.name, o.model, o.host)

# Anthropic without a key fails fast and clearly:
try:
    get_provider('anthropic', api_key='')
except ValueError as e:
    print('expected error:', e)
"
```

### 🧪 Experiment — a fake provider implements the whole interface in 4 lines

This is the pattern the tests use to exercise agents/orchestration with zero LLM
cost. Any object with a `stream` method *is* a provider:

```bash
python -c "
from agentic_kris.llm.base import LLMProvider

class Echo(LLMProvider):
    name = 'echo'
    def stream(self, system, messages):
        yield 'You said: '
        yield messages[-1]['content']

p = Echo()
print(p.complete('sys', [{'role':'user','content':'hi'}]))   # blocking, derived
print(''.join(p.stream('sys', [{'role':'user','content':'hi'}])))  # streaming
"
```

### 🧪 Experiment — a real Ollama round-trip (optional)

Requires a running Ollama with a pulled model:

```bash
ollama pull llama3.1
python -c "
from agentic_kris.llm.factory import get_provider
p = get_provider('ollama', model='llama3.1')
print(p.health_check())
for tok in p.stream('You are terse.', [{'role':'user','content':'Say hello in 3 words.'}]):
    print(tok, end='', flush=True)
print()
"
```
