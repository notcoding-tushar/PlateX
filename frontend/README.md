# PlateX web workbench

On a fresh checkout, install the dependencies from the repository root. Use Python 3.10+ and a Node.js version supported by Vite 7 (20.19+ or 22.12+).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "./backend[api]"
npm ci --prefix frontend
```

On macOS or Linux, use `python3` to create the virtual environment and `.venv/bin/python` to install the backend.

From the repository root, run `npm start`. Open the local URL printed by Vite, usually `http://127.0.0.1:5173`. The launcher uses the repository's `.venv` when present, and Ctrl+C stops both servers.

The development and preview servers forward `/api` to port 8000. FastAPI publishes its OpenAPI explorer at `http://127.0.0.1:8000/docs`.

`npm run build` type-checks the application and creates `dist/`. For production, serve these static assets alongside a reverse proxy for `/api` to FastAPI. The initial plate is the mechanical Zidi reference configuration. Sweep travel translates all contacts along the x axis between the initial and final positions. IRC previews describe unfactored footprints; transferring them retains the current material and supports.

## Pavement and climate inputs

In **IRC Pavement & Bridge**, select a rigid or flexible case, place its traffic contacts, then open **Pavement analysis model** to prepare the model. Flexible catalogue sections require an explicit trial bituminous modulus and a finite subgrade thickness; they approximate a finite bonded plate and do not replace the IRC layered-elastic subgrade strain calculation. On the Plate Solver, **Pavement layers** exposes the resulting stack and its material properties. Layer coordinates must cover the full plate thickness continuously, from `-h/2` to `+h/2`.

The **Elastic foundation** section accepts dimensional Winkler and Pasternak stiffnesses or dimensionless coefficients. IRC rigid preparation offers raw subgrade support or a lumped effective DLC support. Do not represent the same DLC both explicitly and through effective support. **Traffic, vehicle & patch loads** includes contact patches and moving-position sweeps.

## Run the separate IITPAVE program on Windows

Double-click **Run IITPAVE.cmd** in the repository root, or run `& '.\Run IITPAVE.cmd'` in PowerShell. The launcher needs Java on PATH and the locally supplied `external_tools/IRC_37_IITPAVE` distribution, including its `lib` and `IITPAVE` folders. It sets the classpath and working directory needed by the older Java application; it does not install Java or the supplied runtime installer.

In IITPAVE, choose a new pavement section or an existing input file. Enter the layer data, load and tyre pressure, choose the single/dual wheel case, and enter depth/radial analysis points. Submit the values, run the analysis, and view the results in the program. The launcher creates a separate, Git-ignored `external_tools/IITPAVE_work/IITPAVE` working folder for its input and output, leaving the packaged examples in place. IITPAVE reuses its `IITPAVE.IN` and `IITPAVE.out` filenames, so save copies of results you want to retain before running another case. Do not run multiple IITPAVE instances using this shared working folder at the same time.

For prerequisites only, run `& '.\Run IITPAVE.cmd' --check`. The executable and its results are a separate legacy tool; see [IITPAVE comparison report](../IITPAVE%20comparison%20report.md) for model differences and the interface-response concern observed in one test.

For rigid pavements, **Climatic variation** shows the IRC:58-2015 Table 1 region descriptions, including state, hill and coastal qualifications. Enter the site and choose the applicable zone; the software does not infer a zone from a state name. Choose day or night and, if desired, bounded interpolation. Table values are maximum top-to-bottom differences, not an absolute temperature or a time-series weather forecast. The supplied linear through-depth profile approximates a daytime distribution which is nonlinear; permanent curl is not included. Use site-specific data where available. For a project-defined temperature profile, use **Thermal & moisture** on the Plate Solver, where the coefficients and in-plane distribution are explicit. The IRC differential is not automatically applied across an explicit multilayer stack.
