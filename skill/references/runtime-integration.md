# Runtime Integration

Read this file only when implementing client support for the interaction package.

## Required Client Change

Keep the existing `/pet` command and pet overlay. Extend the selected-pet loader so it optionally loads `interaction.json` from the same pet directory. When the file is absent, preserve existing behavior exactly.

The runtime needs five components:

1. A strict manifest parser that rejects unknown schema versions and invalid references.
2. An atlas player that can select official or interaction animations without changing the overlay window.
3. A deterministic state reducer for needs, actions, items, growth, and offline elapsed time.
4. A local persistence adapter keyed by pet id and interaction schema version.
5. Pet interaction controls that dispatch declared actions rather than arbitrary code.

## Command Flow

```text
/pet -> existing toggle command -> existing overlay -> optional interaction runtime
```

Do not register a second `/pet` command. Do not intercept keyboard input. Do not send `/pet` through model prompts or lifecycle hooks.

## Task Events

Map existing pet states to the official atlas:

- running -> official `running`
- needs input -> official `waiting`
- ready -> official `review`
- blocked -> official `failed`

Interaction actions temporarily take visual priority, then return to the highest-priority task or need state. Persist gameplay state independently from chat state.

## Distribution Constraint

Patching `app.asar` is suitable only for a local proof of concept. A public product requires an official extension point or permission to distribute a modified client. Do not package or redistribute OpenAI binaries with the pet skill.
