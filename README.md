# Automatic Body Composition (ABC)
---
[![Github tag](https://badgen.net/github/tag/DMcSweeney/ABC-Toolkit)](https://github.com/DMcSweeney/ABC-Toolkit/tags/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Docs](https://github.com/DMcSweeney/ABC-Toolkit/actions/workflows/pages/pages-build-deployment/badge.svg?branch=master)](https://github.com/DMcSweeney/ABC-Toolkit/actions/workflows/pages/pages-build-deployment)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21511427.svg)](https://doi.org/10.5281/zenodo.21511427)


[**Paper**]()
| [**Getting started**](#getting_started)
| [**Using ABC**](#using_abc)
| [**API Reference**](docs/api-reference.md)
| [**Docs**](https://dmcsweeney.github.io/ABC-Toolkit/)
| [**Contribute**](#contribute)
| [**Citation**](#citation)

The ABC-Toolkit is a web-app for large-scale body composition analyses of CT, MR, and cone-beam CT (CBCT) scans.

A [DICOM server](https://github.com/marcelvanherk/Conquest-DICOM-Server) is built-in so images can be sent directly from clinical PACS and automatically processed.   

See the [full documentation](https://dmcsweeney.github.io/ABC-Toolkit/) for the complete feature list, system architecture, and available segmentation models.

## Requirements
- [Docker](https://www.docker.com/get-started/). [Here](https://docs.docker.com/engine/install/ubuntu/) is a useful guide for Ubuntu.
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). GPU is only needed for vertebral labelling; segmentation is performed by the CPU. To skip vertebral labelling (and the GPU requirement) entirely, don't call `/api/jobs/infer/spine` — pass `slice_number` explicitly to `/api/jobs/infer/segment` instead, which is otherwise looked up from a prior labelling job. See [`slice_number` in the API Reference](docs/api-reference.md#jobs--apijobs).

On Windows, [Windows Subsystem for Linux](https://learn.microsoft.com/en-us/windows/wsl/install) is recommended. This isn't required but ABC hasn't been tested without it and the commands below will be slightly different.

On Linux distributions, you will need to add the current user to the `docker` group with `sudo usermod -a -G docker USERNAME`.

## Getting started
<a name="getting_started"></a>

``` bash
$ git clone git@github.com:DMcSweeney/ABC-toolkit.git && cd ABC-toolkit
$ cp .env-default .env 
$ # EDIT .env; 
$ docker compose up
```

Every variable in `.env` is documented inline in [.env-default](.env-default) — most are fine at their default for local use. The one you're most likely to need to change is `HOST_IP` (defaults to `localhost`, which only works if you're opening the frontend on the same machine running `docker compose`).

Once the stack is up, the frontend is at `https://<HOST_IP>:<FRONTEND_PORT>` (default `https://localhost:5000`) and the API at `https://<HOST_IP>:<BACKEND_PORT>` (default `https://localhost:5001`) — both self-signed HTTPS, so your browser/HTTP client will warn about the certificate (see [ssl/README.md](ssl/README.md)).

## Using ABC
<a name="using_abc"></a>
Tasks are performed by making HTTP requests to pre-specified endpoints. All endpoints have an associated example in the `examples/api` folder, and a full argument-by-argument reference is available in [docs/api-reference.md](docs/api-reference.md).

You can do this whichever way suits you best: through the command-line with tools like `curl`, from python scripts with the [requests library](https://pypi.org/project/requests/), from javascript with [axios](https://axios-http.com/docs/intro) or use a desktop app like [Postman](https://www.postman.com/). Some example python scripts are available in [examples/python/](examples/python/).

If you'd rather not script it, the frontend's **Submit Jobs** page (`/submit_job`) covers the common case directly — either one scan at a time, or a CSV batch (one row per scan; see the CSV format in [docs/api-reference.md](docs/api-reference.md#jobs--apijobs)).

> **Important:** every request that references a scan (`input_path` and similar) must use the path **as seen inside the container**, i.e. starting with `/data/inputs/...` — not the path on your host machine. `INPUT_DIR`/`OUTPUT_DIR` in `.env` control what host folder gets mounted to `/data/inputs`/`/data/outputs`, but requests always address files by their in-container path. For example, if `INPUT_DIR=/home/me/scans` and your scan lives at `/home/me/scans/patient_01`, the `input_path` in your request should be `/data/inputs/patient_01`. See [examples/python/submit_jobs.py](examples/python/submit_jobs.py) for a worked example of this mapping.

## Contribute
<a name="contribute"></a>
Feedback is appreciated, please open a new issue if you have any issues or suggestions. For code modifications, open a new pull request.

