/*== CLAUDE_ZH_CN_VTF_BEGIN ==*/
/*
 * 可见文本修复运行时 (Visible Text Fix)
 * ------------------------------------------------------------------
 * Claude Desktop 中文补丁的一部分。
 *
 * 作用：i18n JSON 覆盖不到的“硬编码英文”（直接写死在 JS 里、不走翻译键的
 * 文案），在运行时把它们的【可见文本】替换为中文。
 *
 * 安全原则（务必遵守）：
 *   1. 只改 DOM 文本节点 (Node.TEXT_NODE) 的内容，绝不动元素的
 *      属性 / class / data-* / aria-label / 图标名 / 枚举值。
 *      —— 翻译内部标识会导致图标消失、路由错乱等问题。
 *   2. 精确映射表只收录“确认是纯展示、且语义无歧义”的短语。
 *   3. 正则兜底数量克制，使用词边界，避免误伤。
 *   4. 跳过 <script>/<style>/<code>/<pre>/输入框 等不该翻译的容器。
 *
 * 通过 globalThis.__CLAUDE_ZH_CN_VTF__ 哨兵防止重复注入/重复初始化。
 */
(function () {
  "use strict";
  if (globalThis.__CLAUDE_ZH_CN_VTF__) return;
  globalThis.__CLAUDE_ZH_CN_VTF__ = true;

  // ---- 精确映射：完整匹配 trim 后的可见文本 ----
  // 仅收录确认安全的纯展示短语。键区分大小写。
  var EXACT = new Map([
    // 导航 / 区块
    ["Projects", "项目"],
    ["Project", "项目"],
    ["Artifacts", "工件"],
    ["Live artifacts", "实时工件"],
    ["Recents", "最近"],
    ["Starred", "已收藏"],
    ["Chats", "对话"],
    ["Scheduled", "已安排"],
    ["Connectors", "连接器"],
    ["Settings", "设置"],
    ["General", "通用"],
    ["Appearance", "外观"],
    ["Account", "账户"],
    ["Profile", "个人资料"],
    ["Feature preview", "功能预览"],
    ["Help & support", "帮助与支持"],

    // 外观选项
    ["Theme", "主题"],
    ["Light", "浅色"],
    ["Dark", "深色"],
    ["System", "跟随系统"],
    ["Auto", "自动"],
    ["Default", "默认"],

    // 常见动作
    ["Customize", "自定义"],
    ["Rename", "重命名"],
    ["Delete", "删除"],
    ["Export", "导出"],
    ["Share", "分享"],
    ["Copy", "复制"],
    ["Edit", "编辑"],
    ["Save", "保存"],
    ["Cancel", "取消"],
    ["Done", "完成"],
    ["Retry", "重试"],
    ["Continue", "继续"],
    ["New chat", "新建对话"],
    ["New project", "新建项目"],

    // 状态 / 杂项
    ["On", "开启"],
    ["Off", "关闭"],
    ["Enabled", "已启用"],
    ["Disabled", "已禁用"],
    ["Loading…", "加载中…"],
    ["Loading...", "加载中…"],
  ]);

  // ---- 正则兜底：用于嵌在更长文本里的固定词 ----
  // 谨慎使用词边界；按顺序应用。
  var SUBSTR = [
    [/\bLive\s+artifacts\b/g, "实时工件"],
    [/\bLive\s+Artifacts\b/g, "实时工件"],
    [/\bArtifacts\b/g, "工件"],
  ];

  // 不进入翻译的容器标签
  var SKIP_TAGS = new Set([
    "SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA", "INPUT",
    "NOSCRIPT", "SVG", "PATH", "CANVAS",
  ]);

  // 仅在这些可见 UI 区域内扫描，缩小范围、降低误伤与开销
  var SCOPE_SELECTOR =
    '[role="dialog"],[role="menu"],[role="listbox"],[role="navigation"],main,nav,aside,header';

  var MAX_NODES_PER_PASS = 900;

  function shouldSkip(node) {
    var p = node.parentNode;
    if (!p || p.nodeType !== 1) return true;
    if (SKIP_TAGS.has(p.tagName)) return true;
    // 可编辑区域不动
    if (p.isContentEditable) return true;
    return false;
  }

  function translateText(raw) {
    var trimmed = raw.trim();
    if (!trimmed) return null;

    // 1) 完整匹配（保留原有前后空白）
    if (EXACT.has(trimmed)) {
      return raw.replace(trimmed, EXACT.get(trimmed));
    }

    // 2) 正则兜底（仅当含 ASCII 字母时才尝试，避免对纯中文做无用功）
    if (/[A-Za-z]/.test(raw)) {
      var out = raw;
      for (var i = 0; i < SUBSTR.length; i++) {
        out = out.replace(SUBSTR[i][0], SUBSTR[i][1]);
      }
      if (out !== raw) return out;
    }
    return null;
  }

  function processRoot(root) {
    if (!root || !root.querySelectorAll) return;
    var scopes = root.matches && root.matches(SCOPE_SELECTOR)
      ? [root]
      : root.querySelectorAll(SCOPE_SELECTOR);
    var count = 0;
    for (var s = 0; s < scopes.length && count < MAX_NODES_PER_PASS; s++) {
      var walker = document.createTreeWalker(
        scopes[s],
        NodeFilter.SHOW_TEXT,
        null
      );
      var n;
      while ((n = walker.nextNode())) {
        if (count >= MAX_NODES_PER_PASS) break;
        if (shouldSkip(n)) continue;
        var next = translateText(n.nodeValue);
        if (next != null && next !== n.nodeValue) {
          n.nodeValue = next;
          count++;
        }
      }
    }
  }

  // ---- 去抖动调度 ----
  var scheduled = false;
  var lastRun = 0;
  var MIN_INTERVAL = 850;

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    var now = Date.now();
    var wait = Math.max(0, MIN_INTERVAL - (now - lastRun));
    setTimeout(function () {
      scheduled = false;
      lastRun = Date.now();
      try {
        processRoot(document.body);
      } catch (e) {
        /* 静默：绝不因翻译异常影响应用 */
      }
    }, wait);
  }

  function start() {
    if (!document.body) {
      setTimeout(start, 100);
      return;
    }
    // 首次全量
    try {
      processRoot(document.body);
    } catch (e) {}

    // 监听后续 DOM 变化
    var obs = new MutationObserver(function () {
      schedule();
    });
    obs.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
/*== CLAUDE_ZH_CN_VTF_END ==*/
