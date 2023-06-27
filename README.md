# Proof of concept

This repository contains the artifacts required to build an alternate MergeStat worker container image. When using this image, MergeStat will execute its sync containers by creating Jobs through the Kubernetes API instead of using Podman. This can be useful for two reasons:

- In many corporate Kubernetes installations, there are policies that prevent executing privileged containers;
- It can improve scalability.

The main idea is quite simple:

- our image inherits from `mergestat/worker:sha-9e60d92`;
- we replace podman´s binary `/usr/bin/podman` for a shell script, thus, when MergeStat executes podman, it is actually executing the shell script;
- The shell script executes a python script, passing to it all command line arguments it received from MergeStat;
- The shell script executes MergeStat sync containers by creating Jobs through the Kubernetes API.

To get all the details, start with the `Dockerfile` file, then the `podman` file and, finally, the `podman.py` file.