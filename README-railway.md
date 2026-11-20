# Deploying on Railway

`docker-compose.yml` defines two services. On Railway each one becomes its own
service in the same project, built from this repo:

| Compose service | Railway service | Root Directory | Volume                  | Public port |
|-----------------|-----------------|----------------|-------------------------|-------------|
| `garage`        | `garage`        | `/server`      | `garage-data` → `/var/lib/garage` | 3900 (S3) or 3902 (website) |
| `webui`         | `webui`         | `/webui`       | none                    | 3909        |

> Railway's canvas can import a compose file (drag `docker-compose.yml` onto the
> project canvas), but it does not build `build:` contexts from it. Whether you
> import it or not, finish with the steps below so each service builds from its
> own folder and the volume is attached.

## 1. Create the services
1. New Project → **Deploy from GitHub repo** → pick this repo. Rename the service to `garage`.
2. `garage` → Settings → **Root Directory** = `/server` (Railway then picks up `server/railway.toml`).
3. **+ New → GitHub Repo** (same repo) → rename to `webui` → Root Directory = `/webui`.

The service names matter: `webui` reaches Garage at `garage.railway.internal`.

## 2. Attach the permanent volume (garage only)
Right-click the `garage` service → **Attach Volume** → mount path **`/var/lib/garage`**.
Garage's `meta/` and `data/` both live under it, so buckets, keys and the layout
survive redeploys. (Railway allows one volume per service, which is why compose
uses a single volume too.)

CLI alternative: `railway service garage && railway volume add --mount-path /var/lib/garage`

## 3. Variables
**garage**
```
GARAGE_RPC_SECRET   = <openssl rand -hex 32>
GARAGE_ADMIN_TOKEN  = <openssl rand -base64 32>
GARAGE_ACCESS_KEY   = <echo GK$(openssl rand -hex 12)>
GARAGE_SECRET_KEY   = <openssl rand -hex 32>
GARAGE_BUCKET       = ckan
GARAGE_CAPACITY     = 1G          # keep <= volume size
```
**webui** (use Railway reference variables so the token is defined once)
```
PORT             = 3909
API_BASE_URL     = http://${{garage.RAILWAY_PRIVATE_DOMAIN}}:3903
S3_ENDPOINT_URL  = http://${{garage.RAILWAY_PRIVATE_DOMAIN}}:3900
S3_REGION        = garage
API_ADMIN_KEY    = ${{garage.GARAGE_ADMIN_TOKEN}}
AUTH_USER_PASS   = admin:<bcrypt hash from: htpasswd -nbBC 10 admin 'password'>
```

## 4. Networking
- `webui` → Settings → Networking → **Generate Domain**, target port **3909**.
- `garage` → **Generate Domain**, target port **3900** for public S3 access
  (or 3902 for the static-website endpoint; `entrypoint.sh` aliases the bucket to
  `RAILWAY_PUBLIC_DOMAIN`, override with `GARAGE_PUBLIC_DOMAIN`).
- Apps inside the project (e.g. CKAN) should use the private endpoint
  `http://garage.railway.internal:3900`, region `garage`.

## 5. Verify
- `garage` deploy logs end with `[setup] done.`
- Redeploy `garage` once: logs should say `layout already configured` and
  `bucket 'ckan' exists` — proof the volume is persisting.
- Open the webui domain, log in, and the `ckan` bucket is listed.

## Local run
```
cp .env.example .env   # fill in values
docker compose up -d --build
```
