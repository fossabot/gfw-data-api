from typing import Any, Dict, List, Optional, Callable, Awaitable
from time import sleep
from datetime import datetime

import boto3

from app.models.pydantic.job import Job

client = boto3.client("batch")

async def execute(jobs: List[Job], callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
    scheduled_jobs = schedule(jobs)

    await poll_jobs(scheduled_jobs.values(), callback)


def schedule(
    jobs: List[Job]
) -> Dict[str, str]:
    """
    Submit multiple batch jobs at once. Submitted batch jobs can depend on each other.
    Dependent jobs need to be listed in `dependent_jobs`
    and must have a `parents` attribute with the parent job names
    """

    scheduled_jobs = dict()

    # first schedule all independent jobs
    for job in jobs:
        if not job.parents:
            scheduled_jobs[job.job_name] = submit_batch_job(job)

    if not scheduled_jobs:
        raise ValueError("No independent jobs in list, can't start scheduling process due to missing dependencies")

    # then retry to schedule all dependent jobs
    # until all parent job are scheduled or max retry is reached
    i = 0

    while len(jobs) != scheduled_jobs:
        for job in jobs:
            if job.job_name not in scheduled_jobs and all([parent in scheduled_jobs for parent in job.parents]):
                depends_on = [
                    {"jobId": scheduled_jobs[parent], "type": "SEQUENTIAL"}
                    for parent in job.parents  # type: ignore
                ]
                scheduled_jobs[job.job_name] = submit_batch_job(job, depends_on)

                scheduled_jobs[job.job_name] = submit_batch_job(job)

        i += 1
        if i > 7:
            raise RecursionError("Too many retries while scheduling jobs. Aboard.")

    return scheduled_jobs


def poll_jobs(job_ids: List[str], callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
    failed_jobs = set()
    completed_jobs = set()
    pending_jobs = set(job_ids)

    while True:
        response = client.describe_jobs(jobs=pending_jobs.difference(completed_jobs))

        for job in response['jobs']:
            if job['status'] == 'COMPLETED':
                callback({
                    "datetime": datetime.now(),
                    "status": "success",
                    "message": f"Successfully completed job {job['jobName']}",
                    "detail": None,
                })
                completed_jobs.add(job['jobId'])
            if job['status'] == 'FAILED':
                callback({
                    "datetime": datetime.now(),
                    "status": "failed",
                    "message": f"Job {job['jobName']} failed during asset creation",
                    "detail": job['statusReason'],
                })
                failed_jobs.add(job['jobId'])

        if completed_jobs == set(job_ids):
            callback({
                "datetime": datetime.now(),
                "status": "success",
                "message": f"Successfully completed all scheduled batch jobs for asset creation",
                "detail": None,
            })
            return True
        elif failed_jobs:
            callback({
                "datetime": datetime.now(),
                "status": "failed",
                "message": f"Job failures occurred during asset creation",
                "detail": None,
            })
            return False

        sleep(30)


def submit_batch_job(
    job: Job, depends_on: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Submit job to AWS Batch
    """

    if depends_on is None:
        depends_on = list()

    response = client.submit_job(
        jobName=job.job_name,
        jobQueue=job.job_queue,
        dependsOn=depends_on,
        jobDefinition=job.job_definition,
        containerOverrides={
            "command": job.command,
            "vcpus": job.vcpus,
            "memory": job.memory,
        },
        retryStrategy={"attempts": job.attempts},
        timeout={"attemptDurationSeconds": job.attempt_duration_seconds},
    )

    return response["jobId"]
