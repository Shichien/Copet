"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");

const LOAD_CHANNEL = "codex_desktop:interactive-pet-state-load";
const SAVE_CHANNEL = "codex_desktop:interactive-pet-state-save";
const MAX_STATE_BYTES = 64 * 1024;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function fileIdForPet(petId) {
  assert(typeof petId === "string", "petId must be a string");
  const fileId = petId.startsWith("custom:") ? petId.slice("custom:".length) : petId;
  assert(/^[a-z0-9][a-z0-9-]{0,79}$/.test(fileId), "petId contains unsupported characters");
  return fileId;
}

function validateState(state, petId) {
  assert(state !== null && typeof state === "object" && !Array.isArray(state), "pet state must be an object");
  assert(state.version === 1, "unsupported pet state version");
  assert(state.petId === petId, "pet state id does not match the requested pet");
  return state;
}

class InteractivePetStore {
  constructor(rootPath) {
    assert(typeof rootPath === "string" && path.isAbsolute(rootPath), "state root must be an absolute path");
    this.rootPath = rootPath;
  }

  statePath(petId) {
    return path.join(this.rootPath, `${fileIdForPet(petId)}.json`);
  }

  async load(petId) {
    const statePath = this.statePath(petId);
    let text;
    try {
      text = await fs.readFile(statePath, "utf8");
    } catch (error) {
      if (error && typeof error === "object" && error.code === "ENOENT") return null;
      throw error;
    }
    assert(Buffer.byteLength(text, "utf8") <= MAX_STATE_BYTES, "pet state file is too large");
    return validateState(JSON.parse(text), petId);
  }

  async save(petId, state) {
    validateState(state, petId);
    const text = JSON.stringify(state);
    assert(Buffer.byteLength(text, "utf8") <= MAX_STATE_BYTES, "pet state is too large");
    await fs.mkdir(this.rootPath, { recursive: true });
    const statePath = this.statePath(petId);
    const temporaryPath = path.join(this.rootPath, `.${fileIdForPet(petId)}.${process.pid}.${crypto.randomUUID()}.tmp`);
    try {
      await fs.writeFile(temporaryPath, text, { encoding: "utf8", flag: "wx", mode: 0o600 });
      await fs.rename(temporaryPath, statePath);
    } catch (error) {
      await fs.rm(temporaryPath, { force: true });
      throw error;
    }
    return { saved: true };
  }
}

function registerIpc({ ipcMain, isTrustedEvent, stateRoot }) {
  assert(ipcMain && typeof ipcMain.handle === "function", "ipcMain.handle is required");
  assert(typeof isTrustedEvent === "function", "isTrustedEvent is required");
  const store = new InteractivePetStore(stateRoot);
  ipcMain.handle(LOAD_CHANNEL, async (event, petId) => {
    assert(isTrustedEvent(event), "untrusted interactive pet state request");
    return store.load(petId);
  });
  ipcMain.handle(SAVE_CHANNEL, async (event, payload) => {
    assert(isTrustedEvent(event), "untrusted interactive pet state request");
    assert(payload !== null && typeof payload === "object" && !Array.isArray(payload), "invalid pet state payload");
    return store.save(payload.petId, payload.state);
  });
  return store;
}

module.exports = {
  InteractivePetStore,
  LOAD_CHANNEL,
  SAVE_CHANNEL,
  fileIdForPet,
  registerIpc,
  validateState,
};
