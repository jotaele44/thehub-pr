import fs from 'node:fs'
import path from 'node:path'
import { chromium, firefox, webkit } from 'playwright'
const APP=process.env.GUI_APP, BASE=process.env.GUI_BASE_URL||'http://127.0.0.1:5173'
const OUT=path.resolve(process.env.GUI_ARTIFACT_DIR||`artifacts/auth-${APP}`); fs.mkdirSync(OUT,{recursive:true})
const routes=['/login','/register','/forgot-password','/reset-password'], widths=[320,375,768,1280,1440,1920], engines={chromium,firefox,webkit}
const results=[]; let failed=false
const rec=r=>{results.push(r); if(r.status==='FAIL') failed=true}
for(const [en,launcher] of Object.entries(engines)){const b=await launcher.launch({headless:true});try{for(const w of widths){const c=await b.newContext({viewport:{width:w,height:w<768?844:900}});const p=await c.newPage();const errs=[];p.on('pageerror',e=>errs.push(String(e)));try{for(const route of routes){errs.length=0;await p.goto(BASE+route,{waitUntil:'domcontentloaded',timeout:45000});await p.waitForTimeout(700);const body=await p.locator('body').innerText();const finalPath=new URL(p.url()).pathname;const file=`${en}-${w}-${route.slice(1)}.png`;await p.screenshot({path:path.join(OUT,file),fullPage:true});rec({app:APP,engine:en,viewport:w,route,final_path:finalPath,status:body.trim()&&finalPath===route&&errs.length===0?'PASS':'FAIL',page_errors:[...errs],screenshot:file})}}catch(e){rec({app:APP,engine:en,viewport:w,status:'FAIL',error:String(e),page_errors:errs})}finally{await c.close()}}}finally{await b.close()}}
const expected=routes.length*widths.length*Object.keys(engines).length, observed=results.filter(r=>r.route).length
const summary={schema_version:'1.0',app:APP,mode:'auth-required',routes,viewports:widths,engines:Object.keys(engines),expected_surface_cells:expected,observed_surface_cells:observed,failures:results.filter(r=>r.status==='FAIL').length,results}
fs.writeFileSync(path.join(OUT,'summary.json'),JSON.stringify(summary,null,2)+'\n');console.log(JSON.stringify({app:APP,expected,observed,failures:summary.failures},null,2));process.exit(failed||observed!==expected?1:0)
