// Build with VITE_E2E_TEST_MODE=true, serve that release build, then:
// node scripts/benchmark_ui.mjs http://127.0.0.1:5176 /tmp/ui-before.json
import { chromium } from '../frontend/node_modules/playwright-core/index.mjs'
import { readFile, writeFile } from 'node:fs/promises'
const [url, output] = process.argv.slice(2)
if (!url || !output || new URL(url).hostname !== '127.0.0.1') throw new Error('Pass a loopback mock release URL and output path')
const browser = await chromium.launch({ headless: true })
const results = process.argv.includes('--resume') ? JSON.parse(await readFile(output,'utf8')).results : []
const percentile = (xs, p) => [...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*p)-1]
try {
  for (const size of [100, 1000, 5000]) for (const shape of ['plain', 'mixed', 'group']) {
    if(results.some(row=>row.size===size && row.shape===shape)) continue
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'ru-RU' })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if(message.type()==='error') errors.push(message.text()) })
    await page.addInitScript(()=>{
      window.__longTasks=[]
      new PerformanceObserver(list=>{
        for(const entry of list.getEntries()) if(window.__longTasks.length<5000) window.__longTasks.push(entry.duration)
      }).observe({type:'longtask',buffered:true})
    })
    await page.goto(`${url}/cards?perf=${size}&shape=${shape}`)
    await page.locator('.cards-table__product').getByRole('checkbox').first().waitFor({ timeout: 120000 })
    const nodes = await page.locator('*').count()
    const samples = {}
    async function timed(name, action, warmup) {
      const start = await page.evaluate(() => performance.now())
      await action()
      const end = await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now())))))
      if(!warmup) (samples[name] ??= []).push(end-start)
    }
    for(let i=0; i<35; i++) {
      await timed('selection', () => page.locator('.cards-table__product').getByRole('checkbox').first().click(), i<5)
      await timed('search', () => page.getByRole('textbox', { name: 'Поиск карточек' }).fill(i%2 ? 'Тест' : ''), i<5)
      await timed('sort', () => page.getByRole('columnheader', {name:/^Цена/}).getByRole('button').click(), i<5)
      await timed('grid', () => page.locator('[aria-label="Сетка"]').click(), i<5)
      await timed('list', () => page.locator('[aria-label="Список"]').click(), i<5)
    }
    await page.getByRole('button', {name:'Снять выбор',exact:true}).click().catch(()=>{})
    await page.getByRole('button', {name:'Создать группу',exact:true}).click()
    const dialog=page.getByRole('dialog')
    for(let i=0;i<35;i++) {
      await timed('groupSearch',()=>dialog.getByRole('textbox',{name:'Поиск карточек'}).fill(i%2 ? 'Тест' : ''),i<5)
      await timed('groupSelection',()=>dialog.getByRole('checkbox').first().click(),i<5)
    }
    const memory=await page.evaluate(()=>({usedJSHeapSize:performance.memory?.usedJSHeapSize ?? null,longTasks:window.__longTasks}))
    const row={size,shape,nodes,errors,samples,memory,summary:Object.fromEntries(Object.entries(samples).map(([name,xs])=>[name,{p50:percentile(xs,.5),p95:percentile(xs,.95)}]))}
    results.push(row)
    console.log(JSON.stringify({size,shape,nodes,summary:row.summary,errors}))
    await writeFile(output,JSON.stringify({environment:{url,viewport:[1440,1000],browser:browser.version(),mode:'release mock',warmups:5,samples:30,timing:'Playwright action through two animation frames; includes automation'},results},null,2))
    await page.close()
  }
} finally { await browser.close() }
