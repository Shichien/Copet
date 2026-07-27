"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const nodePath = require("node:path");
const { load, loadAvatar, parseImage, validateManifest } = require("./interactive-pet-loader.cjs");
const { InteractivePetStore, fileIdForPet } = require("./interactive-pet-store.cjs");

const daisyManifestPath = path.resolve(__dirname, "..", "pet", "package", "interaction.json");

test("Daisy interaction manifest passes strict runtime validation", () => {
  const manifest = JSON.parse(fs.readFileSync(daisyManifestPath, "utf8"));
  assert.equal(validateManifest(manifest, "daisy"), manifest);
});

test("manifest validation rejects executable or unknown fields", () => {
  const manifest = JSON.parse(fs.readFileSync(daisyManifestPath, "utf8"));
  manifest.script = "https://example.invalid/pet.js";
  assert.throws(() => validateManifest(manifest, "daisy"), /unsupported field script/);
});

test("manifest validation rejects traversal atlas paths through dimensions check phase", () => {
  const manifest = JSON.parse(fs.readFileSync(daisyManifestPath, "utf8"));
  manifest.animations.feeding.row = manifest.atlases.interaction.rows;
  assert.throws(() => validateManifest(manifest, "daisy"), /feeding row/);
});

test("PNG dimensions are parsed without decoding pixels", () => {
  const buffer = Buffer.alloc(24);
  buffer[0] = 137;
  buffer.write("PNG", 1, "ascii");
  buffer.write("IHDR", 12, "ascii");
  buffer.writeUInt32BE(1536, 16);
  buffer.writeUInt32BE(2496, 20);
  assert.deepEqual(parseImage(buffer), { mimeType: "image/png", width: 1536, height: 2496 });
});

test("loader enriches only pets with a valid interaction package", async () => {
  const manifestText = fs.readFileSync(daisyManifestPath, "utf8");
  const atlas = fs.readFileSync(path.resolve(__dirname, "..", "pet", "package", "interaction-spritesheet.webp"));
  const directoryPath = "C:\\codex\\pets\\daisy";
  const files = new Map([
    [nodePath.win32.join(directoryPath, "interaction.json"), manifestText],
    [nodePath.win32.join(directoryPath, "interaction-spritesheet.webp"), atlas.toString("base64")],
  ]);
  const appServerClient = { platformPath: async () => nodePath.win32 };
  const fileSystem = {
    readFile: async (filePath) => {
      if (!files.has(filePath)) throw Object.assign(new Error("missing"), { code: "ENOENT" });
      return files.get(filePath);
    },
    readFileBase64: async (filePath) => {
      if (!files.has(filePath)) throw Object.assign(new Error("missing"), { code: "ENOENT" });
      return files.get(filePath);
    },
  };
  const baseLoad = async () => ({
    avatarDirectory: "C:\\codex\\pets",
    avatars: [
      { id: "custom:daisy", displayName: "Daisy", directoryPath },
      { id: "codex", displayName: "Codex" },
    ],
  });
  const result = await load({ appServerClient, baseLoad, fileSystem, preferWsl: false });
  assert.equal(result.avatars[0].interactionManifest.petId, "daisy");
  assert.match(result.avatars[0].interactionSpritesheetUrl, /^data:image\/webp;base64,/);
  assert.equal(result.avatars[1].interactionManifest, undefined);
});

test("single avatar loader applies the same interaction validation", async () => {
  const manifestText = fs.readFileSync(daisyManifestPath, "utf8");
  const atlas = fs.readFileSync(path.resolve(__dirname, "..", "pet", "package", "interaction-spritesheet.webp"));
  const directoryPath = "C:\\codex\\pets\\daisy";
  const files = new Map([
    [nodePath.win32.join(directoryPath, "interaction.json"), manifestText],
    [nodePath.win32.join(directoryPath, "interaction-spritesheet.webp"), atlas.toString("base64")],
  ]);
  const appServerClient = { platformPath: async () => nodePath.win32 };
  const fileSystem = {
    readFile: async (filePath) => {
      if (!files.has(filePath)) throw Object.assign(new Error("missing"), { code: "ENOENT" });
      return files.get(filePath);
    },
    readFileBase64: async (filePath) => {
      if (!files.has(filePath)) throw Object.assign(new Error("missing"), { code: "ENOENT" });
      return files.get(filePath);
    },
  };
  const avatar = await loadAvatar({
    appServerClient,
    avatarId: "custom:daisy",
    baseLoadAvatar: async () => ({ id: "custom:daisy", displayName: "Daisy", directoryPath }),
    fileSystem,
    preferWsl: false,
  });
  assert.equal(avatar.interactionManifest.petId, "daisy");
  assert.match(avatar.interactionSpritesheetUrl, /^data:image\/webp;base64,/);
});

test("main-process store survives a new store instance", async () => {
  const stateRoot = fs.mkdtempSync(path.join(os.tmpdir(), "codex-interactive-pet-"));
  try {
    const state = {
      version: 1,
      petId: "custom:daisy",
      values: { hunger: 72, cleanliness: 61, mood: 83, energy: 44, health: 95, growth: 9, coins: 27 },
      inventory: { meal: 1, soap: 0, toy: 1, medicine: 2 },
      cooldowns: { feed: 12345 },
      decayRemainders: { hunger: -1, cleanliness: -2, mood: -3, energy: -4, health: 0 },
      lastUpdatedAt: 1000,
    };
    await new InteractivePetStore(stateRoot).save(state.petId, state);
    assert.deepEqual(await new InteractivePetStore(stateRoot).load(state.petId), state);
    assert.equal(fs.existsSync(path.join(stateRoot, "daisy.json")), true);
  } finally {
    fs.rmSync(stateRoot, { recursive: true, force: true });
  }
});

test("main-process store rejects traversal and mismatched state ids", async () => {
  assert.throws(() => fileIdForPet("custom:../daisy"), /unsupported characters/);
  const stateRoot = fs.mkdtempSync(path.join(os.tmpdir(), "codex-interactive-pet-"));
  try {
    await assert.rejects(
      new InteractivePetStore(stateRoot).save("custom:daisy", { version: 1, petId: "custom:other" }),
      /does not match/,
    );
  } finally {
    fs.rmSync(stateRoot, { recursive: true, force: true });
  }
});
