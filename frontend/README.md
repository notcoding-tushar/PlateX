# PlateX pavement analysis workbench

On a fresh checkout, install the dependencies from the repository root. Use Python 3.10+ and a Node.js version supported by Vite 7 (20.19+ or 22.12+).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "./backend[api]"
npm ci --prefix frontend
```

On macOS or Linux, use `python3` to create the virtual environment and `.venv/bin/python` to install the backend.

From the repository root, run `npm start`. Open the local URL printed by Vite, usually `http://127.0.0.1:5173`. The launcher uses the repository's `.venv` when present, and Ctrl+C stops both servers.

The development and preview servers forward `/api` to port 8000. FastAPI publishes its OpenAPI explorer at `http://127.0.0.1:8000/docs`.

For a temporary Windows demo, place the official Cloudflare Windows executable at
`external_tools/cloudflare/cloudflared.exe`, then run `node scripts/share.mjs`
from the repository root. Share the printed `trycloudflare.com` address. Keep
the terminal and this computer running, and press Ctrl+C to stop sharing. The
address is accessible to anyone who has it. The launcher builds the frontend
and runs a local API on port 18573. It requires the project's existing virtual
environment and frontend dependencies.

`npm run build` type-checks the application and creates `dist/`. For production, serve these static assets alongside a reverse proxy for `/api` to FastAPI. The initial plate is the mechanical Zidi reference configuration. Sweep travel translates all contacts along the x axis between the initial and final positions. IRC previews describe unfactored footprints; transferring them retains the current material and supports.

## Pavement and climate inputs

In **IRC Pavement & Bridge → IRC Flexible**, choose **IRC:37 Layered Elastic**.
Select the catalogue section, CBR, traffic, bottom DBM modulus and wheel case,
then select **Run layered analysis**. The results show the signed strain at the
bituminous base and subgrade surface, and horizontal tensile stress and strain
at the base of a CTB where present. The default dual case samples one wheel
centre and the pair midpoint. Wheel load overrides and an additional x/y/depth
query are available in their own sections. Run the CTB fatigue pressure case
separately when that loading is required.

The API accepts the same inputs at `POST /api/irc/flexible/layered-elastic`.
For example, send `{"category":"a","cbr":5,"traffic_msa":10,"bituminous_E_MPa":2000,"wheels":"dual","points":[{"x_m":0,"y_m":0,"depth_m":0.2,"side":"below"}]}`.
The API returns metres, pascals and dimensionless strains. The readout converts
them to mm, kPa and microstrain. Depth and displacement increase downwards.
Stress and strain are positive in tension. Horizontal principal values are the
largest signed eigenvalues in the horizontal plane at each sampled point.
Use **Stack checks & source notes** for the underlying trial-section provisions.

Choose **HOSNT12 Q8 finite plate** for a finite section with edge supports.
Place the contacts and open **Pavement analysis model** to prepare a plate with
an explicit subgrade thickness. On the Pavement Layer Solver, **Pavement layers** shows
the stack from `-h/2` to `+h/2`. Choose **Custom pavement stack** to start from the current isotropic properties. Set the number of layers, then edit each thickness and material from bottom to top. The section thickness updates automatically. Under **IRC Bridge**, Class AA wheeled requires four verified signed wheel-centre offsets in millimetres, entered from left to right.

Drag the surface to rotate, or select **Pan**
to reposition the plot. Contour view supports panning. With the plot focused,
arrow keys move the view, Shift+arrows pan and Home restores the initial view.

The **Elastic foundation** section accepts dimensional Winkler and Pasternak stiffnesses or dimensionless coefficients. IRC rigid preparation offers raw subgrade support or a lumped effective DLC support. Do not represent the same DLC both explicitly and through effective support. **Traffic, vehicle & patch loads** includes contact patches and moving-position sweeps.

## Run the separate IITPAVE program on Windows

Double-click **Run IITPAVE.cmd** in the repository root, or run `& '.\Run IITPAVE.cmd'` in PowerShell. The launcher needs Java on PATH and the locally supplied `external_tools/IRC_37_IITPAVE` distribution, including its `lib` and `IITPAVE` folders. It sets the classpath and working directory needed by the older Java application; it does not install Java or the supplied runtime installer.

In IITPAVE, choose a new pavement section or an existing input file. Enter the layer data, load and tyre pressure, choose the single/dual wheel case, and enter depth/radial analysis points. Submit the values, run the analysis, and view the results in the program. The launcher creates a separate, Git-ignored `external_tools/IITPAVE_work/IITPAVE` working folder for its input and output, leaving the packaged examples in place. IITPAVE reuses its `IITPAVE.IN` and `IITPAVE.out` filenames, so save copies of results you want to retain before running another case. Do not run multiple IITPAVE instances using this shared working folder at the same time.

For prerequisites only, run `& '.\Run IITPAVE.cmd' --check`. The executable and its results are a separate legacy tool; see [IITPAVE comparison report](../IITPAVE%20comparison%20report.md) for model differences and the interface-response concern observed in one test.

For rigid pavements, **Climatic variation** shows the IRC:58-2015 Table 1 region descriptions, including state, hill and coastal qualifications. Enter the site and choose the applicable zone; the software does not infer a zone from a state name. Choose day or night and, if desired, bounded interpolation. Table values are maximum top-to-bottom differences, not an absolute temperature or a time-series weather forecast. The supplied linear through-depth profile approximates a daytime distribution which is nonlinear; permanent curl is not included. Use site-specific data where available. For a project-defined temperature profile, use **Thermal & moisture** on the Pavement Layer Solver, where the coefficients and in-plane distribution are explicit. The IRC differential is not automatically applied across an explicit multilayer stack.
