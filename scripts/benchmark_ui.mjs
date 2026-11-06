// See docs/guide/TESTING_AND_TROUBLESHOOTING.md for paired mock release commands.
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs'
import { readFile, writeFile } from 'node:fs/promises'
import { cpus, platform, arch } from 'node:os'
import { percentile, budgets } from './benchmark_ui_metrics.mjs'
const [url, output, ...flags] = process.argv.slice(2)
if (!url || !output || new URL(url).hostname !== '127.0.0.1') throw new Error('Pass a loopback mock release URL and output path')
const baselinePath = flags.find(flag => flag.startsWith('--baseline='))?.slice('--baseline='.length)
const baseline = baselinePath ? JSON.parse(await readFile(baselinePath, 'utf8')) : null
const browser = await chromium.launch({ headless: true })
const environment = { url, viewport: [1440, 1000], browser: browser.version(), mode: 'release mock', dataset: 'varied', seed:42,
  platform:platform(),arch:arch(),cpu:cpus()[0]?.model, warmups:5,samples:30,
  timing:'DOM input/click through two animation frames, includes automation; not native WebView' }
if (baseline && ['browser','mode','dataset','seed','platform','arch','cpu','warmups','samples'].some(key => baseline.environment[key] !== environment[key])) {
  await browser.close(); throw new Error('Baseline environment does not match')
}
const results = flags.includes('--resume') ? JSON.parse(await readFile(output,'utf8')).results : []
const columns = ['title','savings','price','minimum','average','marketplace','availability']
try {
  for (const size of [100,1000,5000]) for (const shape of ['plain','mixed','group']) {
    if(results.some(row=>row.size===size && row.shape===shape)) continue
    const page = await browser.newPage({ viewport:{width:1440,height:1000},locale:'ru-RU' })
    const errors=[]
    page.on('pageerror',error=>errors.push(error.message))
    page.on('console',message=>{if(message.type()==='error') errors.push(message.text())})
    await page.addInitScript(()=>{
      window.__longTasks=[]
      new PerformanceObserver(list=>{for(const entry of list.getEntries()) if(window.__longTasks.length<5000) window.__longTasks.push(entry.duration)}).observe({type:'longtask',buffered:true})
    })
    await page.goto(`${url}/cards?perf=${size}&shape=${shape}&dataset=varied`)
    await page.locator('.cards-table__product').first().waitFor({timeout:120000})
    const nodes=await page.locator('*').count(), samples={}
    async function timed(name, action, warmup) {
      const start=await page.evaluate(()=>performance.now())
      await action()
      const end=await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(performance.now())))))
      // New implementation exposes pending deferred results; never time only the input update.
      await page.locator('.cards-page[aria-busy="true"]').waitFor({state:'hidden'})
      const settled=await page.evaluate(()=>performance.now())
      if(!warmup) (samples[name]??=[]).push(Math.max(end,settled)-start)
    }
    const search=page.getByRole('textbox',{name:'Поиск по названию или артикулу'})
    for(let i=0;i<35;i++) {
      for(const [index,key] of columns.entries()) for(const direction of ['asc','desc']) {
        await timed(`sort:${key}:${direction}`,()=>page.locator('thead th').nth(index+1).getByRole('button').evaluate(button=>button.click()),i<5)
        const actual=await page.locator('thead th').nth(index+1).getAttribute('aria-sort')
        if(actual !== (direction==='asc'?'ascending':'descending')) throw new Error(`Wrong sort ${key}: ${actual}`)
      }
      // Keep title sort active during search (change URL through actual UI).
      await page.locator('thead th').nth(1).getByRole('button').evaluate(button=>button.click())
      await timed('search:title',()=>search.fill(i%2?'Тестовый':''),i<5)
      // Restore desc so the next measured title toggle is ascending.
      await page.locator('thead th').nth(1).getByRole('button').evaluate(button=>button.click())
      await timed('selection',()=>page.locator('.cards-table__product').getByRole('checkbox').first().evaluate(button=>button.click()),i<5)
      await timed('grid',()=>page.getByRole('radio',{name:'Сетка',exact:true}).evaluate(button=>button.click()),i<5)
      await timed('list',()=>page.getByRole('radio',{name:'Список',exact:true}).evaluate(button=>button.click()),i<5)
    }
    const clear=page.getByRole('button',{name:'Снять выбор',exact:true})
    if(await clear.isVisible()) await clear.click()
    await page.getByRole('button',{name:'Создать группу',exact:true}).click()
    const dialog=page.getByRole('dialog')
    for(let i=0;i<35;i++) {
      await timed('groupSearch',()=>dialog.getByRole('textbox',{name:'Поиск карточек'}).fill(i%2?'Тестовый':''),i<5)
      await timed('groupSelection',()=>dialog.getByRole('checkbox').first().evaluate(button=>button.click()),i<5)
    }
    await dialog.getByRole('button',{name:'Отмена',exact:true}).click()
    await page.evaluate(()=>window.__pwPerf.progress(0))
    await page.getByRole('complementary',{name:'Состояние обновления цен'}).waitFor()
    for(let i=0;i<35;i++) await timed('progress',()=>page.evaluate(i=>window.__pwPerf.progress(i+1),i),i<5)
    const memory=await page.evaluate(()=>({usedJSHeapSize:performance.memory?.usedJSHeapSize??null,longTasks:window.__longTasks}))
    const summary=Object.fromEntries(Object.entries(samples).map(([name,xs])=>[name,{p50:percentile(xs,.5),p95:percentile(xs,.95)}]))
    const before=baseline?.results.find(row=>row.size===size&&row.shape===shape)
    if(baseline&&!before) throw new Error(`Missing baseline ${size}/${shape}`)
    const checks=budgets(summary,before?.summary)
    const row={size,shape,nodes,errors,samples,memory,summary,checks}
    results.push(row)
    console.log(JSON.stringify({size,shape,maxP95:Math.max(...Object.values(summary).map(x=>x.p95)),failures:Object.entries(checks).filter(([,x])=>!x.passed),errors}))
    await writeFile(output,JSON.stringify({environment,results},null,2))
    await page.close()
  }
} finally {await browser.close()}
if(results.some(row=>row.errors.length||Object.values(row.checks).some(check=>!check.passed))) process.exitCode=1
