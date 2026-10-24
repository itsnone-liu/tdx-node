#!/usr/bin/env python3
"""米线（Linux）慢频链路每日驱动：采集 → 体检 → 打包 → 本地提交 → 整合 e5。

链路（每一步都打时间戳/行数/PID，留证据）：
  1) 采集  collector/daily_incremental.py --dates <窗口内交易日逗号表> --no-normalize
           COMPLETE 日自动跳过；margin/szse 零行在 7 天内可重试 → 天然补漏
  2) 体检  lhb/backfill_state.json + blockmargin/backfill_state.json → 逐日逐数据集
           COMPLETE / PENDING（未挂）；写 $NODE/last_run_status.json
  3) 打包  make_year_archive.py --stage <stock-data> --years <天数覆盖的年份>
           确定性年包 + MANIFEST（sha256）
  4) 提交  git -C <stock-data> add -A && commit（**仅本地**；push 必须老刘批准）
  5) 整合  stock-selector-v2/scripts/h_slowdata_pull.sh --local
           → MANIFEST 闸门 → rsync data/r2/e5/ → 重建 e5.db（含行数膨胀绊线）

节奏（老刘定）：每日 19:40 主跑（--window 10）；周一 08:00 补「未挂」漏项（--catchup，--window 21）

用法：
  export TDX_NODE=/root/slowdata/node
  python3 daily_slow_linux.py                 # 主跑
  python3 daily_slow_linux.py --catchup       # 周一早补漏
  python3 daily_slow_linux.py --dry-run       # 只打印计划
  python3 daily_slow_linux.py --date 20261023 --window 5 --no-integrate
"""
from __future__ import annotations
import os
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()
STAGE = Path(os.environ.get('SLOWDATA_STAGE', '/root/slowdata/stock-data'))
SSV2 = Path(os.environ.get('SSV2_DIR', '/root/project/workspace/stock-selector-v2'))
PY = os.environ.get('SLOWDATA_PY', '/usr/bin/python3')

DS_KEYS = ['lhb', 'block/sse', 'block/szse', 'margin/sse', 'margin/szse']
# margin/szse 的 day 级键在 state 里前缀是 'margin/szse/'
LHB = NODE / 'lhb'
BM = NODE / 'blockmargin'


def log(msg: str) -> None:
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def load_calendar() -> list[str]:
    days: set[str] = set()
    for fp in (NODE / 'manifests' / 'trading_calendar_2021_2026.json',
               NODE / 'manifests' / 'calendar_prefill_2021.json'):
        if fp.exists():
            days.update(json.loads(fp.read_text(encoding='utf-8')))
    return sorted(days)


def sh(cmd: list[str], what: str, timeout: int) -> tuple[bool, str]:
    """跑子命令并把输出**实时**透到本进程 stdout（systemd 日志可见），返回 (ok, 尾部)。"""
    log(f'>>> {what}')
    t0 = time.time()
    env = {**os.environ, 'TDX_NODE': str(NODE), 'PYTHONUNBUFFERED': '1'}
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1,
                             env=env)
    except Exception as exc:                                # noqa: BLE001
        log(f'<<< {what}: 启动失败 {exc!r}')
        return False, repr(exc)
    tail: list[str] = []
    killed = False
    try:
        assert p.stdout is not None
        for line in p.stdout:
            line = line.rstrip('\n')
            tail.append(line)
            print(line, flush=True)
            if time.time() - t0 > timeout:
                killed = True
                p.kill()
                break
        p.wait(timeout=max(1, timeout - (time.time() - t0)))
    except subprocess.TimeoutExpired:
        killed = True
        p.kill()
    except Exception as exc:                                # noqa: BLE001
        killed = True
        p.kill()
        log(f'<<< {what}: 异常 {exc!r}')
    ok = (p.returncode == 0) and not killed
    log(f'<<< {what}: exit {p.returncode}{" (TIMEOUT)" if killed else ""} '
        f'in {time.time()-t0:.0f}s')
    return ok, '\n'.join(tail[-12:])


# ------------------------------------------------------------------ 体检
def gate(days: list[str]) -> dict:
    """逐日逐数据集判定 COMPLETE / PENDING（未挂）/ FAILED。"""
    lhb_state = json.loads((LHB / 'backfill_state.json').read_text(encoding='utf-8'))
    bm_state = json.loads((BM / 'backfill_state.json').read_text(encoding='utf-8'))
    retry_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    out: dict = {'days': {}, 'pending': [], 'failed': [], 'complete_days': 0,
                 'total_days': len(days)}
    for d in days:
        rec: dict = {}
        r = lhb_state.get(d, {})
        if r.get('status') == 'FAILED':
            rec['lhb'] = 'FAILED'
        elif (r.get('status') == 'COMPLETE'
              and r.get('szse_detail_ok', 0) >= r.get('szse_detail_total', 0)
              and (r.get('sse_main_rows') or r.get('szse_list_rows')
                   or r.get('sse_star_rows'))):
            rec['lhb'] = 'COMPLETE'
        elif not r:
            rec['lhb'] = 'PENDING'
        else:
            rec['lhb'] = r.get('status') or 'PENDING'
        for key in ('block/sse', 'block/szse', 'margin/sse', 'margin/szse'):
            rr = bm_state.get(f'{key}/{d}', {})
            if rr.get('status') == 'FAILED':
                rec[key] = 'FAILED'
            elif rr.get('status') != 'COMPLETE':
                rec[key] = 'PENDING'
            else:
                rows = rr.get('rows')
                sub = rr.get('list_rows')
                zero = (rows == 0) or (sub == 0 and 'list_rows' in rr)
                if zero and d >= retry_cutoff:
                    rec[key] = 'PENDING(空)'      # 发布窗口, 待下轮/周一补
                elif zero:
                    rec[key] = 'COMPLETE(空)'
                else:
                    rec[key] = 'COMPLETE'
        out['days'][d] = rec
        pend = [k for k, v in rec.items() if str(v).startswith('PENDING')]
        fail = [k for k, v in rec.items() if v == 'FAILED']
        if fail:
            out['failed'].append((d, fail))
        if pend:
            out['pending'].append((d, pend))
        elif not fail:
            out['complete_days'] += 1
    return out


def print_gate(g: dict, days: list[str]) -> None:
    print(f'{"day":10s} ' + ' '.join(f'{k:>13s}' for k in DS_KEYS), flush=True)
    for d in days:
        rec = g['days'][d]
        mark = 'OK' if not [k for k, v in rec.items()
                            if str(v).startswith('PENDING') or v == 'FAILED'] else '  '
        print(f'{d:10s} ' + ' '.join(f'{rec[k]:>13s}' for k in DS_KEYS) + f'  {mark}',
              flush=True)


# ------------------------------------------------------------------ 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--catchup', action='store_true',
                    help='周一 08:00 补漏模式（窗口 21 天）')
    ap.add_argument('--date', help='目标交易日 YYYYMMDD，默认=最近交易日')
    ap.add_argument('--window', type=int, default=None,
                    help='回看自然日窗口，默认 10（catchup 21）')
    ap.add_argument('--no-pack', action='store_true')
    ap.add_argument('--no-commit', action='store_true')
    ap.add_argument('--no-integrate', action='store_true')
    ap.add_argument('--force-pack', action='store_true')
    ap.add_argument('--force-integrate', action='store_true',
                    help='整合时强制重建 e5.db（验证用）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    t_start = time.time()
    pid = os.getpid()
    log(f'米线慢频驱动 start pid={pid} NODE={NODE} STAGE={STAGE} '
        f'{"CATCHUP" if args.catchup else "DAILY"}')

    cal = load_calendar()
    if not cal:
        log('FAIL: 无日历清单')
        return 3
    today = datetime.now().strftime('%Y%m%d')
    target = args.date or max((d for d in cal if d <= today), default=None)
    if not target:
        log('FAIL: 日历里没有 <= 今天的交易日')
        return 3
    window = args.window if args.window is not None else (21 if args.catchup else 10)
    lo = (datetime.strptime(target, '%Y%m%d') - timedelta(days=window)).strftime('%Y%m%d')
    days = [d for d in cal if lo <= d <= target]
    years = sorted({d[:4] for d in days})
    log(f'target={target} window={window}d → {len(days)} 个交易日 {days[0]}..{days[-1]}')

    di = NODE / 'collector' / 'daily_incremental.py'
    arch = NODE / 'collector' / 'make_year_archive.py'
    pull = SSV2 / 'scripts' / 'h_slowdata_pull.sh'
    plan = [
        [PY, str(di), '--dates', ','.join(days), '--no-normalize'],
        [PY, str(arch), '--stage', str(STAGE), '--years', ','.join(years)],
        ['bash', str(pull), '--local'] + (['--force'] if args.force_integrate else []),
    ]
    if args.dry_run:
        for p in plan:
            print('DRY:', ' '.join(p), flush=True)
        return 0

    # ---- 1) 采集
    ok_collect, _ = sh(plan[0], f'采集 {len(days)} 日', timeout=3600)

    # ---- 2) 体检
    g = gate(days)
    print('--- 体检 ---', flush=True)
    print_gate(g, days)
    log(f'体检: {g["complete_days"]}/{g["total_days"]} 日全绿; '
        f'PENDING {len(g["pending"])} 日; FAILED {len(g["failed"])} 日')
    status_fp = NODE / 'last_run_status.json'
    status_fp.write_text(json.dumps({
        'ran_at': datetime.now().isoformat(timespec='seconds'),
        'mode': 'catchup' if args.catchup else 'daily',
        'pid': pid, 'target': target, 'window_days': window, 'days': days,
        'target_day_state': g['days'][target],
        'pending': g['pending'], 'failed': g['failed'],
        'complete_days': g['complete_days'], 'total_days': g['total_days'],
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    log(f'status → {status_fp}')

    if not ok_collect:
        log('WARN: 采集子步骤有非零退出（详情见上）；继续走体检+打包，'
            '未完成项留给下一轮/周一补漏')

    # ---- 3) 打包
    ok_pack = True
    if not args.no_pack:
        ok_pack, _ = sh(plan[1], f'打包 {years} 年包 (+MANIFEST)',
                        timeout=1800)

    # ---- 4) 本地提交（push 需批准）
    commit_hash = None
    if not args.no_commit:
        env = {**os.environ, 'HOME': os.environ.get('HOME') or '/root'}
        idc = ['-c', 'user.name=slowdata-bot',
               '-c', 'user.email=slowdata-bot@localhost']
        subprocess.run(['git', '-C', str(STAGE), 'add', '-A'], check=False,
                       capture_output=True, text=True, env=env)
        st = subprocess.run(['git', '-C', str(STAGE), 'status', '--porcelain'],
                            capture_output=True, text=True, env=env)
        n_changed = len([l for l in st.stdout.splitlines() if l.strip()])
        if n_changed:
            r = subprocess.run(['git', '-C', str(STAGE)] + idc + [
                'commit', '-q', '-m',
                f'slowdata auto {target}: lhb+block+margin (米线直采, {len(days)}日窗口)'],
                capture_output=True, text=True, env=env)
            if r.returncode == 0:
                commit_hash = subprocess.run(
                    ['git', '-C', str(STAGE), 'log', '-1', '--format=%h %s'],
                    capture_output=True, text=True, env=env).stdout.strip()
                log(f'本地提交: {commit_hash}（未 push）')
            else:
                log(f'WARN: commit 失败: {r.stderr.strip()[:300]}')
        else:
            log('本地提交: 无变化（年包与上轮一致）')
        log('git 状态: ' + subprocess.run(
            ['git', '-C', str(STAGE), 'status', '-sb'],
            capture_output=True, text=True, env=env).stdout.strip().splitlines()[0])

    # ---- 5) 整合 e5
    ok_integ = True
    if not args.no_integrate:
        ok_integ, _ = sh(plan[2], '整合: 闸门+同步+h_slowdata_pull --local',
                         timeout=3600)

    dt = time.time() - t_start
    log(f'=== SUMMARY mode={"catchup" if args.catchup else "daily"} target={target} '
        f'collect={"OK" if ok_collect else "ERR"} pack={"OK" if ok_pack else "ERR"} '
        f'integrate={"OK" if ok_integ else "ERR"} commit={commit_hash or "-"} '
        f'pending={len(g["pending"])} elapsed={dt:.0f}s ===')
    if g['pending']:
        log('未挂(留待下轮/周一 08:00 补): ' +
            '; '.join(f'{d}:{",".join(k)}' for d, k in g['pending'][:8]))
    return 0 if (ok_collect and ok_pack and ok_integ) else 1


if __name__ == '__main__':
    sys.exit(main())