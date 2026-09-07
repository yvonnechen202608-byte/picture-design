# 提示词配方

只有在真正生图、编辑图片或用户要求完整提示词时读取本文件。先按 `visual-system.md` 确定内容，再使用对应配方；不要把占位符原样发送给模型。

## 生图前内容规格

先在内部整理以下内容：

```text
菜品：<中文名> / <ENGLISH NAME>
输入图片：<逐张写明成品主体参考、食材参考或抽象风格参考>
食材：<4–6 个明确、可视化、彼此不重叠的对象>
步骤：<3–5 个单动作，每项都能画成手绘图标；用户提供五步时完整保留>
成品保真点：<外形、颜色、容器、摆盘、每一种可见蔬菜/配料/点缀、酱汁、质感；逐项列出，不得删除>
强调色：<从本菜提取的一种天然颜色>
精确可见文字：<中文菜名>；<ENGLISH DISH NAME>；食材 / INGREDIENTS；步骤 / PROCESS；成品 / FINAL DISH
事实状态：<用户菜谱 / 创意食谱演绎>
```

## 有菜品照片：完整编辑提示词

```text
Use case: infographic-diagram + compositing
Asset type: original bilingual food recipe poster, portrait 9:16 PNG

Primary request:
Create a new professional food infographic around the dish in Image 1. Cleanly isolate the finished dish from its original background and make it the large lower-right hero. Preserve its recognizable food structure, colors, vessel, plating, proportions, texture, and every visible vegetable, ingredient, garnish, sauce, and topping. A written recipe may control the upper ingredient section and process icons, but omission from that recipe never authorizes removing visible food from Image 1. Do not replace it with a different or idealized dish.

Input images:
- Image 1: locked finished-dish identity and plating reference; preserve every visible food component and the vessel, but not the original background, platform text, logo, or watermark.
- Images 2–4: abstract style references only for warm-white palette, three-zone hierarchy, photographic cutouts, black hand-drawn process icons, dotted arrows, typography mood, and generous negative space. Do not copy their dishes, ingredients, icon shapes, plates, exact object poses, or coordinates.

Content:
- Dish: <中文名> / <ENGLISH NAME>.
- Upper ingredients: <逐项列出 4–6 个食材及其可见形态>.
- Middle-left process: <逐项列出 3–5 个动作与对应手/器具图标；五步时全部保留并压缩间距>.
- Lower-right result: the preserved finished dish from Image 1.

Scene and composition:
Warm near-white seamless background, high-key studio food photography, portrait 9:16. Top 2.5–9%: the relatively large two-line bilingual dish title, horizontally centered and visually above every other element. Nothing may appear above the title. Add only one or two tiny restrained monoline or ingredient-color decorative marks near the title; never use a border or floral ornament. Height 11–14%: place the ingredients label on its own left-aligned row below the title. Keep the central corridor below the title open and airy. Upper 16–40%: neatly spaced top-down ingredient cutouts in a loose knolling grid. Height 40–47%: open breathing space with one black dotted elbow connector traveling down then left into the process. Left 7–30% from height 45–93%: a vertical sequence of 3–5 consistent monoline hand-drawn cooking icons joined by dotted downward arrows. For five steps, uniformly reduce icon size and vertical gaps by about 12–18%; keep the complete fifth icon above a 3–4% canvas-height bottom margin. Lower-right 35–94% from height 58–94%: one visually dominant finished dish, with the entire plate or serving vessel fully visible. Show the complete continuous rim with no cropped edge or missing corner and keep 4–6% canvas-width warm-white clearance around the vessel, especially at the right and bottom. Keep at least 40% visible background and prevent all overlaps.

Photography and illustration:
Ingredients and final dish are photorealistic commercial food photography, top-down or high-angle, sharp natural texture, soft large light from upper left, subtle short shadows to lower right, natural food color, no HDR. Process icons are clean black monoline drawings with rounded caps and slight handmade irregularity; one tiny accent color sampled from <强调色> is allowed, under 15% of the icon area.

Dish title at the absolute visual top center, render verbatim as two lines:
"<中文名>"
"<ENGLISH NAME>"
The Chinese dish name is the primary line at 1.45–1.8 times the section-label height; the English uppercase translation is a secondary line at 42–50% of the Chinese size. Center-align both lines, keep the pair within 56–62% of canvas width, and leave clear whitespace on every side. Nothing may sit above this title. Add no more than one or two tiny restrained decorative marks. Put the ingredients section label on a separate lower row, then begin the ingredient photography below it. For a long title, reduce type size and tracking rather than pushing it to an edge or wrapping into extra lines.

Section labels, render verbatim:
"食材 / INGREDIENTS"
"步骤 / PROCESS"
"成品 / FINAL DISH"
Chinese first and English second. Neutral modern Chinese sans-serif paired with uppercase Swiss-style sans-serif. Near-black medium/semibold. Each section label has a short bold overline and a thin underline. Never omit either language from the dish title or section labels. No other text, gibberish, duplicated characters, or partial words.

Constraints:
Original composition within this visual system. Change the layout rhythm and object poses to suit this dish. Preserve every visible food component from Image 1 even if the written recipe omits it; remove only non-food background, platform text, logos, watermarks, and unrelated props. Dotted paths stay in empty background and never cross food, icons, labels, or plate. No brand, logo, watermark, price, nutrition facts, recipe claims, extra captions, frames, cards, colored background, gradient, wooden table, cloth, kitchen scene, 3D icons, cartoon food, heavy shadows, or decorative sparkle.
```

如果用户给的是准确菜谱，在 `Content` 中逐项使用；如果是照片推断，则只放视觉上可信的主要食材，不加入精确份量、火候或时间。

## 只有菜名或主题：完整生成提示词

沿用上面的提示词，将开头和输入图片段替换为：

```text
Use case: infographic-diagram
Asset type: original bilingual food recipe poster, portrait 9:16 PNG

Primary request:
Create a new professional food infographic for <中文名> / <ENGLISH NAME>. Show a visually plausible editorial interpretation of the dish, not a claim of an authenticated recipe.

Input images:
- Images 1–3: abstract style references only for the warm-white palette, three-zone hierarchy, photographic cutouts, black hand-drawn process icons, dotted arrows, typography mood, and generous negative space. Do not copy their dishes, ingredients, icon shapes, plates, exact object poses, or coordinates.
```

随后完整保留 `Content`、`Scene and composition`、`Photography and illustration`、`Text` 和 `Constraints` 各段。成品描述要写清食物结构、熟度、酱汁、点缀和盘器，不能只写 `delicious food`。

## 只交付提示词

当用户只要提示词时：

- 输出已经替换完所有占位符的完整提示词，不调用生图工具。
- 同时列出假设的食材与步骤，并标明 `用户菜谱` 或 `创意食谱演绎`。
- 不附加模型专属权重语法，例如 `(masterpiece:1.2)`，除非用户指定支持该语法的模型。优先使用清晰的布局、对象、文字与约束描述。

## 定向修正

### 文字修正

```text
Change only the dish title and the three section labels. Render the dish title exactly as two lines: "<中文名>" and "<ENGLISH NAME>". Render the labels exactly: "食材 / INGREDIENTS", "步骤 / PROCESS", and "成品 / FINAL DISH". Chinese must appear in every text group. Remove any missing-language, duplicated, or garbled text. Preserve every food object, icon, dotted path, shadow, crop, spacing, and color unchanged.
```

### 菜名修正

```text
Change only the top hierarchy and its vertical spacing. Move the exact two-line title "<中文名>" above "<ENGLISH NAME>" to the absolute visual top center so no label or object appears above it. Set the Chinese medium/semibold line to 1.45–1.8 times the section-label height and the English uppercase line to 42–50% of the Chinese size. Add no more than one or two tiny restrained monoline or ingredient-color decorative marks. Move "食材 / INGREDIENTS" to a separate left-aligned row below the title, preserve a quiet central gap, and keep all ingredient photography below that row. Preserve all food content, process icons, dotted paths, shadows, and colors unchanged.
```

### 成品盘器裁切修正

```text
Change only the size and placement of the lower-right finished dish. Scale it down just enough and reposition it inward so the complete plate or serving vessel is visible, including the entire continuous rim with no cropped edge or missing corner. Keep 4–6% canvas-width warm-white clearance from the right and bottom edges and clear separation from nearby labels and process icons. Preserve the dish identity, every visible ingredient and garnish, plating, color, texture, title, ingredient block, process sequence, dotted paths, and all text unchanged.
```

### 成品身份修正

```text
Change only the lower-right finished dish so it matches Image 1: <逐项列出外形、容器、每一种可见蔬菜/配料/点缀、酱汁与质感>. Restore anything from Image 1 that was omitted. Do not remove a visible food component merely because the written recipe does not mention it. Keep the original background removed. Preserve the upper ingredients, process icons, text, dotted paths, overall layout, lighting direction, and negative space unchanged.
```

### 连线与留白修正

```text
Change only the connector geometry. Route one dotted elbow line from the lower edge of the ingredient zone down through empty white space, then left into the first process icon. Keep separate dotted downward arrows between the process icons. No line may cross food, text, icons, or the plate. Preserve all objects, wording, colors, and shadows unchanged.
```

### 风格漂移修正

```text
Change only the rendering style of the process sequence: thin near-black monoline hand drawings, rounded caps, slight human irregularity, no 3D, no photoreal hands, no thick sticker outlines. Keep the depicted actions, food photography, typography, layout, and all text unchanged.
```
