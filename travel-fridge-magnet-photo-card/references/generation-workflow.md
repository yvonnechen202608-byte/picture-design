# 生成与验证流程

## 1. 准备摄影源

先用 `view_image` 检查每张本地照片，确认主体、方向、可裁切区域和标签。为每张照片记录：

- 主体与 2–5 个识别特征
- 候选背景色及最终十六进制颜色
- 下半部裁切焦点 `focus-x`、`focus-y`（0–1；默认均为 0.5）
- 最终英文标签，逐字记录

多张照片逐张处理，一张照片对应一张贴纸和一张海报。不要让一次生成调用承担多个不同成品。

若只有文字主题，先用内置 `image_gen` 生成一张摄影源：

```text
Use case: photorealistic-natural
Asset type: documentary travel photograph for the lower half of a poster
Primary request: <用户主题>
Subject: one clear, recognizable primary subject with a natural surrounding context
Style/medium: believable contemporary travel photography, natural material detail, no illustration
Composition/framing: portrait-source friendly; keep the subject near the center so a horizontal 3:2 crop remains usable
Lighting/mood: bright, clean, candid editorial light appropriate to the subject
Constraints: no text, no logo, no watermark, no poster layout, no collage, no border
```

不要把生成的摄影源描述成真实事件记录或用户实拍。

## 2. 只生成透明贴纸主体

使用内置 `image_gen`。本地照片先通过 `view_image` 进入上下文；若所有目标图都有本地路径，则使用 `referenced_image_paths`。否则只纳入包含当前目标图所需的最少最近图片数。每个成品单独调用一次。

根据照片改写尖括号字段，使用以下短提示词：

```text
Use case: style-transfer
Asset type: isolated travel-souvenir fridge-magnet artwork for later compositing
Input image: the supplied photograph is subject reference only
Primary request: create an original compact illustration of <主体>, preserving <识别特征>; reinterpret rather than trace
Scene/backdrop: genuinely transparent background; one isolated closed silhouette only
Style/medium: refined hand-drawn flat illustration, delicate ink contours, restrained colored-pencil and matte print texture, simplified but recognizable, contemporary editorial travel souvenir
Composition/framing: centered, self-contained, mostly frontal or gently simplified perspective, small-icon readability, comfortable transparent margin
Color palette: 4–7 colors derived from the source photograph, led by <主色与点缀色>
Text: none
Constraints: preserve subject count and defining geometry; clean edges; no white border and no drop shadow because both will be added later; no background panel; no extra objects; no logo; no watermark; no letters, numbers, signage, caption, or fake transparent checkerboard
Avoid: photo cutout, photoreal miniature, glossy plastic, clay toy, heavy 3D, childish cartoon, dense scenery, complex micro-details, direct copying of any reference poster
```

人物或动物主题，在 `Constraints` 中补充数量、姿势关系、服装主色或物种花纹。建筑主题补充屋顶、门窗、塔楼或拱门等可核对结构。

生成后检查：

- 背景有真实 alpha 透明度，而不是白底或棋盘格。
- 主体外形与照片相符，且没有无关附加物。
- 没有任何乱码或模型自造文字。
- 插画是平面手绘纪念品，不是照片抠图、黏土或厚重 3D。

一次迭代只纠正一个主要问题。若透明度错误，优先只要求“保留主体不变，改为真正透明背景”。

## 3. 程序化拼版

使用随 Skill 提供的 `scripts/compose_card.py`。优先调用 Codex 工作区依赖提供的 Python；如果当前 Python 已安装 Pillow，也可以直接使用。

```bash
<python> scripts/compose_card.py \
  --photo /absolute/path/source.jpg \
  --sticker /absolute/path/sticker.png \
  --label "Yunnan, 2024" \
  --bg "#3677CC" \
  --focus-x 0.50 \
  --focus-y 0.50 \
  --output /absolute/path/yunnan-2024-card.png
```

`--bg auto` 会从照片中选一个干净主色，但视觉判断优先；若自动结果偏灰、偏脏或与主体冲突，显式传入最接近固定色彩家族的十六进制颜色。用 `--sticker-scale` 在 0.85–1.15 之间微调即可，避免把贴纸放大成上半部主画面。

脚本固定执行：3:4 画布、50/50 硬切、照片 cover 裁切、暖白模切边、右下柔影、居中标签。它不会生成式修改照片。

## 4. 最终验证

用 `view_image` 检查最终 PNG：

- 1080 × 1440 或等比例 3:4，分界恰好在 50%。
- 上半部只有纯色、一个小贴纸和一行标签；四周留白明显。
- 下半部与摄影源内容一致，仅发生必要的等比缩放和裁切。
- 主体没有被文字压住，贴纸与分界线之间有呼吸空间。
- 标签逐字正确、仅一行、无乱码；深浅背景上的对比足够。
- 没有渐变、拼贴装饰、边框、平台水印或额外文案。

若照片裁切不理想，只调整 `--focus-x`/`--focus-y`；若贴纸比例不理想，只调整 `--sticker-scale`。不要重新生成已经正确的部分。
