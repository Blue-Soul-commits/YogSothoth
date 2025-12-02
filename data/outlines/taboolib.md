# taboolib

## 项目简介
TabooLib 是一个面向 Minecraft 插件开发的多平台通用框架，支持 Bukkit、BungeeCord、Velocity 等多种平台，提供丰富的模块和工具库，涵盖 NMS 操作、配置管理、效果渲染、脚本执行、指标统计等功能，旨在简化插件开发流程并提升开发效率。

---

## 目录结构

- `LICENSE`  
  MIT 许可证信息

- `README.md`  
  项目总体介绍与徽章

- `UPDATE-MANUAL-FOR-BUKKIT.md`  
  Bukkit 平台更新手册

- `common/`  
  - 启动逻辑及核心类  
  - `README.md`：启动流程说明  
  - `classloader/`：隔离类加载器相关  
  - `platform/`：平台抽象与基础支持  
  - `common-util/`：通用工具类与注解支持  
  - `common-env/`：运行时环境与依赖管理

- `platform/`  
  - `platform-bukkit/`：Bukkit 平台实现  
  - `platform-bungee/`：BungeeCord 平台实现  
  - `platform-velocity/`：Velocity 平台实现  
  - `platform-application/`：应用平台支持  
  - `platform-afybroker/`：AfyBroker 平台支持

- `module/`  
  - `module-nms-util-legacy/`：旧版 NMS 工具  
  - `module-nms-util-stable/`：稳定版 NMS 工具  
  - `module-nms-util-tag/`：物品 Tag 工具（含版本区分）  
  - `module-nms-util-unstable/`：不稳定 NMS 工具  
  - `module-porticus/`：跨平台任务与消息模块  
  - `module-kether/`：脚本引擎核心模块  
  - `module-metrics/`：指标统计与图表模块  
  - `module-effect/`：特效渲染与数学计算  
  - `module-configuration/`：配置文件解析与管理  
  - `module-chat/`：聊天颜色与格式支持  
  - `module-bukkit-xseries/`：Bukkit 版本兼容工具集  
  - `module-bukkit-util/`：Bukkit 相关工具与 UI 支持  
  - `module-ai/`：AI 路径规划相关

- `expansion/`  
  - `expansion-ioc/`：依赖注入容器  
  - `expansion-submit-chain/`：Kotlin 协程封装

---

## 关键类 / 接口 / 组件列表

### 核心启动与平台支持
- `taboolib.common.LifeCycle`  
- `taboolib.common.classloader.IsolatedClassLoader`  
- `taboolib.common.platform.Platform`  
- `taboolib.common.platform.Plugin`  
- `taboolib.platform.bukkit.BukkitPlugin`  
- `taboolib.platform.bungee.BungeePlugin`  
- `taboolib.platform.VelocityPlugin`  

### 脚本引擎（Kether）
- `taboolib.library.kether.Quest`  
- `taboolib.library.kether.QuestAction`  
- `taboolib.library.kether.QuestContext`  
- `taboolib.library.kether.QuestLoader`  
- `taboolib.library.kether.QuestRegistry`  
- `taboolib.library.kether.QuestService`  
- `taboolib.library.kether.QuestReader`  
- `taboolib.library.kether.ParsedAction`  
- `taboolib.library.kether.Parser`  

### NMS 工具
- `taboolib.module.nms.TinyProtocol`  
- `taboolib.module.nms.TinyReflection`  
- `taboolib.module.nms.NMSLightImpl`  

### 配置管理
- `taboolib.module.configuration.YamlCommentLoader`  
- `taboolib.module.configuration.YamlFormat`  
- `taboolib.library.configuration.BukkitYaml`  
- `taboolib.library.configuration.YamlConstructor`  
- `taboolib.library.configuration.YamlRepresenter`  

### 特效模块
- `taboolib.module.effect.EffectGroup`  
- `taboolib.module.effect.Playable`  
- `taboolib.module.effect.ShowType`  
- `taboolib.module.effect.math.Matrix`  
- `taboolib.module.effect.math.Equations`  
- `taboolib.module.effect.renderer.GeneralEquationRenderer`  
- `taboolib.module.effect.shape.*`（如 Arc、Circle、Cube、Star 等）  
- `taboolib.module.effect.utils.LocationUtils`  

### 指标统计
- `taboolib.module.metrics.Metrics`  
- `taboolib.module.metrics.CustomChart`  
- `taboolib.module.metrics.charts.*`（多种图表类型）  

### 跨平台任务与消息（Porticus）
- `taboolib.module.porticus.PorticusMission`  
- `taboolib.module.porticus.bukkitside.*`  
- `taboolib.module.porticus.bungeeside.*`  
- `taboolib.module.porticus.common.*`  

### 工具类
- `taboolib.common.util.Strings`  
- `taboolib.common.util.Location`  
- `taboolib.common.util.Vector`  
- `taboolib.common.util.Version`  
- `taboolib.module.chat.HexColor`  
- `taboolib.module.chat.StandardColors`  
- `taboolib.library.xseries.*`（版本兼容工具）  

### 依赖注入与环境管理
- `taboolib.common.inject.ClassVisitor`  
- `taboolib.common.env.Dependency`  
- `taboolib.common.env.DependencyDownloader`  
- `taboolib.common.env.RuntimeEnv`  

---

## 典型使用流程 / 调用链

1. **启动阶段**  
   - 插件主类继承 `JavaPlugin`，在静态代码块中启动 `IsolatedClassLoader`，实现类加载隔离。  
   - 通过 `taboolib.common.LifeCycle` 管理插件生命周期。

2. **平台适配**  
   - 根据运行环境加载对应平台实现，如 `BukkitPlugin`、`BungeePlugin`、`VelocityPlugin`。  
   - 平台插件通过 `taboolib.common.platform.Platform` 抽象层调用统一接口。

3. **脚本执行**  
   - 使用 `module-kether` 提供的脚本引擎加载和执行脚本任务。  
   - 通过 `QuestLoader` 加载脚本，`QuestService` 管理执行，`QuestContext` 维护上下文。

4. **NMS 操作**  
   - 利用 `module-nms-util-stable` 等工具类进行 Minecraft 服务器底层操作，兼容多版本。  
   - 通过 `TinyProtocol` 和反射工具实现数据包和内部类操作。

5. **配置管理**  
   - 使用 `module-configuration` 解析 YAML 配置，支持注释和自定义格式。  
   - 结合 `BukkitYaml` 等实现 Bukkit 兼容的配置加载。

6. **特效渲染**  
   - 通过 `module-effect` 提供的数学模型和渲染器绘制各种粒子特效。  
   - 支持多种形状和坐标系，方便开发者调用。

7. **指标统计**  
   - 利用 `module-metrics` 统计插件使用数据，生成多种图表上传。

8. **跨平台消息与任务**  
   - 使用 `module-porticus` 实现跨平台任务调度和消息传递，支持 Bukkit 和 Bungee。

9. **扩展与依赖管理**  
   - 通过 `common-env` 管理运行时依赖，自动下载和重定位。  
   - 使用 `expansion-ioc` 实现依赖注入，简化组件管理。

---

# 结束