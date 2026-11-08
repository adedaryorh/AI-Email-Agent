import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Auth } from '../core/auth';
import { Page } from '../core/page';
import { Icon, Notice } from '../core/ui';
@Component({imports:[FormsModule,Icon,Notice],template:`
<div class="login-layout"><section class="login-intro"><div class="brand light"><span class="brand-mark"><app-icon name="mail"/></span>Email Agent</div><div><span class="eyebrow light">ROOM FOR WHAT MATTERS</span><h1>Your inbox.<br>A clearer head.</h1><p>Thoughtful sorting. Helpful drafts.<br>One quiet place to stay in control.</p><div class="login-illustration"><span class="illustration-envelope"><app-icon name="mail"/></span><span class="illustration-check"><app-icon name="check"/></span></div></div><small>AI-assisted. Human-approved.</small></section>
<section class="login-panel"><form (ngSubmit)="submit()" #form="ngForm"><span class="eyebrow">WELCOME BACK</span><h2>Sign in to your workspace</h2><p class="muted">Your messages, reviews and drafts are waiting.</p><app-notice [error]="error()" [busy]="busy()"/><label for="username">Username</label><input id="username" name="username" [(ngModel)]="username" required autocomplete="username" maxlength="100"><label for="password">Password</label><input id="password" name="password" [(ngModel)]="password" required type="password" autocomplete="current-password" maxlength="1024"><button class="primary wide" type="submit" [disabled]="busy() || form.invalid">{{busy()?'Signing in…':'Sign in'}}<app-icon name="arrow"/></button><p class="form-footnote">Use the browser login configured for this workspace.<br>Your Gmail connection is managed after sign-in.</p></form></section></div>`})
export class Login extends Page {
  username=''; password=''; private readonly auth=inject(Auth); private readonly router=inject(Router);
  submit() { void this.run(async()=>{await this.auth.login(this.username,this.password);this.password='';await this.router.navigateByUrl('/overview');}); }
}
