import '@angular/compiler';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createEnvironmentInjector, runInInjectionContext } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Api, errorMessage } from '../src/app/core/api';
import { Auth } from '../src/app/core/auth';
import { Page } from '../src/app/core/page';
import { Drafts } from '../src/app/pages/drafts';
import { Draft } from '../src/app/core/models';

const original:Draft={id:1,message_id:10,recipient:'reader@example.test',subject:'Re: Help',body:'Original body',version:1,status:'pending',gmail_draft_id:'d1',gmail_message_id:null,created_at:'2026-11-07T00:00:00Z'};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function context(api:unknown) {
  return createEnvironmentInjector([{provide:Api,useValue:api},{provide:ActivatedRoute,useValue:{snapshot:{queryParamMap:new Map()}}}],null!);
}

test('draft edits block approval until saved and use the returned server version',async()=>{
  const calls:unknown[]=[];
  const api={drafts:async()=>[original],edit:async(draft:Draft,body:string)=>{calls.push(['edit',draft.version]);return {...draft,body,version:2,status:'pending'};},draftAction:async(draft:Draft,action:string)=>{calls.push([action,draft.version]);return {...draft,version:3,status:'approved'};}};
  const injector=context(api);
  try {
    const page=runInInjectionContext(injector,()=>new Drafts());await tick();page.select(original);
    page.body='New body';page.action('approve');await tick();assert.equal(calls.length,0);
    page.save();await tick();assert.equal(page.selected()?.version,2);assert.equal(page.dirty(),false);
    page.action('approve');await tick();assert.deepEqual(calls,[['edit',1],['approve',2]]);assert.equal(page.selected()?.status,'approved');
  } finally {injector.destroy();}
});

test('ambiguous send stays blocked and is presented for reconciliation',async()=>{
  const api={drafts:async()=>[],draftAction:async(draft:Draft)=>({...draft,status:'send_unknown'})};
  const injector=context(api);
  try {
    const page=runInInjectionContext(injector,()=>new Drafts());await tick();page.select({...original,status:'approved'});
    page.confirmSend.set(true);page.action('send');await tick();const draft=page.selected()!;
    assert.equal(page.uncertain(draft),true);assert.equal(page.editable(draft),false);assert.equal(page.confirmSend(),false);
    assert.match(page.notice(),/could not be confirmed/);
  } finally {injector.destroy();}
});

test('stale version errors keep local edits and do not advance the draft',async()=>{
  const api={drafts:async()=>[],edit:async()=>{throw new HttpErrorResponse({status:409,error:{detail:'Draft changed; reload before proceeding'}});}};
  const injector=context(api);
  try {
    const page=runInInjectionContext(injector,()=>new Drafts());await tick();page.select(original);page.body='Keep my edits';page.save();await tick();
    assert.equal(page.body,'Keep my edits');assert.equal(page.selected()?.version,1);assert.match(page.error(),/Draft changed/);assert.equal(page.busy(),false);
  } finally {injector.destroy();}
});

test('page operations prevent double submission and recover from failures',async()=>{
  const page=new Page();let release!:()=>void;let calls=0;
  const first=page.run(()=>new Promise<void>(resolve=>{calls++;release=resolve;}));
  await page.run(async()=>{calls++;});assert.equal(calls,1);release();await first;assert.equal(page.busy(),false);
  await page.run(async()=>{throw new Error('Temporary failure');});assert.equal(page.error(),'Temporary failure');assert.equal(page.busy(),false);
});

test('session restore clears an expired identity and logout revokes before clearing it',async()=>{
  let fail=false;let logoutCalled=false;
  const api={session:async()=>{if(fail)throw new Error('expired');return {username:'owner'};},logout:async()=>{logoutCalled=true;}};
  const injector=context(api);
  try {
    const auth=runInInjectionContext(injector,()=>new Auth());assert.equal(await auth.restore(),true);assert.equal(auth.user()?.username,'owner');
    await auth.logout();assert.equal(logoutCalled,true);assert.equal(auth.user(),null);
    await auth.restore();fail=true;assert.equal(await auth.restore(),false);assert.equal(auth.user(),null);
  } finally {injector.destroy();}
});

test('network and validation errors are actionable without rendering server HTML',()=>{
  assert.match(errorMessage(new HttpErrorResponse({status:0})),/Cannot reach/);
  assert.match(errorMessage(new HttpErrorResponse({status:422,error:{detail:[{loc:['body','name'],msg:'Required'}]}})),/name: Required/);
});

import { Knowledge } from '../src/app/pages/knowledge';
import { PreferencesPage } from '../src/app/pages/preferences';
import { AgentPage } from '../src/app/pages/agent';

test('knowledge edits keep local content when the server rejects a stale version',async()=>{
  const doc={id:1,title:'Refunds',content:'Original policy',version:1};
  const injector=context({knowledge:async()=>[doc],saveKnowledge:async()=>{throw new Error('Document changed; reload first');}});
  try {const page=runInInjectionContext(injector,()=>new Knowledge());await tick();page.select(doc);page.content='My edit';page.save();await tick();assert.equal(page.dirty(),true);assert.equal(page.content,'My edit');assert.match(page.error(),/Document changed/);} finally {injector.destroy();}
});

test('preferences update the persisted version and clear dirty state only on success',async()=>{
  let version=0;
  const injector=context({preferences:async()=>({instructions:'',version:0}),savePreferences:async(data:{instructions:string;version:number})=>{version=data.version;return {...data,version:1};}});
  try {const page=runInInjectionContext(injector,()=>new PreferencesPage());await tick();page.instructions='Concise';assert.equal(page.dirty(),true);page.save();await tick();assert.equal(version,0);assert.equal(page.dirty(),false);} finally {injector.destroy();}
});

test('execution timeline loads event details without inventing usage',async()=>{
  const run={id:1,message_id:10,status:'completed',elapsed_ms:20,input_chars:100,created_at:'2026-11-07',events:[{tool:'verify',summary:'Validated',elapsed_ms:20,usage:null}]};
  const injector=context({agentRuns:async()=>[run],agentRun:async()=>run});
  try {const page=runInInjectionContext(injector,()=>new AgentPage());await tick();page.select(1);await tick();assert.equal(page.selected()?.events?.[0].tool,'verify');assert.equal(page.selected()?.events?.[0].usage,null);} finally {injector.destroy();}
});
