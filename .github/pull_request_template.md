## 改了什么 / 为什么

<!-- 一句话说明本 PR 的目的与动机。若是修 bug，附 #issue 号或复现路径。 -->

## 改动类型

- [ ] 译文（resources/*.json）
- [ ] 脚本逻辑（scripts/、*.ps1）
- [ ] 运行时（runtime/visible-text-fix.js）
- [ ] 文档（README/LICENSE 等）
- [ ] 仓库工程化（CI/模板/配置）

## 自测

<!-- 勾选并简述验证方式。改译文的话给出 json.tool 校验结果；改脚本给出 dry-run 输出。 -->

- [ ] `python -m json.tool resources/frontend-zh-CN.json` 等通过
- [ ] 改动例：含 `{...}`/`<tag>` 占位符的条目，译前译后占位符集合一致
- [ ] `python scripts/patch_install.py --dry-run` 探测/定位正常
- [ ] 改 .ps1 的话：用 `Parser` 解析 0 错误、保留 UTF-8 BOM
- [ ] 真机装/卸载一次，往返无残留

## 风险

<!-- 是否触及核心打补丁逻辑/占位符安全/可见文本修复运行时的安全约束？如不确定请说明。 -->
- 运行时安全约束：只改可见文本节点，绝不改元素属性/图标名/枚举（详见 runtime/visible-text-fix.js 顶部注释）。涉及运行时的改动请确认未破坏此约束。