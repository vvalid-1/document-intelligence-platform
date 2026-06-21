export type DiffType = 'equal' | 'add' | 'remove';

export interface DiffEntry {
  type: DiffType;
  text: string;
}

export interface SideLine {
  type: DiffType | 'empty';
  text: string;
  lineNum: number | null;
}

const MAX_LINES = 3000;

export function diffLines(originalText: string, modifiedText: string): DiffEntry[] {
  const a = originalText.split('\n').slice(0, MAX_LINES);
  const b = modifiedText.split('\n').slice(0, MAX_LINES);
  const m = a.length;
  const n = b.length;

  // LCS DP table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (a[i] === b[j]) {
        dp[i][j] = 1 + dp[i + 1][j + 1];
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Trace back to build diff entries
  const result: DiffEntry[] = [];
  let i = 0;
  let j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && a[i] === b[j]) {
      result.push({ type: 'equal', text: a[i] });
      i++;
      j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({ type: 'add', text: b[j] });
      j++;
    } else {
      result.push({ type: 'remove', text: a[i] });
      i++;
    }
  }
  return result;
}

export function toSideBySide(entries: DiffEntry[]): {
  left: SideLine[];
  right: SideLine[];
} {
  const left: SideLine[] = [];
  const right: SideLine[] = [];
  let leftNum = 1;
  let rightNum = 1;

  for (const entry of entries) {
    if (entry.type === 'equal') {
      left.push({ type: 'equal', text: entry.text, lineNum: leftNum++ });
      right.push({ type: 'equal', text: entry.text, lineNum: rightNum++ });
    } else if (entry.type === 'remove') {
      left.push({ type: 'remove', text: entry.text, lineNum: leftNum++ });
      right.push({ type: 'empty', text: '', lineNum: null });
    } else {
      left.push({ type: 'empty', text: '', lineNum: null });
      right.push({ type: 'add', text: entry.text, lineNum: rightNum++ });
    }
  }
  return { left, right };
}

export function diffStats(entries: DiffEntry[]): { added: number; removed: number; equal: number } {
  let added = 0;
  let removed = 0;
  let equal = 0;
  for (const e of entries) {
    if (e.type === 'add') added++;
    else if (e.type === 'remove') removed++;
    else equal++;
  }
  return { added, removed, equal };
}
