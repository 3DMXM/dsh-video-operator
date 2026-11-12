// Local-only Cubism frame export. No model or Core assets are bundled.
import { readFile, writeFile, mkdir, realpath } from 'node:fs/promises'
import { createServer } from 'node:http'
import { dirname, resolve, sep, extname, join } from 'node:path'
import { createHash } from 'node:crypto'
import { chromium } from 'playwright'

const input = process.argv.indexOf('--request')
if (input < 0) throw new Error('--request required')
const request = JSON.parse(await readFile(process.argv[input+1], 'utf8'))
const root = await realpath(request.root)
const release = JSON.parse(await readFile(join(root,'release.json'),'utf8'))
async function inside(base, name) {
  const path = await realpath(resolve(base,name))
  if (path !== base && !path.startsWith(base+sep)) throw new Error('Resource escapes local model directory')
  return path
}
const entry = await inside(root,release.runtimeEntry)
const preview = await inside(root,release.preview)
const runtime = dirname(entry)
const model = JSON.parse(await readFile(entry,'utf8'))
const moc = await inside(runtime,model.FileReferences.Moc)
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const mocHash = hash(await readFile(moc))
if (release.mocSha256 && mocHash !== release.mocSha256) throw new Error('MOC fingerprint does not match release.json')
const atlasHashes = await Promise.all(model.FileReferences.Textures.map(async file => hash(await readFile(await inside(runtime,file)))))
if (release.atlasSha256 && atlasHashes[0] !== release.atlasSha256) throw new Error('Atlas fingerprint does not match release.json')
// Reuse the user's versioned renderer, including its motion/physics/hand arbitration.
// Adapt only the frame clock in memory; leave the sealed source untouched.
let adapter = await readFile(join(preview,'runtime.js'),'utf8')
for (const [from,to] of [
  ['fit(); app.start();','fit(); app.stop();'],
  ['capture() { return canvas.toDataURL(\'image/png\'); },',"stepFrame(dt) { model.update(dt); app.render(); },\n      capture() { return canvas.toDataURL('image/png'); },"],
]) {
  if (adapter.split(from).length !== 2) throw new Error('Unsupported Live2D preview adapter; expected V2.9 frame hooks')
  adapter = adapter.replace(from,to)
}
const html = `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:transparent;width:100%;height:100%;overflow:hidden}#stage{width:100vw;height:100vh}canvas{display:block}</style><div id="stage"><canvas id="avatar"></canvas></div><script type="module">
import {createViewer} from '/adapter/runtime.js';
window.videoTime=0;Object.defineProperty(performance,'now',{value:()=>window.videoTime});
window.init=async config=>{
 window.readyInfo=null;
 window.viewer=await createViewer({canvas:document.querySelector('canvas'),modelUrl:config.modelUrl,onReady:info=>window.readyInfo=info});
 if(window.readyInfo.renderer!=='WebGL'||window.readyInfo.maxTextureSize<8192)throw Error('Live2D requires actual WebGL and 8192 texture support');
 viewer.setPointerFollow(false);viewer.setAutoPlay(true);
 if(!await viewer.playMotion(config.motion))throw Error('Motion is not registered: '+config.motion);
 if(!await viewer.setExpression(config.expression))throw Error('Expression is not registered: '+config.expression);
 const params=viewer.getParameters();window.mouth=params.find(p=>p.id==='ParamMouthOpenY');
 if(config.lipSync&&!window.mouth)throw Error('Model has no mouth-open parameter');
 window.frame=(index,level)=>{
  window.videoTime=index*1000/config.fps;
  if(config.lipSync)viewer.setParameter(mouth.id,mouth.default+level*(mouth.max-mouth.default));
  viewer.stepFrame(1000/config.fps);
  return {png:viewer.capture(),parameters:viewer.getState().parameters};
 };
 return {ready:window.readyInfo,counts:viewer.getModelCounts()};
};
</script>`
const server = createServer(async (req,res) => {
  try {
    const path = decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname)
    res.setHeader('Content-Security-Policy', "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval'; connect-src 'self'; img-src 'self' data: blob:; style-src 'unsafe-inline'; worker-src 'self' blob:")
    if (path === '/') {res.setHeader('Content-Type','text/html');res.end(html);return}
    if (path === '/adapter/runtime.js') {res.setHeader('Content-Type','text/javascript');res.end(adapter);return}
    const base = path.startsWith('/adapter/') ? preview : path.startsWith('/model/') ? runtime : null
    if (!base) {res.writeHead(404);res.end();return}
    const file = await inside(base,path.slice(path.indexOf('/',1)+1))
    const types={'.js':'text/javascript','.json':'application/json','.png':'image/png','.wasm':'application/wasm'}
    res.setHeader('Content-Type',types[extname(file)]||'application/octet-stream')
    res.end(await readFile(file))
  } catch {res.writeHead(404);res.end('Local resource unavailable')}
})
let browser
const errors=[]
try {
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)})
  const origin=`http://127.0.0.1:${server.address().port}`
  const options={headless:true,args:['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
  if(request.browserExecutable)options.executablePath=request.browserExecutable
  browser=await chromium.launch(options)
  const context=await browser.newContext({viewport:{width:request.width,height:request.height},deviceScaleFactor:1,permissions:[]})
  await context.route('**/*',route=>route.request().url().startsWith(origin+'/')?route.continue():route.abort())
  const page=await context.newPage()
  page.on('pageerror',error=>errors.push(error.message))
  page.setDefaultTimeout(120000)
  await page.goto(origin)
  await page.waitForFunction(()=>typeof window.init==='function')
  const info=await page.evaluate(config=>window.init(config),{modelUrl:'/model/'+entry.split(sep).at(-1),motion:request.motion||'Idle',expression:request.expression||'Neutral',fps:request.fps,lipSync:request.lipSync!==false})
  const count=request.envelope.length
  await mkdir(request.framesDir,{recursive:false})
  const samples=[]
  const frameHashes=new Set()
  for(let i=0;i<count;i++) {
    const frame=await page.evaluate(({i,level})=>window.frame(i,level),{i,level:request.envelope[i]})
    const png=Buffer.from(frame.png.split(',')[1],'base64')
    frameHashes.add(hash(png))
    await writeFile(join(request.framesDir,`${String(i).padStart(6,'0')}.png`),png)
    if(i%30===0||i===count-1)samples.push({frame:i,mouth:frame.parameters.ParamMouthOpenY})
  }
  if(errors.length)throw Error(errors.join('; '))
  const result={engine:'Live2D Cubism Core / WebGL',modelVersion:release.version,mocSha256:mocHash,atlasSha256:atlasHashes,adapterSha256:hash(await readFile(join(preview,'runtime.js'))),frames:count,fps:request.fps,motion:request.motion||'Idle',expression:request.expression||'Neutral',lipSync:request.lipSync!==false,distinctFrameHashes:frameHashes.size,parameterSamples:samples,browser:browser.version(),coreVersion:info.ready.coreVersion,modelCounts:info.counts,errors}
  await writeFile(request.report,JSON.stringify(result,null,2))
  console.log(JSON.stringify(result))
} finally {
  if(browser)await browser.close()
  await new Promise(resolve=>server.close(resolve))
}
