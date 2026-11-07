import {
  appendFileSync,
  existsSync,
  renameSync,
  statSync,
  unlinkSync,
} from 'fs';

const MAX_LOG_BYTES = 5 * 1024 * 1024;
const BACKUP_COUNT = 3;

export function appendRotatingLog(logPath: string, data: Buffer | string): void {
  const incomingBytes = Buffer.isBuffer(data) ? data.byteLength : Buffer.byteLength(data);
  if (existsSync(logPath) && statSync(logPath).size + incomingBytes > MAX_LOG_BYTES) {
    const oldestBackup = `${logPath}.${BACKUP_COUNT}`;
    if (existsSync(oldestBackup)) unlinkSync(oldestBackup);

    for (let index = BACKUP_COUNT - 1; index >= 1; index -= 1) {
      const source = `${logPath}.${index}`;
      if (existsSync(source)) renameSync(source, `${logPath}.${index + 1}`);
    }

    renameSync(logPath, `${logPath}.1`);
  }

  appendFileSync(logPath, data);
}
