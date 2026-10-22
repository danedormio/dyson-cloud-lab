# Dyson Cloud Laboratory

**Production website:** https://dyson-cloud-lab.onrender.com

**Current public version:** gravity-only JavaScript preview, not the full earlier coupling/capture simulator.

## Next-generation physics foundation — development branch

This branch introduces **REBOUND IAS15**. The Sun, Earth, 1 kg cloud elements and 1 kg incoming elements are all ordinary massive bodies in one REBOUND simulation. The Sun is not fixed. Initial solar-system test conditions are simplified circular Earth conditions, not real ephemerides. Coupling and orbital-capture actuation remain **disabled** pending separate validation.

The new backend is **not connected to the production website yet**. Everything here is a proposed change awaiting approval.

Install and run, from this repository:

```bash
python -m pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

API endpoints: `GET /health`, `GET /api/state`, `POST /api/reset`, `POST /api/launch`, `POST /api/step`.

Checks run in GitHub Actions on a real REBOUND install and a headless Chromium browser:

```bash
python -m pytest tests/test_rebound.py -v
python -m playwright install chromium
python -m pytest tests/test_browser.py -v
```

[Development and approval-gate protocol](DEVELOPMENT.md).

**Scientific caution:** REBOUND integrates Newtonian gravity, but does not validate hypothetical coupling capabilities. Actuation, recoil, energy/momentum transfers, heat, orbital objectives, and coordinated control require independent implementations and tests.
