#!/usr/bin/env python3
"""raw → 年度归档包（+ MANIFEST.json 更新 + sha256）。

确定性设计（同样输入 → 逐字节同样输出，便于重复构建/校验）：
  - 成员名排序后写入
  - 成员 mtime=0 / uid=0 / gid=0 / uname='' / gname='' / mode=0o666
  - gzip 头 mtime=0、不带文件名

与原 Windows 归档的一致性判据（--verify-old）：成员集 + 逐成员 sha256 全等。
注：原包的 .tar.gz 字节不可复现——gzip 头 mtime 是当年打包时刻，包内无记录。

用法：
  TDX_NODE=/root/slowdata/node python3 make_year_archive.py \
      --stage /root/slowdata/stock-data                 # 打包所有年份 + 更新 MANIFEST
  ... --years 2026 --datasets lhb_raw,block/sse
  ... --out /tmp/packtest --no-manifest                 # 试打包，不改仓库
  ... --verify-old /tmp/packorig                        # 与旧包逐成员对拍
"""
from __future__ import annotations
import os
import argparse
import gzip
import hashlib
import json
import tarfile
import time
from datetime import datetime
from pathlib import Path

NODE = Path(os.environ.get('TDX_NODE') or r'D:\tdx-node').expanduser()

# (archives 里的目录名, raw 源目录(相对 NODE), 包内命名) —— 与 MANIFEST 现有布局逐字对齐
DATASETS = [
    ('block/sse',         'blockmargin/raw/block/sse',         'flat'),
    ('block/szse_list',   'blockmargin/raw/block/szse_list',   'flat'),
    ('block/szse_detail', 'blockmargin/raw/block/szse_detail', 'flat'),
    ('margin/sse',        'blockmargin/raw/margin/sse',        'flat'),
    ('margin/szse',       'blockmargin/raw/margin/szse',       'flat'),
    ('lhb_raw',           'lhb/raw',                           'sub'),
]
DS_BY_NAME = {d[0]: d for d in DATASETS}


def year_files(raw_dir: Path, year: str) -> list[Path]:
    """该 raw 目录下属于 year 的文件（文件名前缀 YYYYMMDD；非规格文件自动排除）。"""
    out = []
    if not raw_dir.is_dir():
        return out
    for p in sorted(raw_dir.rglob('*')):
        if not p.is_file():
            continue
        n = p.name
        if len(n) >= 8 and n[:8].isdigit() and n[:4] == year:
            out.append(p)
    return out


def pack_dataset(raw_dir: Path, out_fp: Path, year: str, mode: str,
                 keep_if_same: bool = True) -> dict:
    """打包一年 → out_fp。

    keep_if_same: 若新包与已存在的旧包**成员集+逐成员 sha256 全等**，则保留旧文件
    （不重写）——保证「内容没变 → git 看不到改动」，每日跑不产生提交噪声，也省一次重压。
    """
    files = year_files(raw_dir, year)
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_fp.with_suffix(out_fp.suffix + '.tmp')
    n = 0
    with tmp.open('wb') as rawfh:
        with gzip.GzipFile(filename='', mode='wb', compresslevel=9,
                           mtime=0, fileobj=rawfh) as gz:
            with tarfile.open(fileobj=gz, mode='w',
                              format=tarfile.PAX_FORMAT) as tf:
                for p in files:
                    arc = p.name if mode == 'flat' else str(
                        p.relative_to(raw_dir))
                    ti = tarfile.TarInfo(name=arc)
                    ti.size = p.stat().st_size
                    ti.mtime = 0
                    ti.mode = 0o666
                    ti.type = tarfile.REGTYPE
                    ti.uid = ti.gid = 0
                    ti.uname = ti.gname = ''
                    with p.open('rb') as fh:
                        tf.addfile(ti, fh)
                    n += 1
    kept = False
    if keep_if_same and out_fp.exists():
        try:
            kept = member_index(tmp) == member_index(out_fp)
        except Exception:                                   # noqa: BLE001
            kept = False
    if kept:
        tmp.unlink()
    else:
        tmp.replace(out_fp)
    days = sorted({p.name[:8] for p in files})
    return {
        'path': f'{out_fp.parent.name}/{out_fp.name}',
        'year': year,
        'files': n,
        'bytes': out_fp.stat().st_size,
        'sha256': sha256_fp(out_fp),
        'date_min': days[0] if days else None,
        'date_max': days[-1] if days else None,
        'kept': kept,
    }


def sha256_fp(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def member_index(fp: Path) -> dict[str, str]:
    """包内 成员名 → 内容 sha256（只算文件成员）。"""
    idx = {}
    with tarfile.open(fp, 'r:gz') as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            h = hashlib.sha256()
            fh = tf.extractfile(m)
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
            idx[m.name] = h.hexdigest()
    return idx


def verify_against(built: Path, old: Path) -> dict:
    if not old.exists():
        return {'old_missing': str(old)}
    b, o = member_index(built), member_index(old)
    miss = sorted(set(o) - set(b))          # 旧有新无 → 丢数据
    extra = sorted(set(b) - set(o))         # 新有旧无 → 新增
    diff = sorted(k for k in (set(b) & set(o)) if b[k] != o[k])
    return {
        'old_files': len(o), 'new_files': len(b),
        'lost': len(miss), 'lost_sample': miss[:5],
        'added': len(extra), 'added_sample': extra[:5],
        'content_diff': len(diff), 'diff_sample': diff[:5],
        'byte_identical': built.read_bytes() == old.read_bytes(),
        'content_identical': not miss and not diff,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='/root/slowdata/stock-data',
                    help='stock-data 仓库根（含 MANIFEST.json）')
    ap.add_argument('--node', default=str(NODE))
    ap.add_argument('--out', default=None, help='输出根，默认=stage')
    ap.add_argument('--years', help='逗号分隔，默认=raw 里出现的所有年份')
    ap.add_argument('--datasets', help='逗号分隔，默认全部')
    ap.add_argument('--no-manifest', action='store_true')
    ap.add_argument('--verify-old', help='旧包根目录，逐成员对拍（不改仓库）')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    node = Path(args.node).expanduser()
    stage = Path(args.stage).expanduser()
    out = Path(args.out).expanduser() if args.out else stage
    man_fp = stage / 'MANIFEST.json'

    datasets = ([DS_BY_NAME[d.strip()] for d in args.datasets.split(',')]
                if args.datasets else DATASETS)

    man = (json.loads(man_fp.read_text(encoding='utf-8'))
           if man_fp.exists() else {'archives': [], 'csv': []})
    entries = {(e['path'], str(e['year'])): e for e in man.get('archives', [])}

    t0 = time.time()
    built, failed = [], []
    for ds_name, raw_rel, mode in datasets:
        raw_dir = node / raw_rel
        if not raw_dir.is_dir():
            print(f'SKIP {ds_name}: raw 目录不存在 {raw_dir}', flush=True)
            continue
        years = ([y.strip() for y in args.years.split(',')] if args.years
                 else sorted({p.name[:4] for p in raw_dir.rglob('*')
                              if p.is_file() and p.name[:8].isdigit()}))
        for year in years:
            base = Path(ds_name).name
            out_fp = out / ds_name / f'{base}_{year}.tar.gz'
            if not year_files(raw_dir, year):
                print(f'SKIP {ds_name} {year}: 无 raw 文件', flush=True)
                continue
            try:
                rec = pack_dataset(raw_dir, out_fp, year, mode)
            except Exception as exc:                       # noqa: BLE001
                failed.append((ds_name, year, repr(exc)))
                print(f'FAIL {ds_name} {year}: {exc!r}', flush=True)
                continue
            rec['path'] = f'{ds_name}/{base}_{year}.tar.gz'
            built.append(rec)
            entries[(rec['path'], year)] = rec
            tag = 'KEEP' if rec.get('kept') else 'PACK'
            msg = (f'{tag} {rec["path"]:34s} files={rec["files"]:6d} '
                   f'{rec["bytes"]/1e6:8.2f}MB {rec["date_min"]}..{rec["date_max"]}')
            print(msg, flush=True)
            if args.verify_old:
                v = verify_against(out_fp, Path(args.verify_old) / rec['path'])
                rec['verify'] = v
                print(f'     VERIFY lost={v.get("lost")} added={v.get("added")} '
                      f'content_diff={v.get("content_diff")} '
                      f'content_identical={v.get("content_identical")} '
                      f'byte_identical={v.get("byte_identical")}', flush=True)

    if built and not args.no_manifest:
        def norm(e: dict) -> dict:
            # kept 只是本次运行标记，不入清单（否则每次跑都刷出假改动）
            return {k: v for k, v in e.items() if k != 'kept'}
        new_entries = [norm(entries[k]) for k in
                       sorted(entries, key=lambda k: (k[0], k[1]))]
        old_entries = [norm(e) for e in man.get('archives', [])]
        if new_entries == old_entries:
            # 档案段逐字段一致 → 保留原文件（含 generated），不产生假提交
            print('MANIFEST unchanged (archives 段逐字段一致，保留原件)', flush=True)
        else:
            man['archives'] = new_entries
            man['generated'] = datetime.now().strftime('%Y-%m-%d')
            tmp = man_fp.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                           encoding='utf-8')
            tmp.replace(man_fp)
            print(f'MANIFEST updated: {man_fp} '
                  f'({len(man["archives"])} archives, '
                  f'generated={man["generated"]})', flush=True)

    print(f'DONE: {len(built)} packs in {time.time()-t0:.1f}s; '
          f'failed={len(failed)}', flush=True)
    for f in failed:
        print('  FAILED:', f)
    return 1 if failed else 0


if __name__ == '__main__':
    import sys
    sys.exit(main())