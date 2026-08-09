# Cloud Run image for the Custody control plane.
#
# The core imports no SDK, so the runtime dependency set exists only for the
# Memory Bank and ADK integration. It is pinned in requirements.txt for a
# reason recorded there: google-adk and google-cloud-aiplatform disagree about
# opentelemetry, and an unpinned install produces a set pip reports as broken.
# That failure surfaces here, in a build, rather than locally.

FROM python:3.12-slim

# Bytecode writing and output buffering are both wrong in a container: the
# first bloats the layer, the second hides logs when Cloud Run kills a process.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a source change does not invalidate the install layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip check

COPY custody/ ./custody/

# Cloud Run injects $PORT and the process must bind 0.0.0.0. Both are handled
# in control_plane.serve(); this default only matters when running locally.
ENV PORT=8080
EXPOSE 8080

# Not a shell form: exec form makes the server PID 1, so Cloud Run's SIGTERM
# reaches it and the instance shuts down cleanly instead of being killed.
CMD ["python", "-m", "custody.control_plane"]
