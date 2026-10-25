# DA3408 Assignment 4

CPU image captioning and monitoring by Arnav Thorat (DA24B027).

## Run

Use `conda activate aiops` and run these from `assignment4/` in separate terminals:

```bash
python -m streamlit run app.py
```

```bash
../monitoring-setup/tools/node_exporter/node_exporter --web.listen-address=127.0.0.1:9100
```

```bash
../monitoring-setup/tools/prometheus/prometheus --config.file=prometheus.yml --storage.tsdb.path=data/prometheus --storage.tsdb.retention.size=100MB --storage.tsdb.retention.time=1d
```

```bash
../monitoring-setup/tools/alertmanager/alertmanager --config.file=alertmanager.yml --storage.path=data/alertmanager --web.listen-address=127.0.0.1:9093 --cluster.listen-address=
```

Start the existing Grafana container with `docker start grafana`.

- App: http://localhost:8501. Open it once to start the metrics endpoint.
- App metrics: http://localhost:18000/metrics.
- Prometheus targets: http://localhost:9090/targets. All three should be UP.
- Dashboard: http://localhost:3000/d/da3408-a4-captioning.
- Alerts: http://localhost:9093.

Single accepts JPG, PNG and WebP images. Bulk accepts ZIPs and processes images
sequentially, including nested folders. Unsupported files are ignored; unreadable
images and entries over 20 MB are skipped. BLIP runs on CPU with four threads.
The model is cached in memory and inference is serialized across sessions.

## Setup on another machine

Install the Python dependencies:

```bash
conda create -n aiops python=3.12 -y
conda activate aiops
python -m pip install -r requirements.txt
```

If `aiops` already exists, activate it without recreating it. Download the model:

```bash
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('Salesforce/blip-image-captioning-base',
                  revision='82a37760796d32b1411fe092ab5d4e227313294b',
                  local_dir='model',
                  allow_patterns=['*.json', 'vocab.txt', 'pytorch_model.bin'])
PY
```

Model files and monitoring data are excluded from Git. The model occupies about
945 MiB. Obtain Prometheus, Node Exporter and Alertmanager separately if the local
`monitoring-setup` tools are unavailable. The retention flags limit stored blocks;
active data and write-ahead logs use additional space.

## Dashboard

`grafana/dashboard.json` is the saved dashboard export and provisioning file.
The datasource UID is `da3408-a4-prometheus`. Provision the existing container:

```bash
docker exec --user root grafana mkdir -p /var/lib/grafana/dashboards/da3408-a4
docker cp grafana/dashboard.json grafana:/var/lib/grafana/dashboards/da3408-a4/dashboard.json
docker cp grafana/datasource.yml grafana:/etc/grafana/provisioning/datasources/da3408-a4.yml
docker cp grafana/provider.yml grafana:/etc/grafana/provisioning/dashboards/da3408-a4.yml
docker restart grafana
```

The datasource uses host gateway `172.17.0.1`; check the Docker gateway on another
machine and adjust `grafana/datasource.yml`. Reapply provisioning after recreating
the container. UI edits should be exported before changing provisioned files.

The dashboard has six plots and four status/count panels. It covers health,
ZIP size, disk space, throughput, image latency, CPU, active requests, memory,
Summary request duration and session outcomes. The two throughput windows share
one plot: solid lines show one second; long dashed lines show one minute.
Bulk uses orange for one second and purple for one minute; Single uses light blue
and green respectively. Distinct colours and long dashes keep the windows readable.

The dashboard refreshes every five seconds. App scrapes run every 250 ms to support
the one-second throughput graph; system scrapes run every five seconds. Most rate
charts average over one minute. Idle latency charts show gaps, not zero latency.
Short-window throughput is a sampled estimate and can be spiky. Older history
from before the scrape change cannot provide one-second rates.

## Metrics and calculations

| Metric | Type | Meaning |
|---|---|---|
| `caption_requests_total` | Counter | Generate clicks by mode |
| `caption_images_total` | Counter | Attempts by mode, session and outcome |
| `caption_request_failures_total` | Counter | Exceptions aborting a request |
| `caption_active_requests` | Gauge | Loading, waiting or processing requests |
| `caption_process_memory_bytes` | Gauge | Whole app process resident memory |
| `caption_image_seconds` | Histogram | Decoding and caption time, including lock wait |
| `caption_request_seconds` | Summary | Complete request time, including model loading |
| `caption_batch_images` | Histogram | Supported entries per submitted ZIP |

Counters reset on restart. Session IDs identify browser sessions, not people.
Only image counters carry session labels. Invalid ZIPs are rejected before
Generate and do not count as processing requests. Skipped images count as image
failures; a batch that finishes with skips is not a failed request.

For evaluation:

- 10 successful images in 60 seconds gives about 0.167 images/s, even if the batch
  itself took only 10 seconds. `rate` adjusts for resets and scrape boundaries.
- Mean image latency is duration-sum increase divided by image-count increase:
  9 seconds across 3 successful images gives 3 seconds/image.
- Summary exports `_sum` and `_count`, not the brief's `_total`: 15 seconds over
  3 requests gives a 5-second mean. It does not export percentiles.
- Mean CPU idle rate 0.75 gives 25% busy CPU across all cores.
- 6 GiB available out of 24 GiB gives 75% host memory usage.
- 30 supported images across 2 ZIPs gives a mean batch size of 15.

`alerts.yml` fires after 15 seconds of failed app scrapes and clears on recovery.
This checks exporter reachability, not caption quality. Alertmanager displays
alerts locally; no external notification destination is configured.

## Recording

Record about one minute with five-second dashboard refresh. Show health, a Single
caption, then a ZIP batch and the corresponding throughput, latency and CPU/RAM
charts. Use Last 5 minutes and warm up the model before recording.

## Attribution

The course monitoring examples were used as references.
The Streamlit and BLIP code is new. AI-generated PromQL prompts are recorded in
dashboard panel descriptions and the alert-rule comment.

References: [BLIP](https://huggingface.co/docs/transformers/en/model_doc/blip),
[Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching),
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
