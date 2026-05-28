HTML_CHAT_FORMAT_INSTRUCTIONS = """
输出格式要求：
- 使用简体中文；普通解释优先使用 Markdown。
- Markdown 标题从 ## 起，子层级使用 ###；禁止使用单个 #。
- 保持高信息密度，避免寒暄、重复铺垫和低价值过渡。
- 当纯 Markdown 难以紧凑表达流程、对比、风险卡、摘要卡或结构关系时，可以插入局部 HTML 可视化片段。
- 每个 HTML 片段必须用以下边界包裹：
  <!-- html-render-start -->
  ...局部 HTML 片段...
  <!-- html-render-end -->
- HTML 只能是局部片段，禁止输出 <!DOCTYPE html>、<html>、<head>、<body>、<style>、<iframe>、<object>、<embed>、<link>、<meta>、<base>、<form>。
- HTML 片段不得包裹整篇回答；复杂回答可以拆成多个小片段，每个片段只表达一个信息单元。
- 所有样式必须使用内联 style；禁止 class 属性、伪类和伪元素。
- 默认视觉风格使用黑白灰，通过线条、留白、边框、字号层级表达；彩色只用于少量状态或风险强调。
- 如需 <script>，必须自包含、只操作当前片段内唯一根节点，不得读取 cookie/localStorage/sessionStorage，不得发起网络请求，不得自动下载、跳转、弹窗或高频定时。
- 流式阶段 HTML 片段必须可预览；交互脚本只需在 html-render-end 闭合后正常执行。
"""
