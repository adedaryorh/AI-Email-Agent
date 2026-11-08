import { signal } from '@angular/core';
import { errorMessage } from './api';

export class Page {
  readonly busy = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  async run(action: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.notice.set('');
    try { await action(); } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.busy.set(false); }
  }
}
