const assert = require('node:assert/strict');
const { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { appendRotatingLog } = require('../../dist/electron/backendLogger.js');

test('rotates backend logs and retains only three backups', () => {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'rudra-log-test-'));
  const logPath = path.join(directory, 'backend.log');
  try {
    writeFileSync(logPath, Buffer.alloc(5 * 1024 * 1024, 97));
    writeFileSync(`${logPath}.1`, 'older-one');
    writeFileSync(`${logPath}.2`, 'older-two');
    writeFileSync(`${logPath}.3`, 'oldest');

    appendRotatingLog(logPath, 'new entry');

    assert.equal(readFileSync(logPath, 'utf8'), 'new entry');
    assert.equal(readFileSync(`${logPath}.1`).byteLength, 5 * 1024 * 1024);
    assert.equal(readFileSync(`${logPath}.2`, 'utf8'), 'older-one');
    assert.equal(readFileSync(`${logPath}.3`, 'utf8'), 'older-two');
    assert.equal(existsSync(`${logPath}.4`), false);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('appends without rotating while the active log is below the limit', () => {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'rudra-log-test-'));
  const logPath = path.join(directory, 'backend.log');
  try {
    writeFileSync(logPath, 'existing');
    appendRotatingLog(logPath, ' entry');
    assert.equal(readFileSync(logPath, 'utf8'), 'existing entry');
    assert.equal(existsSync(`${logPath}.1`), false);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
