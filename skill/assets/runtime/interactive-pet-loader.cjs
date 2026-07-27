"use strict";

const MAX_MANIFEST_BYTES = 256 * 1024;
const MAX_ATLAS_BYTES = 20 * 1024 * 1024;
const NEED_KEYS = new Set([
  "hunger",
  "cleanliness",
  "mood",
  "energy",
  "health",
  "growth",
  "coins",
]);

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function assertFiniteNumber(value, name) {
  assert(typeof value === "number" && Number.isFinite(value), `${name} must be a finite number`);
}

function assertInteger(value, name, min, max) {
  assert(Number.isInteger(value) && value >= min && value <= max, `${name} must be an integer from ${min} to ${max}`);
}

function assertKnownKeys(object, allowed, name) {
  for (const key of Object.keys(object)) {
    assert(allowed.has(key), `${name} contains unsupported field ${key}`);
  }
}

function validateCondition(condition, name) {
  assert(isObject(condition) && Object.keys(condition).length === 1, `${name} must target exactly one value`);
  const [valueName] = Object.keys(condition);
  assert(NEED_KEYS.has(valueName), `${name} targets unsupported value ${valueName}`);
  const comparison = condition[valueName];
  assert(isObject(comparison) && Object.keys(comparison).length === 1, `${name}.${valueName} must have one comparison`);
  const [operator] = Object.keys(comparison);
  assert(operator === "lte" || operator === "gte", `${name}.${valueName} uses unsupported comparison ${operator}`);
  assertFiniteNumber(comparison[operator], `${name}.${valueName}.${operator}`);
}

function validateManifest(manifest, expectedPetId) {
  assert(isObject(manifest), "interaction.json must contain an object");
  assertKnownKeys(
    manifest,
    new Set([
      "schemaVersion",
      "petId",
      "compatibility",
      "atlases",
      "animations",
      "initialState",
      "initialInventory",
      "needs",
      "automaticStates",
      "items",
      "actions",
      "taskEventBindings",
      "transactionPolicy",
    ]),
    "interaction.json",
  );
  assert(manifest.schemaVersion === 1, "schemaVersion must be 1");
  assert(manifest.petId === expectedPetId, `petId must match directory name ${expectedPetId}`);

  assert(isObject(manifest.compatibility), "compatibility is required");
  assert(manifest.compatibility.officialWakeCommand === "/pet", "officialWakeCommand must be /pet");
  assert(manifest.compatibility.requiredRuntimeCapability === "interactive-pet-v1", "unsupported runtime capability");

  assert(isObject(manifest.atlases) && isObject(manifest.atlases.interaction), "interaction atlas is required");
  const atlas = manifest.atlases.interaction;
  assertKnownKeys(atlas, new Set(["path", "columns", "rows", "cellWidth", "cellHeight"]), "atlases.interaction");
  assert(typeof atlas.path === "string" && atlas.path.trim().length > 0, "interaction atlas path is required");
  assertInteger(atlas.columns, "atlas columns", 1, 64);
  assertInteger(atlas.rows, "atlas rows", 1, 64);
  assertInteger(atlas.cellWidth, "atlas cellWidth", 16, 2048);
  assertInteger(atlas.cellHeight, "atlas cellHeight", 16, 2048);
  assert(atlas.columns * atlas.cellWidth <= 8192, "interaction atlas is too wide");
  assert(atlas.rows * atlas.cellHeight <= 8192, "interaction atlas is too tall");

  assert(isObject(manifest.animations) && Object.keys(manifest.animations).length > 0, "animations are required");
  for (const [animationName, animation] of Object.entries(manifest.animations)) {
    assert(/^[a-z][a-z0-9-]{0,63}$/.test(animationName), `invalid animation name ${animationName}`);
    assert(isObject(animation), `animation ${animationName} must be an object`);
    assertKnownKeys(animation, new Set(["atlas", "row", "frames", "durationsMs", "loop", "interruptible"]), `animation ${animationName}`);
    assert(animation.atlas === "interaction", `animation ${animationName} must use the interaction atlas`);
    assertInteger(animation.row, `animation ${animationName} row`, 0, atlas.rows - 1);
    assertInteger(animation.frames, `animation ${animationName} frames`, 1, atlas.columns);
    assert(Array.isArray(animation.durationsMs) && animation.durationsMs.length === animation.frames, `animation ${animationName} durations must match frames`);
    animation.durationsMs.forEach((duration, index) => assertInteger(duration, `animation ${animationName} duration ${index}`, 16, 10000));
    assert(typeof animation.loop === "boolean", `animation ${animationName} loop must be boolean`);
    assert(typeof animation.interruptible === "boolean", `animation ${animationName} interruptible must be boolean`);
  }

  assert(isObject(manifest.initialState), "initialState is required");
  for (const key of NEED_KEYS) {
    assertFiniteNumber(manifest.initialState[key], `initialState.${key}`);
  }
  for (const key of ["hunger", "cleanliness", "mood", "energy", "health"]) {
    assert(manifest.initialState[key] >= 0 && manifest.initialState[key] <= 100, `initialState.${key} must be from 0 to 100`);
  }
  assert(manifest.initialState.growth >= 0 && manifest.initialState.coins >= 0, "growth and coins cannot be negative");

  assert(isObject(manifest.items), "items must be an object");
  for (const [itemName, item] of Object.entries(manifest.items)) {
    assert(/^[a-z][a-z0-9-]{0,63}$/.test(itemName), `invalid item name ${itemName}`);
    assert(isObject(item), `item ${itemName} must be an object`);
    assertKnownKeys(item, new Set(["category", "cost", "consumable"]), `item ${itemName}`);
    assert(typeof item.category === "string" && item.category.length > 0, `item ${itemName} category is required`);
    assertInteger(item.cost, `item ${itemName} cost`, 0, 1000000);
    assert(item.consumable === undefined || typeof item.consumable === "boolean", `item ${itemName} consumable must be boolean`);
  }

  assert(isObject(manifest.initialInventory), "initialInventory must be an object");
  for (const [itemName, count] of Object.entries(manifest.initialInventory)) {
    assert(Object.hasOwn(manifest.items, itemName), `initialInventory references unknown item ${itemName}`);
    assertInteger(count, `initialInventory.${itemName}`, 0, 1000000);
  }

  assert(isObject(manifest.needs), "needs is required");
  assertKnownKeys(
    manifest.needs,
    new Set([
      "range",
      "offlineDecayCapHours",
      "healthSafeFloor",
      "criticalHealthDecayPerHour",
      "decayPerHour",
    ]),
    "needs",
  );
  assert(Array.isArray(manifest.needs.range) && manifest.needs.range.length === 2, "needs.range must contain two values");
  assert(manifest.needs.range[0] === 0 && manifest.needs.range[1] === 100, "needs.range must be 0 to 100");
  assertFiniteNumber(manifest.needs.offlineDecayCapHours, "needs.offlineDecayCapHours");
  assert(manifest.needs.offlineDecayCapHours >= 0 && manifest.needs.offlineDecayCapHours <= 168, "offline decay cap is invalid");
  assertFiniteNumber(manifest.needs.healthSafeFloor, "needs.healthSafeFloor");
  assert(isObject(manifest.needs.decayPerHour), "needs.decayPerHour is required");
  for (const key of ["hunger", "cleanliness", "mood", "energy", "health"]) {
    assertFiniteNumber(manifest.needs.decayPerHour[key], `needs.decayPerHour.${key}`);
  }
  if (manifest.needs.criticalHealthDecayPerHour !== undefined) {
    assertFiniteNumber(manifest.needs.criticalHealthDecayPerHour, "needs.criticalHealthDecayPerHour");
    assert(manifest.needs.criticalHealthDecayPerHour <= 0, "critical health decay cannot be positive");
  }

  assert(Array.isArray(manifest.automaticStates), "automaticStates must be an array");
  for (const [index, automaticState] of manifest.automaticStates.entries()) {
    assert(isObject(automaticState), `automaticStates[${index}] must be an object`);
    assertKnownKeys(automaticState, new Set(["when", "animation", "priority"]), `automaticStates[${index}]`);
    validateCondition(automaticState.when, `automaticStates[${index}].when`);
    assert(Object.hasOwn(manifest.animations, automaticState.animation), `automaticStates[${index}] references unknown animation`);
    assertInteger(automaticState.priority, `automaticStates[${index}].priority`, -1000000, 1000000);
  }

  assert(isObject(manifest.actions) && Object.keys(manifest.actions).length > 0, "actions are required");
  for (const [actionName, action] of Object.entries(manifest.actions)) {
    assert(/^[a-z][a-z0-9-]{0,63}$/.test(actionName), `invalid action name ${actionName}`);
    assert(isObject(action), `action ${actionName} must be an object`);
    assertKnownKeys(action, new Set(["animation", "completionAnimation", "item", "effects", "cooldownSeconds"]), `action ${actionName}`);
    assert(Object.hasOwn(manifest.animations, action.animation), `action ${actionName} references unknown animation`);
    if (action.completionAnimation !== undefined) {
      assert(Object.hasOwn(manifest.animations, action.completionAnimation), `action ${actionName} has unknown completion animation`);
    }
    if (action.item !== undefined) {
      assert(Object.hasOwn(manifest.items, action.item), `action ${actionName} references unknown item`);
    }
    assert(isObject(action.effects), `action ${actionName} effects must be an object`);
    for (const [effectName, amount] of Object.entries(action.effects)) {
      assert(NEED_KEYS.has(effectName), `action ${actionName} has unsupported effect ${effectName}`);
      assertFiniteNumber(amount, `action ${actionName} effect ${effectName}`);
    }
    assertInteger(action.cooldownSeconds, `action ${actionName} cooldownSeconds`, 0, 86400);
  }

  assert(isObject(manifest.transactionPolicy), "transactionPolicy is required");
  assert(manifest.transactionPolicy.applyEffects === "after-animation-completes", "effects must apply after animation completion");
  assert(manifest.transactionPolicy.interruptedAction === "apply-nothing", "interrupted actions must apply nothing");
  assert(manifest.transactionPolicy.clampNeedsToRange === true, "need values must be clamped");
  assert(manifest.transactionPolicy.randomness === "forbidden", "interaction randomness must be forbidden");
  return manifest;
}

function parseImage(buffer) {
  if (
    buffer.length >= 24 &&
    buffer[0] === 137 &&
    buffer.subarray(1, 4).toString("ascii") === "PNG" &&
    buffer.subarray(12, 16).toString("ascii") === "IHDR"
  ) {
    return { mimeType: "image/png", width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
  }
  if (buffer.length < 20 || buffer.subarray(0, 4).toString("ascii") !== "RIFF" || buffer.subarray(8, 12).toString("ascii") !== "WEBP") {
    return null;
  }
  let offset = 12;
  while (offset + 8 <= buffer.length) {
    const chunkType = buffer.subarray(offset, offset + 4).toString("ascii");
    const chunkLength = buffer.readUInt32LE(offset + 4);
    const dataOffset = offset + 8;
    if (dataOffset + chunkLength > buffer.length) return null;
    if (chunkType === "VP8X" && chunkLength >= 10) {
      return { mimeType: "image/webp", width: buffer.readUIntLE(dataOffset + 4, 3) + 1, height: buffer.readUIntLE(dataOffset + 7, 3) + 1 };
    }
    if (chunkType === "VP8L" && chunkLength >= 5 && buffer[dataOffset] === 47) {
      const bits = buffer.readUInt32LE(dataOffset + 1);
      const divisor = 2 ** 14;
      return { mimeType: "image/webp", width: (bits % divisor) + 1, height: (Math.floor(bits / divisor) % divisor) + 1 };
    }
    if (chunkType === "VP8" && chunkLength >= 10 && buffer[dataOffset + 3] === 157 && buffer[dataOffset + 4] === 1 && buffer[dataOffset + 5] === 42) {
      return { mimeType: "image/webp", width: buffer.readUInt16LE(dataOffset + 6) % 2 ** 14, height: buffer.readUInt16LE(dataOffset + 8) % 2 ** 14 };
    }
    offset = dataOffset + chunkLength + (chunkLength % 2);
  }
  return null;
}

function resolveInside(platformPath, directoryPath, relativePath) {
  const resolved = platformPath.resolve(directoryPath, relativePath);
  const relative = platformPath.relative(directoryPath, resolved);
  if (relative === "" || relative === ".." || relative.startsWith(`..${platformPath.sep}`) || platformPath.isAbsolute(relative)) {
    throw new Error("interaction atlas path must stay inside the pet directory");
  }
  return resolved;
}

function isMissingFile(error) {
  return Boolean(error && typeof error === "object" && error.code === "ENOENT");
}

async function loadInteractionForAvatar({ appServerClient, avatar, fileSystem, platformPath }) {
  if (typeof avatar.directoryPath !== "string" || avatar.directoryPath.length === 0) return avatar;
  const manifestPath = platformPath.join(avatar.directoryPath, "interaction.json");
  let manifestText;
  try {
    manifestText = await fileSystem.readFile(manifestPath, appServerClient);
  } catch (error) {
    if (isMissingFile(error)) return avatar;
    return { ...avatar, interactionError: `Cannot read interaction.json: ${error instanceof Error ? error.message : String(error)}` };
  }
  try {
    assert(Buffer.byteLength(manifestText, "utf8") <= MAX_MANIFEST_BYTES, "interaction.json is too large");
    const petId = avatar.id.startsWith("custom:") ? avatar.id.slice("custom:".length) : avatar.id;
    const manifest = validateManifest(JSON.parse(manifestText), petId);
    const atlas = manifest.atlases.interaction;
    const atlasPath = resolveInside(platformPath, avatar.directoryPath, atlas.path);
    const atlasBase64 = await fileSystem.readFileBase64(atlasPath, appServerClient);
    const buffer = Buffer.from(typeof atlasBase64 === "string" ? atlasBase64 : atlasBase64.toString("base64"), "base64");
    assert(buffer.length <= MAX_ATLAS_BYTES, "interaction atlas is too large");
    const image = parseImage(buffer);
    assert(image !== null, "interaction atlas must be a PNG or WebP image");
    assert(image.width === atlas.columns * atlas.cellWidth, "interaction atlas width does not match its manifest");
    assert(image.height === atlas.rows * atlas.cellHeight, "interaction atlas height does not match its manifest");
    return {
      ...avatar,
      interactionManifest: manifest,
      interactionSpritesheetUrl: `data:${image.mimeType};base64,${buffer.toString("base64")}`,
    };
  } catch (error) {
    return { ...avatar, interactionError: error instanceof Error ? error.message : String(error) };
  }
}

async function load({ appServerClient, baseLoad, fileSystem, preferWsl }) {
  const baseResult = await baseLoad({ appServerClient, preferWsl });
  const platformPath = await appServerClient.platformPath();
  const avatars = await Promise.all(
    baseResult.avatars.map((avatar) =>
      loadInteractionForAvatar({ appServerClient, avatar, fileSystem, platformPath }),
    ),
  );
  return { ...baseResult, avatars };
}

async function loadAvatar({ appServerClient, avatarId, baseLoadAvatar, fileSystem, preferWsl }) {
  const avatar = await baseLoadAvatar({ appServerClient, avatarId, preferWsl });
  const platformPath = await appServerClient.platformPath();
  return loadInteractionForAvatar({ appServerClient, avatar, fileSystem, platformPath });
}

module.exports = {
  load,
  loadAvatar,
  parseImage,
  validateManifest,
};
