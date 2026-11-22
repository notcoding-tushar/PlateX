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
