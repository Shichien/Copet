import { s as interopRequire } from "./rolldown-runtime-BG2f4sTM.js";
import { t as requireReact } from "./react-B7eF_de-.js";

const React = interopRequire(requireReact(), 1);
const NEED_KEYS = ["hunger", "cleanliness", "mood", "energy", "health"];
const STATE_VERSION = 1;
const HOUR_MS = 60 * 60 * 1000;
const CRITICAL_PRIORITY = 50;
const ACTION_PRESENTATION = {
  feed: { symbol: "\u25d2", label: "喂食" },
  pet: { symbol: "\u2661", label: "抚摸" },
  bathe: { symbol: "\u25cc", label: "洗澡" },
  play: { symbol: "\u25b7", label: "玩耍" },
  sleep: { symbol: "\u263e", label: "睡觉" },
  treat: { symbol: "+", label: "治疗" },
};
const NEED_PRESENTATION = {
  hunger: { symbol: "\u25d2", label: "饱食" },
  cleanliness: { symbol: "\u25cc", label: "清洁" },
  mood: { symbol: "\u2661", label: "心情" },
  energy: { symbol: "\u26a1", label: "体力" },
  health: { symbol: "+", label: "健康" },
};

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function integer(value, fallback = 0) {
  return Number.isFinite(value) ? Math.trunc(value) : fallback;
}

function createInitialState(manifest, petId, nowMs) {
  const values = {};
  for (const [key, value] of Object.entries(manifest.initialState)) {
    values[key] = integer(value);
  }
  const inventory = {};
  for (const itemName of Object.keys(manifest.items)) {
    inventory[itemName] = integer(manifest.initialInventory[itemName]);
  }
  return {
    version: STATE_VERSION,
    petId,
    values,
    inventory,
    cooldowns: {},
    decayRemainders: Object.fromEntries(NEED_KEYS.map((key) => [key, 0])),
    lastUpdatedAt: nowMs,
  };
}

function normalizeSavedState(saved, manifest, petId, nowMs) {
  if (!saved || saved.version !== STATE_VERSION || saved.petId !== petId) {
    return createInitialState(manifest, petId, nowMs);
  }
  const initial = createInitialState(manifest, petId, nowMs);
  const values = { ...initial.values };
  for (const key of Object.keys(values)) {
    if (Number.isFinite(saved.values?.[key])) values[key] = integer(saved.values[key]);
  }
  for (const key of NEED_KEYS) values[key] = clamp(values[key], 0, 100);
  values.growth = Math.max(0, values.growth);
  values.coins = Math.max(0, values.coins);
  const inventory = { ...initial.inventory };
  for (const itemName of Object.keys(inventory)) {
    if (Number.isFinite(saved.inventory?.[itemName])) inventory[itemName] = Math.max(0, integer(saved.inventory[itemName]));
  }
  const cooldowns = {};
  for (const actionName of Object.keys(manifest.actions)) {
    if (Number.isFinite(saved.cooldowns?.[actionName])) cooldowns[actionName] = Math.max(0, integer(saved.cooldowns[actionName]));
  }
  const decayRemainders = { ...initial.decayRemainders };
  for (const key of NEED_KEYS) {
    if (Number.isFinite(saved.decayRemainders?.[key])) decayRemainders[key] = integer(saved.decayRemainders[key]);
  }
  return {
    ...initial,
    values,
    inventory,
    cooldowns,
    decayRemainders,
    lastUpdatedAt: Number.isFinite(saved.lastUpdatedAt) ? Math.min(nowMs, Math.max(0, integer(saved.lastUpdatedAt))) : nowMs,
  };
}

function applyDecay(state, manifest, nowMs) {
  const rawElapsedMs = Math.max(0, nowMs - state.lastUpdatedAt);
  const elapsedMs = Math.min(rawElapsedMs, manifest.needs.offlineDecayCapHours * HOUR_MS);
  if (elapsedMs === 0) return state.lastUpdatedAt === nowMs ? state : { ...state, lastUpdatedAt: nowMs };
  const values = { ...state.values };
  const decayRemainders = { ...state.decayRemainders };
  for (const key of NEED_KEYS) {
    let rate = manifest.needs.decayPerHour[key];
    if (
      key === "health" &&
      manifest.needs.criticalHealthDecayPerHour !== undefined &&
      (values.hunger <= 10 || values.cleanliness <= 10)
    ) {
      rate += manifest.needs.criticalHealthDecayPerHour;
    }
    const numerator = rate * elapsedMs + (decayRemainders[key] ?? 0);
    const delta = Math.trunc(numerator / HOUR_MS);
    decayRemainders[key] = numerator - delta * HOUR_MS;
    const floor = key === "health" ? manifest.needs.healthSafeFloor : 0;
    values[key] = clamp(values[key] + delta, floor, 100);
  }
  return { ...state, values, decayRemainders, lastUpdatedAt: nowMs };
}

function stateBridge() {
  const bridge = window.electronBridge;
  if (
    !bridge ||
    typeof bridge.loadInteractivePetState !== "function" ||
    typeof bridge.saveInteractivePetState !== "function"
  ) {
    throw new Error("interactive pet state bridge is unavailable");
  }
  return bridge;
}

async function loadState(manifest, petId, nowMs) {
  const saved = await stateBridge().loadInteractivePetState(petId);
  return applyDecay(normalizeSavedState(saved, manifest, petId, nowMs), manifest, nowMs);
}

function stateRevision(state) {
  return JSON.stringify([state.values, state.inventory, state.cooldowns]);
}

function conditionMatches(condition, values) {
  const [valueName, comparison] = Object.entries(condition)[0];
  const [operator, threshold] = Object.entries(comparison)[0];
  return operator === "lte" ? values[valueName] <= threshold : values[valueName] >= threshold;
}

function automaticAnimation(manifest, values, officialState) {
  if (officialState === "waiting" || officialState === "failed") return null;
  const matched = [...manifest.automaticStates]
    .filter((state) => conditionMatches(state.when, values))
    .sort((left, right) => right.priority - left.priority)[0];
  if (matched && matched.priority >= CRITICAL_PRIORITY) return matched.animation;
  if (officialState !== "idle") return null;
  return matched?.animation ?? null;
}

function prepareTransaction(state, manifest, actionName) {
  const action = manifest.actions[actionName];
  if (!action.item) return { actionName, action, purchaseCost: 0, consumeOwned: false };
  const item = manifest.items[action.item];
  const owned = state.inventory[action.item] ?? 0;
  if (item.consumable === false && owned > 0) {
    return { actionName, action, purchaseCost: 0, consumeOwned: false };
  }
  if (owned > 0) {
    return { actionName, action, purchaseCost: 0, consumeOwned: item.consumable !== false };
  }
  if (state.values.coins < item.cost) return null;
  return { actionName, action, purchaseCost: item.cost, consumeOwned: false };
}

function applyTransaction(state, manifest, transaction, nowMs) {
  const values = { ...state.values };
  const inventory = { ...state.inventory };
  const cooldowns = { ...state.cooldowns };
  const { action, actionName } = transaction;
  if (transaction.purchaseCost > 0) values.coins = Math.max(0, values.coins - transaction.purchaseCost);
  if (action.item) {
    const item = manifest.items[action.item];
    if (transaction.consumeOwned) inventory[action.item] = Math.max(0, (inventory[action.item] ?? 0) - 1);
    if (transaction.purchaseCost > 0 && item.consumable === false) inventory[action.item] = 1;
  }
  for (const [key, amount] of Object.entries(action.effects)) {
    const next = (values[key] ?? 0) + amount;
    values[key] = NEED_KEYS.includes(key) ? clamp(integer(next), 0, 100) : Math.max(0, integer(next));
  }
  cooldowns[actionName] = nowMs + action.cooldownSeconds * 1000;
  return { ...state, values, inventory, cooldowns, lastUpdatedAt: nowMs };
}

function interactionStyle(manifest, animationName, frameIndex) {
  const atlas = manifest.atlases.interaction;
  const animation = manifest.animations[animationName];
  const column = clamp(frameIndex, 0, animation.frames - 1);
  const x = atlas.columns === 1 ? 0 : (column / (atlas.columns - 1)) * 100;
  const y = atlas.rows === 1 ? 0 : (animation.row / (atlas.rows - 1)) * 100;
  return {
    backgroundPosition: `${x}% ${y}%`,
    backgroundSize: `${atlas.columns * 100}% ${atlas.rows * 100}%`,
  };
}

function stopPointer(event) {
  event.stopPropagation();
}

function ActionButton({ actionName, disabled, manifest, nowMs, onAction }) {
  const action = manifest.actions[actionName];
  const presentation = ACTION_PRESENTATION[actionName] ?? { symbol: "\u2022", label: actionName };
  const remainingSeconds = Math.max(0, Math.ceil((disabled.cooldownUntil - nowMs) / 1000));
  const item = action.item ? manifest.items[action.item] : null;
  const priceText = item ? `，无库存时消耗 ${item.cost} 币` : "";
  const title = remainingSeconds > 0 ? `${presentation.label}，还需等待 ${remainingSeconds} 秒` : `${presentation.label}${priceText}`;
  return React.createElement(
    "button",
    {
      type: "button",
      className: "interactive-pet-action",
      "data-action": actionName,
      "aria-label": presentation.label,
      title,
      disabled: disabled.busy || remainingSeconds > 0,
      onPointerDown: stopPointer,
      onPointerUp: stopPointer,
      onClick: (event) => {
        event.stopPropagation();
        onAction(actionName);
      },
    },
    presentation.symbol,
  );
}

function NeedBar({ name, value }) {
  const presentation = NEED_PRESENTATION[name];
  return React.createElement(
    "div",
    { className: "interactive-pet-need", title: `${presentation.label} ${value}` },
    React.createElement("span", { "aria-hidden": "true" }, presentation.symbol),
    React.createElement("span", { className: "interactive-pet-need-track" }, React.createElement("span", { style: { width: `${value}%` } })),
  );
}

export function InteractivePetRuntime(props) {
  const { error, manifest, spritesheetUrl } = props;
  if (!manifest || !spritesheetUrl) {
    return error
      ? React.createElement("button", {
          type: "button",
          className: "interactive-pet-error",
          "aria-label": "互动宠物资源错误",
          title: error,
          onPointerDown: stopPointer,
          onClick: stopPointer,
        }, "!")
      : null;
  }

  return React.createElement(ActiveInteractivePetRuntime, props);
}

function ActiveInteractivePetRuntime({ manifest, officialState, petId, spritesheetUrl }) {
  const [state, setState] = React.useState(null);
  const [stateError, setStateError] = React.useState(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [playback, setPlayback] = React.useState(null);
  const [frameIndex, setFrameIndex] = React.useState(0);
  const [nowMs, setNowMs] = React.useState(() => Date.now());
  const [notice, setNotice] = React.useState(null);
  const saveQueueRef = React.useRef(Promise.resolve());
  const queuedRevisionRef = React.useRef(null);

  React.useEffect(() => {
    let active = true;
    setState(null);
    setStateError(null);
    setPlayback(null);
    queuedRevisionRef.current = null;
    loadState(manifest, petId, Date.now()).then((loaded) => {
      if (active) setState(loaded);
    }, (error) => {
      if (active) setStateError(error instanceof Error ? error.message : String(error));
    });
    return () => {
      active = false;
    };
  }, [manifest, petId]);

  React.useEffect(() => {
    if (!state || stateError) return;
    const revision = stateRevision(state);
    if (revision === queuedRevisionRef.current) return;
    queuedRevisionRef.current = revision;
    const snapshot = state;
    saveQueueRef.current = saveQueueRef.current
      .then(() => stateBridge().saveInteractivePetState(petId, snapshot))
      .catch((error) => {
        setStateError(error instanceof Error ? error.message : String(error));
      });
  }, [petId, state, stateError]);

  React.useEffect(() => {
    const timer = window.setInterval(() => {
      const now = Date.now();
      setNowMs(now);
      setState((current) => current ? applyDecay(current, manifest, now) : current);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [manifest]);

  const effectiveState = state ?? createInitialState(manifest, petId, nowMs);
  const ambientAnimation = automaticAnimation(manifest, effectiveState.values, officialState);
  const animationName = playback?.animationName ?? ambientAnimation;

  React.useEffect(() => {
    setFrameIndex(0);
  }, [animationName]);

  React.useEffect(() => {
    if (!animationName) return undefined;
    const animation = manifest.animations[animationName];
    const safeFrame = clamp(frameIndex, 0, animation.frames - 1);
    const timer = window.setTimeout(() => {
      if (safeFrame + 1 < animation.frames) {
        setFrameIndex(safeFrame + 1);
        return;
      }
      if (playback?.phase === "action") {
        const completedAt = Date.now();
        setState((current) => current
          ? applyTransaction(applyDecay(current, manifest, completedAt), manifest, playback.transaction, completedAt)
          : current);
        setNotice(`${ACTION_PRESENTATION[playback.transaction.actionName]?.label ?? playback.transaction.actionName}完成`);
        if (playback.transaction.action.completionAnimation) {
          setPlayback({ animationName: playback.transaction.action.completionAnimation, phase: "completion" });
        } else {
          setPlayback(null);
        }
        return;
      }
      if (playback?.phase === "completion" || playback?.phase === "refuse") {
        setPlayback(null);
        return;
      }
      if (animation.loop) setFrameIndex(0);
    }, animation.durationsMs[safeFrame]);
    return () => window.clearTimeout(timer);
  }, [animationName, frameIndex, manifest, playback]);

  React.useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 1800);
    return () => window.clearTimeout(timer);
  }, [notice]);

  React.useEffect(() => {
    const parent = document.querySelector("[data-avatar-mascot='true']");
    if (!parent) return undefined;
    parent.dataset.interactivePetActive = animationName ? "true" : "false";
    return () => {
      delete parent.dataset.interactivePetActive;
    };
  }, [animationName]);

  const startAction = React.useCallback((actionName) => {
    if (playback) return;
    const cooldownUntil = effectiveState.cooldowns[actionName] ?? 0;
    if (cooldownUntil > Date.now()) return;
    const transaction = prepareTransaction(effectiveState, manifest, actionName);
    if (!transaction) {
      setNotice("金币不足");
      if (manifest.animations.refuse) setPlayback({ animationName: "refuse", phase: "refuse" });
      return;
    }
    setNotice(null);
    setPlayback({ animationName: transaction.action.animation, phase: "action", transaction });
  }, [effectiveState, manifest, playback]);

  if (stateError) {
    return React.createElement("button", {
      type: "button",
      "aria-label": "互动宠物存档错误",
      title: stateError,
      onPointerDown: stopPointer,
      onClick: stopPointer,
      style: {
        position: "absolute",
        left: "4px",
        top: "4px",
        zIndex: 50,
        width: "20px",
        height: "20px",
        borderRadius: "50%",
        border: "1px solid #c83232",
        color: "#c83232",
        background: "var(--color-token-bg-primary)",
        fontWeight: 700,
      },
    }, "!");
  }
  if (!state) return null;

  const animationLayer = animationName
    ? React.createElement("div", {
        className: "interactive-pet-animation",
        "aria-hidden": "true",
        "data-interaction-animation": animationName,
        style: { backgroundImage: `url(${spritesheetUrl})`, ...interactionStyle(manifest, animationName, frameIndex) },
      })
    : null;

  const controls = React.createElement(
    React.Fragment,
    null,
    React.createElement(
      "button",
      {
        type: "button",
        className: "interactive-pet-menu-toggle",
        "data-testid": "interactive-pet-menu-toggle",
        "aria-label": menuOpen ? "收起宠物互动" : "打开宠物互动",
        title: menuOpen ? "收起" : "互动",
        onPointerDown: stopPointer,
        onPointerUp: stopPointer,
        onClick: (event) => {
          event.stopPropagation();
          setMenuOpen((open) => !open);
        },
      },
      "\u2661",
    ),
    menuOpen
      ? React.createElement(
          "div",
          { className: "interactive-pet-panel", onPointerDown: stopPointer, onPointerUp: stopPointer },
          React.createElement(
            "div",
            { className: "interactive-pet-needs" },
            NEED_KEYS.map((name) => React.createElement(NeedBar, { key: name, name, value: effectiveState.values[name] })),
          ),
          React.createElement(
            "div",
            { className: "interactive-pet-actions" },
            Object.keys(manifest.actions).map((actionName) =>
              React.createElement(ActionButton, {
                key: actionName,
                actionName,
                manifest,
                nowMs,
                onAction: startAction,
                disabled: { busy: Boolean(playback), cooldownUntil: effectiveState.cooldowns[actionName] ?? 0 },
              }),
            ),
          ),
          React.createElement(
            "div",
            { className: "interactive-pet-meta" },
            React.createElement("span", { title: "金币" }, `\u25c7 ${effectiveState.values.coins}`),
            React.createElement("span", { title: "成长" }, `\u2191 ${effectiveState.values.growth}`),
          ),
        )
      : null,
    notice ? React.createElement("div", { className: "interactive-pet-notice", role: "status" }, notice) : null,
  );

  return React.createElement(
    React.Fragment,
    null,
    React.createElement("style", null, `
      [data-avatar-mascot='true'][data-interactive-pet-active='true'] > .codex-avatar-root { visibility: hidden; }
      .interactive-pet-animation { position: absolute; inset: 0; z-index: 20; background-repeat: no-repeat; image-rendering: auto; pointer-events: none; }
      .interactive-pet-menu-toggle, .interactive-pet-action, .interactive-pet-error { border: 1px solid color-mix(in srgb, var(--color-token-border-default) 80%, transparent); background: color-mix(in srgb, var(--color-token-bg-primary) 90%, transparent); color: var(--color-token-text-primary); box-shadow: 0 2px 8px rgb(0 0 0 / 18%); }
      .interactive-pet-menu-toggle { position: absolute; right: calc(100% + 6px); bottom: 4px; z-index: 50; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; font-size: 15px; line-height: 20px; }
      .interactive-pet-panel { position: absolute; right: calc(100% + 6px); bottom: 32px; z-index: 45; width: min(138px, calc(100vw - 8px)); padding: 5px 5px 4px; border: 1px solid color-mix(in srgb, var(--color-token-border-default) 80%, transparent); border-radius: 8px; background: color-mix(in srgb, var(--color-token-bg-primary) 93%, transparent); box-shadow: 0 4px 14px rgb(0 0 0 / 20%); backdrop-filter: blur(10px); cursor: default; }
      .interactive-pet-needs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 3px; margin-bottom: 4px; }
      .interactive-pet-need { display: grid; grid-template-columns: 9px minmax(0, 1fr); align-items: center; gap: 2px; min-width: 0; font-size: 8px; }
      .interactive-pet-need-track { display: block; height: 3px; overflow: hidden; border-radius: 2px; background: color-mix(in srgb, var(--color-token-text-secondary) 22%, transparent); }
      .interactive-pet-need-track > span { display: block; height: 100%; background: var(--color-token-text-primary); }
      .interactive-pet-actions { display: grid; grid-template-columns: repeat(6, 1fr); gap: 3px; }
      .interactive-pet-action { min-width: 0; height: 20px; border-radius: 5px; cursor: pointer; font-size: 12px; line-height: 16px; }
      .interactive-pet-action:disabled { cursor: default; opacity: .38; }
      .interactive-pet-meta { display: flex; justify-content: flex-end; gap: 7px; margin-top: 3px; padding-right: 1px; color: var(--color-token-text-secondary); font-size: 8px; line-height: 10px; }
      .interactive-pet-notice { position: absolute; left: 50%; top: 5px; z-index: 55; max-width: calc(100% - 12px); transform: translateX(-50%); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-radius: 5px; padding: 2px 5px; background: color-mix(in srgb, var(--color-token-bg-primary) 92%, transparent); color: var(--color-token-text-primary); box-shadow: 0 2px 8px rgb(0 0 0 / 18%); font-size: 9px; }
      .interactive-pet-error { position: absolute; left: 4px; top: 4px; z-index: 50; width: 20px; height: 20px; border-radius: 50%; color: #c83232; font-weight: 700; }
    `),
    animationLayer,
    controls,
  );
}
