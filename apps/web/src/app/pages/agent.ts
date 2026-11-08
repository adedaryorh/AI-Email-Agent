import { Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { AgentRun } from '../core/models';
import { Page } from '../core/page';
import { Notice } from '../core/ui';
@Component({imports:[DatePipe,DecimalPipe,RouterLink,Notice],template:`
<div class="page-heading"><div><h1>Agent activity</h1><p>Inspect tool calls, outcomes and execution budgets. No hidden reasoning is stored.</p></div><button (click)="load()" [disabled]="busy()">Refresh</button></div><app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
<div class="split-view"><section class="panel list-panel">@for(run of rows();track run.id){<button class="list-item" (click)="select(run.id)" [disabled]="busy()"><strong>Run #{{run.id}} · {{run.status.replaceAll('_',' ')}}</strong><small>{{run.created_at | date:'medium'}} · Message #{{run.message_id}}</small></button>}@empty{<p class="empty">Draft generation creates an execution record here.</p>}<div class="pagination"><button (click)="offset=offset-50;load()" [disabled]="busy() || offset===0">Previous</button><button (click)="offset=offset+50;load()" [disabled]="busy() || rows().length<50">Next</button></div></section>
<section class="panel detail-panel">@if(selected();as run){<h2>Run #{{run.id}}</h2><p>{{run.status}} · {{run.elapsed_ms}} ms · {{run.input_chars}} input characters</p><p class="muted">Character count measures submitted context, not tokens or billed cost.</p><a routerLink="/messages" [queryParams]="{id:run.message_id}">View message</a><ol>@for(event of run.events;track $index){<li><strong>{{event.tool}}</strong><p>{{event.summary}}</p><small>{{event.elapsed_ms}} ms from start @if(event.usage){ · {{event.usage.total_tokens}} provider-reported tokens} @if(event.estimated_cost_usd != null){ · Estimated USD {{event.estimated_cost_usd | number:'1.6-6'}}}</small></li>}</ol>}@else{<p class="empty">Select a run to inspect its execution.</p>}</section></div>`})
export class AgentPage extends Page {
 private readonly api=inject(Api);private readonly route=inject(ActivatedRoute);readonly rows=signal<AgentRun[]>([]);readonly selected=signal<AgentRun|null>(null);offset=0;
 constructor(){super();void this.run(async()=>{this.rows.set(await this.api.agentRuns());const id=Number(this.route.snapshot.queryParamMap.get('id'));if(id>0)this.selected.set(await this.api.agentRun(id));});}
 load(){void this.run(async()=>{this.rows.set(await this.api.agentRuns(this.offset));this.selected.set(null);});}
 select(id:number){void this.run(async()=>this.selected.set(await this.api.agentRun(id)));}
}
