import boto3
from config import Config

ecs_client = boto3.client('ecs')

def start_ecs_task(client_id):
    response = ecs_client.run_task(
        cluster=Config.ECS_CLUSTER_NAME,
        taskDefinition=Config.ECS_TASK_DEFINITION,
        overrides={
            'containerOverrides': [
                {
                    'name': Config.ECS_CONTAINER_NAME,
                    'environment': [
                        {
                            'name': 'CLIENT_ID',
                            'value': str(client_id)
                        },
                    ]
                },
            ]
        },
        count=1,
        launchType=Config.ECS_LAUNCH_TYPE,
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [Config.ECS_SUBNET_ID],
                'assignPublicIp': 'ENABLED'
            }
        }
    )
    return response['tasks'][0]['taskArn']

def stop_ecs_task(task_arn):
    ecs_client.stop_task(
        cluster=Config.ECS_CLUSTER_NAME,
        task=task_arn,
        reason='Transcription complete or timeout reached'
    )