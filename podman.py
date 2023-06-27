from datetime import datetime
from dotenv import dotenv_values
from json import dumps
from kubernetes import client, config
from kubernetes.watch import Watch
from os import getenv, geteuid, path
from sys import argv, exit, stderr

def get_namespace():
    namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    if path.isfile(namespace_path):
        with open(namespace_path, "r") as namespace_file:
            namespace = namespace_file.read().strip()
            return namespace
    else:
        return None


class VolumeMapping:
    def __init__(self, claim_name, mount_path, sub_path=None):
        self.claim_name = claim_name
        self.mount_path = mount_path
        self.sub_path = sub_path

def create_job(namespace, job_name, image, command, env_vars, cpu_limit, memory_limit, cpu_request, memory_request, volume_mappings, run_as_user=None, ttl_seconds_after_finished=None):
    # Inicializa automaticamente o cliente do Kubernetes com base nas informações do ambiente do pod
    config.load_incluster_config()

    # Cria uma instância do cliente do Kubernetes
    batch_v1 = client.BatchV1Api()

    # Define o objeto de especificação do Job
    job = client.V1Job()
    job.api_version = "batch/v1"
    job.kind = "Job"
    job.metadata = client.V1ObjectMeta(name=job_name, namespace=namespace)

    # Define o container no Job
    container = client.V1Container(name="my-container", image=image, command=command)

    # Configura as variáveis de ambiente
    env = [client.V1EnvVar(name=k, value=v) for k, v in env_vars.items()]
    container.env = env

    # Configura os limites e solicitações de CPU e memória
    resources = client.V1ResourceRequirements()
    resources.limits = {"cpu": cpu_limit, "memory": memory_limit}
    resources.requests = {"cpu": cpu_request, "memory": memory_request}
    container.resources = resources

    # Define os volumes e os volume mounts
    volume_mounts = []
    volumes = []

    for volume_mapping in volume_mappings:
        volume_mount = client.V1VolumeMount(
            name=volume_mapping.claim_name,
            mount_path=volume_mapping.mount_path,
            sub_path=volume_mapping.sub_path,
        )
        volume_mounts.append(volume_mount)

        volume = client.V1Volume(
            name=volume_mapping.claim_name,
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=volume_mapping.claim_name
            ),
        )
        volumes.append(volume)

    container.volume_mounts = volume_mounts

    # Define o template do pod
    template = client.V1PodTemplateSpec()
    template.spec = client.V1PodSpec(
        containers=[container],
        volumes=volumes,
        restart_policy="Never",
        security_context=client.V1PodSecurityContext(run_as_user=run_as_user),
    )

    # Define o spec do Job
    job.spec = client.V1JobSpec(template=template, backoff_limit=0, ttl_seconds_after_finished=ttl_seconds_after_finished)

    print(job, file = stderr)

    try:
        # Cria o Job no namespace especificado
        batch_v1.create_namespaced_job(namespace, job)
        print("Job criado com sucesso.", file = stderr)
    except client.ApiException as e:
        print("Erro ao criar o Job: %s" % e, file = stderr)
        return

    # Aguarda a conclusão do Job
    w = Watch()

    try:
        for event in w.stream(batch_v1.list_namespaced_job, namespace=namespace):
            job_event = event['object']
            if job_event.metadata.name == job_name:
                status = job_event.status
                print(status, file = stderr)

                if status.succeeded:
                    print("Job concluído com sucesso.", file = stderr)
                    w.stop()
                elif status.failed:
                    print("Job falhou.", file = stderr)
                    w.stop()
    except Exception as e:
        print("Erro ao acompanhar o Job: %s" % e, file = stderr)



print(argv, file = stderr)

#['/usr/bin/podman.py', 'pull', 'docker://ghcr.io/mergestat/sync-mergestat-explore:latest']
if (len(argv) == 3 and argv[1] == "pull"):
    exit(0)

elif (len(argv) == 4
        and argv[1] == "image"
        and argv[2] == "inspect"):
    image = argv[3]
    result = [
        {
            "Labels": {
                "com.mergestat.sync.clone": "true"
            }            
        }
    ]
    print(dumps(result, indent=4)) 
    exit(0)

#['/usr/bin/podman.py', 'run', '--quiet', '--rm', '--restart', 'on-failure', '--pull', 'never', '--env-file', '/tmp/mergestat-3248512259', '--network', 'host', '-v', '/git/mergestat-repo-45a8cedd-22b4-4fd7-a602-85b2466f361c-3371057527:/mergestat/repo', 'docker://ghcr.io/mergestat/sync-mergestat-explore:latest']
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
    #print(argv[13], file = stderr)
    #print(argv[13].split(":"), file = stderr)
    #print(argv[13].split(":")[0], file = stderr)
    #print(argv[13].split(":")[0][len(git_clone_path) + 1:], file = stderr)

    namespace = get_namespace()
    job_name = "mergestat-" + datetime.now().strftime("%m-%d-%Y-%H-%M-%S-%f")
    image = argv[14][len("docker://"):]
    command = None #["tail", "-f",  "/dev/null"]

    env_vars = dotenv_values(argv[9])
    
    cpu_limit = getenv("CPU_LIMIT", "250m")
    memory_limit = getenv("MEMORY_LIMIT", "256Mi")
    cpu_request = getenv("CPU_REQUEST", "250m")
    memory_request = getenv("MEMORY_REQUEST", "256Mi")

    git_clone_path = getenv("GIT_CLONE_PATH", "/git")

    mergestat_claim_name = getenv("MERGESTAT_CLAIM_NAME", "mergestat-git-pvc")
    mergestat_mount_path = getenv("MERGESTAT_MOUNT_PATH", "/mergestat/repo")
    mergestat_sub_path = argv[13].split(":")[0][len(git_clone_path) + 1:]

    trivy_claim_name = getenv("TRIVY_CLAIM_NAME", "mergestat-trivy-pvc")
    trivy_mount_path = getenv("TRIVY_MOUNT_PATH", "/trivy")

    maven_claim_name = getenv("MAVEN_CLAIM_NAME", "maven-git-pvc")
    maven_mount_path = getenv("MAVEN_MOUNT_PATH", "/maven")

    volume_mappings = [
        VolumeMapping(mergestat_claim_name, mergestat_mount_path, mergestat_sub_path),
        VolumeMapping(trivy_claim_name, trivy_mount_path),
        VolumeMapping(maven_claim_name, maven_mount_path),
    ]

    run_as_user = geteuid()

    ttl_seconds_after_finished = getenv("TTL_SECONDS_AFTER_FINISHED", 1800)

    create_job(namespace, job_name, image, command, env_vars, cpu_limit, memory_limit, cpu_request, memory_request, volume_mappings, run_as_user, ttl_seconds_after_finished)
    exit(0)

else:
    print(f"Unexpected command line: {argv}", file = stderr)
    exit(126)