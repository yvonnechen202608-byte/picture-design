# GitHub 发布检查清单

## 建议仓库信息

- Repository name：`wechat-emotion-sticker-pack`
- Description：`把人物或宠物照片制作成自然动作微信动态表情包的 Codex Skill`
- Topics：`codex-skill`、`wechat-stickers`、`gif-animation`、`image-generation`、`python`、`pillow`
- 建议首个版本标签：`v1.0.0`

## 已准备

- `SKILL.md` 主入口和 `agents/openai.yaml` 界面配置。
- 6份规格、风格、提示词、绑定与配套设计参考文档。
- 12个动画、打包、透明修复和逐帧质检脚本。
- `README.md`、`requirements.txt`、`.gitignore` 与 `NOTICE.md`。
- `RELEASE-VALIDATION.md`，记录不含私密素材的发布审计和 `316/316` 端到端试跑结果。
- 已排查个人绝对路径、用户照片、密钥和生成表情成品。
- Python脚本语法、所有命令行入口和Skill前置信息已检查。

## 发布前由仓库所有者确认

- [ ] 选择是否公开，以及使用 Public 还是 Private 仓库。
- [ ] 选择许可证并添加根目录 `LICENSE`。若希望广泛复用，可考虑 MIT；若暂不授权他人使用，则不要添加开源许可证。
- [ ] 确认GitHub账号名称、仓库简介和版本号。
- [ ] 上传前再次确认暂存区不包含照片、GIF成品、字体或微信后台截图。
- [ ] 创建首个Release时，可附上不含真人或宠物私密照片的演示素材；这不是运行Skill所必需的。

## 推荐上传内容

```text
.gitignore
GITHUB-PUBLISH-CHECKLIST.md
NOTICE.md
README.md
RELEASE-VALIDATION.md
SKILL.md
requirements.txt
agents/
references/
scripts/
```

不要上传 `__pycache__/`、本地输入照片、生成输出目录、字体文件或打包测试产生的ZIP。
