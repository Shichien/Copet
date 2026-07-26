"use strict";

const fs = require("node:fs");
const path = require("node:path");

function replaceExactlyOnce(source, before, after, label) {
  const first = source.indexOf(before);
  if (first < 0) throw new Error(`${label}: target text was not found`);
  if (source.indexOf(before, first + before.length) >= 0) throw new Error(`${label}: target text is not unique`);
  return source.slice(0, first) + after + source.slice(first + before.length);
}

function copyFile(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function main() {
  const appRoot = path.resolve(process.argv[2] ?? "");
  if (!fs.existsSync(path.join(appRoot, "package.json"))) {
    throw new Error("Pass the unpacked app.asar directory as the first argument");
  }
  const packageJson = JSON.parse(fs.readFileSync(path.join(appRoot, "package.json"), "utf8"));
  if (packageJson.version !== "26.715.72359") {
    throw new Error(`Unsupported Codex app version ${packageJson.version}`);
  }

  const buildDir = path.join(appRoot, ".vite", "build");
  const assetsDir = path.join(appRoot, "webview", "assets");
  const mainPath = path.join(buildDir, "main-BYnIDJ6m.js");
  const preloadPath = path.join(buildDir, "preload.js");
  const overlayPath = path.join(assetsDir, "avatar-overlay-page-BRzy9XUw.js");
  const nativeFramePath = path.join(assetsDir, "avatar-overlay-native-frame-Ds3TsVmU.js");
  const mascotPath = path.join(assetsDir, "avatar-mascot-button-CpKDYwdF.js");
  const selectionPath = path.join(assetsDir, "avatar-selection-CaYsHHf5.js");
  const loaderTarget = path.join(buildDir, "interactive-pet-loader.cjs");
  const storeTarget = path.join(buildDir, "interactive-pet-store.cjs");
  const runtimeTarget = path.join(assetsDir, "interactive-pet-runtime.js");

  copyFile(path.join(__dirname, "interactive-pet-loader.cjs"), loaderTarget);
  copyFile(path.join(__dirname, "interactive-pet-store.cjs"), storeTarget);
  copyFile(path.join(__dirname, "interactive-pet-runtime.js"), runtimeTarget);

  let mainSource = fs.readFileSync(mainPath, "utf8");
  mainSource = replaceExactlyOnce(
    mainSource,
    "load(){return n.qt({appServerClient:this.executionHostRegistry.get(),preferWsl:!!process.env.WSL_DISTRO_NAME})}",
    "load(){let e=this.executionHostRegistry.get();return require(\"./interactive-pet-loader.cjs\").load({appServerClient:e,baseLoad:n.qt,fileSystem:n.fi,preferWsl:!!process.env.WSL_DISTRO_NAME})}",
    "main process custom avatar loader",
  );
  mainSource = replaceExactlyOnce(
    mainSource,
    "exports.runMainAppStartup=kae;\n//# sourceMappingURL=main-BYnIDJ6m.js.map",
    "exports.runMainAppStartup=kae;require(\"./interactive-pet-store.cjs\").registerIpc({ipcMain:require(\"electron\").ipcMain,isTrustedEvent:e=>e.senderFrame?.url?.startsWith(\"app://-/\")===!0,stateRoot:require(\"node:path\").join(process.env.CODEX_HOME??require(\"node:path\").join(require(\"node:os\").homedir(),\".codex\"),\"pet-state\")});\n//# sourceMappingURL=main-BYnIDJ6m.js.map",
    "main process interactive pet state store",
  );
  fs.writeFileSync(mainPath, mainSource);

  let preloadSource = fs.readFileSync(preloadPath, "utf8");
  preloadSource = replaceExactlyOnce(
    preloadSource,
    "getFastModeRolloutMetrics:async t=>e.ipcRenderer.invoke(h,t),getSharedObjectSnapshotValue:e=>k[e]",
    "getFastModeRolloutMetrics:async t=>e.ipcRenderer.invoke(h,t),loadInteractivePetState:async t=>e.ipcRenderer.invoke(\"codex_desktop:interactive-pet-state-load\",t),saveInteractivePetState:async(t,n)=>e.ipcRenderer.invoke(\"codex_desktop:interactive-pet-state-save\",{petId:t,state:n}),getSharedObjectSnapshotValue:e=>k[e]",
    "preload interactive pet state bridge",
  );
  fs.writeFileSync(preloadPath, preloadSource);

  let overlaySource = fs.readFileSync(overlayPath, "utf8");
  overlaySource = replaceExactlyOnce(
    overlaySource,
    "spriteVersionNumber:e.spriteVersionNumber,spritesheetUrl:e.spritesheetUrl,notificationBadge:B",
    "spriteVersionNumber:e.spriteVersionNumber,spritesheetUrl:e.spritesheetUrl,interactionManifest:e.interactionManifest,interactionSpritesheetUrl:e.interactionSpritesheetUrl,interactionError:e.interactionError,petId:e.id,notificationBadge:B",
    "overlay avatar props",
  );
  fs.writeFileSync(overlayPath, overlaySource);

  let nativeFrameSource = fs.readFileSync(nativeFramePath, "utf8");
  nativeFrameSource = replaceExactlyOnce(
    nativeFrameSource,
    "assetRef:r.assetRef,lookFrame:Ce,notificationBadge:Ne,spriteVersionNumber:r.spriteVersionNumber,spritesheetUrl:r.spritesheetUrl,state:_e.mascotState",
    "assetRef:r.assetRef,lookFrame:Ce,notificationBadge:Ne,spriteVersionNumber:r.spriteVersionNumber,spritesheetUrl:r.spritesheetUrl,interactionManifest:r.interactionManifest,interactionSpritesheetUrl:r.interactionSpritesheetUrl,interactionError:r.interactionError,petId:r.id,state:_e.mascotState",
    "native overlay avatar props",
  );
  fs.writeFileSync(nativeFramePath, nativeFrameSource);

  let selectionSource = fs.readFileSync(selectionPath, "utf8");
  selectionSource = replaceExactlyOnce(
    selectionSource,
    "description:e.description,displayName:e.displayName,id:e.id,spriteVersionNumber:t,spritesheetUrl:e.spritesheetDataUrl,upgradeDirectoryPath",
    "description:e.description,displayName:e.displayName,id:e.id,interactionManifest:e.interactionManifest,interactionSpritesheetUrl:e.interactionSpritesheetUrl,interactionError:e.interactionError,spriteVersionNumber:t,spritesheetUrl:e.spritesheetDataUrl,upgradeDirectoryPath",
    "custom avatar interaction fields",
  );
  fs.writeFileSync(selectionPath, selectionSource);

  let mascotSource = fs.readFileSync(mascotPath, "utf8");
  mascotSource = replaceExactlyOnce(
    mascotSource,
    'import{n as m,t as h}from"./codex-avatar-DeZCV8Lz.js";',
    'import{n as m,t as h}from"./codex-avatar-DeZCV8Lz.js";import{InteractivePetRuntime as R}from"./interactive-pet-runtime.js";',
    "mascot runtime import",
  );
  mascotSource = replaceExactlyOnce(
    mascotSource,
    "{ariaLabel:n,assetRef:r,className:i,lookFrame:ee,notificationBadge:a,onContextMenu:o,resizeHandle:c,spriteVersionNumber:l,spritesheetUrl:u,state:d,style:f,transientState:p}=e",
    "{ariaLabel:n,assetRef:r,className:i,lookFrame:ee,notificationBadge:a,onContextMenu:o,resizeHandle:c,spriteVersionNumber:l,spritesheetUrl:u,state:d,style:f,transientState:p,interactionManifest:im,interactionSpritesheetUrl:iu,interactionError:ir,petId:ip}=e",
    "mascot runtime props",
  );
  mascotSource = replaceExactlyOnce(
    mascotSource,
    "children:[N,P,F]",
    "children:[N,(0,x.jsx)(R,{manifest:im,spritesheetUrl:iu,error:ir,petId:ip,officialState:C}),P,F]",
    "mascot runtime render",
  );
  fs.writeFileSync(mascotPath, mascotSource);

  console.log(JSON.stringify({ appRoot, version: packageJson.version, patched: true }, null, 2));
}

main();
