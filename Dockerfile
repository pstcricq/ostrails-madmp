# The madmp image, built from this checkout. It serves the DMP API by default,
# and runs any madmp command, `madmp store migrate` and `madmp store sync`
# among them.
#
#   docker build -t madmp .

# The Python of .python-version at its patch, on its Debian release, slim, for
# both stages.
ARG BASE=python:3.12.16-slim-trixie

# The build stage: uv installs the locked environment into /app/.venv, where it
# sits in a checkout.
FROM ${BASE} AS build

RUN pip install --no-cache-dir --root-user-action=ignore uv==0.12.5

# The checkout's own layout, under /app in both stages: definitions/ beside
# src/.
WORKDIR /app

# The dependencies first, from uv.lock alone: this layer is rebuilt only when
# pyproject.toml or uv.lock changes. --locked installs the versions of
# uv.lock, failing when it no longer matches pyproject.toml, --no-dev leaves
# out the dev group, --extra api adds the API and the store.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --extra api --no-install-project

# Then the package itself, installed editable: /app/.venv points at /app/src,
# its README the package's description, its licence and notice beside it.
COPY README.md LICENSE NOTICE ./
COPY src src
COPY definitions definitions
RUN uv sync --locked --no-dev --extra api

FROM ${BASE}
# The environment, the package, the definitions, the licence and the notice,
# at the paths of the build stage, the environment's commands first on the
# PATH.
COPY --from=build /app/LICENSE /app/NOTICE /app/
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/definitions /app/definitions
ENV PATH="/app/.venv/bin:$PATH"
# Commands run from /app, as from the root of a checkout.
WORKDIR /app

RUN useradd --system --no-create-home madmp
USER madmp

EXPOSE 8081
CMD ["madmp", "api", "serve", "--host", "0.0.0.0", "--port", "8081"]
