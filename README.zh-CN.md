# Tales of Maj’Eyal — Apple Silicon 原生构建

[English](README.md) | 简体中文

ToME **1.7.6** 的社区 ARM64 macOS 构建。使用官方完整源码和资源，运行时采用 LuaJIT 2.1、SDL2/SDL3 兼容层和 OpenAL Soft。
游戏及捆绑的动态库均为 ARM64，运行无需 Homebrew 或 Rosetta。

## 下载与安装

每个 [Release](https://github.com/Jadeiin/tome4-macos-arm64/releases) 提供两种 DMG：

| 下载文件 | 布局 | 安装方法 |
| --- | --- | --- |
| `Tales-of-MajEyal-…-arm64.N.dmg` | 游戏资产位于 `.app` 内 | 将 `Tales of Maj'Eyal.app` 拖到 Applications。 |
| `Tales-of-MajEyal-…-arm64.N-split.dmg` | `T-Engine.app` 与 `game/`、`bootstrap/` 并列 | 将整个 `Tales of Maj'Eyal` 文件夹拖到 Applications 或其他位置，保持目录内容在一起。 |

两种布局使用同一引擎，运行库均捆绑在 `.app` 内。分离布局可直接管理 DLC 和 addon 文件，无需打开应用包。
最低 macOS 版本见对应 Release 和 `build-info.json`；CI 使用 `macos-15` 的 ARM64 runner，打包时也会检查动态库要求的系统版本。

应用使用 ad hoc 签名，未进行 Apple 公证。若 macOS 拦截，确认下载来源后在系统设置的“隐私与安全性”中允许打开。
公开构建包含游戏本体；购买的 DLC 可在本机导入。

全屏进入独立的 macOS Space，切换应用时保持显示器分辨率和游戏窗口状态。支持的 macOS 版本可启用游戏模式。2× Retina 显示器建议将 Screen Zoom 设为 200%，以保持通常的界面大小。

## 从源码构建

需要 Apple Silicon Mac、Apple Command Line Tools 和原生 Homebrew。
在仓库目录执行：

```sh
/opt/homebrew/bin/brew bundle install --file=Brewfile --no-upgrade
/usr/bin/python3 scripts/fetch-source.py
/usr/bin/python3 scripts/build-native.py
/usr/bin/python3 scripts/package-native.py
/usr/bin/python3 scripts/verify-native.py
/usr/bin/python3 scripts/check-bundled-runtime.py
open "dist/Tales of Maj'Eyal.app"
```

`project.json` 固定官方源码版本、下载地址和 SHA-256。下载器校验完整归档后再提取；若源码目录已存在，会保留它并退出。
已有源码时，重新构建可直接从 `build-native.py` 开始。
`package-native.py` 同时生成 `dist/Tales of Maj'Eyal.app` 和 `dist/Tales of Maj'Eyal/`；打开 `dist/Tales of Maj'Eyal/T-Engine.app` 即可使用分离布局。

Brewfile 声明 9 个直接依赖：`pkgconf`、`sdl2-compat`、`sdl2_image`、`sdl2_ttf`、`libpng`、`libogg`、`libvorbis`、`openal-soft`、`luajit`。间接依赖由 Homebrew 安装。
OpenAL Soft 为 keg-only，构建脚本已设置 pkg-config 路径。
默认部署目标匹配构建机；可用 `TOME_MACOS_MIN` 指定引擎目标，但应用最终最低版本不会低于捆绑动态库的要求。

打包脚本将非系统运行库复制到 `Contents/Frameworks`，改为相对路径，并重新签名。SDL2 动态加载的 SDL3 也包含在包内。
清单与来源记录位于 `Contents/Resources/runtime-libraries.json`，许可证文件与 Homebrew formula 位于 `ThirdPartyLicenses`。
`Info.plist` 声明角色扮演游戏类别与游戏模式支持。`--build-version` 设置独立于游戏版本的数字构建号；CI 使用运行序号。
macOS 系统库和框架由系统提供。Homebrew 更新后重新打包会使用当时安装的版本，Brewfile 不锁定版本。

## 原生兼容代码

版本控制维护以下内容：

- `scripts/build-native.py`：Apple Clang 原生构建，排除旧 Lua、Steam 和旧内嵌浏览器。
- `scripts/NativeMain.m`：Cocoa 启动、应用资源目录，以及 macOS 原生全屏 Space。详见[全屏和游戏模式说明](docs/macos-native-fullscreen.md)。
- `scripts/native-display.lua`：保留原版全屏／无边框／窗口选项；窗口与无边框复用完整原版分辨率列表及重启流程，原生全屏显示桌面渲染尺寸。Retina 渲染保持窗口和鼠标坐标一致。
- `scripts/NativeLua.c`：PhysFS 虚拟文件加载、原版 `table.sort(list, "字段名")` 扩展，以及原版 `math.mod`／`string.gfind` 别名；详见[运行时兼容性排查](docs/luajit-runtime.md)。
- `scripts/lua51-resolvers.lua`：优先执行可在当前阶段处理的 instant resolver，避免铭文依赖未解析。文件名沿用最初的诊断版本，当前运行时为 LuaJIT。
- `scripts/patch-native.py`、`patches/native-arm64.patch`：统一的上游补丁与可重复执行的安装脚本；脚本从缓存的官方原始文件恢复后应用补丁，并复制 Lua 辅助代码。
- 打包、校验、发布脚本、Brewfile、源码元数据和 GitHub Actions。

官方下载包、解压后的源码、编译缓存、应用、日志、DLC、设置与存档均不进入 Git。
源码提取后由构建脚本应用补丁；官方游戏与 DLC 压缩档案保持原样。
当前构建使用 ARM64 LuaJIT 2.1，不提供旧 Lua 5.1 字节码存档转换。

## 检查

无需启动游戏窗口的检查：

```sh
/usr/bin/python3 scripts/check-release-tools.py
/usr/bin/python3 scripts/check-luajit-vfs.py
/usr/bin/python3 scripts/check-lua51-resolvers.py
/usr/bin/python3 scripts/check-talent-coroutines.py
/usr/bin/python3 scripts/verify-native.py
/usr/bin/python3 scripts/check-bundled-runtime.py
/usr/bin/python3 scripts/verify-native.py --layout split
/usr/bin/python3 scripts/check-bundled-runtime.py --layout split
```

覆盖源码归档与发布文件校验、虚拟文件加载、铭文解析、真实技能代码的协程暂停与收尾，以及应用架构、动态链接、签名和迁移目录后的库加载。
完整游戏检查在有图形会话的本机终端或 macOS runner 中运行：

```sh
/usr/bin/python3 scripts/check-first-floor.py --talents
/usr/bin/python3 scripts/check-first-floor.py --layout split --talents
```

它使用独立配置创建矮人 Bulwark，进入首层，生成 100 枚铭文，再取消并完成盾牌连击目标选择，随后关闭测试游戏。
如果应用包含 DLC，会同时检查对应模块加载；可加 `--require-dlcs` 强制要求三套购买的 DLC：Ashes of Urh’Rok、Embers of Rage 和 Forbidden Cults。
检查记录保存在 `logs/`。默认设置和存档位于 `~/Library/Application Support/T-Engine/4.0/`，独立测试配置位于 `build/`。
这些检查不覆盖完整战役或长时间稳定性。

## GitHub Actions 与 Release

[workflow](.github/workflows/build.yml) 在 `main` 更新、Pull Request、手动触发及 `v*` tag 推送时执行：

1. 在 `macos-15` 原生 ARM64 runner 上安装 Homebrew 依赖。
2. 下载并校验官方完整源码，应用补丁并编译。
3. 执行 LuaJIT 回归、架构和签名检查、迁移后的运行库检查，以及真实首层与技能目标选择检查。
4. 用 `hdiutil` 创建并校验两种布局的 DMG，附带共用的源码包、构建信息和 SHA-256 校验值。
5. 对 `v1.7.6-arm64.N` tag，在独立发布 job 中校验文件 SHA-256，再由一个 `run` step 调用 runner 自带的 **GitHub CLI** 发布 Release。

普通分支与 PR 构建提供 Actions artifacts；只有成功的 tag 构建发布 Release。
公开打包显式排除本机购买的 DLC。CI 游戏检查使用 OpenAL Soft 的 null 音频后端，验证不依赖 runner 的音频设备。
Release 源码包包含对应提交的构建代码，以及经过 SHA-256 校验的官方完整源码归档。
构建和测试日志在失败时也会上传。构建 job 仅有 `contents: read`，发布 job 才获得 `contents: write`。

### 发布新版本

推送新的版本 tag 后，GitHub Actions 会自动构建并发布：

```sh
git tag v1.7.6-arm64.4
git push origin v1.7.6-arm64.4
```

构建进度和日志见仓库的 Actions 页面，发布文件见 Releases 页面。

### 本机生成发布文件

先完成编译及上述检查，再执行：

```sh
/usr/bin/python3 scripts/package-native.py --without-dlcs
/usr/bin/python3 scripts/make-release.py --tag v1.7.6-arm64.4
```

输出位于 `dist/release/`。重新构建同一版本时会覆盖该版本的生成文件。
普通本机构建会在两种布局中包含导入的 DLC；公开 DMG 打包会拒绝包含 DLC 文件的布局。

## 导入已购买的 DLC

```sh
/usr/bin/python3 scripts/import-dlcs.py "/path/to/SteamLibrary/steamapps/common/TalesMajEyal/game/dlcs"
/usr/bin/python3 scripts/package-native.py
```

DLC 压缩档案来自用户自己的 Steam 安装，检查完整性后在本机复制。职业和种族解锁仍遵循游戏规则。
已安装分离版时，也可直接将购买的 `.teaac` 压缩档案复制到应用旁的 `game/dlcs/`；addon 放在 `game/addons/` 或游戏原有的用户 addon 目录中。

## 来源与许可

官方游戏与源码：<https://te4.org/>；官方下载地址和哈希见 `project.json`。
引擎及本仓库的原生兼容代码使用 GPL-3.0，见 [LICENSE](LICENSE)。媒体适用官方 `COPYING-MEDIA`，仅用于 Tales of Maj’Eyal 游戏。
应用中保留官方许可和致谢，以及第三方运行库的许可与来源信息。这是社区构建，与官方发行版独立。
