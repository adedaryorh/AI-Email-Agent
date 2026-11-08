import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { rmSync } from 'node:fs';
// Controller tests use Angular's real injection/signals in Node, without a browser server.
try {
  await build({entryPoints:['tests/frontend.spec.ts'],bundle:true,platform:'node',format:'esm',packages:'external',tsconfig:'tsconfig.json',outfile:'.test-build/frontend.spec.mjs',logLevel:'warning'});
  const result=spawnSync(process.execPath,['--test','--experimental-test-isolation=none','.test-build/frontend.spec.mjs'],{stdio:'inherit'});
  process.exitCode=result.status ?? 1;
} finally { rmSync('.test-build',{recursive:true,force:true}); }
