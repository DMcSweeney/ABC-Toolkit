# Automatic Body Composition (ABC)
---

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/DMcSweeney/ABC-toolkit/format.yml?branch=master)


[**Paper**]()
| [**Requirements**](#requirments)
| [**Getting started**](#getting_started)
| [**Contribute**](#contribute)
| [**Citation**](#citation)

## Requirements
<a name="requirements"></a>
- [Docker](https://www.docker.com/get-started/). For linux, I used this [guide](https://docs.docker.com/engine/install/ubuntu/).
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

On Windows, I recommend installing [Windows Subsystem for Linux](https://learn.microsoft.com/en-us/windows/wsl/install) (WSL). This isn't required but I haven't tested without it and the commands below may be slightly different.

On Linux distributions, you will need to add the current user to the `docker` group with `sudo usermod -a -G docker USERNAME`.

## Getting started
<a name="getting_started"></a>

``` bash
$ git clone git@github.com:DMcSweeney/ABC-toolkit.git && cd bodyComp
$ cp .env-default .env 
$ ## EDIT .env  <---!!
$ mkdir data/inputs data/outputs
$ docker compose up
```

## Using the toolkit
Tasks are performed by making HTTP requests (GET, POST, PUT, DELETE) to pre-specified endpoints. ALl endpoints have an associated example in the `examples` folder. **I need to make better documentation for every endpoint!**

You can do this whichever way suits you best; through the command-line with tools like `curl`, from python scripts with the [requests library](https://pypi.org/project/requests/), from javascript with [axios](https://axios-http.com/docs/intro) or use a desktop app like [Postman](https://www.postman.com/). Some example python scripts are available in `examples/scripts/python`; `submit_jobs.py` is probably the most useful.

Endpoints: All endpoints have an example in the `examples/api`

## Contribute
<a name="contribute"></a>
Feedback is appreciated, please open a new issue if you have any issues or suggestions. For code modifications, open a new pull request.
