# Interaction Pet Contract

## Compatibility

The official Codex runtime reads `pet.json` and `spritesheet.webp`. The interaction extension never changes their geometry or manifest fields.

An interaction-capable runtime additionally reads `interaction.json` and `interaction-spritesheet.webp`. The current Codex client does not read these files.

## Package

```text
package/
  pet.json
  spritesheet.webp
  interaction.json
  interaction-spritesheet.webp
```

`interaction.json` owns:

- interaction atlas geometry and animation rows
- deterministic needs and offline decay caps
- user actions and item effects
- automatic need-state selection
- Codex task-state bindings
- compatibility metadata stating that an extended runtime is required

## Deterministic State

Every need uses an integer range from 0 to 100. A runtime applies decay from elapsed time, caps offline decay to the manifest value, clamps every result, and persists the updated timestamp. Do not add random decay, random rewards, or hidden probability.

The default state is:

```json
{
  "hunger": 80,
  "cleanliness": 80,
  "mood": 70,
  "energy": 80,
  "health": 100,
  "growth": 0,
  "coins": 30
}
```

The package also declares starter inventory. Consumable items are spent only after an action animation completes. When inventory is empty, the runtime may buy exactly one required item at its declared price as part of the same transaction. Non-consumable items remain owned after purchase.

Health never decreases below the configured safe floor from offline decay alone. When hunger or cleanliness is critically low, the declared critical health decay applies deterministically. The base contract has no death state.

## Event Priority

An interaction runtime resolves one visible state in this order:

1. active direct action
2. Codex needs-input or blocked state
3. critical health, hunger, cleanliness, or energy condition
4. Codex running or ready state
5. ambient happy or official idle state

Direct actions are transactional. Apply their item cost and state effects only after their non-looping animation completes. Interrupted actions apply neither cost nor reward.

## Security

The extension is data-only. It contains no executable JavaScript, commands, remote URLs, or dynamic code. A future runtime must validate the manifest before loading it and must keep network access disabled by default.
