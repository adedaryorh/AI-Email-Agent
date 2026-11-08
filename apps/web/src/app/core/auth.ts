import { Injectable, inject, signal } from '@angular/core';
import { CanActivateFn, CanDeactivateFn, Router } from '@angular/router';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { Api } from './api';
import { User } from './models';

@Injectable({providedIn:'root'})
export class Auth {
  readonly user = signal<User|null>(null);
  private readonly api = inject(Api);
  async restore() { try { this.user.set(await this.api.session()); return true; } catch { this.user.set(null); return false; } }
  async login(username:string, password:string) { this.user.set(await this.api.login(username,password)); }
  async logout() { await this.api.logout(); this.user.set(null); }
}
export const authenticated: CanActivateFn = async () => {
  const auth = inject(Auth), router = inject(Router);
  return await auth.restore() || router.createUrlTree(['/login']);
};
export const sessionErrors: HttpInterceptorFn = (request, next) => {
  const router = inject(Router), auth = inject(Auth);
  return next(request).pipe(catchError((error: unknown) => {
    if (error instanceof HttpErrorResponse && error.status === 401 && !request.url.includes('/auth/')) {
      auth.user.set(null); void router.navigateByUrl('/login');
    }
    return throwError(() => error);
  }));
};

export const unsavedEdits: CanDeactivateFn<{dirty: () => boolean}> = component => {
  return !inject(Auth).user() || !component.dirty() || window.confirm('Discard unsaved edits and leave this page?');
};
