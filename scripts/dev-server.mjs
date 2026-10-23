// Portable development entry point, also compatible with supervised previews.
// Kumar Waibhav Akshat <kwa.waibhav@gmail.com>
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, delimiter } from 'node:path';

const runtimePython = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
const managedPython = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const python = runtimePython || (existsSync(managedPython) ? managedPython : process.platform === 'win32' ? 'python' : 'python3');
const forwarded = process.argv.slice(2).filter((value) => value !== '--strictPort');
if (!forwarded.includes('--port')) forwarded.push('--port', '4173');
const env = { ...process.env };
// Optional checkout-local dependencies for isolated development containers.
if (existsSync('.preview-deps')) env.PYTHONPATH = [resolve('.preview-deps'), env.PYTHONPATH].filter(Boolean).join(delimiter);
const child = spawn(python, ['scripts/serve.py', ...forwarded], { stdio: 'inherit', env });
child.on('error', (error) => { console.error(error.message); process.exit(1); });
child.on('exit', (code) => process.exit(code ?? 1));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
