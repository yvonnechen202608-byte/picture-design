# WeChat Emotion Sticker Pack Skill

一个用于 Codex 的微信动态表情包制作 Skill：输入一张人物或动物照片，建立角色身份锁，生成8张独立情绪母图，并打包为带自然动画、动态手写文字和个性化配套视觉的微信表情素材。

## 能力

- 支持极简线条、像素、萌系卡通、Q版简约和3D立体风。
- 默认生成开心、生气、伤心、大笑、惊讶、害羞、感谢和再见8个语义。
- 输出8张240×240 GIF主图、8张120×120 PNG缩略图，以及封面、聊天面板图标、详情页横幅和两张赞赏图。
- 使用姿态保持动画，避免脸部、身体和四肢出现橡皮式拉扯。
- 支持人物与动物的不同动作逻辑；对猫咪使用符合承重、休息姿势和尾巴平衡的自然动作。
- 内置GIF体积压缩、异瞳等小面积身份色保护、透明度检查、关节连续性检查和逐帧质检图。

## 环境要求

- Codex，且当前环境可以使用图片生成工具。
- Python 3.10或更高版本。
- Pillow与NumPy，版本范围见 `requirements.txt`。
- 系统中至少有一种覆盖中文的字体；也可在运行打包脚本时通过 `--font` 指定字体文件。

安装Python依赖：

```bash
python3 -m pip install -r requirements.txt
```

## 安装为 Codex Skill

将整个 `wechat-emotion-sticker-pack` 目录复制或克隆到 Codex skills 目录，保持以下入口文件位置不变：

```text
$CODEX_HOME/skills/wechat-emotion-sticker-pack/SKILL.md
```

随后可使用类似提示词调用：

```text
使用 $wechat-emotion-sticker-pack，把这张宠物照片做成一套Q版简约风微信动态表情包。
```

## 目录结构

```text
wechat-emotion-sticker-pack/
├── SKILL.md
├── README.md
├── RELEASE-VALIDATION.md
├── requirements.txt
├── agents/openai.yaml
├── references/
│   ├── animation-rig.md
│   ├── companion-design.md
│   ├── dynamic-text.md
│   ├── prompt-recipes.md
│   ├── style-presets.md
│   └── wechat-specs.md
└── scripts/
    ├── package_stickers.py
    ├── pose_preserving_animation.py
    ├── validate_pack.py
    └── ...
```

`SKILL.md` 是 Codex 的主入口。`references/` 保存按任务读取的规格与设计规则，`scripts/` 负责确定性的动画、打包、压缩和验证。

本次GitHub发布包的自动检查与端到端试跑结果见 `RELEASE-VALIDATION.md`。

## 独立运行打包脚本

准备8张带真实alpha透明背景的PNG或WEBP母图，文件名依次以 `01` 到 `08` 开头，并准备按 `references/animation-rig.md` 标注的绑定文件：

```bash
python3 scripts/package_stickers.py <母图目录> <新输出目录> \
  --style chibi \
  --rig <animation-rig.json> \
  --reference-photo <原照片> \
  --companion-theme portrait \
  --title <专辑名称>
```

验证输出：

```bash
python3 scripts/validate_pack.py <输出目录>
```

只有验证报告中的 `ok` 为 `true`，才能称为通过脚本规格检查。机器检查不能替代对动作自然度、版权、字体授权和微信后台最新要求的人工确认。

## 隐私与素材

仓库不应包含用户照片、生成的角色母图、表情成品、字体文件、微信后台截图或本地绝对路径。建议把这些内容放在仓库之外；`.gitignore` 也预设排除了常用的本地输入与输出目录。

## 项目状态

当前动画引擎标识为 `pose-preserving-intact-silhouette-v10`。微信开放平台规格可能变化，提交前请以后台最新提示为准。

## 许可证

当前发布材料未擅自指定开源许可证。仓库所有者应在公开发布前选择合适的 `LICENSE`；若不添加许可证，其他人默认没有复制、修改或分发代码的授权。
