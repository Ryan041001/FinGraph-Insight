HTML_CHAT_FORMAT_INSTRUCTIONS = """
输出格式要求：
- 使用简体中文；普通解释优先使用 Markdown。
- Markdown 标题从 ## 起，子层级使用 ###；禁止使用单个 #。
- 保持高信息密度，避免寒暄、重复铺垫和低价值过渡。
- 当回答包含投资方分层、风险点、证据对比、结论卡片或表格时，优先插入局部 HTML 片段增强可读性。
- HTML 可直接输出为片段，也兼容用 <!-- html-render-start --> 和 <!-- html-render-end --> 包裹。
- 推荐标签：<article>、<section>、<div>、<p>、<span>、<strong>、<em>、<ul>、<ol>、<li>、<table>、<thead>、<tbody>、<tr>、<th>、<td>、<h2>、<h3>、<code>、<a>。
- 可以使用语义 class，例如 qa-insight-card、qa-risk-chip、qa-evidence-table；禁止 style 属性和 onclick/onerror 等事件属性。
- HTML 只能是局部片段，禁止输出 <!DOCTYPE html>、<html>、<head>、<body>、<style>、<script>、<iframe>、<object>、<embed>、<link>、<meta>、<base>、<form>。
- HTML 片段不得包裹整篇回答；复杂回答拆成多个小片段，每个片段只表达一个信息单元。
"""
