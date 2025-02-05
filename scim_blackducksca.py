from flask import Flask, request
import socket
import logging
import os
import json
import requests
import re
import sys
from blackduck.HubRestApi import HubInstance

__author__ = "Jouni Lehto"
__versionro__="0.0.1"

app = Flask(__name__)

MAX_LIMIT=100
BD_URL=os.getenv("BD_URL")

class NoAuthorizationException(Exception):
    pass
class NoBDUrlException(Exception):
    pass
class NoBearerException(Exception):
    pass


def getToken(request):
    global BD_URL
    if request and request.headers.get("Authorization"):
        matching_headers = [string for string in dict(request.headers) if "bdurl" == string.casefold()]
        if matching_headers and len(matching_headers) == 1:
            BD_URL = request.headers.get(matching_headers[0])
        elif not BD_URL:
            response = app.make_response(createSCIMErrorResponse(scimType="invalidSyntax", status_code="401", detail="Header: \"bdurl\" was missing!"))
            response.mimetype = "application/scim+json"
            response.status_code = "401"
            return None, response
        if str(request.headers.get("Authorization")).rfind("Bearer") > -1:
            token = request.headers.get("Authorization").split('Bearer')[-1].strip()
            if token:
                return token, None
            else:
                response = app.make_response(createSCIMErrorResponse(scimType="invalidSyntax", status_code="401", detail="Header: \"Bearer\" token was missing!"))
                response.mimetype = "application/scim+json"
                response.status_code = "401"
                return None, response
        else:
            response = app.make_response(createSCIMErrorResponse(scimType="invalidSyntax", status_code="401", detail="Header: \"Bearer\" token was missing!"))
            response.mimetype = "application/scim+json"
            response.status_code = "401"
            return None, response
    else:
        response = app.make_response(createSCIMErrorResponse(scimType="invalidSyntax", status_code="401", detail="Header: \"Authorization\" was missing!"))
        response.mimetype = "application/scim+json"
        response.status_code = "401"
        return None, response

# API Endpoint to get used Schemas
@app.route('/scim/v2/Schemas', methods=['GET'])
def getSchema():
    for root, dirs, files in os.walk(os.getcwd()):
        for filename in files:
            if filename == "scimUserSchema.json":
                with open(root + os.path.sep + filename, "r") as schemaFile:
                    response = app.make_response(json.dumps(json.load(schemaFile), indent=3))
                    response.mimetype = "application/scim+json"
                    response.status_code = "200"
                    response = addHeadersForSwagger(response)
                    logging.info(response.json)
                    return response

# API Enpoint to add user. If user exists already then HTTP Error 409 returned.
@app.route('/scim/v2/Users', methods=['POST'])
def addUser():
    global BD_URL
    try:
        printRequest(request)
        if request.json:
            access_token, response = getToken(request)
            if access_token:
                hub = HubInstance(BD_URL, api_token=access_token, write_config_flag=False)
                scimUser = createBDUser(request.json)
                #Test if user already exists
                parameters = {"limit":1,"q": f"userName:{scimUser['userName']}"}
                users = hub.get_users(parameters=parameters)
                if users and users["totalCount"] > 0:
                    response = app.make_response(createSCIMErrorResponse("uniqueness", f"Given userName {scimUser['userName']} already exists.", "409"))
                    response.mimetype = "application/scim+json"
                    response.status_code = "409"
                    response = addHeadersForSwagger(response)
                    return response
                userURL = hub.create_user(scimUser)
                user = hub.get_user_by_url(userURL)
                if user:
                    response = app.make_response(createUserSCIMResponse(user, None))
                    response.mimetype = "application/scim+json"
                    response.status_code = "201"
                    response = addHeadersForSwagger(response)
                    return response
            else:
                return response
        else:
            response = app.make_response(createSCIMErrorResponse(scimType="invalidValue", status_code="400", detail="User data was missing!"))
            response.mimetype = "application/scim+json"
            response.status_code = "400"
            response = addHeadersForSwagger(response)
            return response
    except Exception as ex:
        response = app.make_response(createSCIMErrorResponse(scimType="invalidValue", status_code="400", detail=f"Request is unparsable, syntactically incorrect, or violates schema, error: {str(ex)}"))
        response.mimetype = "application/scim+json"
        response.status_code = "400"
        response = addHeadersForSwagger(response)
        return response

# API Enpoint to update user from Black Duck. If user not exists, then http error 404 returned,
# if user update success, then updated user is returned.
# Id can be Black Duck User Id or userName
@app.route('/scim/v2/Users/<string:Id>', methods=['PATCH'])
def updateUser(Id):
    global BD_URL
    printRequest(request)
    access_token, response = getToken(request)
    if access_token:
        hub = HubInstance(BD_URL, api_token=access_token, write_config_flag=False)
        users = get_user_by_id(hub, Id)
        if not users or not "totalCount" in users or users["totalCount"] == 0: 
            #If user is not found with ID then trying to find user by using Id as an username.
            parameters = {"limit":1,"q": f"userName:{Id}"}
            users = hub.get_users(parameters=parameters)
        if users and users["totalCount"] > 0:
            if request.json:
                for operation in request.json["Operations"]:
                    if operation["op"].casefold() == "replace":
                        if "path" in operation and operation["path"] == "emails[type eq \"work\"].value":
                            users["items"][0]["email"] = operation["value"]
                        elif "path" in operation and operation["path"] == "userName":
                            users["items"][0]["userName"] = operation["value"]
                        elif "path" in operation and operation["path"] == "active":
                            users["items"][0]["active"] = operation["value"]
                        elif "path" in operation and operation["path"] == "name.givenName":
                            users["items"][0]["firstName"] = operation["value"]
                        elif "path" in operation and operation["path"] == "name.familyName":
                            users["items"][0]["lastName"] = operation["value"]
                        else:
                            if "name.familyName" in operation["value"]:
                                users["items"][0]["lastName"] = operation["value"]["name.familyName"]
                            if "emails[type eq \"work\"].value" in operation["value"]:
                                users["items"][0]["email"] = operation["value"]["emails[type eq \"work\"].value"]
                            if "userName" in operation["value"]:
                                users["items"][0]["userName"] = operation["value"]["userName"]
                            if "name.givenName" in operation["value"]:
                                users["items"][0]["firstName"] = operation["value"]["name.givenName"]
                            if "active" in operation["value"]:
                                users["items"][0]["active"] = operation["value"]["active"]
                hub.update_user_by_url(users["items"][0]["_meta"]["href"], users["items"][0])
                response = app.make_response(createUserSCIMResponse(users["items"][0], None))
                response.mimetype = "application/scim+json"
                response.status_code = "200"
                response = addHeadersForSwagger(response)
                return response
        else:
            response = app.make_response(createSCIMErrorResponse(scimType="invalidValue", status_code="404", detail=f"Username: {Id} not found!"))
            response.mimetype = "application/scim+json"
            response.status_code = "404"
            response = addHeadersForSwagger(response)
            return response
    else:
        return response

# API Endpoint to delete user, but Black Duck is not supporting this, so user is only inactivated.
@app.route('/scim/v2/Users/<string:Id>', methods=['DELETE'])
def deleteUser(Id):
    global BD_URL
    access_token, response = getToken(request)
    printRequest(request)
    if access_token:
        hub = HubInstance(BD_URL, api_token=access_token, write_config_flag=False)
        user = get_user_by_id(hub, Id)
        if user: 
            user["active"] = False
            hub.update_user_by_url(user["_meta"]["href"], user)
            response = app.make_response("")
            response.status_code = "200"
            response = addHeadersForSwagger(response)
            return response
        else:       
            #If user is not found with ID then trying to find user by using Id as an username.
            parameters = {"limit":1,"q": f"userName:{Id}"}
            users = hub.get_users(parameters=parameters)
            if users and users["totalCount"] > 0:
                users["items"][0]["active"] = False
                hub.update_user_by_url(users["items"][0]["_meta"]["href"], users["items"][0])
                response = app.make_response("")
                response.status_code = "200"
                response = addHeadersForSwagger(response)
                return response
            else:
                response = app.make_response(createSCIMErrorResponse(scimType="invalidValue", status_code="404", detail=f"Username: {Id} not found!"))
                response.mimetype = "application/scim+json"
                response.status_code = "404"
                response = addHeadersForSwagger(response)
                return response
    else:
        return response

# API Endpoint to get user info for given Id or username. If not found, then http error 404 returned otherwise
# returned the existing user info.
# Id can be Black Duck User Id or userName
@app.route('/scim/v2/Users/<string:Id>', methods=['GET'])
def getUser(Id):
    global BD_URL
    printRequest(request)
    access_token, response = getToken(request)
    if access_token:
        hub = HubInstance(BD_URL, api_token=access_token, write_config_flag=False)
        user = get_user_by_id(hub, Id)
        logging.info(user)
        if user and "userName" in user:
            response = app.make_response(createUserSCIMResponse(user, Id))
            response.mimetype = "application/scim+json"
            response.status_code = "200"
            response = addHeadersForSwagger(response)
            return response
        else: 
            #If user is not found with ID then trying to find user by using Id as an username.
            parameters = {"limit":100,"q": f"userName:{Id}"}
            searched_users = hub.get_users(parameters=parameters)
            if searched_users and "totalCount" in searched_users and searched_users["totalCount"] > 0:
                response = app.make_response(createUserSCIMResponse(searched_users["items"][0], None))
                response.mimetype = "application/scim+json"
                response.status_code = "200"
                response = addHeadersForSwagger(response)
                return response
            else:
                response = app.make_response(createSCIMErrorResponse(scimType="invalidValue", status_code="404", detail=f"User: {Id} not found!"))
                response.mimetype = "application/scim+json"
                response.status_code = "404"
                response = addHeadersForSwagger(response)
                return response
    else:
        return response

# API Endpoint to get users from Black Duck. This API Endpoint supports filttering.
# Only following filtters are supported: userName and email, and supported operation is only eq = equals.
@app.route('/scim/v2/Users', methods=['GET'])
def getUsers():
    global BD_URL
    printRequest(request)
    access_token, response = getToken(request)
    if access_token:
        USER_MAXLIMIT = int(request.args.get('count')) if request.args and request.args.get('count') else MAX_LIMIT
        hub = HubInstance(BD_URL, api_token=access_token, write_config_flag=False)
        parameters = {"limit": USER_MAXLIMIT}
        parameters["offset"] = int(request.args.get('startIndex')) if request.args and request.args.get('startIndex') else 1
        #check are there any other filters given
        if request.query_string:
            #Only userName and email are currently supported
            query_string = requests.utils.unquote(request.query_string)
            if query_string.find('eq') > 0 and query_string.find('userName') > 0:
                parameters["q"] = "userName:" + re.split(r"\+eq\+|eq",query_string)[-1].strip().replace('\"','')
            elif query_string.find('eq') > 0 and query_string.find('email') > 0:
                parameters["q"] = "email:" + re.split(r"\+eq\+|eq",query_string)[-1].strip().replace('\"','')
        users = hub.get_users(parameters=parameters)
        logging.info(users)
        scimUsersResponse = {"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "totalResults": 0}
        if users:
            all_data = users
            if "totalCount" in users and users["totalCount"] > 0:
                total = int(request.args.get('count')) if request.args and request.args.get('count') else users['totalCount']
                downloaded = USER_MAXLIMIT
                while total > downloaded:
                    parameters["offset"] = downloaded
                    users = hub.get_users(parameters=parameters)
                    all_data['items'] = all_data['items'] + users['items']
                    downloaded += USER_MAXLIMIT
                scimUsersResponse["totalResults"] = int(request.args.get('count')) if request.args and request.args.get('count') else users['totalCount']
                scimUsersResponse["itemsPerPage"] = USER_MAXLIMIT
                scimUsersResponse["startIndex"] = 1
                scimUserReources = []
                for user in all_data["items"]:
                    scimUserReources.append(createUserSCIMResponse(user,None))
                scimUsersResponse['Resources'] = scimUserReources
        response = app.make_response(scimUsersResponse)
        response.mimetype = "application/scim+json"
        response.status_code = "200"
        response = addHeadersForSwagger(response)
        return response
    else:
        return response

def printRequest(request):
    logging.debug(f'Request: {request}')
    logging.debug(f'Request headers: {request.headers}')

def get_user_by_id(hub, user_id):
    url = BD_URL + "/api/users/{}".format(user_id)
    headers = {'Accept': 'application/vnd.blackducksoftware.user-4+json'}
    response = hub.execute_get(url, custom_headers=headers)
    jsondata = response.json()
    return jsondata

def createBDUser(scimUser):
    if scimUser:
        bdUser = {
            "userName" : scimUser["userName"],
            "firstName" :  scimUser["name"]["givenName"],
            "lastName" :  scimUser["name"]["familyName"],
            "email" :  scimUser["emails"][0]["value"],
            "active" : True,
            "type" : "EXTERNAL"
        }
        return bdUser

def createUserSCIMResponse(user, userID):
    scimUser = {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"]}
    if "_meta" in user:
        id = user["_meta"]["href"].split('/')[-1]
    else:
        id = userID
    if id:
        scimUser["id"] = id
    scimUser["userName"] = user["userName"]
    if "externalUserName" in user and user["externalUserName"]:
        scimUser["externalId"] = user["externalUserName"]
    scimUser["displayName"] = f'{user["firstName"]} {user["lastName"]}'
    scimUser["name"] = {
        "givenName": user["firstName"],
        "familyName": user["lastName"],
        "formatted": f'{user["firstName"]} {user["lastName"]}'}
    scimUser["emails"] = [{
        "type": "work",
        "value": user["email"],
        "primary": True }]
    scimUser["active"] = user["active"]
    if "_meta" in user:
        scimUser["meta"] = {
            "resourceType": "User",
            "location": user["_meta"]["href"]}
    return scimUser

def createSCIMErrorResponse(scimType,detail, status_code):
    error = {
     "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
     "scimType": scimType,
     "detail": detail,
     "status": status_code
    }
    return json.dumps(error)

def addHeadersForSwagger(response):
    response.headers["X-Requested-With"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-requested-with"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST,GET,DELETE,OPTIONS"
    return response

if __name__ == '__main__':
    hostname=socket.gethostname()   
    IPAddr=socket.gethostbyname(hostname)
    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(module)s: %(message)s', stream=sys.stderr, level=logging.DEBUG)
    logging.info(f"Black Duck Webhook Listener Version: {__versionro__}")
    app.logger.setLevel(logging.DEBUG)
    app.run(host=IPAddr, port=8090, debug=True)
