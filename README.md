# Copet

Copet 为 Codex 桌面宠物加入可交互的养成玩法，同时保留原生 `/pet` 唤醒和收起方式。

当前运行时包含喂食、抚摸、洗澡、玩耍、睡觉和治疗，以及饱食、清洁、心情、体力、健康、成长、金币、库存、冷却、离线衰减和磁盘存档。所有结算均由数据清单确定，不使用隐藏随机数。

![Copet 互动面板](docs/copet-overlay.png)

## 当前支持范围

- Windows 11
- Microsoft Store Codex `26.715.10079.0`
- Codex 应用版本 `26.715.72359`
- PowerShell 7、Node.js、npm
- Python 3 与 Pillow，用于素材流水线和校验

客户端补丁采用严格版本和哈希检查。版本不匹配时会直接停止，不会尝试套用不确定的修改。商店安装目录不会被修改，安装器只创建独立本地副本。

## 构建与安装

在仓库根目录打开 PowerShell 7：

```powershell
& '.\runtime\build-interactive-codex.ps1'
& '.\runtime\install-interactive-codex.ps1'
& '.\runtime\launch-interactive-codex.ps1' -IsolatedProfile
```

启动独立副本后，在 Codex 输入 `/pet`，选择宠物命令即可唤醒 Daisy。互动状态默认保存在 `%USERPROFILE%\.codex\pet-state\daisy.json`。

已有不同的互动素材时，普通安装会拒绝覆盖。明确升级整个互动包时使用：

```powershell
& '.\runtime\install-interactive-codex.ps1' -PetPackageOnly -UpgradePetPackage
```

`-PetPackageOnly` 会验证现有独立副本的安装标记和 `app.asar` 哈希，只更新宠物素材。即使 Microsoft Store Codex 后续自动升级，也不会把旧客户端补丁套到新版本。

`runtime/app.asar` 由构建脚本从本机 Codex 生成，并被 `.gitignore` 排除，不属于仓库内容。

## 测试

```powershell
& '.\test.ps1'
```

该命令运行运行时单元测试、互动素材流水线测试和完整宠物包校验。

## 目录

- `runtime`：客户端加载、互动界面、磁盘存档、补丁、构建、安装和启动脚本
- `pet`：Daisy 官方宠物包、互动行为清单、十二组动画任务和参考素材
- `skill`：可复用的互动宠物素材准备、合图和校验流程
- `docs`：真实 Codex 独立副本的界面截图

## 素材状态

仓库当前的 `pet/package/interaction-spritesheet.webp` 是明确标记的运行时测试图集，只用于验证功能链路，不是十二组正式互动动画。`pet/qa/test-atlas.json` 记录了它的来源和用途。

正式素材流程已经准备完成：十二组任务必须使用同一角色参考图生成，清除色键后合成 `1536×2496` 图集，并通过 `skill/scripts/validate_interaction_pack.py` 校验。正式图集生成后应替换测试图集并使用 `-UpgradePetPackage` 安装。
