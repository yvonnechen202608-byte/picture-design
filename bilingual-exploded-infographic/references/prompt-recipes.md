# 提示词配方

只在真正生成、编辑图片，或用户要求完整提示词时读取本文件。先按 `visual-system.md` 规划内容，再选对应配方；不得把尖括号占位符原样发送给模型。

## 生图前内容规格

先在内部整理：

```text
主题：<中文主题名> / <ENGLISH NAME>
输入图片：<逐张声明主体身份参考、部件细节参考或抽象风格参考>
拆解类型：<装配顺序 / 剖面层次 / 容器承接 / 浅爆炸云团 / 实体隐喻>
从上到下的部件：<4–7 项；逐项写外形、颜色、质感和相对大小>
精确双语标签：
1. <中文部件名｜中文短语> / <ENGLISH PART | English notes>
2. ...
主体保真点：<形状、容器、配料、点缀、颜色、切面和表面质感>
背景模式：<浅色高调 / 深色餐桌>
事实状态：<用户提供的配方或结构 / 基于可见信息的视觉拆解 / 创意隐喻>
禁止项：<本主题最容易出现的身份漂移、错误部件与无关装饰>
```

## 有菜品或物件照片：完整编辑提示词

```text
Use case: image editing + infographic diagram + controlled compositing
Asset type: original bilingual exploded-view editorial poster, portrait 4:5 PNG

Primary request:
Create a new photorealistic exploded-view infographic around the subject in Image 1. Cleanly isolate the subject from its original background, then separate only its visually supported components into a calm vertical floating assembly. Preserve the subject's recognizable identity, proportions, natural colors, vessel or base, every visible ingredient or part, garnish, sauce, cut surface, and characteristic texture. Remove the original background, platform text, logos, watermarks, hands, and unrelated props. Do not redesign it into a different dish or object.

Input image roles:
- Image 1: locked subject identity and content reference. Preserve <逐项写主体保真点>.
- Images 2–4: abstract style references only for portrait proportions, central floating decomposition, neutral palette, side annotation rails, typography mood, thin connectors, tactile photographic texture, and generous negative space. Do not copy their dishes, objects, vessels, layers, text, arrows, background scene, object poses, or coordinates.

Content and order:
- Theme: <中文主题名> / <ENGLISH NAME>.
- Decomposition logic: <拆解类型>.
- Arrange these components from top to bottom in their credible assembly order: <逐项列出 4–7 个部件，并说明形态、颜色、质感与相对大小>.
- Reconstruct only small occluded areas needed to make the separation plausible. Do not invent unsupported hidden ingredients, materials, mechanisms, or claims.

Composition:
Portrait 4:5. Build one strong vertical subject axis near the horizontal center. Start the highest component around 6–11% canvas height and end the vessel or base around 82–94%. Keep the normal component width around 38–55% of the canvas and the widest component below 62%. Separate neighboring components with 2–4% canvas-height air gaps. Maintain the original assembly logic and a consistent front or slightly elevated camera angle. Place 4–7 annotations in alternating left and right information rails, each rail roughly 17–24% canvas width. Keep 5–7% side margins and 4–6% top and bottom margins. Preserve at least 42% visible background in the light mode or 30% in the dark mode. No component, vessel rim, label, or arrow may be cropped.

Photography and illustration:
Hyper-real commercial food or product photography with editorial cutout precision and a subtle photo-illustration collage quality. Use one large soft light from the upper left or front-left, coherent short soft shadows to the lower right, restrained contrast, crisp edges, and natural surface micro-detail. Preserve fibers, pores, crumbs, moisture, char, glaze, sauce viscosity, grain, metal, paper, ceramic, or fabric texture as appropriate. Floating layers have no visible supports, hands, wires, or motion blur. No plastic CGI, cartoon rendering, flat vector art, HDR, neon color, glow, or oversharpening.

Background and palette:
Use <浅色高调 / 深色餐桌>. <若浅色：warm ivory #F3F1EC to soft pale gray #E7E8E5, near-black text, warm-gray connectors, no visible horizon. 若深色：black-green charcoal #101512 to graphite #202322 or a heavily blurred warm-wood culinary environment, warm-ivory text, warm-beige connectors, subject clearly separated from the background.> Let the subject provide 2–4 natural accent color families. Keep saturation natural and do not apply a global brown or cinematic color wash.

Exact visible text:
All semantic text must be bilingual. Chinese is always primary and English secondary. Render every group verbatim; do not omit either language, translate into English only, add extra copy, or create gibberish.

Optional small theme title:
"<中文主题名>"
"<ENGLISH NAME>"

Component annotations:
1. "<中文部件名｜中文短语>"
   "<ENGLISH PART | English notes>"
2. <完整列出所有标签>

Typography:
Use clear modern Chinese sans-serif for annotations, visually similar to Source Han Sans or PingFang SC, paired with a neutral Swiss-style English sans-serif similar to Inter or Helvetica Neue. Chinese part names use medium or semibold; descriptors use regular. English is 58–72% of the Chinese visual height with slightly open tracking. If the optional title is shown, use restrained contemporary Chinese serif and a smaller editorial English serif or clean uppercase sans-serif. No calligraphy, brush lettering, decorative script, chunky display type, or English-only headline.

Connectors and labels:
Use thin warm-gray or warm-beige 1–1.5 px visual-weight lines, short elbow connectors or low-curvature arrows, open arrowheads, and optional tiny terminal dots. Each line points to exactly one component, stays in negative space, and never crosses food, objects, other lines, or text. In the light mode prefer unboxed labels or pale ivory boxes with hairline borders; in the dark mode allow restrained translucent charcoal rounded panels. Keep text compact, aligned, and fully legible.

Originality and constraints:
Create a new arrangement for this subject within the visual system. Do not reproduce any reference image's exact layer count, component pose, crop, vessel, wood surface, kitchen scene, label wording, arrow curve, or coordinate. No brand, logo, watermark, QR code, price, nutrition panel, certification, unsupported origin, medical claim, random garnish, decorative sparkle, thick arrows, card grid, UI chrome, or dense paragraph text.
```

## 只有菜名、物件名或文字主题

使用上面的完整提示词，但替换开头与输入图片段：

```text
Use case: infographic diagram
Asset type: original bilingual exploded-view editorial poster, portrait 4:5 PNG

Primary request:
Create a new photorealistic exploded-view infographic for <中文主题名> / <ENGLISH NAME>. Translate the theme into a credible central floating assembly with 4–7 visually distinct components. This is an editorial visual interpretation, not a claim of an authenticated recipe, real hidden structure, nutrition result, or scientific diagram.

Input image roles:
- Images 1–3, if supplied: abstract style references only for portrait proportions, central floating decomposition, neutral palette, side annotation rails, typography mood, thin connectors, tactile photographic texture, and generous negative space. Do not copy their objects, layers, text, arrows, backgrounds, poses, or coordinates.
```

随后完整保留 `Content and order`、`Composition`、`Photography and illustration`、`Background and palette`、`Exact visible text`、`Typography`、`Connectors and labels`、`Originality and constraints`。

如果主题不是食物，把“ingredient / flavor”词汇替换为准确的“component / material / function / meaning / mood”，仍保持写实材质和双语短标签。

## 拉面类内容示例

这是内容规划示例，不是固定文案，也不得对其他菜照搬：

```text
主题：豚骨拉面 / TONKOTSU RAMEN
拆解类型：容器承接；从调味与配菜向面条、汤底、碗逐层下降
部件顺序：芝麻蒜片与海苔 → 红姜与葱花 → 青菜与木耳 → 溏心蛋 → 炙烤叉烧 → 碱水面 → 浓豚骨汤与陶碗
双语标签：
- 海苔｜咸鲜海味 / NORI | Briny · Mineral
- 葱花｜清辛草本 / SCALLION | Fresh · Herbal
- 木耳｜脆弹菌香 / WOOD EAR | Crisp · Earthy
- 溏心蛋｜咸甜绵润 / AJITAMA | Savory-sweet · Jammy
- 叉烧｜炭香油润 / CHASHU | Smoky · Rich
- 碱水面｜弹韧麦香 / ALKALINE NOODLES | Springy · Wheaty
- 豚骨汤｜浓醇胶质 / PORK BROTH | Creamy · Gelatinous
事实状态：如果只给照片，标记为“基于可见信息的视觉拆解”；不可声称是真实配方
```

## 只交付提示词

- 输出已经替换完全部占位符的完整提示词，不调用生图工具。
- 附上精确双语文字清单，方便用户检查中文和英文。
- 说明 `事实状态`。只有照片时使用“基于可见信息的视觉拆解”，只有主题时使用“创意视觉演绎”。
- 不使用模型专属权重语法，除非用户指定的模型确实支持。

## 定向修正

### 中文或英文缺失、乱码

```text
Change only the visible typography. Render every annotation as the exact two-line bilingual pair provided below, with Chinese on the first line and English on the second line. Restore any missing Chinese or English, remove duplicated or garbled characters, and add no extra text. Preserve every object, component order, crop, shadow, background, connector, and spacing unchanged: <粘贴完整精确双语文案>.
```

### 主体身份漂移

```text
Change only the central subject so it matches Image 1: <逐项列出主体形状、容器、可见配料或部件、颜色、切面和质感>. Restore anything visible in Image 1 that was omitted and remove anything unsupported that was added. Keep the background removed. Preserve all labels, connectors, composition, spacing, lighting direction, and background unchanged.
```

### 部件顺序或指向错误

```text
Change only the vertical assembly order and annotation targets. Arrange the components exactly from top to bottom as follows: <顺序>. Route each bilingual label to its matching component and to no other component. Preserve component appearance, scale, lighting, all wording, background, and overall margins unchanged.
```

### 连线穿物或过重

```text
Change only the connector geometry and weight. Use thin warm-gray or warm-beige hairlines, short elbow paths or low-curvature open arrows. Route every line entirely through negative space, with one label pointing to one component. Remove crossings and thick filled arrowheads. Preserve all objects, text, positions, colors, shadows, and crop unchanged.
```

### 留白不足或裁切

```text
Change only the scale and spacing of the full assembly. Scale the central stack and annotations down just enough to restore 5–7% side margins, 4–6% top and bottom margins, and clear air between every layer. Show the complete vessel, crust, base, and all label boxes with no cropped edge. Preserve subject identity, component order, exact text, colors, and background unchanged.
```

### 风格漂移

```text
Change only the rendering and graphic styling: photoreal tactile cutout photography, coherent soft upper-left light, calm central vertical suspension, restrained natural color, generous negative space, editorial bilingual typography, and thin quiet connectors. Remove plastic CGI, cartoon rendering, neon saturation, heavy cards, thick arrows, and busy decoration. Preserve the subject, component order, exact bilingual wording, and factual content unchanged.
```
