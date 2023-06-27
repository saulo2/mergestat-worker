from datetime import datetime
from dotenv import dotenv_values
from json import dumps
from kubernetes import config, client
from kubernetes.client.rest import ApiException
from os import getenv, geteuid
from sys import argv, exit
from time import sleep

def log(message):
    with open("/tmp/podman.log", "a") as log_file:
        print(message, file = log_file)

def pull():
    # Does nothing. 
    exit(0)

def inspect():
    # Since this script does not pull images, it is not able to inspect them.
    # Thus, it always returns the "com.mergestat.sync.clone" label,
    # forcing MergeStat to clone git repositories, even when it is not necessary.
    result = [
        {
            "Labels": {
                "com.mergestat.sync.clone": "true"
            }            
        }
    ]
    print(dumps(result, indent=4)) 
    exit(0)

class PVCMapping:
    def __init__(self, claim_name, sub_path, mount_path):
        self.claim_name = claim_name
        self.sub_path = sub_path    
        self.mount_path = mount_path

def create_job(backoff_limit,
               command,
               container_name,
               cpu_limit, 
               cpu_request, 
               env,
               image,
               job_name,
               memory_limit, 
               memory_request,
               pvc_mappings,
               restart_policy, 
               run_as_user,
               ttl_seconds_after_finished):
    # Get namespace in which this script is executing
    with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as namespace_file:
        namespace = namespace_file.read()

    # Create a job with the supplied settings
    object_meta = client.V1ObjectMeta(name = job_name)
    env = [client.V1EnvVar(name = name, value = value) for name, value in env.items()]
    limits = {"cpu": cpu_limit, "memory": memory_limit}
    requests = {"cpu": cpu_request, "memory": memory_request}
    resource_requirements = client.V1ResourceRequirements(limits = limits, requests = requests)
    volume_mounts = [client.V1VolumeMount(name = p.claim_name, mount_path = p.mount_path, sub_path = p.sub_path) for p in pvc_mappings]
    container = client.V1Container(command = command, env = env, image = image, name = container_name, resources = resource_requirements, volume_mounts = volume_mounts) 
    pod_security_context = client.V1PodSecurityContext(run_as_user = run_as_user)
    volumes = [client.V1Volume(name = p.claim_name, persistent_volume_claim = client.V1PersistentVolumeClaimVolumeSource(claim_name = p.claim_name)) for p in pvc_mappings]
    pod_spec = client.V1PodSpec(containers = [container], restart_policy = restart_policy, security_context = pod_security_context, volumes = volumes)
    pod_template_spec = client.V1PodTemplateSpec(spec = pod_spec)
    job_spec = client.V1JobSpec(backoff_limit = backoff_limit, template = pod_template_spec, ttl_seconds_after_finished = ttl_seconds_after_finished)
    job = client.V1Job(metadata = object_meta, spec = job_spec)

    config.load_incluster_config()

    batch_api = client.BatchV1Api()
    batch_api.create_namespaced_job(namespace = namespace, body = job)

    # Wait for the job´s end
    while True:
        job = batch_api.read_namespaced_job(namespace = namespace, name = job_name)
        if job.status.failed == 1 or job.status.succeeded == 1:
            break
        else:
            sleep(1)

    # Copy job´s stdout
    core_api = client.CoreV1Api()
    pods = core_api.list_namespaced_pod(namespace = namespace, label_selector = f"job-name={job_name}")
    if pods.items:
        pod_name = pods.items[0].metadata.name
        pod_log = core_api.read_namespaced_pod_log(namespace = namespace, name = pod_name, container = container_name, follow = False)
        print(pod_log)

        # Exit with the same exit code of the job
        pod = core_api.read_namespaced_pod(namespace = namespace, name = pod_name)
        exit_code = pod.status.container_statuses[0].state.terminated.exit_code
        exit(exit_code)

    # Exit anyway
    exit(1)

def run():
    backoff_limit = 0
    command = None
    container_name = "container"
    cpu_limit = getenv("CPU_LIMIT", "250m")
    cpu_request = getenv("CPU_REQUEST", "250m")
    env = dotenv_values(argv[9])
    image = argv[-1][len("docker://"):]
    job_name = "mergestat-" + datetime.now().strftime("%m-%d-%Y-%H-%M-%S-%f")
    memory_limit = getenv("MEMORY_LIMIT", "256Mi")
    memory_request = getenv("MEMORY_REQUEST", "256Mi")

    pvc_mappings = getenv("PVC_MAPPINGS", "")
    pvc_mappings = pvc_mappings.split(",")
    pvc_mappings = [p.split(":") for p in pvc_mappings]
    pvc_mappings = [PVCMapping(claim_name = p[0], sub_path = None, mount_path = p[1]) for p in pvc_mappings]

    if len(argv) == 15:
        claim_name = getenv("GIT_PVC")

        git_clone_path = getenv("GIT_CLONE_PATH")
        git_clone_path_len = len(git_clone_path)
        sub_path = argv[13]
        sub_path = sub_path.split(":")
        sub_path = sub_path[0]
        sub_path = sub_path[git_clone_path_len + 1:]

        pvc_mapping = PVCMapping(claim_name = claim_name, sub_path = sub_path, mount_path = "/mergestat/repo")

        pvc_mappings.append(pvc_mapping)

    restart_policy = "Never"
    run_as_user = geteuid()
    ttl_seconds_after_finished = getenv("TTL_SECONDS_AFTER_FINISHED", 1800)

    create_job(backoff_limit = backoff_limit,
               command = command, 
               container_name = container_name,
               cpu_limit = cpu_limit, 
               cpu_request = cpu_request,
               env = env,
               pvc_mappings = pvc_mappings,
               memory_limit = memory_limit, 
               memory_request = memory_request, 
               image = image, 
               job_name = job_name,
               restart_policy = restart_policy,
               run_as_user = run_as_user, 
               ttl_seconds_after_finished = ttl_seconds_after_finished)               

def unexpected():
    log(f"Unexpected command line: {argv}")
    exit(1)

def main():
    #['/usr/bin/podman.py', 'pull', 'docker://publicaveis-docker.repo.bcnet.bcb.gov.br/dides/nexos-mergestat-maven-bacen:20230627094416935']
    if (len(argv) == 3
            and argv[1] == "pull"):
        pull()

    #['/usr/bin/podman.py', 'image', 'inspect', 'publicaveis-docker.repo.bcnet.bcb.gov.br/dides/nexos-mergestat-maven-bacen:20230627094416935']
    elif (len(argv) == 4
            and argv[1] == "image"
            and argv[2] == "inspect"):
        inspect()

    #['/usr/bin/podman.py', 'run', '--quiet', '--rm', '--restart', 'on-failure', '--pull', 'never', '--env-file', '/tmp/mergestat-798915348', '--network', 'host', 'docker://publicaveis-docker.repo.bcnet.bcb.gov.br/dides/nexos-mergestat-maven-bacen:20230627094416935']
    elif (len(argv) == 13
        and argv[1] == "run"
        and argv[2] == "--quiet"
        and argv[3] == "--rm"
        and argv[4] == "--restart"
        and argv[5] == "on-failure"
        and argv[6] == "--pull"
        and argv[7] == "never"
        and argv[8] == "--env-file"
        and argv[10] == "--network"
        and argv[11] == "host"):
        run()

    #['/usr/bin/podman.py', 'run', '--quiet', '--rm', '--restart', 'on-failure', '--pull', 'never', '--env-file', '/tmp/mergestat-2251375782', '--network', 'host', '-v', '/git/mergestat-repo-9daf4648-b800-4f20-91ab-13a14d6a73d9-115409061:/mergestat/repo', 'docker://publicaveis-docker.repo.bcnet.bcb.gov.br/dides/nexos-mergestat-maven-bacen:20230627094416935']
    elif (len(argv) == 15
        and argv[1] == "run"
        and argv[2] == "--quiet"
        and argv[3] == "--rm"
        and argv[4] == "--restart"
        and argv[5] == "on-failure"
        and argv[6] == "--pull"
        and argv[7] == "never"
        and argv[8] == "--env-file"
        and argv[10] == "--network"
        and argv[11] == "host"
        and argv[12] == "-v"):
        run()

    else:
        unexpected()

main()