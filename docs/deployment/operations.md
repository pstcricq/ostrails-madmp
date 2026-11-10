# Operations

What running the stack involves once it is up: looking at it, changing it, and what to do when something is off.

## Looking at it

| | Docker Compose | Kubernetes (k3d) |
|---|---|---|
| state | `make docker-ps` | `make k8s-ps`, with the last events |
| every log, last lines | `make docker-logs n=50` | `make k8s-logs n=50` |
| one service, followed | `make docker-logs s=dmp-api` | `make k8s-logs s=dmp-api` |
| the API | `curl http://localhost:8081/health` | `curl http://localhost:8090/health` |

The API logs one line per write, the DMP and what happened, never the document.

## Changing it

| To change | Do | What restarts |
|---|---|---|
| a rules file or a project | a **new version** file, then deploy and `dsw-sync` | `dmp-api`, after `prepare-db` syncs the new definitions |
| the code of madmp | a commit, then deploy the new image | `dmp-api` |
| a variable (an address, a version) | the value, then deploy | the pods that read it |
| a secret | the value, then deploy | the Deployments that read it |
| DS Wizard's version | `DSW_SERVER_VERSION`, `DSW_DOCWORKER_VERSION` and `DSW_CLIENT_VERSION` in `.env.example`, the last patch of each for the same release, then deploy | DS Wizard's three services; its server migrates its database |

Deploying again is always safe: what did not change is left running.

!!! warning "A database password is set once"

    A PostgreSQL the stack runs creates its account at its first start, with the password of that moment. Changing `DMP_PASSWORD` or `DSW_DB_PASSWORD` later changes what the services send, not what the server expects: change it on the server too (`ALTER USER`), or the services cannot connect. `deploy.sh` warns when it sees one change.

## Resetting

| | |
|---|---|
| stop, keep the data | `make docker-down`, `make k8s-down` |
| delete the data | `make docker-reset`, `make k8s-reset`, after a confirmation |
| delete the local cluster | `make k3d-down` |

DS Wizard's demo accounts reopen with a fresh database: run `make dsw-admin` again after a reset. The deploy scripts say so at the end while the demo administrator still logs in.

## When something is off

| Symptom | Likely cause | Look at |
|---|---|---|
| a check refuses a value | a key missing, fixed, unknown, or a malformed line | the message names each key, and each line by its number |
| a Deployment `NOT READY` | the reason follows on the same line | `k8s-ps`, then `k8s-logs s=<service>` |
| the API does not start | a value missing, or a database without a migration | its first log lines name it |
| Submit answers 404 | `SUBMISSION_URL` without its route | it ends in `/templates` |
| Submit answers 401 | the token DS Wizard sends is not `TEMPLATE_WRITE_TOKEN` | run `make dsw-submission` again |
| Submit answers 422 | the plan does not hold up | the message lists every check to fix |
| Submit answers 400 | rules other than the project version's, or an unknown project version | `make store-sync` ran with the definitions of the template? redeploy the image of the same commit |
| a document cannot be downloaded | `S3_URL` does not resolve from the browser | `127.0.0.1 minio` in `/etc/hosts`, locally |
| `dsw-publish` refuses a package | the instance holds that version with another content | raise the project's version |
| `validate-frozen` fails | a published version file was edited | revert it, add a new version |

## Backups

The data worth keeping is in the two PostgreSQL databases and the bucket. The definitions in the DMP database come from git and are synced again at every start; the DMPs exist nowhere else. Back the databases up as any PostgreSQL, with `pg_dump` from the server's container or the target's own backup, and the bucket with the target's S3 tools.
