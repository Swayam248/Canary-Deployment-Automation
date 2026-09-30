# Progressive Delivery Platform --- Kubernetes Canary Deployment with Argo Rollouts

A hands-on project that demonstrates how to deploy a FastAPI application
on Kubernetes and progressively release a new version using **Argo
Rollouts**. It includes Docker image builds, Kubernetes workloads and
Services, health probes, canary rollout steps, and an unhealthy-release
abort/rollback demonstration.

> **Environment used:** Windows PowerShell, Docker Desktop Kubernetes,
> `kubectl`, and the Argo Rollouts kubectl plugin. The examples use
> local Docker images, so a cloud account or public container registry
> is not required.

## Table of contents

-   [What this project demonstrates](#what-this-project-demonstrates)
-   [Architecture](#architecture)
-   [Prerequisites](#prerequisites)
-   [1. Create the project](#1-create-the-project)
-   [2. Build the FastAPI application](#2-build-the-fastapi-application)
-   [3. Run the application locally](#3-run-the-application-locally)
-   [4. Containerize the application](#4-containerize-the-application)
-   [5. Prepare Kubernetes](#5-prepare-kubernetes)
-   [6. Create a namespace and regular
    Deployment](#6-create-a-namespace-and-regular-deployment)
-   [7. Expose the Pods with a
    Service](#7-expose-the-pods-with-a-service)
-   [8. Install Argo Rollouts](#8-install-argo-rollouts)
-   [9. Install the Argo Rollouts CLI plugin on
    Windows](#9-install-the-argo-rollouts-cli-plugin-on-windows)
-   [10. Replace the Deployment with a
    Rollout](#10-replace-the-deployment-with-a-rollout)
-   [11. Deploy v2 through a canary
    rollout](#11-deploy-v2-through-a-canary-rollout)
-   [12. Access the application](#12-access-the-application)
-   [13. Demonstrate an unhealthy v3 and abort
    it](#13-demonstrate-an-unhealthy-v3-and-abort-it)
-   [14. Return the project files to the healthy v2
    state](#14-return-the-project-files-to-the-healthy-v2-state)
-   [Useful commands](#useful-commands)
-   [Important concepts and
    limitations](#important-concepts-and-limitations)
-   [Interview explanation](#interview-explanation)

## What this project demonstrates

-   Building a small REST API with FastAPI.
-   Running the API with Uvicorn.
-   Packaging the application in a Docker image.
-   Deploying containers to Kubernetes.
-   Using readiness and liveness probes.
-   Exposing Pods through a Kubernetes ClusterIP Service.
-   Defining a canary rollout using Argo Rollouts.
-   Progressing from v1 to v2 and inspecting rollout revisions.
-   Creating a deliberately unhealthy v3 and aborting the rollout to
    preserve the stable v2 revision.

## Architecture

``` text
FastAPI application
       |
       v
Docker image (v1 / v2 / v3)
       |
       v
Kubernetes namespace: canary-demo
       |
       +--> Argo Rollouts controller watches the Rollout resource
       |
       +--> Rollout manages ReplicaSets and application Pods
       |
       +--> ClusterIP Service selects Pods labelled app=canary-app
       |
       +--> readiness/liveness probes call /health
```

**Important:** This local setup uses a standard Kubernetes Service and
replica-based canary progression. Without a traffic router such as an
ingress controller or service mesh integrated with Argo Rollouts,
`setWeight: 25` does **not** guarantee exactly 25% of HTTP requests
reach the canary. It represents the rollout's desired canary weight
through replica scaling in this basic setup.

## Prerequisites

Install or enable:

-   Docker Desktop with Kubernetes enabled.
-   Git.
-   Python 3.12 (or a compatible Python version).
-   Visual Studio Code or another editor.
-   `kubectl`.
-   PowerShell.

You should be able to run:

``` powershell
docker --version
git --version
python --version
kubectl version --client
kubectl get nodes
```

For the local image workflow, Docker Desktop's Kubernetes environment
must be able to access images built locally. This worked in the project
environment used for these steps.

## 1. Create the project

Create this directory structure from the project root:

``` text
Canary-Dep/
├── app/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── rollout.yaml
├── .dockerignore
├── .gitignore
└── README.md
```

In PowerShell, change to your project folder. Example path used during
the walkthrough:

``` powershell
cd C:\Users\Arpan\OneDrive\Desktop\Canary-Dep
```

Create the `app` and `k8s` folders if they do not already exist.

## 2. Build the FastAPI application

Create `app/requirements.txt`:

``` text
fastapi
uvicorn[standard]
```

Create `app/main.py` with the initial **v1** application:

``` python
from fastapi import FastAPI

app = FastAPI()

VERSION = "v1"


@app.get("/")
def root():
    return {
        "message": "Hello from Canary Deployment",
        "version": VERSION
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": VERSION
    }
```

The `/` endpoint returns the application message and version. The
`/health` endpoint is used by Kubernetes readiness and liveness probes.

## 3. Run the application locally

From the project root, create and activate a virtual environment:

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r app\requirements.txt
```

Start the app from the `app` directory:

``` powershell
cd app
uvicorn main:app --reload
```

Open these URLs in a browser:

-   `http://127.0.0.1:8000/`
-   `http://127.0.0.1:8000/health`
-   `http://127.0.0.1:8000/docs`

Stop the local server with `Ctrl+C`, then return to the project root:

``` powershell
cd ..
```

## 4. Containerize the application

Create `app/Dockerfile`:

``` dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build the v1 image from inside the `app` directory:

``` powershell
cd app
docker build -t canary-app:v1 .
docker images canary-app
```

Run it locally:

``` powershell
docker run -dit -p 8000:8000 --name canary-cont canary-app:v1
```

Visit `http://localhost:8000/` and `http://localhost:8000/health`.

Useful container commands:

``` powershell
docker ps
docker logs canary-cont
docker exec -it canary-cont bash
```

If `bash` is unavailable in an image, try `sh` instead:

``` powershell
docker exec -it canary-cont sh
```

Stop and remove the test container when finished, especially before
reusing port 8000:

``` powershell
docker stop canary-cont
docker rm canary-cont
```

Create `.dockerignore` in the project root:

``` text
venv/
__pycache__/
*.pyc
.git/
.gitignore
```

This prevents local development files and Git metadata from being
included in the Docker build context.

Return to the project root if necessary:

``` powershell
cd ..
```

## 5. Prepare Kubernetes

Enable Kubernetes in Docker Desktop and verify the current context and
node:

``` powershell
kubectl config get-contexts
kubectl get nodes
kubectl get pods -A
```

The walkthrough used the `docker-desktop` context. Your context may
differ; make sure you are targeting the intended local cluster before
applying manifests.

## 6. Create a namespace and regular Deployment

Create `k8s/namespace.yaml`:

``` yaml
apiVersion: v1
kind: Namespace
metadata:
  name: canary-demo
```

Apply it from the project root:

``` powershell
kubectl apply -f k8s\namespace.yaml
kubectl get namespaces
```

Create `k8s/deployment.yaml` as an initial example of a standard
Kubernetes Deployment:

``` yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: canary-app
  namespace: canary-demo
spec:
  replicas: 2

  selector:
    matchLabels:
      app: canary-app

  template:
    metadata:
      labels:
        app: canary-app

    spec:
      containers:
        - name: canary-app
          image: canary-app:v1
          imagePullPolicy: IfNotPresent

          ports:
            - containerPort: 8000

          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5

          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
```

Apply and inspect it:

``` powershell
kubectl apply -f k8s\deployment.yaml
kubectl get deployments -n canary-demo
kubectl get pods -n canary-demo
kubectl describe pods -n canary-demo
```

**Readiness probe:** tells Kubernetes whether a Pod is ready to receive
traffic. **Liveness probe:** tells Kubernetes whether the container
should be restarted when its health check continues to fail.

## 7. Expose the Pods with a Service

Create `k8s/service.yaml`:

``` yaml
apiVersion: v1
kind: Service
metadata:
  name: canary-service
  namespace: canary-demo
spec:
  selector:
    app: canary-app

  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000

  type: ClusterIP
```

Apply and verify:

``` powershell
kubectl apply -f k8s\service.yaml
kubectl get services -n canary-demo
kubectl get endpoints -n canary-demo
```

The Service selects Pods with the label `app: canary-app` and provides a
stable in-cluster endpoint. The `port` is the Service port; `targetPort`
is the container port.

Before using Argo Rollouts, delete the standard Deployment so both
controllers do not try to manage the same application labels and
workload:

``` powershell
kubectl delete deployment canary-app -n canary-demo
kubectl get deployments -n canary-demo
```

Keep the Service: it will continue to select application Pods with the
matching label.

## 8. Install Argo Rollouts

Create the controller namespace:

``` powershell
kubectl create namespace argo-rollouts
```

Install the Argo Rollouts controller using the official release
manifest:

``` powershell
kubectl apply --server-side --namespace argo-rollouts --filename https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

Verify the controller is running:

``` powershell
kubectl get deployments -n argo-rollouts
kubectl get pods -n argo-rollouts
```

Argo Rollouts installs a Kubernetes controller and custom resource
definitions. The controller watches `Rollout` resources and manages
their ReplicaSets according to the configured deployment strategy.

## 9. Install the Argo Rollouts CLI plugin on Windows

The plugin adds commands such as `kubectl argo rollouts get rollout`. In
this walkthrough, the Windows AMD64 release executable was downloaded
from the official Argo Rollouts GitHub Releases page and saved as:

``` text
%USERPROFILE%\bin\kubectl-argo-rollouts.exe
```

Add that directory to the current PowerShell session's PATH:

``` powershell
$env:Path += ";$env:USERPROFILE\bin"
kubectl argo rollouts version
```

If `kubectl argo rollouts` reports `unknown command "argo"`, verify that
the executable exists and the directory is on PATH. The command above
only changes the current PowerShell session. To use the command in a new
terminal, add the directory to your user PATH through Windows
Environment Variables or run the PATH command again.

Download the executable only from the official Argo Rollouts release
page: https://github.com/argoproj/argo-rollouts/releases

## 10. Replace the Deployment with a Rollout

Create `k8s/rollout.yaml`:

``` yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout

metadata:
  name: canary-app
  namespace: canary-demo

spec:
  replicas: 4

  selector:
    matchLabels:
      app: canary-app

  template:
    metadata:
      labels:
        app: canary-app

    spec:
      containers:
        - name: canary-app
          image: canary-app:v1
          imagePullPolicy: IfNotPresent

          ports:
            - containerPort: 8000

          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5

          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10

  strategy:
    canary:
      steps:
        - setWeight: 25
        - pause:
            duration: 30s

        - setWeight: 50
        - pause:
            duration: 30s

        - setWeight: 75
        - pause:
            duration: 30s
```

Apply and inspect:

``` powershell
kubectl apply -f k8s\rollout.yaml
kubectl get rollouts -n canary-demo
kubectl argo rollouts get rollout canary-app -n canary-demo
```

To watch the rollout change over time:

``` powershell
kubectl argo rollouts get rollout canary-app -n canary-demo --watch
```

The rollout starts with v1 and four desired replicas. The canary steps
describe progression weights and pauses before moving toward the full
new version.

## 11. Deploy v2 through a canary rollout

Edit `app/main.py` and change only:

``` python
VERSION = "v2"
```

Build the v2 image from the `app` directory:

``` powershell
cd app
docker build -t canary-app:v2 .
docker images canary-app
cd ..
```

Edit `k8s/rollout.yaml` and change the image from:

``` yaml
image: canary-app:v1
```

to:

``` yaml
image: canary-app:v2
```

Apply and watch:

``` powershell
kubectl apply -f k8s\rollout.yaml
kubectl argo rollouts get rollout canary-app -n canary-demo --watch
```

When the rollout finishes, inspect it without watch mode:

``` powershell
kubectl argo rollouts get rollout canary-app -n canary-demo
kubectl get pods -n canary-demo
```

In the successful walkthrough, Argo Rollouts reported the rollout as
`Healthy`, v2 as the stable image, four desired/ready/available
replicas, and the prior v1 ReplicaSet as scaled down.

## 12. Access the application

In a separate PowerShell window, run:

``` powershell
kubectl port-forward svc/canary-service 8080:8000 -n canary-demo
```

Keep that terminal running. Open:

-   `http://localhost:8080/`
-   `http://localhost:8080/health`

The response should show version `v2`. Stop port forwarding with
`Ctrl+C` when finished.

## 13. Demonstrate an unhealthy v3 and abort it

This section intentionally creates an unhealthy version so you can
observe how failed health checks affect a rollout. **Do not use this
deliberately broken endpoint in a real deployment.**

Replace `app/main.py` temporarily with:

``` python
from fastapi import FastAPI, Response

app = FastAPI()

VERSION = "v3"


@app.get("/")
def root():
    return {
        "message": "Hello from Canary Deployment",
        "version": VERSION
    }


@app.get("/health")
def health(response: Response):
    response.status_code = 500
    return {
        "status": "unhealthy",
        "version": VERSION
    }
```

Build v3 from the `app` directory:

``` powershell
cd app
docker build -t canary-app:v3 .
docker images canary-app
cd ..
```

Make sure the Argo Rollouts plugin is available in this terminal. If
needed:

``` powershell
$env:Path += ";$env:USERPROFILE\bin"
```

Edit `k8s/rollout.yaml` to use:

``` yaml
image: canary-app:v3
```

Apply and watch the rollout:

``` powershell
kubectl apply -f k8s\rollout.yaml
kubectl argo rollouts get rollout canary-app -n canary-demo --watch
```

Because `/health` returns HTTP 500, the v3 Pod fails its health probes
and may enter `CrashLoopBackOff` as the liveness probe repeatedly fails.
During the demonstration, the rollout showed v2 as the stable ReplicaSet
and v3 as the canary revision, with the v3 Pod not ready.

Abort the rollout:

``` powershell
kubectl argo rollouts abort canary-app -n canary-demo
kubectl argo rollouts get rollout canary-app -n canary-demo
kubectl get pods -n canary-demo
```

The v2 ReplicaSet remains the stable, healthy version. Argo Rollouts may
still show the overall rollout as `Degraded` because it records the
failed/aborted v3 revision in rollout history. That historical status
does not by itself mean the stable v2 Pods are unhealthy.

## 14. Return the project files to the healthy v2 state

Restore `app/main.py` to the healthy v2 application:

``` python
from fastapi import FastAPI

app = FastAPI()

VERSION = "v2"


@app.get("/")
def root():
    return {
        "message": "Hello from Canary Deployment",
        "version": VERSION
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": VERSION
    }
```

Make sure `k8s/rollout.yaml` uses:

``` yaml
image: canary-app:v2
```

The cluster's stable v2 revision was already healthy after the abort. If
you need to re-apply the v2 manifest after the files are restored, run:

``` powershell
kubectl apply -f k8s\rollout.yaml
kubectl argo rollouts get rollout canary-app -n canary-demo
kubectl get pods -n canary-demo
```

Confirm that the v2 Pods are `Running` and ready, and test
`http://localhost:8080/` if port-forwarding is still active.

## Useful commands

``` powershell
# Cluster and context
kubectl config get-contexts
kubectl get nodes
kubectl get pods -A

# Namespace resources
kubectl get all -n canary-demo
kubectl get deployments -n canary-demo
kubectl get rollouts -n canary-demo
kubectl get pods -n canary-demo
kubectl get services -n canary-demo
kubectl get endpoints -n canary-demo

# Details and logs
kubectl describe pod <pod-name> -n canary-demo
kubectl logs <pod-name> -n canary-demo

# Argo Rollouts
kubectl argo rollouts get rollout canary-app -n canary-demo
kubectl argo rollouts get rollout canary-app -n canary-demo --watch
kubectl argo rollouts abort canary-app -n canary-demo

# Local Docker images
docker images canary-app
```

## Important concepts and limitations

-   **Deployment vs Rollout:** A standard Deployment provides Kubernetes
    rolling updates. An Argo Rollouts `Rollout` supports additional
    strategies such as canary and blue-green.
-   **Controller:** The Argo Rollouts controller watches Rollout
    resources and reconciles the desired state.
-   **ReplicaSet:** A ReplicaSet maintains a requested number of Pods
    for a particular Pod template/revision.
-   **Service selector:** The Service selects Pods through labels, not
    by fixed Pod IP addresses.
-   **Readiness vs liveness:** Readiness controls whether a Pod should
    receive Service traffic; liveness can trigger a container restart
    after repeated failures.
-   **Abort vs rollback:** Aborting stops the current rollout
    progression and keeps the stable revision in service. The rollout
    history may still record the failed revision.
-   **Canary vs blue-green:** Canary introduces a new version
    progressively. Blue-green keeps separate old/new environments and
    switches traffic between them. This project implements canary;
    blue-green is not implemented here.
-   **Traffic percentages:** In this basic local setup, canary weights
    are not precise HTTP request percentages because no traffic router
    or service mesh is configured.
-   **Local images:** The project uses locally built images and is
    intended for a local learning environment. A shared cluster
    typically needs a registry such as Docker Hub, Amazon ECR, or
    another accessible image registry.
-   **Health-check limitation:** The demo uses `/health` as both
    readiness and liveness. A production application may need separate
    checks and more carefully tuned probe thresholds.

## Interview explanation

> I built a Progressive Delivery Platform using FastAPI, Docker,
> Kubernetes, and Argo Rollouts. I containerized a simple API, deployed
> it in Kubernetes, and exposed the Pods through a ClusterIP Service. I
> configured readiness and liveness probes and replaced the standard
> Deployment with an Argo Rollouts Rollout using canary steps. I built
> and deployed v2, watched the rollout progress to a healthy stable
> revision, and then deliberately built an unhealthy v3 whose health
> endpoint returned HTTP 500. The canary Pod failed its health checks,
> so I aborted the rollout and verified that the stable v2 ReplicaSet
> and Pods remained healthy. The project helped me understand rollout
> revisions, ReplicaSets, probes, Services, canary progression, and
> abort/rollback behavior. In this local setup, the weights are
> replica-based rather than exact HTTP request percentages because I did
> not configure a traffic router or service mesh.

## Repository

Suggested GitHub repository name: `Canary-Deployment-Automation` or
`progressive-delivery-platform`.

Once the files are ready, commit and push the project from the project
root:

``` powershell
git status
git add .
git commit -m "Document Kubernetes canary deployment project"
git push
```
