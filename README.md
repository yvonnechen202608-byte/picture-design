# Airy Photo Doodle Poster

> 将任意主题、概念或产品，转译成“实物摄影 × 手绘涂鸦”的高留白主题海报。

![Airy Photo Doodle Poster 封面](assets/cover.png)

`airy-photo-doodle-poster` 是一个面向 Codex 的 AI 绘图 Skill。

它会在更换主题和产品的同时，持续保留统一的视觉气质：

- 暖白纸面与大面积留白
- 真实产品或物件作为视觉主角
- 单一自然强调色
- 黑色单线涂鸦小人
- 松弛、自然的中文手写标题
- 轻盈、有趣、带一点编辑感的版式

它学习的是一套抽象视觉规律，不会直接复制参考图片中的构图、文字、人物动作或品牌标识。

## 效果预览

<!-- 建议把生成案例放进 assets/examples/ -->

| 产品海报 | 主题海报 | 横版封面 |
| --- | --- | --- |
| ![](assets/examples/product-poster.png) | ![](assets/examples/theme-poster.png) | ![](assets/examples/cover-example.png) |

## 视觉 DNA

这套 Skill 会尽量维持以下规则：

- **留白比例：** 约占画面的 45%–75%
- **主体数量：** 一个清晰的实物或产品主角
- **色彩结构：** 暖白底色 + 黑色线条 + 一个自然强调色
- **插画语言：** 1–3 个简洁、无具体身份的单线小人
- **互动方式：** 小人攀爬、搬运、测量、擦拭、采集或观察主体
- **字体气质：** 松弛、不规则、有呼吸感的中文手写字
- **整体质感：** 高调实物摄影、轻柔阴影、纸面感和编辑式排版

## 安装

### 方法一：使用 Skill Installer

在 Codex 中输入：

```text
使用 $skill-installer 安装：
https://github.com/<你的GitHub用户名>/airy-photo-doodle-poster
```

安装完成后，如果没有立即显示，可以重新启动 Codex。

### 方法二：手动安装到个人目录

```bash
git clone https://github.com/<你的GitHub用户名>/airy-photo-doodle-poster.git \
  ~/.agents/skills/airy-photo-doodle-poster
```

### 方法三：安装到当前项目

在项目根目录执行：

```bash
mkdir -p .agents/skills

git clone https://github.com/<你的GitHub用户名>/airy-photo-doodle-poster.git \
  .agents/skills/airy-photo-doodle-poster
```

## 使用方法

在 Codex 对话中明确调用：

```text
使用 $airy-photo-doodle-poster

主题：灵感发芽
画面比例：3:4
标题由你拟定
直接生成最终图片
```

### 产品海报

上传产品照片后输入：

```text
使用 $airy-photo-doodle-poster，把我上传的产品作为主物。

保留产品的外形、结构、材质和颜色，
重新设计构图、小人动作与中文手写标题。
画面比例为 3:4。
```

### 公众号封面

```text
使用 $airy-photo-doodle-poster

为“5分钟定制你的专属画风”制作一张微信公众号封面。
比例为 2.35:1。
标题：5分钟，定制你的专属画风
副标题：AI 绘图 Skill · GitHub 开源
```

### 抽象主题

```text
使用 $airy-photo-doodle-poster

主题：正在生长的好奇心
请把抽象概念转译成一个真实物件，
搭配具有叙事感的涂鸦小人和中文手写标题。
不要出现品牌、Logo 或水印。
```

## 项目结构

```text
airy-photo-doodle-poster/
├── README.md
├── LICENSE
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── visual-system.md
└── assets/
    ├── cover.png
    └── examples/
```

- `SKILL.md`：Skill 的核心工作流程和执行规则
- `references/visual-system.md`：配色、留白、构图、字体和插画规范
- `agents/openai.yaml`：Skill 的展示名称和界面配置
- `assets/`：README 封面和效果案例

## 如何定制成自己的画风

你可以修改 `references/visual-system.md` 中的视觉变量：

### 改配色

```text
背景：暖白色
强调色：鼠尾草绿
线条：近黑色
辅助色：浅灰绿色
```

### 改小人风格

```text
把圆润小人改成细长、笨拙、略带停顿感的单线人物。
不画五官细节，只保留姿态和动作。
```

### 改字体气质

```text
标题使用纤细、松弛、字距不规则的中文手写字。
避免粗黑综艺字体、商业促销字体和标准印刷体。
```

### 改构图

```text
主体缩小到画面的 30%–40%，
放在右下方或视觉中心偏下的位置，
保留大面积可呼吸的空白区域。
```

如果 Skill 的适用范围发生变化，也应同步修改 `SKILL.md` 顶部的 `description`，让 Codex 能更准确地判断什么时候调用它。

## 工作方式

Skill 会依次完成：

1. 提取主题中最重要的视觉概念
2. 选择适合摄影呈现的真实主体
3. 建立高留白的版式骨架
4. 从主体颜色中确定一个强调色
5. 设计涂鸦小人与主体的互动动作
6. 拟定简短的中文手写标题
7. 检查产品外观、文字、Logo 和原创性
8. 生成最终海报

## 适合的场景

- 产品展示海报
- 食品与饮品视觉
- 微信公众号封面
- 小红书配图
- 品牌内容插画
- 概念海报
- 课程与文章头图
- 创意提案和灵感草图

## 不适合的场景

- 满版复杂场景
- 密集型商业促销 KV
- 大量正文排版
- 精确复刻某张现有作品
- 模仿特定在世艺术家的个人画风
- 对产品结构要求达到工业制图级精度的任务

## 原创性说明

本项目提取和使用的是高层视觉规律，例如留白比例、摄影与线稿的组合方式、色彩数量和版式节奏。

使用时请避免：

- 复刻参考作品的具体构图
- 沿用原作品中的标题或文案
- 复制具有识别度的小人动作组合
- 保留第三方 Logo、签名或水印
- 将生成结果描述成原作者的作品

参考图片只用于帮助理解视觉语言，不应直接收录到开源仓库中，除非你确认拥有相应授权。

## 已知限制

- 图片模型生成中文时，偶尔可能出现错字，需要重新生成或局部编辑
- 产品外观的还原程度取决于参考照片的清晰度和拍摄角度
- 长段文字不适合直接生成在图片中，建议后期排版
- 不同图片模型对手写字和单线人物的理解可能略有差异

## License

本项目推荐使用 [MIT License](LICENSE)。

你可以自由使用、修改和分发本 Skill，但第三方参考图片、品牌标识和生成模型仍需遵守各自的使用条款。

## Contributing

欢迎提交 Issue 或 Pull Request：

- 补充新的构图模板
- 优化中文手写标题
- 增加产品外观保护规则
- 改进不同画幅下的版式表现
- 分享使用案例

如果这个 Skill 对你有帮助，欢迎给仓库一个 Star。
