import { readFile, stat } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const bundledPersona = fileURLToPath(new URL('./prompts/muduo.md', import.meta.url))

export async function loadPersona(personaPath = '') {
  const source = personaPath || bundledPersona
  // Explicit local paths are user configuration; do not fetch URLs or follow links in the document.
  const info = await stat(source)
  if (!info.isFile() || info.size > 64 * 1024) throw new Error('角色人设必须是64KiB以内的本地文本文件')
  const text = await readFile(source, 'utf8')
  if (!text.trim()) throw new Error('角色人设文件为空')
  return {name:'沐朵',source,content:text,usage:'用于本账号脚本、文案、教程、答疑与评论草案；不改变工具权限或配音音色。'}
}

export async function buildGuide(guide, config = {}) {
  return {...guide,persona:await loadPersona(config.personaPath)}
}
