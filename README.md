<p align="center"><img src="logo_black.png" width="300"></p>

# SSO-Monitor.Me: The First Reproducible and Reliable SSO-Archive for Single Sign-On Landscape and Security Measurements

SSO-Monitor is a web-based Single Sign-On automation framework for monitoring the SSO ecosystem that was developed for the paper
"SoK: SSO-Monitor — The Current State and Future Research Directions in Single Sign-On Security Measurements".
It is designed to continuously iterate over millions of websites to monitor the SSO landscape across the web.
Therefore, it regularly visits websites, determines their login pages, and checks whether they support SSO on their login pages.
You can find more details in the [paper](https://sso-monitor.me/paper.pdf) our on our [companion website](https://sso-monitor.me/).

## 🚀 Quick Start

- Use [Ubuntu 22.04](https://releases.ubuntu.com/jammy/) (or similar)
- Install [Docker](https://docs.docker.com/get-docker/) and [Docker-Compose](https://docs.docker.com/compose/install/)
- Make sure ports `80`, `443`, `5672`, `8080`, `27017`, `8081`, `9000`, `9090`, `6379`, `8082`, and `8888` are free on your host
- Clone this repo: `git clone https://github.com/RUB-NDS/SSO-Monitor.git`
- Go into this directory: `cd ./SSO-Monitor`
- Go to the worker backend directory and run the worker backend
  ```
  cd worker-backend
  conda activate vllm3
  python vllm_backend.py
  ```
- In a new shell run the following (Run classification backnend):
  ```
  cd worker-backend
  conda activate vllm3
  python classify_screenshots_parrallel.py
  ```
- Host images locally in new shell
  ```
  cd worker/modules/loginpagedetection/screenshot_flows
  python -m python -m http.server 8001
  ```
- In a new shell run the vllm serve command for OS-ATLAS:
  ```
  CUDA_VISIBLE_DEVICES=1 vllm serve "OS-Copilot/OS-Atlas-Base-7B" --max-model-len 8192 --gpu-memory-utilization 0.9 --api-key token-abc123 --port 8002
  ```
- In another shell run the Qwen2.5VL for image classification
  ```
  vllm serve "Qwen/Qwen2.5-VL-7B-Instruct" --max-model-len 8192 --gpu-memory-utilization 0.9 --api-key token-abc123
  ```
- Run: `docker-compose build`
- Run: `docker-compose up`
- Open `http://localhost:8080` in your webbrowser for SSO-Monitor's web interface
  - The default username and password is `admin:changeme`
- *Optional:* Open `http://localhost:8081` or `http://localhost:9090` in your webbrowser for a web interface showing SSO-Monitor's database ([mongo-express](https://github.com/mongo-express/mongo-express)) and large file storage ([minio](https://min.io/))

## 🔍 Scanning

- Go to the admin dashboard: `http://localhost:8080/admin`
- Under "Run New Analyses", click on "Landscape" and expand the dropdowns in the newly opened modal
- Enter your domain of choice that you want to scan under "Domain"
  - Note that you can configure more than 40 different scan configuration in this modal, but keeping the default ones should be sufficient for your initial testing purposes
- Click the "Run Analysis" button
- Now, one of the two workers will fetch the task, run the analysis, and make the results visible via the webinterface
  - After some time, visit `http://localhost:8081/db/sso-monitor/landscape_analysis_tres` to see the newly created database entry with the result of the analysis

## 👾 Troubleshoot

To reset SSO-Monitor and clear its database, run the following commands:
- Press `Ctrl+C` and run `docker-compose down` to close and exit the tool
- Remove all volumes: `docker volume rm sso-monitor-2_db sso-monitor-2_jupyter-home sso-monitor-2_minio sso-monitor-2_rabbitmq-mnesia sso-monitor-2_redis-data sso-monitor-2_traefik-acme sso-monitor-2_traefik-logs`
- Start SSO-Monitor: `docker-compose up`

## ⁉️ Questions and Feedback

If you have any questions, suggestions, or feedback, please raise an [issue](https://github.com/RUB-NDS/SSO-Monitor/issues) or contact the authors via [email](https://sso-monitor.me/).

## 📝 Citation

Please use the following citation for the [paper](https://sso-monitor.me//paper.pdf):
```
@inproceedings{
    sso-monitor,
    title={{SoK: SSO-Monitor - The Current State and Future Research Directions in Single Sign-On Security Measurements}},
    author={{Jannett, Louis and Westers, Maximilian and Wich, Tobias and Mainka, Christian and Mayer, Andreas and Mladenov, Vladislav}},
    booktitle={{2024 IEEE 9th European Symposium on Security and Privacy (EuroS&P)}},
    year={2024},
    volume={},
    number={},
    pages={},
    keywords={Single Sign-On;Authentication;Authorization;OAuth;OpenID Connect;Web Archive;SSO Archive},
    doi={TBD}
}
```
