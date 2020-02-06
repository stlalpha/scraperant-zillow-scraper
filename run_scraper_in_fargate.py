# This script runs the scraper as a task in AWS ECS Fargate, using boto.
import os
import argparse
import boto3

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION_NAME = os.environ.get('AWS_REGION_NAME')

client = boto3.client(
    'ecs',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION_NAME,
)

# This scrapper takes arguments. At least zillow url is required
p = argparse.ArgumentParser()
p.add_argument('--zillow-url', dest='zillow_url', required=True)
p.add_argument('--sample-mode', dest='sample_mode', action='store_true', default=False)


def run_scraper_in_fargate(zillow_url, sample_mode=False):
    docker_cmd = [
        "python",
        "./run_scraper.py",
        "--zillow-url",
        "{}".format(zillow_url)
    ]
    if sample_mode:
        docker_cmd.append("--sample-mode")

    # Call AWS API
    aws_response = client.run_task(
        cluster='zillow-scraper-cluster',
        count=1,
        enableECSManagedTags=False,
        group='family:zillow-scraper-task-definition',
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [
                    'subnet-09d613d49a04cd6fc',
                    'subnet-04917b09c4a29fced',
                ],
                'securityGroups': [
                    'sg-0a8c2a98bf54399d2',
                ],
                'assignPublicIp': 'ENABLED'
            }
        },
        overrides={
            'containerOverrides': [
                {
                    'name': 'zillow-scraper',
                    'command': docker_cmd,
                    'environment': [
                        {
                            "name": "AWS_ACCESS_KEY_ID",
                            "value": os.environ.get("CONTAINER_AWS_ACCESS_KEY_ID")
                        },
                        {
                            "name": "AWS_SECRET_ACCESS_KEY",
                            "value": os.environ.get("CONTAINER_AWS_SECRET_ACCESS_KEY")
                        },
                        {
                            "name": "PROXYCRAWL_TOKEN",
                            "value": os.environ.get("PROXYCRAWL_TOKEN")
                        }
                    ],
                },
            ],
            'executionRoleArn': 'arn:aws:iam::675985711616:role/ecsTaskExecutionRole',
            'taskRoleArn': 'arn:aws:iam::675985711616:role/ecsTaskExecutionRole'
        },
        # Let it use the latest active revision of the task
        taskDefinition='zillow-scraper-task-definition'
    )
    return aws_response


if __name__ == '__main__':
    args = p.parse_args()
    print("[run_scraper_in_fargate.py]> Launching scraper in AWS..")
    response = run_scraper_in_fargate(**vars(args))
    print("[run_scraper_in_fargate.py]> AWS Response:\n{}".format(response))
