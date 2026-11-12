import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { join, dirname, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { buildGuide, loadPersona } from '../persona.js'

test('bundled persona supplies MuDuo and platform rules', async () => {
  const result = await buildGuide({workflow:'create'})
  assert.equal(result.workflow,'create')
  assert.equal(result.persona.name,'沐朵')
  assert.match(result.persona.content,/不热络，但从不敷衍/)
  assert.match(result.persona.content,/B站：只制作和发布横屏/)
  assert.match(result.persona.content,/抖音：只制作和发布竖屏/)
})

test('configured original is re-read and failures do not silently fall back', async () => {
  const dir = await mkdtemp(join(tmpdir(),'video-persona-'))
  try {
    const file = join(dir,'persona.md')
    await writeFile(file,'沐朵原文一')
    assert.equal((await buildGuide({}, {personaPath:file})).persona.content,'沐朵原文一')
    await writeFile(file,'沐朵原文二')
    assert.equal((await loadPersona(file)).content,'沐朵原文二')
    await writeFile(file,' ')
    await assert.rejects(loadPersona(file),/为空/)
    await writeFile(file,'x'.repeat(65537))
    await assert.rejects(loadPersona(file),/64KiB/)
    await assert.rejects(loadPersona(join(dir,'missing.md')))
  } finally {
    assert.equal(dirname(dir),tmpdir())
    assert.ok(basename(dir).startsWith('video-persona-'))
    await rm(dir,{recursive:true,force:true})
  }
})
