import fs from 'node:fs'
import path from 'node:path'
import { chromium, firefox, webkit } from 'playwright'

const APP = process.env.GUI_APP
const BASE = process.env.GUI_BASE_URL || 'http://127.0.0.1:5173'
const API = process.env.GUI_API_BASE_URL || 'http://127.0.0.1:8000'
const OUT = path.resolve(process.env.GUI_ARTIFACT_DIR || `artifacts/dynamic-${APP}`)
fs.mkdirSync(OUT, { recursive: true })
const widths=[320,375,768,1280,1440,1920], engines={chromium,firefox,webkit}, results=[]
let failed=false
const rec=r=>{results.push(r); if(r.status==='FAIL') failed=true}
const missing='__gui_missing_8f13c7__'
const enc=encodeURIComponent

async function json(url, fallback=null){try{const r=await fetch(url); if(!r.ok)return fallback; return await r.json()}catch{return fallback}}

async function resolveAgua(){
  const alerts=await json(`${API}/alerts`,{items:[]}); const alert=(alerts?.items||[])[0]
  const events=await json(`${API}/events`,{items:[]}); const event=(events?.items||[])[0]
  const assets=await json(`${API}/assets`,[]); const asset=(Array.isArray(assets)?assets:assets?.items||[]).find(a=>a?.municipality)
  const alertId=alert?.alert_id||alert?.id
  const eventId=event?.event_id||event?.id
  const municipio=asset?.municipality
  return [
    {name:'alert',positive:alertId?`/alerts/${enc(alertId)}`:null,negative:`/alerts/${missing}`},
    {name:'sector',positive:'/sector/power',negative:`/sector/${missing}`},
    {name:'event',positive:eventId?`/events/${enc(eventId)}`:null,negative:`/events/${missing}`},
    {name:'municipio',positive:municipio?`/municipios/${enc(municipio)}`:null,negative:`/municipios/${missing}`},
  ]
}

async function hrefFrom(page,listPath,prefix){
  await page.goto(BASE+listPath,{waitUntil:'domcontentloaded',timeout:45000}); await page.waitForTimeout(900)
  return await page.locator(`a[href^="${prefix}"]`).first().getAttribute('href').catch(()=>null)
}

async function resolveCentinelas(page){
  return [
    {name:'matter',positive:await hrefFrom(page,'/matters','/matters/'),negative:`/matters/${missing}`},
    {name:'pipeline',positive:await hrefFrom(page,'/pipeline','/pipeline/'),negative:`/pipeline/${missing}`},
    {name:'entity',positive:await hrefFrom(page,'/entidades','/entidad/'),negative:`/entidad/${missing}`},
  ]
}

for(const [engineName,launcher] of Object.entries(engines)){
  const browser=await launcher.launch({headless:true})
  try{
    for(const width of widths){
      const context=await browser.newContext({viewport:{width,height:width<768?844:900}})
      const page=await context.newPage(); const pageErrors=[]; page.on('pageerror',e=>pageErrors.push(String(e)))
      try{
        const specs=APP==='aguayluz-pr'?await resolveAgua():APP==='centinelas-pr'?await resolveCentinelas(page):[]
        if(!specs.length) throw new Error(`Unsupported GUI_APP ${APP}`)
        for(const spec of specs){
          for(const [state,route] of [['positive',spec.positive],['missing',spec.negative]]){
            if(!route){rec({app:APP,engine:engineName,viewport:width,surface:spec.name,state,status:'FAIL',reason:'canonical positive sample unavailable'});continue}
            pageErrors.length=0
            await page.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:45000}); await page.waitForTimeout(900)
            const body=(await page.locator('body').innerText()).trim(); const finalPath=new URL(page.url()).pathname
            const screenshot=`${engineName}-${width}-${spec.name}-${state}.png`; await page.screenshot({path:path.join(OUT,screenshot),fullPage:true})
            rec({app:APP,engine:engineName,viewport:width,surface:spec.name,state,route,final_path:finalPath,status:body.length>0&&pageErrors.length===0?'PASS':'FAIL',body_nonempty:body.length>0,page_errors:[...pageErrors],screenshot})
          }
        }
        if(APP==='centinelas-pr'){
          await page.goto(BASE+'/autores',{waitUntil:'domcontentloaded',timeout:45000}); await page.waitForTimeout(400)
          const finalPath=new URL(page.url()).pathname
          rec({app:APP,engine:engineName,viewport:width,mode:'redirect',from:'/autores',to:'/entidades',final_path:finalPath,status:finalPath==='/entidades'?'PASS':'FAIL'})
        }
      }catch(error){rec({app:APP,engine:engineName,viewport:width,status:'FAIL',error:String(error),page_errors:[...pageErrors]})}
      finally{await context.close()}
    }
  }finally{await browser.close()}
}
const dynamicCount=APP==='aguayluz-pr'?4:APP==='centinelas-pr'?3:0
const expectedDynamic=dynamicCount*2*Object.keys(engines).length*widths.length
const observedDynamic=results.filter(r=>r.surface).length
const expectedRedirect=APP==='centinelas-pr'?Object.keys(engines).length*widths.length:0
const observedRedirect=results.filter(r=>r.mode==='redirect').length
const summary={schema_version:'1.0',app:APP,expected_dynamic_cells:expectedDynamic,observed_dynamic_cells:observedDynamic,expected_redirect_assertions:expectedRedirect,observed_redirect_assertions:observedRedirect,failures:results.filter(r=>r.status==='FAIL').length,results}
fs.writeFileSync(path.join(OUT,'summary.json'),JSON.stringify(summary,null,2)+'\n')
console.log(JSON.stringify({app:APP,expected_dynamic:expectedDynamic,observed_dynamic:observedDynamic,expected_redirect:expectedRedirect,observed_redirect:observedRedirect,failures:summary.failures},null,2))
process.exit(failed||observedDynamic!==expectedDynamic||observedRedirect!==expectedRedirect?1:0)
