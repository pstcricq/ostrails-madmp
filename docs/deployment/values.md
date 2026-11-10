# Values

Every value the repository reads is a key of an example file, with its local value written beside it. A target fills the empty keys; a key with a value is fixed, changed by a commit.

| File | Holds |
|---|---|
| `.env.example` | everything common: the `madmp` commands (database, API, DS Wizard) and what both stacks read |
| `deploy/kubernetes/.env.example` | what only the Kubernetes stack reads: `INGRESS_CLASS`, `DMP_API_URL` |
| `deploy/<target>/.env` | a target's own values, never committed |

**The rule:** a target's keys are those of `.env.example` and of its own `.env.example`. Its `.env` fills the empty ones; without the file, the environment does, which is how a CI or CD job runs. A key in both examples is refused.

```bash
grep -E '^[A-Z][A-Z0-9_]*=$' .env.example > deploy/docker/.env
cat .env.example deploy/kubernetes/.env.example | grep -E '^[A-Z][A-Z0-9_]*=$' > deploy/kubernetes/.env
```

## The keys

| Section | Key | Fixed | Local value |
|---|---|---|---|
| DMP database | `DMP_POSTGRES_VERSION` | `17.5` | |
| | `DMP_HOST`, `DMP_PORT`, `DMP_DB` | | `dmp-postgres`, `5432`, `dmp` |
| | `DMP_USER`, `DMP_PASSWORD` | | `dmp_app`, `openssl rand -hex 24` |
| DMP API | `TEMPLATE_WRITE_TOKEN`, `DMP_READ_TOKEN`, `DMP_WRITE_TOKEN` | | `openssl rand -hex 24` |
| DS Wizard | `DSW_API_URL` | | `http://localhost:3000/wizard-api`, `http://localhost:8090/wizard-api` on k3d |
| | `DSW_USER`, `DSW_PASSWORD` | | `madmp-admin@example.com`, `openssl rand -hex 24` |
| | `SUBMISSION_URL` | | `http://dmp-api:8081/templates` |
| Stack | `STACK_NAME` | | `madmp`: the compose project, or the namespace |
| | `MADMP_IMAGE`, `MADMP_TAG` | | `madmp`, `local` |
| DS Wizard database | `DSW_POSTGRES_VERSION` | `17.5` | |
| | `DSW_DB_HOST`, `DSW_DB_PORT`, `DSW_DB_NAME` | | `dsw-postgres`, `5432`, `engine-wizard` |
| | `DSW_DB_USER`, `DSW_DB_PASSWORD` | | `dsw`, `openssl rand -hex 24` |
| Object storage | `MINIO_VERSION`, `MC_VERSION` | release tags | |
| | `S3_URL` | | `http://minio:9000`, `http://minio:8090` on k3d |
| | `S3_BUCKET`, `S3_USER`, `S3_PASSWORD` | | `engine-wizard`, `minio`, `openssl rand -hex 24` |
| DS Wizard server | `DSW_SERVER_VERSION`, `DSW_DOCWORKER_VERSION`, `DSW_CLIENT_VERSION` | `4.31.3`, `4.31.0`, `4.31.0`, the last patch of each for 4.31 | |
| | `DSW_CLIENT_URL` | | `http://localhost:8080/wizard`, `http://localhost:8090/wizard` on k3d |
| | `GENERAL_SECRET` | | `openssl rand -hex 16`, exactly 32 characters |
| | `GENERAL_RSA_PRIVATE_KEY` | | `openssl genrsa -traditional 4096`, between double quotes |
| Ingress (Kubernetes) | `INGRESS_CLASS` | | `traefik` on k3d, the cluster's controller elsewhere |
| | `DMP_API_URL` | | `http://localhost:8090` on k3d |

A key ending in `_USER`, `_PASSWORD`, `_SECRET`, `_TOKEN` or `_PRIVATE_KEY` is a **secret**: printed as `set`, kept in a Secret on Kubernetes, masked in the CI. Database and S3 accounts go into connection URLs: letters, digits, `-` and `_` only.

## How they are checked

`deploy/scripts/values.sh`, sourced by every check and deploy script, before anything runs:

1. **The `.env` is read, never executed.** `KEY=value` lines, comments and blank lines only; LF line endings; each key once; a value on several lines between double quotes; no space at either end, no single quotes. A wrong line is named by its number, never shown: it may be a secret.
2. **Every empty key filled.** No fixed or unknown key in the `.env`, no fixed key in the environment. With a `.env`, a variable of the same name in the shell is ignored, and said so.
3. **The configuration printed**, under the sections of the examples, every secret as `set`.
4. **Every key exported** for the script that sourced it.

```text
Configuration (.env.example and deploy/kubernetes/.env.example, then deploy/kubernetes/.env)

  DMP database
    DMP_POSTGRES_VERSION        17.5
    DMP_HOST                    dmp-postgres
    DMP_PORT                    5432
    DMP_DB                      dmp
    DMP_USER                    set
    DMP_PASSWORD                set
  …

Checks
  values                        36 keys: 7 fixed, 13 secrets and 16 variables from deploy/kubernetes/.env
  servers                       run by the stack: dmp-database dsw-database storage
```

Every error of a step is reported at once, so a fresh target is fixed in one pass. There is no default value anywhere: a default address is one deployment's address baked into every other.

## For the madmp commands

The `madmp` commands read the same keys from the environment, each only those it needs, and each names every one that is missing. Make adds `ENV_FILE=<file>`, the lines of `.env.example` filled in, read by `uv run --env-file`:

```bash
make dsw-sync ENV_FILE=deploy/kubernetes/.env    # the DS Wizard of the k3d stack
make store-sync ENV_FILE=dmp.env                 # a database reachable from this machine
```

A stack's `.env` names its servers as the stack's containers reach them, `dmp-postgres` for instance, which this machine does not resolve: the `store` commands are run by `prepare-db` inside the stack, the `dsw` commands from outside through the published addresses.
