import boto3
import json
from time import sleep as sleep

# DO NOT forget to modify the instance ids under register_instance() function
region = 'region-name' # Region name --> MODIFY HERE
tgARN = 'arn:aws:elasticloadbalancing:regionName:Account:targetgroup/tg-name/id' # TargetGroup ARN --> MODIFY HERE
tgInstancePort = 443 # TargetGroup's instance ports (integer) --> MODIFY HERE

elb = boto3.client('elbv2')
ec2 = boto3.client('ec2', region_name=region)

def tg_state():
    tgState = elb.describe_target_health(TargetGroupArn = tgARN)
    tgState = tgState['TargetHealthDescriptions'][0]['TargetHealth']['State']
    return tgState

def find_unhealthy_instance():
    unhealthyInstance = elb.describe_target_health(TargetGroupArn = tgARN)
    unhealthyInstance = unhealthyInstance['TargetHealthDescriptions'][0]['Target']['Id']
    return unhealthyInstance

def check_instance_state(instance):
    InstanceStatus = ec2.describe_instances(InstanceIds=[instance])
    InstanceState = InstanceStatus['Reservations'][0]['Instances'][0]['State']['Name']
    return InstanceState

def deregister_instance():
    unhealthyInstanceId = find_unhealthy_instance()
    print('INFO: Failed instance is', unhealthyInstanceId)
    elb.deregister_targets(
        TargetGroupArn=tgARN,
        Targets=[
            {
                'Id': unhealthyInstanceId,
                'Port': tgInstancePort
            },
        ]
    )
    print ('TASK: Deregistration started...')
    ec2.stop_instances(InstanceIds=[unhealthyInstanceId])
    print ('TASK: Deregistered instance is being shut down...')

def register_instance():
    print ('TASK: Other instance is being registered...')
    backendServerId = find_unhealthy_instance()
    # modify the instance ids below
    defInstance = 'i-xxxx' # default-instance --> MODIFY HERE
    bkpInstance = 'i-yyyy' # backup-instance --> MODIFY HERE
    if backendServerId == defInstance:
        bkpInstance = bkpInstance
    else:
        bkpInstance = defInstance
    bkpInstanceState = check_instance_state(bkpInstance)
    print ('INFO: Backup instance state is', bkpInstanceState)
    if bkpInstanceState == 'stopped':
        print ('INFO: Starting backup instance')
        ec2.start_instances(InstanceIds=[bkpInstance])
        # sleep value has to be adjusted
        # if OS is windows, increase this value
        # also adjust aws lambda function's timeout value accordingly
        sleep(20)
    elb.register_targets(
        TargetGroupArn=tgARN,
        Targets=[
            {
                'Id': bkpInstance,
                'Port': tgInstancePort
            }
        ]
    )
    print ('TASK: Registration started...')

def handler(event, context):
    tgState = tg_state()
    if tgState != 'unhealthy':
        print ("INFO: HEALTHY or TRANSITION in place! - see the following STATUS log...")
    else:
        print ("STATUS: UNHEALTHY!!! - starting rotation")
        deregister_instance()
        register_instance()
    tgNextState = tg_state()
    print ('STATUS: ' + '"' + tgNextState + '"')
    return {
        'statusCode': 200,
        'body': json.dumps('Lambda function for ELB Target rotation is completed successfully!')
    }
