# scim-blackducksca
SCIM -interface for Black Duck SCA

# Needed changes
Black Duck URL - Service will need Black Duck URL via Environment variable BD_URL or as a bdurl header.<br>
Black Duck Access Token - Service will need read&write access token via Authorization header. <br>
Example:<br>
'Authorization': 'Bearer access_token'

# Supported services/endpoints
GET /scim/v2/Schemas - return SCIM Schema <br>
POST /scim/v2/Users - Add user, If user exists already then HTTP Error 409 returned<br>
PATCH /scim/v2/Users/<string:Id> - Change user info, If user not exists, then http error 404 returned<br>
DELETE /scim/v2/Users/<string:Id> - Deactivate user from Black Duck SCA<br>
GET /scim/v2/Users/<string:Id> - Get user info for given Id or username. If not found, then http error 404 returned otherwise<br>
PUT /scim/v2/Users/<string:Id> - Replace user info for given Id or username. If not found, then http error 404 returned otherwise<br>
GET /scim/v2/Users - Get users from Black Duck. This API Endpoint supports filttering. Only following filtters are supported: userName and email, and supported operation is only eq = equals.

## See examples
[test cases](SCIM_2_0_SPEC_test.json)

# Example how to run SCIM service with AWS Lightsail service

```
## Create the blackduck-scim-container -docker image.
docker build -t blackduck-scim-container:latest .

## Create the small aws lightsail container service
aws lightsail create-container-service --service-name blackduck-scim-service --power small --scale 1

## Use below command to check when the container service is in READY state
aws lightsail get-container-services

## This can be run when container-service is in READY state
aws lightsail push-container-image --service-name blackduck-scim-service --label blackduck-scim-container --image blackduck-scim-container

## Previous command will give you the image name, which you need to update into containers.json, before running the next command below.
Example:
   Image "blackduck-scim-container" registered.
   Refer to this image as ":blackduck-scim-service.blackduck-scim-container.1" in deployments.
aws lightsail create-container-service-deployment --service-name blackduck-scim-service --containers file://lightsail/containers.json --public-endpoint file://lightsail/public-endpoint.json

## Use this to check when the service is ready. This will also show the webhook URL.
Service state must be "ACTIVE"
URL Example:
    "url": "https://blackduck-scim-service.p7pkbhrp45cc2.us-east-1.cs.amazonlightsail.com/"
URL to add github will then be: https://blackduck-scim-service.p7pkbhrp45cc2.us-east-1.cs.amazonlightsail.com/scim/v2
aws lightsail get-container-services --service-name blackduck-scim-service

## After testing is done, you can delete the service with below command.
aws lightsail delete-container-service --service-name blackduck-scim-service
aws lightsail get-container-services

## If you want to get the logs. Logs are paged. This command will give you the page-token for the next page.
aws lightsail get-container-log --service-name blackduck-scim-service --container-name blackduck-scim

## You need to add the page-token when getting the next page.
aws lightsail get-container-log --service-name blackduck-scim-service --container-name blackduck-scim --page-token
```