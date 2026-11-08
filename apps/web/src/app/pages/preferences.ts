import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api } from '../core/api';
import { Page } from '../core/page';
import { Notice } from '../core/ui';
@Component({imports:[FormsModule,Notice],template:`
<div class="page-heading"><div><h1>Reply preferences</h1><p>Curate tone, language and corrections yourself. Email instructions never become preferences automatically.</p></div></div><app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
<section class="panel detail-panel"><label>Instructions<textarea class="reply-editor" [(ngModel)]="instructions" maxlength="4000" [disabled]="busy() || !loaded" placeholder="Use a warm, concise tone. Ask for an order number when it is missing."></textarea></label><p>Preferences cannot authorize sending or override verification. Updating them requires existing drafts to be verified again.</p><div class="action-row"><button class="primary" (click)="save()" [disabled]="busy() || !loaded || !dirty()">Save preferences</button><button (click)="clear()" [disabled]="busy() || !loaded">Clear saved preferences</button></div></section>`})
export class PreferencesPage extends Page {
 private readonly api=inject(Api);instructions='';private saved='';private version=0;loaded=false;
 constructor(){super();void this.run(async()=>{const data=await this.api.preferences();this.instructions=this.saved=data.instructions;this.version=data.version;this.loaded=true;});}
 dirty(){return this.instructions!==this.saved;}
 save(){void this.run(async()=>{const data=await this.api.savePreferences({instructions:this.instructions,version:this.version});this.instructions=this.saved=data.instructions;this.version=data.version;this.notice.set('Preferences saved.');});}
 clear(){if(window.confirm('Clear your saved preferences?')){this.instructions='';this.save();}}
}
