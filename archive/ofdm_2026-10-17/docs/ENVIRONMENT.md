# Automatic project environment

This Mac has a Python environment in `/Users/ofi/repos/grc/.venv`. Interactive zsh terminals use `direnv` to activate it when their working directory is this project or a subfolder. Leaving the project restores the previous environment. A new terminal started elsewhere retains its normal environment until you enter this folder.

The venv was created with radioconda's Python and `--system-site-packages`. It shares the existing GNU Radio, UHD, NumPy, SciPy, Qt, and other radioconda dependencies; it is not a fully independent copy of the radio stack. Project-specific Python packages can be installed into `.venv`. Keep `/Users/ofi/radioconda` installed and avoid casually upgrading the shared radio dependencies. The environment folder is ignored by Git and should be recreated rather than copied to another machine.

Live Qt plot testing found a Qwt build linked to Qt6 while this GNU Radio uses PyQt5/Qt5. Qwt was replaced with Qt5 build `qwt=6.3.0=h4ff56cd_0` and pinned in `/Users/ofi/radioconda/conda-meta/pinned`. The installation check now constructs a real Qt sink, beyond testing Python imports. Preserve that compatibility when updating this radio environment.

## Use it

Open a **new terminal**, then run:

```sh
cd /Users/ofi/repos/grc
command -v python
echo "$VIRTUAL_ENV"
python -c 'from gnuradio import gr; print(gr.version())'
```

Expected Python: `/Users/ofi/repos/grc/.venv/bin/python`. Expected `VIRTUAL_ENV`: `/Users/ofi/repos/grc/.venv`. The prompt may still show `(base)` because conda supplies the underlying tools. `direnv` does not change the prompt to show `(.venv)`; check the interpreter path instead.

For a terminal that was already open during setup, run `source ~/.zshrc` once. Automatic activation occurs before the next prompt. VS Code project terminals start in the workspace folder and use the same shell hook. Its default Python interpreter is also set to `.venv/bin/python`; the Python extension's separate terminal activation is disabled to let direnv manage entering/leaving the folder.

Use `python -m pip install PACKAGE` for local Python additions. Run `python scripts/run_all.py` for the full validation and report. `antenna-grc` uses the venv Python and finds native GRC tools in radioconda. The double-click `.command` launcher also prefers the venv.

## Recreate on this Mac

```sh
cd /Users/ofi/repos/grc
/Users/ofi/radioconda/bin/python -m venv --system-site-packages .venv
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
/Users/ofi/radioconda/bin/direnv allow .
```

The interactive zsh hook in `~/.zshrc` uses the absolute radioconda `direnv` path. A timestamped backup of `.zshrc` was saved before adding it. If `.envrc` changes, inspect the change and run `direnv allow` again; unapproved `.envrc` files are not automatically run. On another machine, adjust the radioconda paths in `.envrc` and the shell hook to match that installation.

To disable project activation, run `direnv deny /Users/ofi/repos/grc` and change directory or open a new terminal. The venv remains available manually through `source .venv/bin/activate`.
