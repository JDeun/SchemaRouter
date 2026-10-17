# Qwen3 model-selected 2-step native-bound host tool-history contrast — E0 DEV

**Owner:** #1477, qualification A02/R05. Stacked on the model-proposed
two-step parent #1506, with pinned Qwen3-0.6B on GitHub Actions Linux CPU.

## Observed baseline

[run 39029981154](https://github.com/JDeun/SchemaRouter/actions/runs/39029981154)
demonstrated that all English/Korean/Japanese tasks produced one
authorized real SchemaRouter-bound synthetic read and then a
**premature final**; 0/3 complete. The follow-up generic one-time
TASK_INCOMPLETE [run 39030372571](https://github.com/JDeun/SchemaRouter/actions/runs/39030372571)
likewise yielded one bound call and a premature final in each case
(0/3). Original negative raw results remain frozen and unmodified.

## Preregistered possible transport-format confound

The original pinned Qwen adapter decodes
`skip_special_tokens=False`, so its generated assistant
tool-call content may contain a canonical ChatML end-of-turn marker.
The E0 host-execution pilot then embeds that **raw assistant text**
inside a *new* rendered chat-template assistant message and wraps the
tool's already tagged response in additional XML.

[Hugging Face's Transformers tool-use documentation](https://huggingface.co/docs/transformers/en/chat_extras)
recommends representing an executed assistant tool call in a
structured `tool_calls` key and appending a
tool-role response. We will test whether this difference **matters**
for the previously failed stateful second turn, rather than assume a
Qwen reasoning failure or promise a performance gain.

The one experiment tests **two named non-default transcript modes**
with the *same fixed natural language prompts*, the same Qwen weight
revision, source routes, first provider output, exposed tool schemas,
host-side route/typed input validation, strict final-answer oracle,
and current policy.

- `raw` (original reference): assistant
  XML **with generated EOS marker** and tool-role content with manual
  `<tool_response>` wrapper. Kept
  byte-compatible and remains the default.
- `strip-eos`: remove **only one canonical
  terminal ChatML EOS suffix** from assistant *history*, but retain the
  same XML tool call and XML-wrapped tool-role response.
- `structured`: represent the actual
  already-authorized executed call with an assistant
  `tool_calls=[{type:function,function:{name,arguments}}]`
  and pass **plain serialized public JSON** in the tool-role response.
  Let the model's own chat template handle structural markup.

Neither mode changes the parsing/authorization of the model's **new**
proposal, the number or identity of allowed tools, hidden metadata,
prompt instructions or provider I/O. No expected route order or task
gold may enter the tokenizer. The module does not authorize operations:
it can only append a sanitized transcript **after** an actual
principal-approved host invocation.

A 2-step success still requires two real SchemaRouter executor
invocations, correct dependent model-proposed typed argument and an
exact final JSON matched to the hidden actual host result. Failed
model attempts and early finals remain visible as metrics-only
negative cases, not substituted successes.

## Limitations and gate

Exposed researcher-authored **three cases, one per EN/KO/JA**. In-process
synthetic read providers and a single boolean final oracle, not
original third-party provider operations or independent author-reviewed
E2. A positive result may be a task/transcript-format effect on this
small source and does **not** warrant tuned production defaults.

**A02 NOT_VERIFIED, R05 NOT_VERIFIED, 0/19 independent E2;
v0.18 release #1356 and default model promotion HOLD.**
