# Automatic Body Composition (ABC)
---

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Github Pages](https://img.shields.io/badge/github%20pages-121013?style=for-the-badge&logo=github&logoColor=white)](https://dmcsweeney.github.io/ABC-Toolkit/)

[**Paper**]()
| [**Getting started**](#getting_started)
| [**Using ABC**](#using_abc)
| [**Docs**](https://dmcsweeney.github.io/ABC-Toolkit/)
| [**Contribute**](#contribute)
| [**Citation**](#citation)

The ABC-Toolkit is a web-app for large-scale body composition analyses of CT scans.

A [DICOM server](https://github.com/marcelvanherk/Conquest-DICOM-Server) is built-in so images can be sent directly from clinical PACS and automatically processed.   

An exhaustive list of features is available here.

## Requirements
- [Docker](https://www.docker.com/get-started/). [Here](https://docs.docker.com/engine/install/ubuntu/) is a useful guide for Ubuntu.
- [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). GPU is only needed for vertebral labelling; segmentation is performed by the CPU. Vertebral labelling can be bypassed (see **here**).

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

## Using ABC
<a name="using_abc"></a>
Tasks are performed by making HTTP requests to pre-specified endpoints. All endpoints have an associated example in the `examples/api` folder.

You can do this whichever way suits you best: through the command-line with tools like `curl`, from python scripts with the [requests library](https://pypi.org/project/requests/), from javascript with [axios](https://axios-http.com/docs/intro) or use a desktop app like [Postman](https://www.postman.com/). Some example python scripts are available in `examples/scripts/python`. 

## Contribute
<a name="contribute"></a>
Feedback is appreciated, please open a new issue if you have any issues or suggestions. For code modifications, open a new pull request.

