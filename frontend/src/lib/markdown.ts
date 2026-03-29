import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
        return `<pre class="hljs rounded-xl overflow-x-auto"><code class="language-${lang}">${highlighted}</code></pre>`
      } catch { /* ignore */ }
    }
    const escaped = escapeHtml(str)
    return `<pre class="hljs rounded-xl overflow-x-auto"><code>${escaped}</code></pre>`
  },
})

// Open links in new tab
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const defaultRender = md.renderer.rules.link_open || function (tokens: any[], idx: number, options: any, _env: any, self: any) {
  return self.renderToken(tokens, idx, options)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
md.renderer.rules.link_open = function (tokens: any[], idx: number, options: any, env: any, self: any): string {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultRender(tokens, idx, options, env, self) as string
}

export function renderMarkdown(text: string): string {
  const html = md.render(text)
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ['iframe'],
    ADD_ATTR: ['target', 'rel'],
  })
}
