"""Reproduce software validation and plots; never runs USRP hardware graphs.

Usage: python scripts/run_all.py [--matlab /path/to/matlab]
Requires this interpreter's GNU Radio/radioconda and an installed licensed
MATLAB with Communications Toolbox and WLAN Toolbox. No downloads occur.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matlab',default=os.environ.get('MATLAB_BIN') or shutil.which('matlab') or '/Applications/MATLAB_R2026a.app/bin/matlab')
    args=parser.parse_args()
    logs=ROOT/'results/validation'; logs.mkdir(parents=True,exist_ok=True)
    for folder in ('grc','reference','figures'): (ROOT/'results'/folder).mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env.pop('PYTHONPATH',None)
    runs=[]

    def run(label,command):
        print(f'[{label}]',flush=True); started=time.monotonic()
        with (logs/f'{len(runs)+1:02d}_{label}.log').open('w') as output:
            process=subprocess.run(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        record=dict(label=label,command=command,exit_code=process.returncode,elapsed_seconds=time.monotonic()-started)
        runs.append(record)
        if process.returncode:
            raise RuntimeError(f'{label} failed; inspect {output.name}')

    def matlab(label,expression):
        # MATLAB string quoting; paths are data in this argument, never shell code.
        path=str(ROOT/'matlab').replace("'","''")
        run(label,[args.matlab,'-batch',f"addpath('{path}'); {expression}"])

    status='failed'
    try:
        run('installation_check',[sys.executable,'scripts/check_install.py'])
        run('python_reference',[sys.executable,'scripts/run_python_reference.py'])
        matlab('matlab_theory_and_references',
            'validate_wifi_profile; run_theory; validate_python_results; export_wlan_reference; run_wlan_awgn;')
        run('unit_tests',[sys.executable,'-m','unittest','discover','-s','tests','-v'])
        run('build_grc',[sys.executable,'scripts/build_flowgraphs.py'])
        # Use the installed compiler's main directly; avoids a shell/python shebang dependency.
        files=[str(path) for path in sorted((ROOT/'grc').glob('*.grc'))]
        run('compile_grc',[sys.executable,'-c','from gnuradio.grc.compiler import main; main()',
                           '-o',str(ROOT/'grc/generated'),*files])
        run('grc_all_modulations',[sys.executable,'scripts/validate_grc_symbols.py'])
        run('grc_symbol_simulation',[sys.executable,'grc/generated/awgn_symbol_benchmark.py'])
        run('score_grc_symbols',[sys.executable,'scripts/analyze_symbols.py'])
        for rate in range(8):
            run(f'grc_wlan_rate_{rate}',[sys.executable,'grc/generated/wlan_reference_channel.py','--rate-index',str(rate)])
            run(f'python_wlan_rate_{rate}',[sys.executable,'scripts/analyze_wlan.py','--rate-index',str(rate),'--require-complete'])
            run(f'grc_ofdm_fft_rate_{rate}',[sys.executable,'grc/generated/wlan_ofdm_fft.py','--rate-index',str(rate)])
            run(f'validate_grc_fft_rate_{rate}',[sys.executable,'scripts/validate_grc_fft.py','--rate-index',str(rate)])
        matlab('cross_validate_grc',
            f"validate_python_results('{str(ROOT/'results/grc').replace(chr(39),chr(39)*2)}'); "
            'for rate=0:7, analyze_wlan_capture(rate); end')
        run('live_siso_labs',[sys.executable,'scripts/validate_live_labs.py'])
        matlab('live_siso_matlab','validate_live_labs;')
        run('summary_figures',[sys.executable,'scripts/plot_validation.py'])
        run('live_siso_figures',[sys.executable,'scripts/plot_live_results.py'])
        status='passed'
    finally:
        source_files=[p for pattern in ('*.py','*.m','*.grc','*.json','*.md','*.bib','*.toml','*.command','.envrc') for p in ROOT.rglob(pattern)
                      if not any(part in ('results','__pycache__','generated','.venv','.direnv','.git') for part in p.relative_to(ROOT).parts)]
        import numpy, scipy, matplotlib, yaml
        from gnuradio import gr
        manifest=dict(status=status,utc=datetime.now(timezone.utc).isoformat(),
            python=platform.python_version(),platform=platform.platform(),runs=runs,
            software=dict(gnuradio=gr.version(),numpy=numpy.__version__,scipy=scipy.__version__,
                          matplotlib=matplotlib.__version__,pyyaml=yaml.__version__),
            hardware_executed=False,
            limitations=['WLAN receiver checks use known packet timing/rate; no autonomous acquisition validation',
                         'No real RF, calibrated antenna performance, or live steering has been measured',
                         'Coded curves use exploratory packet counts; post-FEC errors are correlated'],
            source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_files)})
        (logs/'status.json').write_text(json.dumps(manifest,indent=2)+'\n')
    subprocess.run([sys.executable,'scripts/generate_report.py'],cwd=ROOT,env=env,check=True)
    print(f'Validation {status}; see {logs / "status.json"}',flush=True)


if __name__=='__main__': main()
