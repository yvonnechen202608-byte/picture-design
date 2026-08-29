# 提示词配方

仅在实际生成素材、批量维持一致性或制作展示页时读取。把方括号内容替换成本次照片中的真实信息；不要虚构照片里没有且用户未要求的对象。

## 单个透明素材

```text
Use case: style-transfer
Asset type: reusable transparent PNG journal sticker illustration
Input image: the attached photo is the subject and structural reference, not a style to copy
Primary request: isolate and redraw only [元素名称] as one standalone illustrated cutout
Keep recognizable: [轮廓、姿态、结构、材质、原图局部颜色等 2–4 项]
Remove: every unrelated object, scenery, label, price tag, reflection and occlusion fragment
Style/medium: warm nostalgic editorial illustration; matte gouache and opaque watercolor with restrained colored-pencil detail; subtly uneven hand-drawn edges; tactile paper grain inside the object only
Color palette: warm ivory highlights, honey ochre and ink brown foundations, muted olive/forest green and dusty blue-green, with no more than one small terracotta or mustard accent
Composition: one complete object centered, natural original viewing angle, object fills about 76–84% of canvas, 8–12% clear padding, no cropping
Background: genuinely transparent with an actual alpha channel; no white background, checkerboard, scene, ground plane, frame, outline sticker border or drop shadow
Constraints: preserve the subject’s identity while simplifying detail; no added props; no text, logo, signature or watermark; do not imitate any source composition
Avoid: photorealism, 3D plastic, smooth vector art, cartoon big eyes, neon saturation, HDR gloss, dirty vintage filter, white halo, stray pixels
```

## 组合物件

只在组合关系本身有意义时使用，例如茶具、桌椅、成对摆件。

```text
Redraw [组合名称] as one coherent transparent PNG cutout. Preserve the real spatial relationship and relative scale of [成员列表]. Keep every member fully visible and physically plausible. Do not add a background or scatter the members into a collage. Apply the same warm matte gouache visual system and actual alpha transparency as the rest of this sticker pack.
```

## 同组一致性锚点

从第一张合格素材中记录并在后续提示词中复用这一段；只替换对象字段。

```text
Series lock: same warm-to-cool balance, ink-brown contour weight, matte gouache opacity, fine paper grain, two-to-three-level shading, detail density and edge softness as the approved first asset. Change only the subject-specific shape, material and identifying colors.
```

不要把第一张素材当作必须复制的构图模板；一致性锚点只锁风格参数。

## 透明度定向修正

```text
Change only the background treatment. Keep the illustrated object, crop, proportions, colors, brush texture and detail exactly unchanged. Remove every background pixel and export a genuinely transparent PNG with a real alpha channel. Keep clean anti-aliased edges with no white halo, checkerboard, floor, shadow or stray fragments.
```

## 主体漂移定向修正

```text
Change only the subject fidelity. Restore these identifying features from the input photo: [特征列表]. Keep the approved palette, gouache texture, transparent background, framing and all unrelated details unchanged. Do not add new objects.
```

## 展示页/联系表

展示页是额外交付，不能替代独立 PNG。

```text
Use case: stylized-concept
Asset type: editorial contact sheet for a journal-sticker collection
Primary request: arrange the provided finished sticker illustrations without redrawing them
Scene/backdrop: clean warm-ivory paper, almost flat, no desk scene
Composition: asymmetrical loose catalogue; 55–70% negative space; 1–2 large hero objects, medium supporting objects, small accents; varied scale; no cards, borders or drop shadows; preserve every cutout silhouette
Typography: optional short title only, thin high-contrast editorial serif with loose tracking in ink brown; tiny quiet handwritten annotation only if exact copy is provided
Constraints: preserve the supplied artwork exactly; no new objects, no fake labels, no logos, no watermark
```

## 生成前自检

- 这一条提示词是否只指向一个独立素材？
- 是否列出了 2–4 个必须保留的辨识特征？
- 是否明确写真透明和禁止白底/棋盘格/投影？
- 是否保留本次照片主题，而不是套用旧参考图的具体对象？
- 同组锁定项是否只覆盖风格，不锁死每张构图？
